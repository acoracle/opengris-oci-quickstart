#!/usr/bin/env python3
"""Create a private OCIR repository, build the worker image, and push from an OCI VM.

Uses the VM's instance principal for repository management and a short-lived
OCIR bearer token for Podman. No user API keys or permanent auth token needed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import oci

ROOT = Path(__file__).resolve().parents[1]


def vm_metadata():
    spec = importlib.util.spec_from_file_location(
        'vm_config', Path(__file__).with_name('generate-scaler-config.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.metadata('instance')


def find_repository(client, compartment, name):
    page = None
    while True:
        kwargs = {'display_name': name}
        if page:
            kwargs['page'] = page
        response = client.list_container_repositories(compartment, **kwargs)
        for item in response.data.items:
            if item.display_name == name and item.lifecycle_state == 'AVAILABLE':
                return client.get_container_repository(item.id).data
        next_page = response.headers.get('opc-next-page')
        if not next_page:
            return None
        if next_page == page:
            raise RuntimeError('OCI returned a non-advancing repository page')
        page = next_page


def ensure_repository(client, compartment, name):
    repository = find_repository(client, compartment, name)
    if repository is None:
        print(f'Creating private OCIR repository {name} in {compartment}', file=sys.stderr)
        details = oci.artifacts.models.CreateContainerRepositoryDetails(
            compartment_id=compartment, display_name=name,
            is_public=False, is_immutable=False)
        try:
            repository = client.create_container_repository(details).data
        except oci.exceptions.ServiceError as exc:
            if exc.status != 409:
                raise
            repository = find_repository(client, compartment, name)
            if repository is None:
                raise RuntimeError(
                    'Repository name conflicts with another resource. Check whether it exists '
                    'in a different compartment; specify its actual compartment or another name.'
                ) from exc
    if repository.is_public:
        raise RuntimeError('Existing repository is public; choose a private repository. '
                           'This script does not change repository visibility.')
    if not repository.namespace:
        raise RuntimeError('OCI did not return the registry namespace')
    return repository


def registry_token(client, signer, host):
    # Reuse the OCI SDK's HTTP session; sign the registry request with the same VM identity.
    response = client.base_client.session.get(
        f'https://{host}/20180419/docker/token', auth=signer,
        timeout=(5, 30), allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f'OCIR token request failed: HTTP {response.status_code}. '
                           'Check the scheduler dynamic group, manage repos policy, and IAM propagation.')
    token = response.json().get('token')
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError('OCIR did not return a registry bearer token')
    return token


def publish(client, signer, host, image):
    # The build may take longer than a token lifetime; obtain the token after it finishes.
    token = registry_token(client, signer, host)
    with tempfile.TemporaryDirectory(prefix='scaler-ocir-') as directory:
        authfile = str(Path(directory) / 'auth.json')
        digestfile = Path(directory) / 'digest.txt'
        subprocess.run(['podman', 'login', '--authfile', authfile,
                        '--username', 'BEARER_TOKEN', '--password-stdin', host],
                       input=token + '\n', text=True, check=True)
        token = None
        subprocess.run(['podman', 'push', '--authfile', authfile,
                        '--digestfile', str(digestfile), image], check=True)
        digest = digestfile.read_text().strip()
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
            raise RuntimeError('Push completed but Podman returned an unexpected image digest')
    return digest


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default='opengris')
    parser.add_argument('--tag', default='montecarlo-v1')
    parser.add_argument('--registry-compartment-id', help='defaults to the VM compartment')
    parser.add_argument('--registry-host', help='optional OCIR alias, e.g. fra.ocir.io')
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'worker-image.json')
    args = parser.parse_args()
    component = r'[a-z0-9]+(?:[._-][a-z0-9]+)*'
    if not re.fullmatch(component + r'(?:/' + component + r')*', args.repository):
        parser.error('repository must be a lowercase container repository name, optionally with / separators')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', args.tag):
        parser.error('invalid container image tag')
    if args.registry_host and not re.fullmatch(r'[a-z0-9-]+\.ocir\.io', args.registry_host):
        parser.error('registry-host must be a commercial OCI registry hostname, e.g. fra.ocir.io')
    return args


def main():
    args = arguments()
    try:
        if not shutil.which('podman'):
            raise RuntimeError('Podman is required. Install it with: sudo dnf install -y podman')
        subprocess.run(['podman', 'info'], check=True, stdout=subprocess.DEVNULL)
        instance = vm_metadata()
        region = (instance.get('canonicalRegionName')
                  or instance.get('regionInfo', {}).get('regionIdentifier'))
        if not region:
            raise RuntimeError('VM metadata did not return a canonical region')
        region = region.lower()
        alias = instance.get('regionInfo', {}).get('regionKey', region).lower()
        host = args.registry_host or f'{alias}.ocir.io'
        if not re.fullmatch(r'[a-z0-9-]+\.ocir\.io', host):
            raise RuntimeError('Cannot derive a commercial OCIR hostname from VM metadata')
        compartment = args.registry_compartment_id or instance['compartmentId']
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        client = oci.artifacts.ArtifactsClient({'region': region}, signer=signer, timeout=(5, 30))
        repository = ensure_repository(client, compartment, args.repository)
        image_repository = f'{host}/{repository.namespace}/{args.repository}'
        image = f'{image_repository}:{args.tag}'
        print(f'Building {image}', file=sys.stderr)
        subprocess.run(['podman', 'build', '--platform', 'linux/amd64',
                        '-f', str(ROOT / 'container' / 'Dockerfile'), '-t', image, str(ROOT)],
                       cwd=ROOT, check=True)
        digest = publish(client, signer, host, image)
        result = {'image': image, 'image_digest_ref': f'{image_repository}@{digest}',
                  'digest': digest, 'repository_id': repository.id,
                  'registry_compartment_id': compartment, 'region': region}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(f'Published {result["image_digest_ref"]}\nSaved image metadata: {args.output}')
        return 0
    except subprocess.CalledProcessError as exc:
        print(f'ERROR: Podman {exc.cmd[1]} failed (exit {exc.returncode}).', file=sys.stderr)
    except Exception as exc:
        print(f'ERROR: {getattr(exc, "message", str(exc))}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
