import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import oci
import pytest

spec = importlib.util.spec_from_file_location(
    'cleanup', Path(__file__).resolve().parents[1] / 'scripts/cleanup.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


@pytest.fixture
def worker():
    return {'type': 'oci_raw', 'auth_type': 'instance_principal', 'oci_region': 'eu-frankfurt-1',
            'compartment_id': 'compartment', 'subnet_id': 'subnet', 'worker_manager_id': 'demo-manager',
            'container_image': 'fra.ocir.io/example/opengris@sha256:abc',
            'worker_scheduler_address': 'tcp://10.0.0.10:8516'}


@pytest.fixture
def resources(worker):
    instance = SimpleNamespace(id='instance', display_name='scaler-worker-12345678',
                               lifecycle_state='ACTIVE', compartment_id='compartment',
                               vnics=[SimpleNamespace(vnic_id='vnic')],
                               containers=[SimpleNamespace(container_id='container')])
    container = SimpleNamespace(image_url=worker['container_image'], environment_variables={
        'COMMAND': "scaler_worker_manager baremetal_native 'tcp://10.0.0.10:8516' "
                   '--mode fixed --worker-type OCI_RAW --worker-manager-id demo-manager'})
    client, network = MagicMock(), MagicMock()
    client.get_container_instance.return_value = SimpleNamespace(data=instance, headers={'etag': 'version'})
    client.get_container.return_value.data = container
    network.get_vnic.return_value.data.subnet_id = 'subnet'
    return client, network, instance, container


def test_matches_actual_raw_worker_command(worker, resources):
    client, network, instance, _ = resources
    assert cleanup.inspect_match(client, network, instance.id, worker).data is instance


@pytest.mark.parametrize('changed', ['name', 'image', 'subnet', 'scheduler', 'manager', 'compartment', 'state'])
def test_unrelated_instances_are_excluded(worker, resources, changed):
    client, network, instance, container = resources
    if changed == 'name':
        instance.display_name = 'another-app'
    elif changed == 'image':
        container.image_url = 'another-image'
    elif changed == 'subnet':
        network.get_vnic.return_value.data.subnet_id = 'another-subnet'
    elif changed == 'compartment':
        instance.compartment_id = 'another-compartment'
    elif changed == 'state':
        instance.lifecycle_state = 'DELETING'
    else:
        old, new = ('10.0.0.10', '10.0.0.20') if changed == 'scheduler' else ('demo-manager', 'other-manager')
        container.environment_variables['COMMAND'] = container.environment_variables['COMMAND'].replace(old, new)
    assert cleanup.inspect_match(client, network, instance.id, worker) is None
    client.delete_container_instance.assert_not_called()


def test_deletion_uses_etag_and_waits(worker, resources):
    client, network, instance, _ = resources
    client.delete_container_instance.return_value.headers = {'opc-work-request-id': 'delete-request'}
    client.get_work_request.return_value.data.status = 'SUCCEEDED'
    cleanup.remove(client, network, instance, worker, 10)
    client.delete_container_instance.assert_called_once_with('instance', if_match='version')
    client.get_work_request.assert_called_once_with('delete-request')


def test_changed_target_is_not_deleted(worker, resources):
    client, network, instance, container = resources
    container.image_url = 'changed-image'
    with pytest.raises(RuntimeError, match='no longer matches'):
        cleanup.remove(client, network, instance, worker, 10)
    client.delete_container_instance.assert_not_called()


def test_failed_work_request_is_reported():
    client = MagicMock()
    client.get_work_request.return_value.data.status = 'FAILED'
    with pytest.raises(RuntimeError, match='FAILED'):
        cleanup.wait_deleted(client, 'request', 10)


def test_default_run_is_preview(monkeypatch, worker, resources, capsys):
    client, network, instance, _ = resources
    client.list_container_instances.return_value = SimpleNamespace(
        data=SimpleNamespace(items=[instance]), headers={})
    monkeypatch.setattr('sys.argv', ['cleanup.py'])
    monkeypatch.setattr(cleanup, 'load_worker', lambda *args: worker)
    monkeypatch.setattr(oci.auth.signers, 'InstancePrincipalsSecurityTokenSigner', lambda: object())
    monkeypatch.setattr(oci.container_instances, 'ContainerInstanceClient', lambda *args, **kw: client)
    monkeypatch.setattr(oci.core, 'VirtualNetworkClient', lambda *args, **kw: network)
    assert cleanup.main() == 0
    assert '"mode": "preview"' in capsys.readouterr().out
    client.delete_container_instance.assert_not_called()


def test_multiple_managers_need_selection(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text('[[worker_manager]]\ntype="oci_raw"\n[[worker_manager]]\ntype="oci_raw"\n')
    with pytest.raises(ValueError, match='exactly one'):
        cleanup.load_worker(path)
