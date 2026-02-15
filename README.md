# LatencyLab

LatencyLab is a local, design time latency exploration tool for event driven interactive systems.

It is not a profiler, tracer or runtime observer. It exists to prevent confident people from shipping bad architecture.

LatencyLab simulates many independent executions from a declarative JSON model to answer questions that usually get postponed until it is too late:

- where perceived latency actually comes from  
- which causal paths dominate latency most often  
- how execution contexts and contention affect responsiveness  
- which architectural changes help before code is written  

If this output surprises you, that is the point.

## Who this is for

LatencyLab is aimed at senior engineers, architects and CTOs who make structural decisions that are expensive to undo.

If you have ever said “we will profile it later”, this is what later should have looked like.

LatencyLab is not for tuning code.  
It is for validating architectural decisions before they harden.

## Context

LatencyLab exists to support design time reasoning about latency rather than post hoc analysis.

The motivation, philosophy and trade offs behind the tool are described in more detail in the accompanying blog post:

[LatencyLab guide](https://www.crankthecode.com/posts/latencylab)

Reading that is not required to use the tool. It explains why the tool exists and what kinds of problems it is intended to make visible.

## What it does

Instead of attaching to running production code, LatencyLab executes explicit models of tasks, events, queues, delays and resource contention using deterministic scheduling and seeded randomness.

Models are executed many times to produce concrete outputs such as critical paths, queue wait, UI timing and percentiles.

This is how you find the latency problem before it is politically expensive.

## Core outputs

The primary interface is a CLI that reads a JSON execution model and produces:

- `summary.json` containing aggregate latency and contention statistics  
- `runs.csv` containing per run metrics suitable for analysis or plotting  
- `trace.csv` containing optional per task instance timing and causality data  

## Install (dev)

```bash
python -m pip install -e .[dev]
python -m pip install -r requirements.txt
```

## Tests

Run the full test suite:

```bash
python -m pytest
```

Run the full test suite **with strict coverage enforcement**:

```bash
python -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=100
```

This repository currently maintains **100% unit test coverage** under that command.

## UI (GUI)

The GUI lives in [`latencylab_ui/`](latencylab_ui/__init__.py:1).

Note: the UI is intentionally **not packaged** into the published distribution (see notes in
[`ARCHITECTURE.md`](ARCHITECTURE.md:47)). Run it from a clone of this repository.

Launch via the module entry point:

```bash
python -m latencylab_ui
```

There is also a small repo-root convenience shim:

```bash
python runner.py
```

If you see an error about `PySide6` missing, install the GUI dependency via
[`requirements.txt`](requirements.txt:1) (or `pip install PySide6`).
