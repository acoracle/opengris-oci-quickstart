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

Tasks trigger creation of workers. The smoke test prints task results, worker hostnames, and package versions. A container instance being `ACTIVE` alone does not prove workers have registered or processed tasks.

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
