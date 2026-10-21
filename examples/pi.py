#!/usr/bin/env python3
"""Estimate pi with Monte Carlo darts distributed through Scaler.

Default workload: 128 tasks * 200 chunks * 2,000,000 darts = 51.2 billion darts.
Start with --tasks 8 --chunks-per-task 2 --chunk-size 100000 for a quick check.
"""
import argparse
import math
import time

from scaler import Client


def count_inside_unit_circle(seed: int, chunks: int, chunk_size: int) -> int:
    """Sample the unit square in bounded batches and count quarter-circle hits."""
    import numpy as np

    rng = np.random.default_rng(seed)
    inside = 0
    for _ in range(chunks):
        x = rng.random(chunk_size, dtype=np.float64)
        y = rng.random(chunk_size, dtype=np.float64)
        inside += int(np.count_nonzero(x * x + y * y <= 1.0))
    return inside


def positive_integer(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError('must be at least 1')
    return result


def nonnegative_integer(value):
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError('must be nonnegative')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scheduler', default='tcp://127.0.0.1:8516')
    parser.add_argument('--object-storage-address', default=None,
                        help='default: use the address advertised by the scheduler')
    parser.add_argument('--tasks', type=positive_integer, default=128)
    parser.add_argument('--chunks-per-task', type=positive_integer, default=200)
    parser.add_argument('--chunk-size', type=positive_integer, default=2_000_000)
    parser.add_argument('--seed', type=nonnegative_integer, default=0,
                        help='first task seed; subsequent tasks use consecutive seeds')
    parser.add_argument('--local-workers', type=positive_integer,
                        help='start a local test cluster instead of using OCI workers')
    args = parser.parse_args()

    cluster = None
    try:
        address = args.scheduler
        if args.local_workers:
            from scaler import SchedulerClusterCombo
            cluster = SchedulerClusterCombo(n_workers=args.local_workers, logging_level='ERROR')
            address = cluster.get_address()
        with Client(address=address, object_storage_address=args.object_storage_address) as client:
            started = time.perf_counter()
            futures = [client.submit(count_inside_unit_circle, args.seed + task,
                                     args.chunks_per_task, args.chunk_size)
                       for task in range(args.tasks)]
            # A final estimate is printed only after every task returns successfully.
            inside = sum(future.result() for future in futures)
            elapsed = time.perf_counter() - started
    finally:
        if cluster is not None:
            cluster.shutdown()

    total = args.tasks * args.chunks_per_task * args.chunk_size
    pi_estimate = 4.0 * inside / total
    print(f'threw {total:,} darts across {args.tasks} tasks in {elapsed:.2f}s')
    print(f'pi ~= {pi_estimate:.6f}  (error {abs(pi_estimate - math.pi):.2e})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
