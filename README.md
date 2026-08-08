# LatencyLab

Simulate your architecture's latency before you build it.

LatencyLab is a design-time latency simulator. You describe a planned (or existing) software architecture as a small, explicit model: the units of work, the events that trigger them and the shared resources they queue behind. LatencyLab executes that model thousands of times with realistic timing variation. Out come the numbers you cannot get from a whiteboard: how long the flow takes across percentiles, which chain of work actually held each run up and how often each chain is the culprit. It works on the design, not the code, so it applies to any event-driven software: web backends, desktop and mobile UIs, microservices and embedded pipelines. Change the model, run again on the same seed and you can see exactly what an architectural decision costs before a line of it is written.

It is not a profiler, tracer or runtime observer. It exists to prevent confident people from shipping bad architecture.

## The workflow

The workflow is a loop: model, run, read, change one thing, run again on the same seed, compare. If the dominant critical path moved or the percentiles shifted, that difference is the cost or benefit of your design change, isolated from luck, because the randomness was identical.

Each run answers questions that usually get postponed until it is too late:

- where perceived latency actually comes from  
- which causal paths dominate latency most often  
- how execution contexts and contention affect responsiveness  
- which architectural changes help before code is written  

If this output surprises you, that is the point.

## What is a model?

A model is your architecture written down small enough to argue about. It has four parts:

- **System.** A name and the entry event that kicks off a run (for the shipped example, `user.checkout_clicked`).
- **Contexts.** The things work runs on: a thread pool, a database connection, a browser main thread, a worker queue. Each has one property, **concurrency**: how many things it can genuinely do at once. Concurrency 1 means everything sent to it waits in line, which is exactly what a single database connection or a UI thread is. This is where queueing (and therefore most surprising latency) comes from.
- **Tasks.** The units of work: which context each runs on, how long it takes (as a distribution, not a single number, because real durations vary) and which event it emits when it finishes.
- **Wiring.** Which events trigger which tasks, optionally after a delay (debounces, retry backoffs, poll intervals). The wiring is the architecture.

You are not modelling your code. You are modelling the shape of the design: what happens, what waits for what and what competes for what. A useful model is often 10 to 20 tasks. Models are plain JSON; the desktop app's Composer builds them without hand-writing any.

This excerpt from the shipped [Checkout example](examples/checkout.json) is a complete round trip through all four parts (the full model has ten tasks):

```json
{
  "schema_version": 2,
  "entry_event": "user.checkout_clicked",
  "contexts": {
    "ui": { "concurrency": 1 },
    "db": { "concurrency": 1 }
  },
  "tasks": {
    "ui.handle_click": {
      "context": "ui",
      "duration_ms": { "dist": "fixed", "value": 4.0 },
      "emit": ["checkout.started"]
    },
    "db.load_cart": {
      "context": "db",
      "duration_ms": { "dist": "lognormal", "mu": 4.4, "sigma": 0.45 },
      "emit": ["cart.loaded"]
    },
    "ui.render_cart": {
      "context": "ui",
      "duration_ms": { "dist": "normal", "mean": 18.0, "std": 4.0, "min": 1.0 },
      "emit": ["ui.section_rendered"]
    }
  },
  "wiring": {
    "user.checkout_clicked": ["ui.handle_click"],
    "checkout.started": ["db.load_cart"],
    "cart.loaded": ["ui.render_cart"]
  }
}
```

## Who this is for

LatencyLab is for anyone making structural decisions about event-driven software: senior engineers, architects and CTOs, at the point where those decisions are still cheap to change. It is domain-agnostic: because it simulates the design rather than instrumenting code, the same tool models a web checkout, a desktop app's UI thread, a fan-out of microservice calls or an embedded event pipeline.

If you have ever said "we will profile it later", this is what later should have looked like.

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

## What running it actually does

LatencyLab executes the model as a simulation: the entry event fires, tasks run on their contexts, queues form where concurrency is exhausted and durations are drawn from the distributions you chose. It does this hundreds or thousands of times, each run seeded, so the whole experiment is reproducible bit for bit. One run tells you nothing; the spread across runs is the finding.

For every run it records the **makespan** (how long the whole flow took, which is how long the user waited) and the **critical path** (the specific chain of tasks and waits that prevented the run finishing sooner; expensive work off that chain delayed nobody).

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
| Legacy v1 engine | NumPy, optional and lazily imported; the live execution path for `schema_version: 1` models and the frozen oracle the snapshot test pins |
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

`generate_icons.py` derives every platform asset from the single master
`latencylab.png`, including the opaque macOS variants the Dock, Finder and the
disk image need. If the mark itself has changed, run `render_master_icon.py`
first: the published site SVG is the source and the master PNG is a render of
it, never an independent drawing.

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
