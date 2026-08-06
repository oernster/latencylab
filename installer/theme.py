"""The setup program's look, taken from the application it installs.

LatencyLab runs on a dark Fusion palette accented in teal, so the installer
does too: the first thing a user sees should already look like the thing they
are about to run.

Two rules matter more than the colours. Every button carries a 2px transparent
border at rest, so lighting one on hover changes its colour and never its size.
And every hover and focus rule is gated on `:enabled`, so a disabled button
stays visibly dead under the mouse and as a skipped focus target.
"""

from __future__ import annotations

# The application's own accent (latencylab_ui/theme.py, _ACCENT_TEAL).
ACCENT = "#26a69a"
ACCENT_TEXT = "#0f0f0f"

WINDOW_BG = "#1e1e1e"
SURFACE_BG = "#181818"
BUTTON_BG = "#282828"
BUTTON_BG_HOVER = "#323232"
TEXT = "#e4e4e4"
TEXT_DISABLED = "#969696"
BORDER = "#3c3c3c"

# Named so the border width appears once and the transparent default and the
# accent ring can never drift apart.
BORDER_WIDTH_PX = 2

STYLESHEET = f"""
QWidget {{
    background-color: {WINDOW_BG};
    color: {TEXT};
}}

QPlainTextEdit, QTextBrowser {{
    background-color: {SURFACE_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
}}

QPushButton {{
    background-color: {BUTTON_BG};
    color: {TEXT};
    border: {BORDER_WIDTH_PX}px solid transparent;
    border-radius: 4px;
    padding: 6px 18px;
    min-width: 96px;
}}

QPushButton:enabled:hover {{
    background-color: {BUTTON_BG_HOVER};
    border: {BORDER_WIDTH_PX}px solid {ACCENT};
}}

QPushButton:enabled:focus {{
    border: {BORDER_WIDTH_PX}px solid {ACCENT};
}}

QPushButton:disabled {{
    color: {TEXT_DISABLED};
    background-color: {BUTTON_BG};
}}

QPushButton#primary:enabled {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
}}

QPushButton#primary:enabled:hover {{
    background-color: {ACCENT};
    border: {BORDER_WIDTH_PX}px solid {TEXT};
}}

QPushButton#primary:enabled:focus {{
    border: {BORDER_WIDTH_PX}px solid {TEXT};
}}

QCheckBox {{
    spacing: 8px;
}}

QCheckBox:enabled:focus {{
    border: {BORDER_WIDTH_PX}px solid {ACCENT};
}}

QProgressBar {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
}}

QLabel#title {{
    font-size: 18px;
    font-weight: bold;
}}

QLabel#subtitle {{
    color: {TEXT_DISABLED};
}}
"""
