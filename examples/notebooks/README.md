# OpenGRIS notebook examples on OCI

[Back to examples](../README.md)

These notebooks are included locally from the [official Scaler gallery](https://finos.github.io/opengris-scaler/tutorials/examples.html), adapted to use the existing OCI scheduler. No download is needed after cloning this repository. Upstream license and notices are included in this directory.

| Notebook | What it demonstrates |
|---|---|
| [00_Check_OCI.ipynb](00_Check_OCI.ipynb) | A small connection test that imports the notebook dependencies on workers and returns their package versions. Start here. |
| [AlphaResearch.ipynb](AlphaResearch.ipynb) | Parfun distributes independent signal calculations, followed by portfolio analysis. |
| [VolSurface.ipynb](VolSurface.ipynb) | Parfun distributes trade pricing using a calibrated volatility surface. |
| [SwapCVA.ipynb](SwapCVA.ipynb) | ParGraph expresses calculation dependencies, while Parfun distributes simulation work. |
| [XVA.ipynb](XVA.ipynb) | ParGraph schedules a multi-stage portfolio risk calculation on the OCI workers. |

## Install or upgrade the demo

For an existing installation, stop Scaler before upgrading its environment. On the scheduler VM:

```bash
bash scripts/install-environment.sh
source ~/scaler-py312/bin/activate
```

The installer includes JupyterLab, an IPython kernel, and the notebook libraries: SciPy, pandas, Parfun, ParGraph, QuantLib, tqdm, and yfinance, alongside the existing Scaler and NumPy versions. It registers the **OpenGRIS Scaler (Python 3.12)** kernel. The host and worker lock files pin matching calculation dependencies; Jupyter itself is installed on the VM, not in the worker image.

Rebuild and push the worker image so remote tasks have these libraries too:

```bash
python scripts/build-and-push.py --tag notebooks-v1
```

Generate the configuration from the new image digest using the [configuration instructions](../../docs/running-examples.md#generate-the-vm-specific-configuration), then restart Scaler. Updating the VM environment alone does not update existing containers.

## Run Jupyter on the VM

Keep Scaler running in one terminal. In another terminal on the same VM:

```bash
bash scripts/start-notebooks.sh
```

This starts JupyterLab on `127.0.0.1:8888`, serving this notebook directory. On your workstation, open an SSH tunnel:

```bash
ssh -N -L 8888:127.0.0.1:8888 opc@VM_SSH_HOST
```

Replace `VM_SSH_HOST` with your SSH destination. With OCI Bastion, add the same `-L` option to your working Bastion SSH command and retain its proxy settings.

Open the Jupyter login URL printed on the VM in your workstation browser, using `http://127.0.0.1:8888` and its token. The browser is on your workstation, but the Python kernel runs on the VM. No public ingress rule for port 8888 is needed. Select **OpenGRIS Scaler (Python 3.12)** and run `00_Check_OCI.ipynb` first.

## Run a gallery notebook

Open one notebook and run its cells in order. Each gallery notebook contains a native implementation, which runs on the scheduler VM, and a parallel implementation, which submits to the existing OCI workers. XVA has been changed from creating a local cluster to using that same remote scheduler. Outputs and execution counts were cleared from all bundled copies.

The original benchmark sizes are retained: sequential comparison cells can run for a long time, and parallel cells can provision billable workers up to your configured capacity limit. Reduce the workload parameters before a first experiment; there is no fixed runtime guarantee. Use the small connection notebook to validate installation before starting these larger calculations.

Notebook defaults are `tcp://127.0.0.1:8516` for the scheduler and `tcp://127.0.0.1:8517` for Scaler's object-storage service. Those loopback addresses are correct because the kernel runs on the VM. Container workers continue to use the VM's private IP from the Scaler configuration. Parfun is configured with `use_worker_client=True`, so nested tasks in SwapCVA use their worker's scheduler connection rather than the notebook's loopback address. If needed, set `SCALER_SCHEDULER_ADDRESS` and `SCALER_OBJECT_STORAGE_ADDRESS` before starting Jupyter to override the notebook defaults.

Use `JUPYTER_PORT=8889 bash scripts/start-notebooks.sh` to change the local notebook port, and adjust the SSH tunnel accordingly. Stop Jupyter with Ctrl-C when finished; it does not stop Scaler or delete worker instances. Follow the [cleanup guide](../../docs/cleanup.md) when the demo is over.
