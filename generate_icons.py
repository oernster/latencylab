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

from PIL import Image, ImageDraw

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

# macOS composites the Dock, Finder and disk-image icons straight onto the
# desktop, so a transparent canvas leaves the mark reading as red and yellow
# floating on whatever is behind it: on the default light appearance, a pale
# grey. The macOS assets are therefore drawn on an opaque black tile.
# Windows and the Flatpak hicolor set keep the transparent originals, because
# both composite against a surface the icon is not supposed to occlude.
MAC_PNG_STEM = f"{PNG_STEM}_mac"
MAC_CANONICAL_PNG_NAME = f"{MAC_PNG_STEM}.png"
MAC_BACKGROUND_RGBA = (0, 0, 0, 255)

# Apple's macOS app icon grid. The artwork is not the full canvas: it is a
# rounded square occupying 824 of a 1024 point canvas, with a corner radius of
# 185.4 points. A full-bleed square icon renders visibly larger than every
# system app beside it in the Dock, and with hard corners. Expressed as
# fractions so they hold at any rendered size.
MAC_TILE_FRACTION = 824 / 1024
MAC_TILE_RADIUS_FRACTION = 185.4 / 824

# How much of the tile the mark itself occupies, leaving the interior margin
# system icons keep between their glyph and the tile edge.
MAC_MARK_FRACTION = 0.74

# The rounded corners are drawn at this multiple of the target size and scaled
# back down, because Pillow's rounded_rectangle has no antialiasing of its own
# and an aliased corner is obvious against the desktop.
MAC_MASK_SUPERSAMPLE = 4

# Only the sizes macOS actually consumes, rather than the full hicolor ladder:
# the largest is the source for the .icns and for the disk image icon, and the
# canonical one is what the running application hands to setWindowIcon.
MAC_PNG_SIZES = (ICNS_SIZE,)

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


def rounded_mask(side: int, radius: float) -> Image.Image:
    """An antialiased single-channel mask of a rounded square of `side` pixels."""

    scale = MAC_MASK_SUPERSAMPLE
    large = Image.new("L", (side * scale, side * scale), 0)
    ImageDraw.Draw(large).rounded_rectangle(
        (0, 0, side * scale - 1, side * scale - 1),
        radius=radius * scale,
        fill=255,
    )
    return large.resize((side, side), RESAMPLE)


def fit_mark(master: Image.Image, box: int) -> Image.Image:
    """The mark, trimmed of its transparent margin and scaled to fit `box`."""

    bounds = master.getbbox()
    mark = master.crop(bounds) if bounds is not None else master
    width, height = mark.size
    longest = max(width, height)
    return mark.resize(
        (max(1, round(width * box / longest)), max(1, round(height * box / longest))),
        RESAMPLE,
    )


def mac_icon(master: Image.Image, size: int) -> Image.Image:
    """The macOS rendering: the mark centred on an opaque rounded tile.

    The tile is inset within a transparent canvas to Apple's proportions, so the
    icon sits at the same visual size as the system applications beside it.
    """

    tile_side = round(size * MAC_TILE_FRACTION)
    tile = Image.new("RGBA", (tile_side, tile_side), MAC_BACKGROUND_RGBA)

    mark = fit_mark(master, round(tile_side * MAC_MARK_FRACTION))
    tile.alpha_composite(
        mark,
        ((tile_side - mark.width) // 2, (tile_side - mark.height) // 2),
    )
    tile.putalpha(rounded_mask(tile_side, tile_side * MAC_TILE_RADIUS_FRACTION))

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inset = (size - tile_side) // 2
    canvas.paste(tile, (inset, inset))
    return canvas


def write_mac_pngs(master: Image.Image, assets_dir: Path) -> list[Path]:
    """The macOS PNGs: the .icns/disk-image source and the Dock icon."""

    written: list[Path] = []
    for size in MAC_PNG_SIZES:
        path = assets_dir / f"{MAC_PNG_STEM}_{size}.png"
        mac_icon(master, size).save(path, format="PNG")
        written.append(path)

    canonical = assets_dir / MAC_CANONICAL_PNG_NAME
    mac_icon(master, CANONICAL_PNG_SIZE).save(canonical, format="PNG")
    written.append(canonical)
    return written


def write_icns(master: Image.Image, assets_dir: Path) -> Path:
    path = assets_dir / ICNS_NAME
    mac_icon(master, ICNS_SIZE).save(path, format="ICNS")
    return path


def main() -> int:
    if not MASTER_PNG.is_file():
        sys.stderr.write(f"Master icon not found: {MASTER_PNG}\n")
        return 1

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    master = load_master()

    written = write_pngs(master, ASSETS_DIR)
    written.extend(write_mac_pngs(master, ASSETS_DIR))
    written.append(write_ico(master, ASSETS_DIR))
    written.append(write_icns(master, ASSETS_DIR))

    for path in written:
        print(f"wrote {path.relative_to(PROJECT_ROOT)}")
    print(f"{len(written)} files written to {ASSETS_DIR.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
