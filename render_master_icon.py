"""Re-render the master icon PNG from the published SVG.

The mark's origin is the SVG on the site and the repository-root PNG is a
raster of it, never an independent drawing. That direction was documented and
had no tool, which made it a step somebody had to remember: change the SVG,
then remember to re-render, then remember to regenerate the platform set. A
forgotten re-render leaves the site showing one mark and the application
another, and nothing fails to say so.

    python render_master_icon.py     ->  latencylab.png (1024x1024 RGBA)
    python generate_icons.py         ->  everything else, from that PNG

This is a build script. It is exempt from the size cap and the coverage gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

PROJECT_ROOT = Path(__file__).resolve().parent

# The published mark, which is the source of truth for the artwork.
SVG_SOURCE = PROJECT_ROOT / "docs" / "assets" / "latencylab.svg"

# The master every platform asset derives from, named after the project
# directory lowercased, as generate_icons.py expects.
PNG_MASTER = PROJECT_ROOT / "latencylab.png"

# Square and large enough to be the source for the whole generated set,
# including the macOS 1024 icon.
MASTER_PX = 1024


def render(svg_path: Path, png_path: Path, *, size: int = MASTER_PX) -> Path:
    """Rasterise `svg_path` to a transparent square PNG at `size`."""

    if not svg_path.is_file():
        raise SystemExit(f"No SVG to render at {svg_path}")

    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise SystemExit(f"{svg_path} is not a renderable SVG")

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    if not image.save(str(png_path)):
        raise SystemExit(f"Could not write {png_path}")
    return png_path


def main() -> int:
    # An offscreen surface is enough to rasterise, and asking for a real one on
    # a headless machine is how this would fail in CI.
    QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
    app = QGuiApplication(sys.argv)

    written = render(SVG_SOURCE, PNG_MASTER)
    print(f"[render_master_icon] {SVG_SOURCE.name} -> {written.name} ({MASTER_PX}px)")
    print("[render_master_icon] Now run: python generate_icons.py")

    del app
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
