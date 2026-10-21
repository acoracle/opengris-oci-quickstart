import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name', ['00_Check_OCI', 'AlphaResearch', 'VolSurface', 'SwapCVA', 'XVA'])
def test_bundled_notebook_is_clean_and_uses_remote_scheduler(name):
    notebook = json.loads((ROOT / 'examples/notebooks' / f'{name}.ipynb').read_text())
    assert notebook['metadata']['kernelspec']['name'] == 'opengris-scaler'
    code = []
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            ast.parse(source)
            assert not cell['outputs']
            assert cell['execution_count'] is None
            code.append(source)
    source = '\n'.join(code)
    assert 'SCALER_SCHEDULER_ADDRESS' in source
    assert 'SCALER_OBJECT_STORAGE_ADDRESS' in source
    assert '172.31.3.107' not in source
    assert 'SchedulerClusterCombo' not in source
    if name in {'AlphaResearch', 'VolSurface', 'SwapCVA'}:
        assert 'use_worker_client=True' in source


def pins(path):
    return dict(line.split('==', 1) for line in path.read_text().splitlines()
                if line and not line.startswith('#'))


def test_host_and_worker_dependency_versions_match():
    host = pins(ROOT / 'requirements-linux-amd64.lock')
    worker = pins(ROOT / 'requirements-worker-linux-amd64.lock')
    for name, version in worker.items():
        assert host.get(name) == version, name
    assert host['opengris-scaler'] == '2.9.0'
    assert host['numpy'] == '2.2.6'
    for package in ('scipy', 'pandas', 'opengris-parfun', 'pargraph', 'quantlib', 'yfinance'):
        assert package in worker
    assert 'jupyterlab' in host
    assert 'ipykernel' in host
    assert 'jupyterlab' not in worker


def test_jupyter_kernel_can_submit_to_scaler_workers(monkeypatch):
    nbformat = pytest.importorskip('nbformat')
    nbclient = pytest.importorskip('nbclient')
    import socket
    from scaler import SchedulerClusterCombo

    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    data_address = f'tcp://127.0.0.1:{port}'
    cluster = SchedulerClusterCombo(n_workers=2, object_storage_address=data_address, logging_level='ERROR')
    try:
        monkeypatch.setenv('SCALER_SCHEDULER_ADDRESS', cluster.get_address())
        monkeypatch.setenv('SCALER_OBJECT_STORAGE_ADDRESS', data_address)
        path = ROOT / 'examples/notebooks/00_Check_OCI.ipynb'
        notebook = nbformat.read(path, as_version=4)
        result = nbclient.NotebookClient(
            notebook, timeout=180, kernel_name='opengris-scaler',
            resources={'metadata': {'path': str(path.parent)}},
        ).execute()
        outputs = '\n'.join(output.get('text', '') for cell in result.cells
                            if cell.cell_type == 'code' for output in cell.outputs)
        assert 'Notebook worker check passed' in outputs
    finally:
        cluster.shutdown()
