# LatencyLab: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the Qt-free core in `latencylab/`, the PySide6 front end in `latencylab_ui/` and the packaging metadata) read against `ARCHITECTURE.md` and the tests it names.

---

## 1. The 100% coverage gate is opt-in, so it is not a gate

`ARCHITECTURE.md` lists it under "Quality gates (enforced by tests)": "Unit test coverage is enforced at 100% when running with `pytest-cov` using `--cov-fail-under=100`." Nothing enforces it. `pyproject.toml` has no `addopts` and `.coveragerc` has no `fail_under`, so `python -m pytest` (the command the README gives first) runs the whole suite and reports success at any coverage level. The gate only exists when somebody remembers to paste the long form from the README.

That is the difference between a constraint and a reminder. The repo already knows the answer, because the boundary and size invariants are real tests that fail on their own. The fix is one line in `pyproject.toml`:

```
[tool.pytest.ini_options]
addopts = "-q --cov=latencylab --cov=latencylab_ui --cov-report=term-missing --cov-fail-under=100 --cov-config=.coveragerc"
```

Until that lands, every claim of 100% in the README and in `ARCHITECTURE.md` is a claim about a command, not about the repository.

## 2. Three version strings and no `VERSION` file

The repo carries three, and they disagree:

| Location | Value |
|---|---|
| `latencylab/version.py` | `2.0.1` |
| `latencylab_ui/__init__.py` | `0.1.0` |
| `pyproject.toml` | `0.1.0` |

There is no `VERSION` file and no `stamp_version.py`. The core says it is on its third major release, the packaging metadata says it is pre-1.0 and the UI has its own unrelated number. Anything reading the version (an About dialog, a published wheel, a bug report) gets a different answer depending on which one it reaches for.

The fix is the pattern the other projects here already use: a `VERSION` file at root as the single real string, `version.py` reading it with a `0.0.0-dev` fallback, `pyproject.toml` made dynamic, `latencylab_ui` importing the core's rather than declaring its own. This is small, mechanical and should be done before anything else in this file, because every other change makes the disagreement older.

## 3. The licence is stated three different ways

`LICENSE` at root is GNU GPL-3.0. `pyproject.toml` declares `license = "MIT"` with `license-files = ["LICENSE"]`, so the published metadata says MIT while pointing at the GPL text. `latencylab_ui/LGPL3.txt` ships a third licence for the UI package.

The intent is legible (GPL core, LGPL Qt front end, matching the Fulcrum split) but the declaration does not say it. A packaged wheel currently advertises MIT for GPL code, which is the one failure mode here that reaches other people. Resolve by deciding the split explicitly, then making all three artefacts agree: a root `LICENSE` describing the map, `LICENSE-GPL-3.0.txt` and `LICENSE-LGPL-3.0.txt` beside it and a `pyproject.toml` that names what is actually shipped.

## 4. Two modules sit one edit away from breaking the build

`tests/test_codebase_size_limits.py` fails any Python file over 400 lines, across the whole repo. Two files are inside the top 5% of that budget:

- `latencylab_ui/focus_cycle.py` at 396
- `tests/test_ui_main_window.py` at 389

Adding four lines to the first, or twelve to the second, turns a green suite red for a reason unrelated to the change being made. Shaving a line or two buys nothing, because the next edit puts it back. Each should be taken to 350 or below by extracting one cohesive concern, not by trimming. Six more files sit between 355 and 367 and are fine where they are.

The size test itself has no notion of the danger band; adding a warning tier (fail over 400, report over 380) would make this self-policing rather than a thing to remember.

## 5. The v1 NumPy engine is a permanent optional dependency

`sim_legacy.py` is the frozen behavioural oracle: `test_determinism.test_v1_outputs_are_stable_golden_snapshot()` pins its output and `ARCHITECTURE.md` names it invariant 4. That is a legitimate reason to keep an old engine.

The cost is that `sim_legacy.py` needs NumPy, so the project carries a `legacy` extra and a dev dependency on NumPy purely to run the oracle, while `sim_v2.py` (the engine that actually ships) is stdlib-only. Every environment that runs the full suite therefore installs a scientific-stack dependency to check a snapshot.

