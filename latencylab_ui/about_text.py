from __future__ import annotations

"""What the About dialog says.

Separated from the dialog that shows it so the credits can be asserted without
a QApplication, and so the dialog stays a layout rather than a layout plus a
bill of materials.

Every dependency the application actually ships is named here with its licence.
The point is not decoration: LatencyLab is distributed under the GPL and the
LGPL, and both oblige it to say what it is built on. A credits list that drifts
from the real dependency set is worse than none, so the test pins it against
the project's own requirements.
"""

from dataclasses import dataclass

from latencylab.version import __version__

APP_NAME = "LatencyLab"
APP_TAGLINE = "Design-time latency exploration for event-driven systems"
APP_AUTHOR = "Oliver Ernster"
APP_URL = "https://oernster.github.io/latencylab/"

LICENCE_SUMMARY = (
    "Distributed under the GNU General Public License version 3 (the model and "
    "the command line interface) and the GNU Lesser General Public License "
    "version 3 (the PySide6 user interface). Both texts are on the Help menu."
)


@dataclass(frozen=True, slots=True)
class Credit:
    """One dependency, its licence, and why it is here.

    `distributions` names the packages on PyPI that this credit accounts for.
    It is what lets a test read the project's own requirement files and prove
    nothing is installed that goes uncredited, which is the only way a list
    like this stays true after the first dependency change.
    """

    name: str
    licence: str
    context: str
    distributions: tuple[str, ...] = ()


# PySide6 and Python are first: they are what the application IS. The rest
# follow in the order a reader meets them, runtime before tooling.
CREDITS: tuple[Credit, ...] = (
    Credit(
        "PySide6 (Qt for Python)",
        "LGPL-3.0",
        "the user interface",
        ("pyside6",),
    ),
    Credit("Python", "PSF", "the language and standard library"),
    Credit("NumPy", "BSD-3-Clause", "the schema version 1 executor", ("numpy",)),
    Credit("pytest and pytest-cov", "MIT", "the test suite", ("pytest", "pytest-cov")),
    Credit("black and flake8", "MIT", "formatting and linting", ("black", "flake8")),
    Credit("Pillow", "HPND", "generating the icon set", ("pillow",)),
    Credit("Nuitka", "Apache-2.0", "the Windows build", ("nuitka",)),
    Credit(
        "PyInstaller",
        "GPL-2.0-or-later with an exception",
        "the macOS build",
        ("pyinstaller",),
    ),
)

CREDITED_DISTRIBUTIONS = frozenset(
    name for credit in CREDITS for name in credit.distributions
)


def about_html(*, python_version: str, pyside_version: str) -> str:
    """Render the About body.

    The runtime versions are passed in rather than read here, so the text can be
    rendered and asserted without importing a GUI toolkit to ask it its version.
    """

    credits_html = "\n".join(
        f"<li><b>{credit.name}</b> - {credit.licence} ({credit.context}).</li>"
        for credit in CREDITS
    )

    return (
        f"<h2>{APP_NAME}</h2>"
        f"<p><b>{APP_TAGLINE}</b></p>"
        f"<p><b>Version:</b> {__version__}</p>"
        f"<p><b>Author:</b> {APP_AUTHOR}</p>"
        f'<p><a href="{APP_URL}">{APP_URL}</a></p>'
        f"<p>{LICENCE_SUMMARY}</p>"
        f"<p><b>Python:</b> {python_version}<br>"
        f"<b>PySide6 (Qt for Python):</b> {pyside_version}</p>"
        "<hr>"
        "<h3>Open source credits</h3>"
        f"<ul>{credits_html}</ul>"
        "<p>Built on the Python and Qt ecosystems, with thanks to their "
        "communities.</p>"
    )
