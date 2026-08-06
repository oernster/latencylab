# LatencyLab: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the Qt-free core in `latencylab/`, the PySide6 front end in `latencylab_ui/` and the packaging metadata) read against `ARCHITECTURE.md` and the tests it names.

---

Nothing is open. The two sections below record the standing decisions that keep it that way.

---

## Looks like debt, not worth touching

- The twenty-odd `except Exception` blocks in `latencylab_ui`. Each carries a `# noqa: BLE001` and most sit on Qt style, dialog or file-dialog paths where an exception is worse than a degraded widget. Narrowing them individually is churn on the least valuable surface in the repo.
- The `main_window_*.py` family (`bindings`, `dock_switching`, `file_io`, `menus`, `panels`, `top_bar`) and the `model_composer_*.py` family look like one class shattered across seven files. That is the 400-line cap doing its job and each part is cohesive.
- The `test_*_coverage.py` and `test_*_remaining_coverage.py` files are named after the gate rather than after behaviour. Ugly, honest and harmless; renaming them changes nothing that runs.
- `sim.py` at 29 lines is a facade that only dispatches. That is the executor seam working, not an anaemic module.
- `runner.py` at root is a shim launcher. It is two lines of convenience and does not need a home in a package.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **The `latencylab` / `latencylab_ui` two-package split.** It is the Qt-free boundary, it is enforced by `test_ui_dependency_boundaries.py` and it is the single most important structural property the repo has.
- **`test_codebase_size_limits.py` scanning the whole repo, plus a named exemption for the delivery scripts.** The exempt set is eight files, listed by name and matched only at the repository root, and a companion test fails if any of those names stops existing so a rename cannot leave a hole behind. The line between exempt and not is deliberate: the recipe that invokes Nuitka is a script, and the window it produces is a program. `installer/` is application code and is held to the cap like everything else.
- **The golden v1 snapshot in `test_determinism.py`.** The frozen-output assertion is what makes the tool's determinism claim checkable.
- **`sim_legacy.py` and the optional NumPy dependency.** This reads as an old engine kept alive to satisfy a snapshot test. It is not: `default_executor_for_model` dispatches any model declaring `schema_version == 1` to `LegacyNumpyExecutor`, so `sim_legacy.py` is a live execution path and deleting it would remove a feature rather than retire a fixture. The cost is already contained: the project's runtime `dependencies` are empty, NumPy is confined to the `legacy` and `dev` extras and `sim_legacy.py` raises a `ModuleNotFoundError` naming the extra to install. What the arrangement lacks is documentation, not a redesign.
- **The `RunExecutor` protocol with a single production implementation.** It looks like premature abstraction; it is the seam that keeps `sim.py` stdlib-only and lets the legacy engine be lazily imported. Removing it re-couples the core to NumPy.
- **The UI being excluded from the published wheel.** Deliberate, documented and excluded by name in `pyproject.toml` and now asserted by `test_core_boundaries_and_packaging.py` rather than described.
- **The `ruff check` baseline.** A default-rules `ruff check` reports a substantial backlog on this repository. flake8 is the configured linter here and it is clean; ruff is a second opinion that has not been adopted, so its findings are a reading rather than a regression. Clearing them wholesale would be a large diff across the UI package for no behavioural gain. The findings that were worth taking (unused imports, unused locals, malformed comment markers) have been applied.
- **`E501` in `extend-ignore`.** black owns line length in this repository and formats every code line to 88, so a passing `black --check` means the only lines left over 88 are ones black declined to split: string literals and comments. Reporting those teaches people to reformat prose to satisfy a code rule or to sprinkle `noqa`. The rationale is written into `.flake8` beside the setting so it cannot be read as an oversight.
