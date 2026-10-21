import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import oci
import pytest

spec = importlib.util.spec_from_file_location(
    'publisher', Path(__file__).resolve().parents[1] / 'scripts/build-and-push.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def repository(public=False):
    return SimpleNamespace(id='repository-id', namespace='example', is_public=public)


def test_create_explicitly_private_mutable_repository(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(publisher, 'find_repository', lambda *args: None)
    client.create_container_repository.return_value.data = repository()
    result = publisher.ensure_repository(client, 'registry-compartment', 'opengris')
    details = client.create_container_repository.call_args.args[0]
    assert details.compartment_id == 'registry-compartment'
    assert details.is_public is False
    assert details.is_immutable is False
    assert result.namespace == 'example'


def test_existing_private_repository_is_reused(monkeypatch):
    client = MagicMock()
    existing = repository()
    monkeypatch.setattr(publisher, 'find_repository', lambda *args: existing)
    assert publisher.ensure_repository(client, 'compartment', 'opengris') is existing
    client.create_container_repository.assert_not_called()


def test_existing_public_repository_is_not_modified(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(publisher, 'find_repository', lambda *args: repository(public=True))
    with pytest.raises(RuntimeError, match='public'):
        publisher.ensure_repository(client, 'compartment', 'opengris')
    client.update_container_repository.assert_not_called()


def test_repository_lookup_follows_pagination():
    client = MagicMock()
    client.list_container_repositories.side_effect = [
        SimpleNamespace(data=SimpleNamespace(items=[]), headers={'opc-next-page': 'next'}),
        SimpleNamespace(data=SimpleNamespace(items=[SimpleNamespace(
            display_name='opengris', lifecycle_state='AVAILABLE', id='found')]), headers={})]
    client.get_container_repository.return_value.data = repository()
    result = publisher.find_repository(client, 'compartment', 'opengris')
    assert result.namespace == 'example'
    assert client.list_container_repositories.call_args.kwargs['page'] == 'next'
    client.get_container_repository.assert_called_once_with('found')


def test_token_request_is_signed_and_redirects_disabled():
    client = MagicMock()
    response = client.base_client.session.get.return_value
    response.status_code = 200
    response.json.return_value = {'token': 'temporary-secret'}
    signer = object()
    assert publisher.registry_token(client, signer, 'fra.ocir.io') == 'temporary-secret'
    kwargs = client.base_client.session.get.call_args.kwargs
    assert kwargs['auth'] is signer
    assert kwargs['allow_redirects'] is False


@pytest.mark.parametrize('fail_push', [False, True])
def test_podman_credentials_use_stdin_and_are_cleaned_up(monkeypatch, fail_push):
    calls = []
    digest = 'sha256:' + 'a' * 64
    monkeypatch.setattr(publisher, 'registry_token', lambda *args: 'temporary-secret')

    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert 'temporary-secret' not in command
        if command[1] == 'login':
            assert kwargs['input'] == 'temporary-secret\n'
            Path(command[command.index('--authfile') + 1]).write_text('temporary credentials')
        if command[1] == 'push':
            if fail_push:
                raise publisher.subprocess.CalledProcessError(1, command)
            Path(command[command.index('--digestfile') + 1]).write_text(digest)

    monkeypatch.setattr(publisher.subprocess, 'run', run)
    if fail_push:
        with pytest.raises(publisher.subprocess.CalledProcessError):
            publisher.publish(None, None, 'fra.ocir.io', 'fra.ocir.io/example/opengris:v1')
    else:
        assert publisher.publish(None, None, 'fra.ocir.io', 'fra.ocir.io/example/opengris:v1') == digest
    login = calls[0][0]
    assert not Path(login[login.index('--authfile') + 1]).parent.exists()


def test_main_builds_from_repo_root_and_records_pushed_digest(monkeypatch, tmp_path):
    args = argparse.Namespace(repository='opengris', tag='v1', registry_compartment_id=None,
                              registry_host=None, output=tmp_path / 'image.json')
    monkeypatch.setattr(publisher, 'arguments', lambda: args)
    monkeypatch.setattr(publisher.shutil, 'which', lambda name: '/usr/bin/podman')
    monkeypatch.setattr(publisher, 'vm_metadata', lambda: {
        'canonicalRegionName': 'EU-FRANKFURT-1', 'compartmentId': 'vm-compartment',
        'regionInfo': {'regionKey': 'FRA'}})
    monkeypatch.setattr(oci.auth.signers, 'InstancePrincipalsSecurityTokenSigner', lambda: object())
    client_factory = MagicMock()
    monkeypatch.setattr(oci.artifacts, 'ArtifactsClient', client_factory)
    ensure = MagicMock(return_value=repository())
    monkeypatch.setattr(publisher, 'ensure_repository', ensure)
    monkeypatch.setattr(publisher, 'publish', lambda *args: 'sha256:' + 'a' * 64)
    run = MagicMock()
    monkeypatch.setattr(publisher.subprocess, 'run', run)
    assert publisher.main() == 0
    ensure.assert_called_once_with(client_factory.return_value, 'vm-compartment', 'opengris')
    build = run.call_args
    assert build.args[0][-1] == str(publisher.ROOT)
    assert build.kwargs['cwd'] == publisher.ROOT
    result = json.loads(args.output.read_text())
    assert result['image'] == 'fra.ocir.io/example/opengris:v1'
    assert result['image_digest_ref'] == 'fra.ocir.io/example/opengris@sha256:' + 'a' * 64
