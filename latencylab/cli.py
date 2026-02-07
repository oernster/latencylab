from __future__ import annotations

import argparse
import json
from pathlib import Path

from latencylab.io import write_runs_csv, write_summary_json, write_trace_csv
from latencylab.metrics import aggregate_runs
from latencylab.model import Model
from latencylab.sim import simulate_many
from latencylab.validate import validate_model


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="latencylab", description="LatencyLab simulator")
    sub = p.add_subparsers(dest="cmd", required=True)

    sim = sub.add_parser("simulate", help="Run simulations for a model")
    sim.add_argument("--model", required=True, type=Path)
    sim.add_argument("--runs", required=True, type=int)
    sim.add_argument("--seed", required=True, type=int)
    sim.add_argument("--out-summary", required=True, type=Path)
    sim.add_argument("--out-runs", required=True, type=Path)
    sim.add_argument("--out-trace", required=False, type=Path)
    sim.add_argument(
        "--max-tasks-per-run",
        required=False,
        type=int,
        default=200_000,
        help="Safety limit to prevent infinite runs in cyclic models",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    p = _build_parser()
    args = p.parse_args(argv)

    if args.cmd == "simulate":
        raw = json.loads(args.model.read_text(encoding="utf-8"))
        model = Model.from_json(raw)
        validate_model(model)

        runs, traces = simulate_many(
            model=model,
            runs=args.runs,
            seed=args.seed,
            max_tasks_per_run=args.max_tasks_per_run,
            want_trace=bool(args.out_trace),
        )

        summary = aggregate_runs(model=model, runs=runs)
        write_summary_json(args.out_summary, summary)
        write_runs_csv(args.out_runs, runs)
        if args.out_trace:
            write_trace_csv(args.out_trace, traces)

        return 0

    raise AssertionError(f"Unhandled command: {args.cmd}")

