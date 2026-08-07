"""Derive every platform icon asset from the single master PNG.

The master is `latencylab.png` at the repository root: a square 1024x1024 RGBA
render of the stopwatch mark the site uses. Everything under `assets/`
is generated from it and nothing else, so the Windows executable, the installer
window, the macOS bundle and the Flatpak hicolor set cannot drift apart.

Run it after changing the master:

    python generate_icons.py

Pillow is the only dependency and it is already a dev dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
MASTER_PNG = PROJECT_ROOT / "latencylab.png"
ASSETS_DIR = PROJECT_ROOT / "assets"

# Loose PNGs: the Flatpak hicolor set (16 to 512), the installer badge and the
# crisp source the macOS icns is built from.
PNG_SIZES = (16, 24, 32, 48, 64, 96, 128, 256, 512, 1024)

# Frames inside the multi-size Windows .ico. Each is rendered from the master
# rather than handed to Pillow as a `sizes` list: given a base image plus sizes,
# Pillow derives the smaller frames itself and the 16 and 24 pixel results are
# visibly worse, which are exactly the sizes the taskbar and Explorer use.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

# The one PNG other code reaches for when it just wants "the icon".
CANONICAL_PNG_SIZE = 256

# macOS wants the largest square available as its source.
ICNS_SIZE = 1024

PNG_STEM = "latencylab_icon"
ICO_NAME = "latencylab.ico"
ICNS_NAME = "latencylab.icns"
CANONICAL_PNG_NAME = f"{PNG_STEM}.png"

RESAMPLE = Image.Resampling.LANCZOS


def load_master(master: Path = MASTER_PNG) -> Image.Image:
    """Return the master as a square RGBA image.

    A non-square master is centre-cropped rather than stretched, because every
    downstream format assumes square and a squashed glyph is worse than a
    trimmed one.
    """

    image = Image.open(master).convert("RGBA")
    width, height = image.size
    if width != height:
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
    return image


def _scaled(master: Image.Image, size: int) -> Image.Image:
    return master.resize((size, size), RESAMPLE)


def write_pngs(master: Image.Image, assets_dir: Path) -> list[Path]:
    written: list[Path] = []
    for size in PNG_SIZES:
        path = assets_dir / f"{PNG_STEM}_{size}.png"
        _scaled(master, size).save(path, format="PNG")
        written.append(path)

    canonical = assets_dir / CANONICAL_PNG_NAME
    _scaled(master, CANONICAL_PNG_SIZE).save(canonical, format="PNG")
    written.append(canonical)
    return written


def write_ico(master: Image.Image, assets_dir: Path) -> Path:
    """Write a genuine multi-frame .ico, every frame rendered from the master."""

    frames = [_scaled(master, size) for size in sorted(ICO_SIZES)]
    largest = frames[-1]
    path = assets_dir / ICO_NAME
    largest.save(
        path,
        format="ICO",
        sizes=[(size, size) for size in sorted(ICO_SIZES)],
        append_images=frames[:-1],
    )
    return path


def write_icns(master: Image.Image, assets_dir: Path) -> Path:
    path = assets_dir / ICNS_NAME
    _scaled(master, ICNS_SIZE).save(path, format="ICNS")
    return path


def main() -> int:
    if not MASTER_PNG.is_file():
        sys.stderr.write(f"Master icon not found: {MASTER_PNG}\n")
        return 1

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    master = load_master()

    written = write_pngs(master, ASSETS_DIR)
    written.append(write_ico(master, ASSETS_DIR))
    written.append(write_icns(master, ASSETS_DIR))

    for path in written:
        print(f"wrote {path.relative_to(PROJECT_ROOT)}")
    print(f"{len(written)} files written to {ASSETS_DIR.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
