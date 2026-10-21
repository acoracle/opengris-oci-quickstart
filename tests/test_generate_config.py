import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tomllib
from unittest.mock import patch

import oci
import pytest

source = Path(__file__).resolve().parents[1] / 'scripts/generate-scaler-config.py'
spec = importlib.util.spec_from_file_location('generator', source)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture
def args():
    return argparse.Namespace(profile='DEFAULT', auth_type='config_file', vnic_id=None,
        advertise_ip=None, container_image='fra.ocir.io/example/opengris:test',
        instance_ocpus=4.0, instance_memory_gb=30.0, max_task_concurrency=None)


def metadata(resource):
    if resource == 'instance':
        return dict(id='instance-test', canonicalRegionName='EU-FRANKFURT-1',
                    compartmentId='compartment-test', availabilityDomain='fyxu:EU-FRANKFURT-1-AD-1')
    return [{'vnicId': 'secondary'}, {'vnicId': 'primary'}]


def vnic(vnic_id):
    return SimpleNamespace(data=oci.core.models.Vnic(
        id=vnic_id, is_primary=vnic_id == 'primary',
        private_ip='172.16.0.97' if vnic_id == 'primary' else '10.0.1.9',
        subnet_id='subnet-' + vnic_id))


def discover(args):
    with patch.object(generator, 'metadata', side_effect=metadata), \
         patch('oci.config.from_file', return_value={}) as profile, \
         patch('oci.core.VirtualNetworkClient') as sdk:
        sdk.return_value.get_vnic.side_effect = vnic
        result = generator.discover(args)
        profile.assert_called_once_with(profile_name='DEFAULT')
        assert sdk.call_args.args[0]['region'] == 'eu-frankfurt-1'
        return result


def test_primary_vnic_not_first_and_output(args):
    info = discover(args)
    assert info['private_ip'] == '172.16.0.97'
    assert info['subnet_id'] == 'subnet-primary'
    config = tomllib.loads(generator.render(info, args))
    worker, = config['worker_manager']
    assert worker['availability_domain'] == 'fyxu:EU-FRANKFURT-1-AD-1'
    assert worker['worker_scheduler_address'] == 'tcp://172.16.0.97:8516'
    assert worker['object_storage_address'] == 'tcp://172.16.0.97:8517'
    assert worker['instance_ocpus'] == 4.0
    assert worker['instance_memory_gb'] == 30.0
    assert 'numpy==2.2.6' in worker['requirements_txt']
    assert 'max_task_concurrency' not in worker


def test_explicit_interface_ip_and_capacity(args):
    args.vnic_id = 'secondary'
    args.advertise_ip = '10.1.0.9'
    args.max_task_concurrency = 16
    info = discover(args)
    worker, = tomllib.loads(generator.render(info, args))['worker_manager']
    assert worker['subnet_id'] == 'subnet-secondary'
    assert worker['worker_scheduler_address'] == 'tcp://10.1.0.9:8516'
    assert worker['max_task_concurrency'] == 16


def test_unknown_vnic_rejected(args):
    args.vnic_id = 'unattached'
    with pytest.raises(RuntimeError, match='not a VNIC attached'):
        discover(args)


def test_save_preserves_previous_config(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text('previous settings')
    saved, backup = generator.save(path, 'new settings')
    assert saved.read_text() == 'new settings'
    assert backup.read_text() == 'previous settings'
    assert len(list(tmp_path.iterdir())) == 2


def test_metadata_uses_v2_and_bypasses_proxy():
    with patch('urllib.request.build_opener') as factory:
        response = factory.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b'{"region": "eu-frankfurt-1"}'
        assert generator.metadata('instance')['region'] == 'eu-frankfurt-1'
        assert factory.call_args.args[0].proxies == {}
        request = factory.return_value.open.call_args.args[0]
        assert request.full_url == 'http://169.254.169.254/opc/v2/instance/'
        assert request.get_header('Authorization') == 'Bearer Oracle'


def test_region_info_fallback(args):
    def legacy(resource):
        result = metadata(resource)
        if resource == 'instance':
            result.pop('canonicalRegionName')
            result['region'] = 'iad'
            result['regionInfo'] = {'regionIdentifier': 'us-ashburn-1'}
        return result
    with patch.object(generator, 'metadata', side_effect=legacy), \
         patch('oci.config.from_file', return_value={}), \
         patch('oci.core.VirtualNetworkClient') as sdk:
        sdk.return_value.get_vnic.side_effect = vnic
        assert generator.discover(args)['region'] == 'us-ashburn-1'


def test_instance_principal_does_not_read_key_file(args):
    args.auth_type = 'instance_principal'
    with patch.object(generator, 'metadata', side_effect=metadata), \
         patch('oci.config.from_file') as keyfile, \
         patch('oci.auth.signers.InstancePrincipalsSecurityTokenSigner') as signer, \
         patch('oci.core.VirtualNetworkClient') as sdk:
        sdk.return_value.get_vnic.side_effect = vnic
        info = generator.discover(args)
        keyfile.assert_not_called()
        assert sdk.call_args.kwargs['signer'] is signer.return_value
        worker, = tomllib.loads(generator.render(info, args))['worker_manager']
        assert worker['auth_type'] == 'instance_principal'


def test_scaler_can_parse_generated_worker_configuration(args):
    from scaler.config.reconstruction import _from_toml
    from scaler.config.section.oci_raw_worker_manager import OCIRawWorkerManagerConfig
    info = discover(args)
    worker, = tomllib.loads(generator.render(info, args))['worker_manager']
    parsed = _from_toml(OCIRawWorkerManagerConfig, worker)
    assert parsed.instance_ocpus == 4.0
    assert str(parsed.worker_manager_config.effective_worker_scheduler_address) == 'tcp://172.16.0.97:8516'
