# Examples

[Back to README](../README.md) · [Start Scaler](../docs/running-examples.md)

Run commands from the repository root with your Scaler environment activated and scheduler running.

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

Commands default to the scheduler on `tcp://127.0.0.1:8516`. Add `--scheduler tcp://VM_PRIVATE_IP:8516` when submitting from another reachable host. See [execution details and scaling](../docs/running-examples.md) for partitioning, outputs, and the pricing confidence-interval limitation. Run `python examples/pi.py --help` for workload options; its default workload is 51.2 billion samples.
