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

## Dependencies

- Core runtime: stdlib-only (see [`requirements.txt`](requirements.txt:1))
- Dev/test tools + legacy v1 compatibility: [`requirements-dev.txt`](requirements-dev.txt:1)

Legacy note: v1 exact-output compatibility currently uses a NumPy-backed executor.
v2 execution is stdlib-only.

## Run

```powershell
latencylab simulate --model examples/interactive.json --runs 10000 --seed 123 --out-summary out/summary.json --out-runs out/runs.csv --out-trace out/trace.csv
```

## Model v2 (MVP extensions)

v2 is additive-only and must not change the meaning/results of any valid v1 model.

### Delayed wiring (synthetic delay nodes)

In v2, wiring listeners may be either:

- a task name (v1-compatible)
- an object: `{ "task": "t1", "delay_ms": <dist or number> }`

Example:

```json
{
  "version": 2,
  "wiring": {
    "e1": [{"task": "t1", "delay_ms": {"dist": "fixed", "value": 5.0}}]
  }
}
```

Delay semantics:

- the event still occurs at emission time
- the downstream task is enqueued only after the delay completes
- delays do **not** consume context capacity
- delays are visible in traces and critical paths as synthetic nodes named
  `delay(<event>-><task>)`

### Task metadata (measurement-only)

Tasks may optionally include:

```json
"meta": { "category": "input", "tags": ["hot"], "labels": {"team": "ui"} }
```

Metadata never affects scheduling; it is surfaced in `summary.json` under
`task_metadata`.

Outputs:

- [`out/summary.json`](out/summary.json:1): percentiles for first/last UI-tagged event times, makespan, plus top critical-path sequences
- [`out/runs.csv`](out/runs.csv:1): one row per run with per-run metrics
- [`out/trace.csv`](out/trace.csv:1): optional per-task-instance timestamps (enqueue/start/end) and causality pointers

