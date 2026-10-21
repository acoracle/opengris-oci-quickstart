# OpenGRIS notebook examples on OCI

[Back to examples](../README.md)

These notebooks are included locally from the [official Scaler gallery](https://finos.github.io/opengris-scaler/tutorials/examples.html), adapted to use the existing OCI scheduler. No download is needed after cloning this repository. Upstream license and notices are included in this directory.

## Notebook gallery

The columns follow the [upstream example gallery](https://finos.github.io/opengris-scaler/tutorials/examples.html), through **Num Workers**, adapted to this OCI deployment.

| Examples | Parfun | Pargraph | Client | Workers | Num Workers |
|---|---|---|---|---|---|
| [Multi-Signal Alpha Research](AlphaResearch.ipynb) | Yes | No | OCI_RAW | OCI Container Instances | Up to 16* |
| [Vol Surface Calibration & PDE Exotic Pricing](VolSurface.ipynb) | Yes | No | OCI_RAW | OCI Container Instances | Up to 16* |
| [Swap Portfolio CVA](SwapCVA.ipynb) | Yes | Yes | OCI_RAW | OCI Container Instances | Up to 16* |
| [Portfolio-Level XVA Risk](XVA.ipynb) | No | Yes | OCI_RAW | OCI Container Instances | Up to 16* |

Here **Client** identifies the deployment backend, following the requested gallery format: the notebook uses Scaler's Python client, and `oci_raw` manages the remote workers. **Num Workers** counts Scaler worker processes, not container instances.

*The guide's `max_task_concurrency = 16` configuration permits up to 16 concurrent worker task slots, normally four 4-OCPU container instances with four workers each. This is a configured ceiling, not a measured benchmark worker count or a fixed pool; Scaler provisions capacity as needed. If you change the configuration, update this limit accordingly. The upstream AWS/native benchmark worker counts and timings are not OCI measurements.

Start with [00_Check_OCI.ipynb](00_Check_OCI.ipynb), a small connection test that imports the notebook dependencies on workers and returns their package versions.

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
cd ~/opengris-oci-quickstart
bash scripts/start-notebooks.sh
```

This starts JupyterLab on `127.0.0.1:8888`, serving this notebook directory. Leave it running and copy the login URL containing its token.

## Open an SSH tunnel from your workstation

Run the following on your **workstation**, in a new terminal, while Jupyter runs on the VM:

```bash
ssh -i ~/.ssh/YOUR_PRIVATE_KEY -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8888:127.0.0.1:8888 opc@VM_SSH_HOST
```

Replace `~/.ssh/YOUR_PRIVATE_KEY` with your SSH private key path and `VM_SSH_HOST` with the hostname or IP you normally use to SSH into the VM. If your SSH agent or SSH configuration already supplies the key, omit `-i ~/.ssh/YOUR_PRIVATE_KEY`. Use the VM's private IP only if your workstation can reach it through VPN or another private connection.

The command forwards workstation port 8888 to port 8888 on the VM. `-N` opens only the tunnel, so a successful connection normally stays open without displaying a shell prompt. Keep this terminal open while using Jupyter.

### If you connect through OCI Bastion

Use your working **Managed SSH session** command, retaining its identity file, target VM, and `ProxyCommand`. Add these options to the outer SSH command that connects to `opc` on the VM:

```bash
-N -o ExitOnForwardFailure=yes -L 127.0.0.1:8888:127.0.0.1:8888
```

Keep the Bastion session active; recreate an expired session and update the session ID in your SSH command. These instructions assume a Managed SSH session to the VM, rather than a Bastion port-forwarding session.

### Open Jupyter and check the connection

Open the Jupyter login URL printed on the VM in your workstation browser, using `http://127.0.0.1:8888` and its token. The browser is on your workstation, but the Python kernel runs on the VM. No public ingress rule for port 8888 is needed. Select **OpenGRIS Scaler (Python 3.12)** and run `00_Check_OCI.ipynb` first.

If workstation port 8888 is already in use, forward a different local port:

```bash
ssh -i ~/.ssh/YOUR_PRIVATE_KEY -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8889:127.0.0.1:8888 opc@VM_SSH_HOST
```

Then use `http://127.0.0.1:8889` with the same Jupyter token. The VM still uses port 8888.

If the browser cannot connect, verify Jupyter's listener on the VM with `ss -lnt | grep ':8888'`. Add `-v` to the SSH command on your workstation to diagnose SSH connection failures. Stop the tunnel with Ctrl-C when finished.

## Run a gallery notebook

Open one notebook and run its cells in order. Each gallery notebook contains a native implementation and a parallel implementation:

| Notebook section | Where the calculations execute |
|---|---|
| **Native Python Implementation** | On the Jupyter kernel's host CPUs, without submitting tasks to Scaler. In this setup, that host is the scheduler VM. |
| **ParGraph / Parfun Implementation** | On Scaler workers in OCI Container Instances. The Jupyter kernel submits work and collects results. |

Your workstation browser displays the notebook; it does not execute its Python calculations. The execution location is determined by the selected Jupyter kernel, which this guide runs on the VM.

For example, in XVA, `run_sequential(MEDIUM_CONFIG)` computes directly on the VM, while `run_graph(MEDIUM_CONFIG)` submits the calculation through Scaler. Running all cells performs both versions: the native calculation can take a long time before the distributed calculation starts, and the native section does not itself provision Scaler workers.

The original benchmark sizes are retained: sequential comparison cells can run for a long time, and parallel cells can provision billable workers up to your configured capacity limit. Reduce the workload parameters before a first experiment; there is no fixed runtime guarantee. Use the small connection notebook to validate installation before starting these larger calculations.

Notebook defaults are `tcp://127.0.0.1:8516` for the scheduler and `tcp://127.0.0.1:8517` for Scaler's object-storage service. Those loopback addresses are correct because the kernel runs on the VM. Container workers continue to use the VM's private IP from the Scaler configuration. Parfun is configured with `use_worker_client=True`, so nested tasks in SwapCVA use their worker's scheduler connection rather than the notebook's loopback address. If needed, set `SCALER_SCHEDULER_ADDRESS` and `SCALER_OBJECT_STORAGE_ADDRESS` before starting Jupyter to override the notebook defaults.

Stop Jupyter with Ctrl-C when finished; it does not stop Scaler or delete worker instances. Follow the [cleanup guide](../../docs/cleanup.md) when the demo is over.
