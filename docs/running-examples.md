# Running examples and testing scaling

[Back to README](../README.md)

Run shell commands from the repository root.

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

The short wait keeps tasks active briefly so worker activity is easier to observe. It does not perform a numerical calculation or measure CPU performance.

If no workers are available, the pending tasks prompt the OCI Raw manager to provision capacity. The first run can take longer while a container instance is created, its image is pulled, and workers start. Existing workers can execute the test immediately.

Successful output contains eight result dictionaries. For example, the first two might look like:

```text
{'task': 0, 'host': 'worker-container-host', 'scaler': '2.9.0', 'numpy': '2.2.6'}
{'task': 1, 'host': 'worker-container-host', 'scaler': '2.9.0', 'numpy': '2.2.6'}
```

Confirm that **all eight results appear** and that the versions match the example environment: Scaler `2.9.0` and NumPy `2.2.6`. The script prints results in submission order and exits after collecting them all. It reports the versions; it does not assert that they match those expected values.

Repeated hostnames are normal: several workers and tasks can share one container instance. This test does not require eight workers or eight container instances, and its output does not prove that tasks ran simultaneously.

Receiving all eight results verifies the client-to-scheduler connection, task dispatch, worker execution, and result return. If the test caused new workers to be created, it also exercises OCI provisioning and image startup. A container instance reaching `ACTIVE` alone is not sufficient; completed tasks show that workers are actually executing work.

The test checks package metadata, so it does not verify NumPy calculations or the Monte Carlo code. Run the examples below to check the actual calculation path. If results never arrive or the script raises an error, inspect the scheduler and worker logs using the [troubleshooting guide](troubleshooting.md).

## Run the Monte Carlo examples

On the scheduler VM in the second terminal:

```bash
bash opengris/run-example.sh --scheduler tcp://127.0.0.1:8516 --parallelism 4
bash opengris/run-example.sh --scheduler tcp://127.0.0.1:8516 --all-examples --parallelism 4
bash opengris/run-grid.sh --scheduler tcp://127.0.0.1:8516 --parallelism 4
```

Run a particular input:

```bash
bash opengris/run-example.sh --scheduler tcp://127.0.0.1:8516 \
  --spec examples/asian-call.json --parallelism 4
```

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
