# Examples

[Back to README](../README.md) · [Start Scaler](../docs/running-examples.md)

This repository includes two kinds of examples:

- **Script-based examples** run from the command line: estimate pi, price individual contracts, or run a market-risk scenario grid. They submit tasks directly to Scaler and combine the results, providing a straightforward way to test the OCI deployment.
- **Notebook-based examples** run interactively in Jupyter: explore larger financial calculations using Parfun and ParGraph. They include native Python implementations that run on the Jupyter host and parallel implementations that execute on Scaler workers. See the [notebook guide](notebooks/README.md) for setup and the SSH tunnel.

## How parallel execution works

| Term | Meaning in this demo |
|---|---|
| Task | One function call and its inputs, such as simulating a batch of paths. Tasks wait until their inputs and a worker are available. |
| Worker | A Scaler process that executes one task at a time, then takes another. Several workers can run inside one container. |
| Container instance | OCI compute capacity hosting the worker container. With this demo's 4-OCPU configuration, each instance starts four workers. |

For example, 15 independent tasks can run on four workers in one container instance: four execute at a time while the others wait. More tasks do not automatically mean more containers. Scaler's scaling policy decides when to request capacity; `max_task_concurrency = 16` is a ceiling, not a request to start 16 workers immediately.

The pricing example's `--parallelism` and the pi example's `--tasks` control how work is split. Parfun splits function inputs; ParGraph exposes calculations that can run once their dependencies are ready. See [parallelization and scaling](../docs/running-examples.md#parallelization-tasks-workers-and-container-instances), including why the XVA notebook may use just one instance.

Run commands from the repository root with your Scaler environment activated and scheduler running.

### Worked example: pi tasks and batches

```bash
python examples/pi.py --tasks 8 --chunks-per-task 2 --chunk-size 100000
```

| Parameter | Meaning |
|---|---|
| `--tasks 8` | Submit eight independent tasks. They run as workers become available. |
| `--chunks-per-task 2` | Each task processes two batches sequentially. |
| `--chunk-size 100000` | Each batch generates 100,000 random points. |

Each task generates `2 × 100,000 = 200,000` points. Across all tasks, the calculation generates **`8 × 2 × 100,000 = 1,600,000` points**. Each task returns its count of points inside the quarter-circle; the client sums the counts and calculates pi.

The two batches do not mean two workers. With two workers, two tasks execute at a time; with four workers, four execute at a time; with eight workers, all eight can execute simultaneously. In this demo, one 4-OCPU container instance starts four workers, so it can process the eight tasks in two groups of four, with workers taking the next waiting task as they finish. Actual timing depends on task duration and worker availability; these small tasks may finish before any additional capacity is provisioned.


## [Estimate pi](pi.py)

Samples random points in a square and estimates pi from the fraction inside a quarter-circle.
Scaler workers count hits independently, and the client combines their counts into one estimate.

```bash
python examples/pi.py --tasks 8 --chunks-per-task 2 --chunk-size 100000
```

## [European call](sample-simulation.json)

Estimates the value of a contract that pays the amount by which the final simulated price exceeds 100, or zero otherwise.
Only the price at the final date determines the payment; workers simulate separate batches of possible price paths.

```bash
bash opengris/run-example.sh --spec examples/sample-simulation.json --parallelism 4
```

## [European put](european-put.json)

Estimates the value of a contract that pays the amount by which 100 exceeds the final simulated price, or zero otherwise.
It uses the same terminal-price simulation approach as the call, with the payment increasing when the final price is lower.

```bash
bash opengris/run-example.sh --spec examples/european-put.json --parallelism 4
```

## [Asian call](asian-call.json)

Uses the arithmetic average of the simulated observation prices instead of only the final price.
The payment is the amount by which that average exceeds 100, or zero, so the calculation must retain information along each path.

```bash
bash opengris/run-example.sh --spec examples/asian-call.json --parallelism 4
```

## [Cash digital call](cash-digital-call.json)

Pays a fixed amount of 10 if the final simulated price is above 100, and zero otherwise.
It demonstrates a threshold-based payment whose size does not increase as the final price rises further.

```bash
bash opengris/run-example.sh --spec examples/cash-digital-call.json --parallelism 4
```

## [Up-and-out call](up-and-out-call.json)

Uses the European call payment, but cancels it if the simulated price reaches or exceeds 125 at a monitored point.
Workers check each path's observations for a barrier breach; crossings between observation points are not detected.

```bash
bash opengris/run-example.sh --spec examples/up-and-out-call.json --parallelism 4
```

## [Market-risk grid](grids/market-risk-grid.json)

Runs nine European-call scenarios combining three starting prices with three volatility values.
Each scenario is split into independent Scaler tasks and produces its own aggregated price estimate.

```bash
bash opengris/run-grid.sh --parallelism 4
```

## Notebook examples

The [notebook gallery](notebooks/README.md#notebook-gallery) includes the four official OpenGRIS examples, a table of their Parfun/ParGraph usage and OCI worker configuration, and a small worker connection check.
Run Jupyter on the scheduler VM and use your workstation browser through an SSH tunnel; the installer includes the required notebook packages.

```bash
bash scripts/start-notebooks.sh
```

For an existing installation, rerun the installer, rebuild the worker image, and regenerate the Scaler configuration first; follow the [notebook setup guide](notebooks/README.md).

Commands default to the scheduler on `tcp://127.0.0.1:8516`. Add `--scheduler tcp://VM_PRIVATE_IP:8516` when submitting from another reachable host. See [execution details and scaling](../docs/running-examples.md) for partitioning, outputs, and the pricing confidence-interval limitation. Run `python examples/pi.py --help` for workload options; its default workload is 51.2 billion samples.
