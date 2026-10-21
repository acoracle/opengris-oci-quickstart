# Running examples and testing scaling

[Back to README](../README.md)

Run shell commands from the repository root.

## Generate the VM-specific configuration

After [building and pushing the worker image](installation.md), activate the environment and load its saved digest:

```bash
source ~/scaler-py312/bin/activate
IMAGE="$(python -c 'import json; print(json.load(open("results/worker-image.json"))["image_digest_ref"])')"
python scripts/generate-scaler-config.py \
  --container-image "$IMAGE" \
  --max-task-concurrency 16 \
  --output config-montecarlo.toml
cat config-montecarlo.toml
```

The generator defaults to **`auth_type = "instance_principal"`**. No `~/.oci/config` or user API signing key is required. It reads IMDSv2, then uses `GetVnic` to discover the subnet. It normalizes the region and keeps the tenancy-prefixed availability-domain name. Existing output is backed up before replacement. To retain user API-key authentication instead:

```bash
python scripts/generate-scaler-config.py --container-image "$IMAGE" \
  --auth-type config_file --profile DEFAULT
```

The default size is 4 OCPUs and 30 GB per container instance. `--max-task-concurrency 16` permits up to four such instances. It is a ceiling, not a request to prestart four instances. Container instances incur charges while provisioned.

## Start Scaler and verify remote execution

Keep Scaler running in one terminal:

```bash
source ~/scaler-py312/bin/activate
cd ~/opengris-oci-quickstart
scaler config-montecarlo.toml
```

In a second terminal on the same VM:

```bash
source ~/scaler-py312/bin/activate
cd ~/opengris-oci-quickstart
python scripts/smoke-test.py
```

### What the smoke test does

The smoke test is a small check that the grid can execute work and return results before you run the Monte Carlo examples. It connects to the scheduler at `tcp://127.0.0.1:8516` and submits **eight independent Python tasks**, numbered 0 through 7.

Each task runs on a Scaler worker, waits two seconds, and returns:

- `task`: the submitted task number.
- `host`: the hostname of the container where the worker executed it.
- `scaler` and `numpy`: the installed package versions reported by that worker.


If no workers are available, the pending tasks prompt the OCI Raw manager to provision capacity. The first run can take longer while a container instance is created, its image is pulled, and workers start. Existing workers can execute the test immediately.


## Run the notebooks through an SSH tunnel

Keep Scaler running. On the VM, from the repository root:

```bash
bash scripts/start-notebooks.sh
```

On your workstation, in a separate terminal:

```bash
ssh -i ~/.ssh/YOUR_PRIVATE_KEY -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8888:127.0.0.1:8888 opc@VM_SSH_HOST
```

