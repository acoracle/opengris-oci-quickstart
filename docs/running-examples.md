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


If no workers are available, the pending tasks prompt the OCI Raw manager to provision capacity. The first run can take longer while a container instance is created, its image is pulled, and workers start. Existing workers can execute the test immediately.


## Estimate pi with Monte Carlo

[`examples/pi.py`](../examples/pi.py) throws random points into the unit square. It counts points satisfying `x² + y² <= 1`, which lie inside a quarter of a unit circle. The hit fraction estimates `pi / 4`, so the client calculates `pi = 4 * total_hits / total_darts`.

Start with a small run against your running scheduler:

```bash
python examples/pi.py --tasks 8 --chunks-per-task 2 --chunk-size 100000
```

This submits eight tasks and samples **1,600,000 points** in total. Each task uses NumPy on a worker and returns only its hit count. The client sums the counts after every future completes, then prints the estimated pi, its absolute difference from `math.pi`, and elapsed time.

For the larger workload from the original example:

```bash
python examples/pi.py --tasks 128 --chunks-per-task 200 --chunk-size 2000000
```

This samples **51,200,000,000 points**. It is also the script's default workload. Runtime depends on available workers, CPU performance, and container startup; no fixed completion time is assumed. Tasks can trigger additional OCI capacity up to the worker manager's configured limit.

`--tasks` controls the number of independent Scaler tasks. `--chunks-per-task` controls task duration, and `--chunk-size` controls the NumPy batch size and per-task memory use. The script processes batches without retaining all points. Each task has a distinct seed, starting from `--seed` (default 0); keeping the seed and workload settings unchanged makes the sampled points reproducible regardless of which worker executes a task.

The scheduler defaults to `tcp://127.0.0.1:8516`. Use `--scheduler tcp://VM_PRIVATE_IP:8516` when submitting from another reachable host. `--object-storage-address tcp://VM_PRIVATE_IP:8517` can override the scheduler's advertised data address when needed. NumPy is already included in this repository's worker image; this example needs no image rebuild or additional packages.

The final estimate is printed only after all tasks succeed. An exception or disconnection before that point means the run has not produced a complete estimate.

For a local check without OCI:

```bash
python examples/pi.py --local-workers 2 \
  --tasks 8 --chunks-per-task 2 --chunk-size 100000
```

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
