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

## Who this is not for

- Anyone tuning code that already exists. Use a profiler.
- Anyone who wants a dashboard that reassures them everything is fine.
- Anyone expecting generated recommendations. It will not tell you how to make a function faster.
- Anyone unwilling to commit to explicit structure. The model has to be written down before it can be run.

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

## Stack

| Concern | Choice |
|---|---|
| Language | Python 3.10 or newer |
| Core engine | Standard library only, no Qt and no third party runtime dependency |
| Legacy v1 engine | NumPy, optional and lazily imported, kept only as a frozen oracle |
| Desktop UI | PySide6, a client of the headless core |
| Tests | pytest with pytest-cov, gate configured in `pyproject.toml` |
| Style | black and flake8 at 88 columns |
| Packaging | setuptools, version read from the root `VERSION` file |
| Licence | core GPL-3.0, UI LGPL-3.0 |

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

This repository maintains **100% unit test coverage** and that is enforced by
the command above: coverage reporting and the 100% threshold are configured in
`pyproject.toml`, so there is no separate command to remember and no way to run
the suite without the gate.

## Build

The distributable is the headless CLI core. The desktop UI is deliberately left
out of it (see the packaging notes in [ARCHITECTURE.md](ARCHITECTURE.md)), so a
built wheel contains `latencylab/` and nothing else.

```bash
python -m pip install build
python -m build
```

The version comes from the root `VERSION` file, which is the only place in the
repository that holds a version string. After changing it, refresh the site:

```bash
python stamp_version.py
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): the layers, the invariants and the tests that enforce them.
- [TECH_DEBT.md](TECH_DEBT.md): the standing reference to what is still open, what is
  deliberately left and what only looks like debt.

## UI (GUI)

The GUI lives in [`latencylab_ui/`](latencylab_ui/__init__.py:1).

Note: the UI is intentionally **not packaged** into the published distribution (see the
packaging notes in [`ARCHITECTURE.md`](ARCHITECTURE.md)). Run it from a clone of this
repository.

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

## Licence

Licensed by component, which is what the running application shows under
Help:

- The simulation core in `latencylab/` (and therefore the published
  distribution) is **GPL-3.0**. The full text is in [LICENSE](LICENSE).
- The PySide6 desktop front end in `latencylab_ui/` is **LGPL-3.0**. The full
  text is in [`latencylab_ui/LGPL3.txt`](latencylab_ui/LGPL3.txt).
