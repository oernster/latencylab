# LatencyLab

LatencyLab is a **local, design-time latency exploration tool** for event-driven interactive systems.

It is **not** a profiler, tracer or runtime observer. Instead it simulates many independent executions from a declarative model (JSON) to answer questions like:

- where perceived latency comes from
- which causal paths most often dominate latency
- how execution contexts and contention affect responsiveness
- which structural changes improve outcomes before code is written

## Context

LatencyLab exists to support design-time reasoning about latency rather than post-hoc analysis. The motivation, philosophy and trade-offs behind the tool are described in more detail in the accompanying blog post:

https://www.crankthecode.com/posts/latencylab

Reading that is not required to use the tool, but it explains the problems LatencyLab is intended to make visible.

## Core outputs

The primary interface is a **CLI** that reads a JSON execution model and produces:

- `summary.json`: aggregate latency and contention statistics
- `runs.csv`: per-run metrics suitable for spreadsheet or plotting workflows
- `trace.csv`: optional per-task-instance timing and causality data

## Install (dev)

    python -m pip install -e .[dev]

## Dependencies

- Core runtime: stdlib-only (see `requirements.txt`)
- Dev and test tools plus legacy v1 compatibility: `requirements-dev.txt`

## UI (PySide6)

The repository includes an optional desktop UI client under `latencylab_ui/`.

Install PySide6:

    python -m pip install -r requirements.txt

Run the UI from source:

    python -m latencylab_ui

Notes:

- The UI is a client of the core; no Qt imports exist under `latencylab/`
- Simulations run in a background thread
- Cancel in v1 does not stop the simulation mid-run; it discards results when the run completes
- Results can be saved to disk to support comparison across runs rather than one-off exploration

Legacy note: v1 exact-output compatibility currently uses a NumPy-backed executor.  
v2 execution is stdlib-only.

## Run (CLI)

    latencylab simulate --model examples/interactive.json --runs 10000 --seed 123 --out-summary out/summary.json --out-runs out/runs.csv --out-trace out/trace.csv

## Application version vs model schema version

The installed LatencyLab package has its own application version (`latencylab.version.__version__`).

Separately, each model JSON declares a **model schema version**.
Canonical field name: `schema_version`.

- `schema_version: 1` = legacy executor for exact output stability
- `schema_version: 2` = MVP extensions including delayed wiring and task metadata

For compatibility, the loader also accepts legacy aliases `version` and `model_version`.

## Schema notes

- Tasks emit events via `emit` (list of event names)
- Duration distributions use `duration_ms: {"dist": ..., ...}` with:
  - `fixed`: `value`
  - `normal`: `mean`, `std`, optional `min`
  - `lognormal`: `mu`, `sigma`
- Events are declared as a map: `events: {"event_name": {"tags": [...]}}`
- Wiring is a map: `wiring: {"event_name": ["task", {"task": "...", "delay_ms": ...}]}`

## Model v2 extensions

v2 is additive-only and must not change the meaning or results of any valid v1 model.

### Delayed wiring (synthetic delay nodes)

In v2, wiring listeners may be either:

- a task name (v1-compatible)
- an object: `{ "task": "t1", "delay_ms": <dist or number> }`

Example:

    {
      "schema_version": 2,
      "wiring": {
        "e1": [{"task": "t1", "delay_ms": {"dist": "fixed", "value": 5.0}}]
      }
    }

Delay semantics:

- the event still occurs at emission time
- the downstream task is enqueued only after the delay completes
- delays do not consume context capacity
- delays are visible in traces and critical paths as synthetic nodes named `delay(<event>-><task>)`

### Task metadata (measurement-only)

Tasks may optionally include:

    "meta": { "category": "input", "tags": ["hot"], "labels": {"team": "ui"} }

Metadata never affects scheduling; it is surfaced in `summary.json` under `task_metadata`.

Outputs:

- `summary.json`: percentiles for first and last UI-tagged event times, makespan and top critical-path sequences
- `runs.csv`: one row per run with per-run metrics
- `trace.csv`: optional per-task-instance timestamps and causality pointers
