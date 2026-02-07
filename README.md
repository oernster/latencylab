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

The MVP is a **CLI** that reads a JSON execution model and produces:

- `summary.json`: aggregate latency and contention statistics
- `runs.csv`: per-run metrics suitable for spreadsheet or plotting workflows
- `trace.csv`: optional per-task-instance timing and causality data

## Install (dev)

```powershell
python -m pip install -e .[dev]