Replace the key path and `VM_SSH_HOST` with those used to SSH into your VM. Leave this terminal open, then open the Jupyter URL printed on the VM in your workstation browser, using `http://127.0.0.1:8888` and its token. See the [notebook guide](../examples/notebooks/README.md#open-an-ssh-tunnel-from-your-workstation) for OCI Bastion, port conflicts, and connection checks.

## Choose an example

The [examples catalogue](../examples/README.md) describes each calculation in two lines and shows how to run pi, one pricing input, or the scenario grid. The pi script is in [`examples/pi.py`](../examples/pi.py).

The adapter reuses upstream `run_partition()` and `aggregate()`. One simulation becomes several Scaler tasks; futures return partial statistics to the client for aggregation. All five examples and the nine market-risk scenarios are supported. `--parallelism` is the number of logical tasks per simulation, not the number of container instances. Preserve the same partition count and seed when comparing results with the Kubernetes demo.

Outputs are under `results/opengris/<invocation-id>/`, with a manifest, reusable input specifications, per-partition results, worker metadata, summaries, and `completed.json` after all scenarios finish. The adapter checks that worker and client source hashes match. A failed invocation can leave partial files; there is no automatic resume or durable job service in this adapter.

**Statistical limitation:** the upstream reducer treats antithetic payoffs as independent when calculating standard error. This adapter preserves that calculation to reproduce upstream output; its confidence intervals are not a corrected uncertainty estimate.

## Parallelization: tasks, workers, and container instances

The notebook or command-line script is the **client**: it submits tasks and collects results. The **scheduler**, on the VM, assigns tasks to workers. The **OCI Raw worker manager** creates or removes container instances when the scheduler requests a change in capacity.

A **task** is a function call with its inputs. A **worker** is a Scaler process that executes one task at a time in this demo. A worker can execute many tasks over its lifetime. A **container instance** provides CPU, memory, and networking for the container that starts those worker processes. These are different counts: 128 tasks do not require 128 workers or 128 container instances.

With the guide's configuration:

| Setting or count | Meaning |
|---|---|
| `instance_ocpus = 4.0` | OCI Raw starts four workers per container instance. |
| `instance_memory_gb = 30.0` | Memory available to the container instance, shared by its workers and their calculations. |
| `max_task_concurrency = 16` | Permits capacity for up to 16 concurrent tasks, corresponding to four instances at this size. It does not prestart them. |
| `--parallelism 128` | Splits one pricing simulation into 128 tasks; workers execute these as capacity becomes available. |
| Pi `--tasks 128` | Submits 128 independent hit-counting tasks; the client sums their results. |

A NumPy batch or a Monte Carlo path is not automatically a separate Scaler task. The application chooses the task boundaries. Increasing paths inside an existing task increases its work without increasing the number of tasks available to schedule.

**Parfun** partitions function inputs into tasks and combines the results. **ParGraph** manages a graph of dependent calculations and submits calculations when their inputs become available. The XVA notebook uses ParGraph; a large total graph does not mean all its nodes can run simultaneously.

### Why only one container instance?

In the Scaler 2.9.0 `vanilla` policy used here, pending work triggers an initial capacity request when no workers exist. Once workers are connected, expansion requires the scheduler's task count divided by its worker count to exceed **10**. It requests additional worker capacity incrementally; OCI Raw converts the requested concurrency into whole container instances and provisions them sequentially. The policy does not estimate each task's remaining execution time.

For example, the XVA notebook initially exposes 15 calibration tasks. One instance supplies four workers, giving `15 / 4 = 3.75` tasks per worker. That is below the expansion threshold, so the first instance can process the calculations in batches even when they take several minutes. Later graph nodes become runnable as their dependencies finish. Choosing `FULL_CONFIG` makes tasks heavier but does not create more graph nodes, so it does not itself force more instances.

The scheduler log `tasks=15, workers=0, current=0 -> desired=1` records the initial requested worker capacity. OCI Raw rounds that request up to one instance containing four workers; its separate `Desired unit count` log counts instances. Worker `connected` messages confirm registration. `balancing task` messages describe task redistribution, not completed calculations.

To use more instances, the application must expose sufficient runnable work for the policy, or the deployment must use a scaling policy suited to a smaller number of long tasks. Raising `max_task_concurrency` alone changes only the ceiling. These thresholds describe this pinned version and default policy.

To exercise scaling, create longer work and more tasks:

```bash
python - <<'PY'
import json
from pathlib import Path
spec = json.loads(Path('examples/sample-simulation.json').read_text())
spec.update(run_id='scaling-demo', simulations=100_000_000)
Path('results').mkdir(exist_ok=True)
Path('results/scaling-demo.json').write_text(json.dumps(spec, indent=2))
PY
bash opengris/run-example.sh --scheduler tcp://127.0.0.1:8516 \
  --spec results/scaling-demo.json --parallelism 128
```

This may create additional billable instances up to your configured limit. Inspect worker hostnames in the output to see where the work ran.

See [Troubleshooting and cleanup](troubleshooting.md) if workers do not connect or tasks fail.
