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

## Desktop application

The same engine is available behind a PySide6 desktop front end, which adds inspection rather than capability: every number it shows comes from the same run the CLI would have produced.

- **Examples menu.** Every model the application ships with is on it, so a fresh install has something to run before you have written a model of your own. Start with **Checkout**: a storefront checkout where a 150ms debounce added for politeness turns out to own the median.
- **Model Composer.** Author a model in the app rather than by hand and export it as JSON. It is a two-pane dialog: the four parts of a model down the left, the editor for the selected one on the right. Edit opens the loaded model in the same dialog, so composing and changing are one surface rather than two.
- **Guide and information panels.** The Guide is the shortest path to a first run: six numbered steps, then the reasons. The information panel is the companion on reading the output. Both read themselves at a pace you can follow and hand control straight back the moment you touch them.
- **Distributions.** A makespan histogram binned by the Freedman-Diaconis rule, plus a critical-path frequency chart. No resimulation, no smoothing, no inference. The application mark in the middle of the toolbar is the control that opens it.
- **Cancel that cancels.** Stopping a run stops the work at the boundary between one run and the next, then reports how many runs completed. It never aggregates a partial set.
- **Full keyboard navigation.** One explicit focus ring: Tab and Right forward, Shift+Tab and Left back, wrapping at both ends. A disabled control is skipped and wears a red ring rather than lighting up.
- **Light and dark themes**, both built from one token set.
- Open and Export both start in your Downloads folder.

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
| Delivery | Nuitka plus a bespoke installer (Windows), Flatpak (Linux), disk image (macOS) |
| Licence | core GPL-3.0, UI LGPL-3.0 |

## Install (dev)

```bash
python -m pip install -e .[dev]
python -m pip install -r requirements.txt
```

`requirements.txt` brings in PySide6, which only the desktop UI needs. The
simulation core has no runtime dependency at all.

### The legacy extra

Models declaring `schema_version: 1` execute on a frozen NumPy-backed engine
kept as a behavioural oracle, so NumPy is needed to run them and nothing else.
It is deliberately not a runtime dependency:

```bash
python -m pip install -e .[legacy]
```

Without it, a v1 model fails with a message naming this extra. Models at
`schema_version: 2` never touch it. The `dev` extra already includes it, because
the golden-snapshot test needs the oracle.

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

### Desktop builds

Each platform has one entry point at the repository root. All of them stage the
generated icons and the shipped examples beside the application. The toolchain
they need is the `build` extra, kept out of `dev` so running the suite does not
install a compiler.

```bash
python -m pip install -e .[build]
python generate_icons.py
python buildexe.py
python buildinstaller.py
```

`build_flatpak.sh` builds the Linux Flatpak (and `clean_flatpak.sh` removes only
what it produced), while `builddmg.py` builds the macOS disk image on macOS.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): the layers, the invariants and the tests that enforce them.
- [TECH_DEBT.md](TECH_DEBT.md): the standing reference to what is still open, what is
  deliberately left and what only looks like debt.

## UI (GUI)

The GUI lives in [`latencylab_ui/`](latencylab_ui/__init__.py:1).

Note: the UI is intentionally **not packaged** into the published distribution (see the
packaging notes in [`ARCHITECTURE.md`](ARCHITECTURE.md)). Run it from a clone of this
repository or install one of the desktop builds above.

Launch via the module entry point:

```bash
python -m latencylab_ui
```

There is also a small repo-root convenience shim, which is what the frozen build
starts at too:

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
