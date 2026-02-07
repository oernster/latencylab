# LatencyLab

LatencyLab is a **local, design-time latency exploration tool** for event-driven interactive systems.

It is **not** a profiler, tracer, or runtime observer. Instead, it simulates many independent executions from a declarative model (JSON) to answer questions like:

- where perceived latency comes from
- which causal paths most often dominate latency
- how execution contexts and contention affect responsiveness
- which structural changes improve outcomes before code is written

The MVP is a **CLI** that reads a JSON execution model and produces:

- `summary.json`: aggregate latency and contention statistics
- `runs.csv`: per-run metrics suitable for spreadsheet/plotting workflows

## Install (dev)

```powershell
python -m pip install -e .[dev]
```

## Run

```powershell
latencylab simulate --model examples/interactive.json --runs 10000 --seed 123 \
  --out-summary out/summary.json --out-runs out/runs.csv --out-trace out/trace.csv
```

Outputs:

- [`out/summary.json`](out/summary.json:1): percentiles for first/last UI-tagged event times, makespan, plus top critical-path sequences
- [`out/runs.csv`](out/runs.csv:1): one row per run with per-run metrics
- [`out/trace.csv`](out/trace.csv:1): optional per-task-instance timestamps (enqueue/start/end) and causality pointers

