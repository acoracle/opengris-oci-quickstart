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


## Choose an example

The [examples catalogue](../examples/README.md) describes each calculation in two lines and shows how to run pi, one pricing input, or the scenario grid. The pi script is in [`examples/pi.py`](../examples/pi.py).

The adapter reuses upstream `run_partition()` and `aggregate()`. One simulation becomes several Scaler tasks; futures return partial statistics to the client for aggregation. All five examples and the nine market-risk scenarios are supported. `--parallelism` is the number of logical tasks per simulation, not the number of container instances. Preserve the same partition count and seed when comparing results with the Kubernetes demo.

Outputs are under `results/opengris/<invocation-id>/`, with a manifest, reusable input specifications, per-partition results, worker metadata, summaries, and `completed.json` after all scenarios finish. The adapter checks that worker and client source hashes match. A failed invocation can leave partial files; there is no automatic resume or durable job service in this adapter.

**Statistical limitation:** the upstream reducer treats antithetic payoffs as independent when calculating standard error. This adapter preserves that calculation to reproduce upstream output; its confidence intervals are not a corrected uncertainty estimate.

### Why only one container instance?

A 4-OCPU instance runs four workers. Small examples can finish on that instance. The Scaler 2.9.0 vanilla policy grows capacity gradually using task-to-worker thresholds, and OCI Raw provisions instances sequentially. `max_task_concurrency` permits capacity; it does not prewarm a fixed pool.

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
