#!/usr/bin/env python3
"""Run the repository's existing JSON examples using OpenGRIS Scaler 2.9.0.

Place this file in opengris/ inside the quickstart checkout. The client imports
_upstream/montecarlo/app/ directly; remote workers need that same directory in their PYTHONPATH.
Results persist on the client filesystem. This is a synchronous replacement for
the numerical execution path, not the Helm/IAM/Object Storage lifecycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "_upstream" / "montecarlo"
sys.path.insert(0, str(SOURCE_ROOT / "app"))


def source_hash() -> str:
    import montecarlo

    digest = hashlib.sha256()
    for path in sorted(Path(montecarlo.__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def calculate_partition(spec, index: int, count: int, expected_source: str):
    # Keep this callable self-contained so Scaler can serialize it by value.
    import hashlib
    import os
    import platform
    import socket
    from importlib.metadata import version
    from pathlib import Path

    import montecarlo
    import numpy as np
    from montecarlo.engine import run_partition

    digest = hashlib.sha256()
    for path in sorted(Path(montecarlo.__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    actual_source = digest.hexdigest()
    if actual_source != expected_source:
        raise RuntimeError("Client and worker montecarlo source differ; rebuild the worker image")
    if np.__version__ != "2.2.6" or version("opengris-scaler") != "2.9.0":
        raise RuntimeError("Worker requires numpy==2.2.6 and opengris-scaler==2.9.0")
    result = run_partition(spec, index, count, engine_version=montecarlo.__version__)
    return {
        "partial": result.to_dict(),
        "worker": {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scaler": version("opengris-scaler"),
            "source_sha256": actual_source,
        },
    }


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--spec", type=Path, help="existing simulation JSON")
    selection.add_argument("--grid", type=Path, help="existing scenario-grid JSON")
    selection.add_argument("--all-examples", action="store_true", help="run examples/*.json")
    parser.add_argument("--parallelism", type=positive_integer, default=4,
                        help="logical partitions per simulation, not worker count (default: 4)")
    parser.add_argument("--scheduler", default="tcp://127.0.0.1:8516")
    parser.add_argument("--local-workers", type=positive_integer,
                        help="start a local test cluster instead of connecting to OCI")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "opengris")
    parser.add_argument("--max-scenarios", type=positive_integer, default=24)
    args = parser.parse_args()

    import numpy as np
    from importlib.metadata import version
    from montecarlo.aggregate import aggregate
    from montecarlo.grid import render_grid
    from montecarlo.spec import load_spec
    from scaler import Client, SchedulerClusterCombo

    if np.__version__ != "2.2.6" or version("opengris-scaler") != "2.9.0":
        parser.error("Install numpy==2.2.6 and opengris-scaler==2.9.0 on the client")
    source = source_hash()
    invocation_id = uuid.uuid4().hex[:12]
    scenarios = []
    if args.grid:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = render_grid(args.grid, temporary, args.max_scenarios)
            for item in manifest["scenarios"]:
                scenarios.append((item["scenario_id"], load_spec(item["spec_file"]), item["axes"]))
    else:
        paths = sorted((SOURCE_ROOT / "examples").glob("*.json")) if args.all_examples else [
            args.spec or SOURCE_ROOT / "examples" / "sample-simulation.json"
        ]
        scenarios = [(path.stem, load_spec(path), {}) for path in paths]
    if not scenarios:
        parser.error("No simulation examples found")
    for _, spec, _ in scenarios:
        if args.parallelism > spec.simulations:
            parser.error("parallelism cannot exceed simulations")
        if round(spec.confidence_level, 2) not in (0.90, 0.95, 0.99):
            parser.error("The upstream reducer supports confidence levels 0.90, 0.95, 0.99")

    output = args.output_dir / invocation_id
    output.mkdir(parents=True, exist_ok=False)
    prepared = []
    for scenario_id, spec, axes in scenarios:
        spec = replace(spec, run_id=f"{spec.run_id[:40]}-{invocation_id}")
        directory = output / scenario_id
        directory.mkdir()
        request = json.loads(spec.canonical_json)
        # The upstream loader rejects cash_payoff on non-digital products,
        # although its canonical representation includes that default field.
        if spec.product_type != "cash_digital":
            request.pop("cash_payoff")
        write_json(directory / "spec.json", request)
        prepared.append((scenario_id, spec, axes, directory))
    write_json(output / "manifest.json", {
        "invocation_id": invocation_id,
        "source_sha256": source,
        "partitions_per_scenario": args.parallelism,
        "scenarios": [{"scenario_id": key, "run_id": spec.run_id,
                       "input_sha256": spec.input_sha256, "axes": axes}
                      for key, spec, axes, _ in prepared],
        "uncertainty_warning": "Upstream antithetic standard-error formula is preserved, not corrected",
    })
    print(f"Results directory: {output}", file=sys.stderr, flush=True)

    cluster = None
    try:
        address = args.scheduler
        if args.local_workers:
            cluster = SchedulerClusterCombo(n_workers=args.local_workers, logging_level="ERROR")
            address = cluster.get_address()
        with Client(address=address) as client:
            started = perf_counter()
            pending = []
            for scenario_id, spec, axes, directory in prepared:
                futures = [client.submit(calculate_partition, spec, index, args.parallelism, source)
                           for index in range(args.parallelism)]
                pending.append((scenario_id, spec, directory, futures))
            print(f"Submitted {len(prepared) * args.parallelism} tasks", file=sys.stderr, flush=True)
            for scenario_id, spec, directory, futures in pending:
                partials, workers = [], []
                for index, future in enumerate(futures):
                    result = future.result()
                    write_json(directory / f"part-{index:05d}.json", result)
                    partials.append(result["partial"])
                    workers.append(result["worker"])
                summary = aggregate(partials, spec.confidence_level, args.parallelism)
                summary.update({"execution_backend": "opengris-scaler", "workers": workers,
                                "source_sha256": source,
                                "uncertainty_warning": "Upstream antithetic standard-error formula is preserved"})
                write_json(directory / "summary.json", summary)
                print(json.dumps({"scenario": scenario_id, "price": summary["price"],
                                  "simulations": summary["simulations"],
                                  "partitions": summary["partitions"]}), flush=True)
            write_json(output / "completed.json", {"status": "complete", "scenarios": len(prepared),
                       "wall_seconds": perf_counter() - started})
    finally:
        if cluster is not None:
            cluster.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