This is worth revisiting exactly once: if the v1 outputs are frozen, they can be frozen as *data*. Recording the golden snapshot as a committed JSON fixture and asserting `sim_v2` against it preserves the invariant, keeps the regression protection and lets `sim_legacy.py` and NumPy leave the repo entirely. If the intent is instead to keep v1 executable for future comparison, then it is not debt and belongs in the section below; that decision has not been made either way, which is why it is here.

## 6. The core package is flat, and `ARCHITECTURE.md` does not claim otherwise

`latencylab/` is thirteen sibling modules (`model`, `sim`, `sim_v2`, `sim_legacy`, `executors`, `metrics`, `io`, `validate`, `types`, `cli`) with no `domain` / `application` / `infrastructure` split. The one layering invariant that is enforced is the Qt-free boundary between the two packages.

This is a deliberate difference from the rest of the portfolio and it is defensible at this size: a simulator with one clear input type and one clear output type does not need four directories. The debt is not the flatness, it is that `io.py` (file reading and writing) and `validate.py` (pure rules) sit at the same level as `model.py` (the domain types), so nothing structural prevents the domain reaching for the filesystem. A single source-scan test asserting that `model.py`, `types.py` and `validate.py` import neither `io` nor `os` nor `pathlib` would buy the guarantee without the directory churn. That is the proportionate fix.

## 7. There is no delivery path

The site presents LatencyLab as a tool. The repository ships no `buildexe.py`, no installer, no Flatpak script and no DMG script, and the README says to run it from a clone. `ARCHITECTURE.md` notes the UI is deliberately not packaged into the published distribution.

For a design-time instrument used by its author this is a reasonable place to stop, so this is recorded as a known boundary rather than a defect. It becomes real debt the moment the tool is offered to anyone who is not going to clone a repo and create a venv.

## 8. Two example models are tracked at repository root

`stellody_music_discovery.json` and `stellody_music_discovery_STRESS.json` sit at root while `examples/` exists and holds `contention.json` and `interactive.json`. They are the same kind of artefact in two places, and the root copies name an unrelated project. Move them into `examples/` or drop them.

---

## Looks like debt, not worth touching

- The twenty-odd `except Exception` blocks in `latencylab_ui`. Each carries a `# noqa: BLE001` and most sit on Qt style, dialog or file-dialog paths where an exception is worse than a degraded widget. Narrowing them individually is churn on the least valuable surface in the repo.
- The `main_window_*.py` family (`bindings`, `dock_switching`, `file_io`, `menus`, `panels`, `top_bar`) and the `model_composer_*.py` family look like one class shattered across seven files. That is the 400-line cap doing its job and each part is cohesive.
- The seven `test_*_coverage.py` and `test_*_remaining_coverage.py` files are named after the gate rather than after behaviour. Ugly, honest and harmless; renaming them changes nothing that runs.
- `sim.py` at 29 lines is a facade that only dispatches. That is the executor seam working, not an anaemic module.
- `runner.py` at root is a shim launcher. It is two lines of convenience and does not need a home in a package.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **The `latencylab` / `latencylab_ui` two-package split.** It is the Qt-free boundary, it is enforced by `test_ui_dependency_boundaries.py` and it is the single most important structural property the repo has.
- **`test_codebase_size_limits.py` scanning the whole repo rather than one package.** Whole-repo is the correct scope here precisely because there are no exempt delivery scripts to carve out.
- **The golden v1 snapshot in `test_determinism.py`.** Whatever happens to `sim_legacy.py` under item 5, the frozen-output assertion stays. It is what makes the tool's determinism claim checkable.
- **The `RunExecutor` protocol with a single production implementation.** It looks like premature abstraction; it is the seam that keeps `sim.py` stdlib-only and lets the legacy engine be lazily imported. Removing it re-couples the core to NumPy.
- **The UI being excluded from the published wheel.** Deliberate and documented. The CLI is the distributable, the GUI is the workbench.
