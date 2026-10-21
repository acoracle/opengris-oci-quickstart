#!/usr/bin/env python3
"""Preview or delete OCI Raw workers matching a Scaler configuration.

Stop Scaler first. Default is a read-only preview; --delete removes matching
container instances and waits for their deletion work requests to succeed.
The scheduler VM, OCIR repository, IAM, networking, and local files are retained.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys
import time
import tomllib

import oci

ROOT = Path(__file__).resolve().parents[1]
INACTIVE = {'DELETING', 'DELETED', 'TERMINATING', 'TERMINATED'}


def load_worker(path, manager_id=None):
    config = tomllib.loads(path.read_text())
    workers = [w for w in config.get('worker_manager', []) if w.get('type') == 'oci_raw']
    if manager_id:
        workers = [w for w in workers if w.get('worker_manager_id') == manager_id]
    if len(workers) != 1:
        raise ValueError('Select exactly one OCI Raw manager; use --worker-manager-id for multiple managers')
    worker = workers[0]
    for field in ('oci_region', 'compartment_id', 'subnet_id', 'container_image',
                  'worker_manager_id', 'worker_scheduler_address'):
        if not worker.get(field):
            raise ValueError(f'Configuration must include {field} for cleanup matching')
    return worker


def command_matches(command, worker):
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if len(parts) < 3 or Path(parts[0]).name != 'scaler_worker_manager':
        return False
    if parts[1:3] != ['baremetal_native', worker['worker_scheduler_address']]:
        return False
    for option, expected in (('--worker-manager-id', worker['worker_manager_id']),
                             ('--worker-type', 'OCI_RAW')):
        if parts.count(option) != 1:
            return False
        index = parts.index(option)
        if index + 1 == len(parts) or parts[index + 1] != expected:
            return False
    return True


def inspect_match(client, network, instance_id, worker):
    response = client.get_container_instance(instance_id)
    instance = response.data
    if (not (instance.display_name or '').startswith('scaler-worker-')
            or instance.lifecycle_state in INACTIVE
            or instance.compartment_id != worker['compartment_id']):
        return None
    if not instance.vnics or not instance.containers:
        return None
    for item in instance.vnics:
        if network.get_vnic(item.vnic_id).data.subnet_id != worker['subnet_id']:
            return None
    for item in instance.containers:
        container = client.get_container(item.container_id).data
        if container.image_url != worker['container_image']:
            return None
        if not command_matches((container.environment_variables or {}).get('COMMAND', ''), worker):
            return None
    return response


def candidates(client, network, worker):
    page = None
    while True:
        kwargs = {'page': page} if page else {}
        response = client.list_container_instances(worker['compartment_id'], **kwargs)
        for item in response.data.items:
            if ((item.display_name or '').startswith('scaler-worker-')
                    and item.lifecycle_state not in INACTIVE):
                try:
                    match = inspect_match(client, network, item.id, worker)
                except oci.exceptions.ServiceError as exc:
                    if exc.status == 404:
                        continue  # Already removed by the manager or another cleanup.
                    raise
                if match:
                    yield match.data
        next_page = response.headers.get('opc-next-page')
        if not next_page:
            break
        if next_page == page:
            raise RuntimeError('OCI returned a non-advancing container-instance page')
        page = next_page


def wait_deleted(client, request_id, timeout):
    deadline = time.monotonic() + timeout
    while True:
        state = client.get_work_request(request_id).data.status
        if state == 'SUCCEEDED':
            return
        if state in {'FAILED', 'CANCELED', 'CANCELLED'}:
            raise RuntimeError(f'Deletion work request {request_id}: {state}; inspect its OCI errors')
        if time.monotonic() >= deadline:
            raise RuntimeError(f'Timed out waiting for deletion {request_id}; check it in OCI Console')
        time.sleep(2)


def remove(client, network, instance, worker, timeout):
    # Revalidate the target immediately before deletion, and use optimistic concurrency.
    response = inspect_match(client, network, instance.id, worker)
    if response is None:
        raise RuntimeError(f'Instance no longer matches: {instance.id}; not deleted')
    etag = response.headers.get('etag')
    if not etag:
        raise RuntimeError(f'No ETag for {instance.id}; not deleted')
    deletion = client.delete_container_instance(instance.id, if_match=etag)
    request_id = deletion.headers.get('opc-work-request-id')
    if not request_id:
        raise RuntimeError(f'Deletion accepted for {instance.id}, but no work-request ID returned; verify in OCI')
    print(f'Deleting {instance.display_name}: {request_id}', flush=True)
    wait_deleted(client, request_id, timeout)
    print(f'Deleted {instance.id}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config-montecarlo.toml')
    parser.add_argument('--worker-manager-id')
    parser.add_argument('--delete', action='store_true', help='delete matches; default is preview only')
    parser.add_argument('--wait-seconds', type=int, default=600, help='deletion timeout per instance')
    args = parser.parse_args()
    if args.wait_seconds < 1:
        parser.error('wait-seconds must be positive')
    try:
        worker = load_worker(args.config, args.worker_manager_id)
        region = worker['oci_region'].lower()
        if worker.get('auth_type', 'instance_principal') == 'instance_principal':
            kwargs = {'signer': oci.auth.signers.InstancePrincipalsSecurityTokenSigner(), 'timeout': (5, 30)}
            config = {'region': region}
        elif worker['auth_type'] == 'config_file':
            config = oci.config.from_file(profile_name=worker.get('oci_profile', 'DEFAULT'))
            config['region'] = region
            kwargs = {'timeout': (5, 30)}
        else:
            raise ValueError('Cleanup supports instance_principal or config_file authentication')
        client = oci.container_instances.ContainerInstanceClient(config, **kwargs)
        network = oci.core.VirtualNetworkClient(config, **kwargs)
        instances = list(candidates(client, network, worker))
        print(json.dumps({'mode': 'delete' if args.delete else 'preview', 'region': region,
                          'compartment_id': worker['compartment_id'],
                          'instances': [{'id': i.id, 'name': i.display_name, 'state': i.lifecycle_state}
                                        for i in instances]}, indent=2))
        if not args.delete:
            print('Preview only. Stop Scaler, then rerun with --delete to remove these workers.')
            return 0
        failures = 0
        for instance in instances:
            try:
                remove(client, network, instance, worker, args.wait_seconds)
            except oci.exceptions.ServiceError as exc:
                if exc.status == 404:
                    print(f'Already removed: {instance.id}')
                else:
                    failures += 1
                    print(f'ERROR {instance.id}: {exc.message}', file=sys.stderr)
            except Exception as exc:
                failures += 1
                print(f'ERROR {instance.id}: {exc}', file=sys.stderr)
        return 1 if failures else 0
    except Exception as exc:
        print(f'ERROR: {getattr(exc, "message", str(exc))}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
