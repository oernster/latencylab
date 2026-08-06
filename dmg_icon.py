"""Icon helpers for the macOS DMG build.

Two jobs: turn the generated master PNG into an `.icns`, then give the disk
image file its own Finder icon. Both are macOS-only and both are optional in
the sense that the DMG is still valid without them.

The volume icon (what you see once the image is mounted) is not handled here:
create-dmg's own `--volicon` does that correctly, and the hand-rolled
read-write round trip this module used to do set the icon file but never got
the custom-icon bit to survive the conversion back to a compressed image.

This is a build script. It is exempt from the size cap and from the coverage
gate.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# The iconset sizes macOS expects, each with its @2x retina partner.
ICONSET_SIZES = (16, 32, 128, 256, 512)
RETINA_SCALE = 2

# The Finder attribute letter for "this file has a custom icon".
CUSTOM_ICON_FLAG = "C"

# The resource type an .icns occupies in a resource fork.
ICON_RESOURCE_TYPE = "icns"


def png_to_icns(png: Path, icns: Path, work_dir: Path) -> Path:
    """Build an .icns from a large square PNG using iconutil.

    generate_icons.py already writes an .icns via Pillow, which is enough for
    the application bundle. This exists for the volume icon, where macOS is
    fussier about the iconset actually containing every size.
    """

    iconset = work_dir / f"{icns.stem}.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    for size in ICONSET_SIZES:
        _sips(png, iconset / f"icon_{size}x{size}.png", size)
        _sips(
            png,
            iconset / f"icon_{size}x{size}@2x.png",
            size * RETINA_SCALE,
        )

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
        check=True,
    )
    return icns


def _sips(source: Path, destination: Path, size: int) -> None:
    subprocess.run(
        [
            "sips",
            "-z",
            str(size),
            str(size),
            str(source),
            "--out",
            str(destination),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def set_file_icon(target: Path, icns: Path, work_dir: Path) -> None:
    """Give a file its own Finder icon, the way Finder actually reads one.

    A volume icon only appears once the image is mounted. The icon someone
    sees on the DMG sitting in their Downloads folder belongs to the file, and
    that means an icon resource in the file's resource fork plus the
    custom-icon bit in its Finder info.

    A failure here costs the DMG its Finder icon and nothing else, so the
    caller is expected to treat it as non-fatal.
    """

    # sips -i writes the icon into the .icns file's own resource fork, which is
    # then the thing DeRez can read back out as a resource description. Work on
    # a copy so the source icon in assets/ is left alone.
    staged_icns = work_dir / f"{target.stem}-icon.icns"
    shutil.copyfile(icns, staged_icns)
    subprocess.run(
        ["sips", "-i", str(staged_icns)], check=True, stdout=subprocess.DEVNULL
    )

    # Kept as bytes: a resource description carries raw high bytes in its
    # $"..." literals and is not UTF-8, so decoding it fails outright.
    description = subprocess.run(
        ["DeRez", "-only", ICON_RESOURCE_TYPE, str(staged_icns)],
        check=True,
        capture_output=True,
    ).stdout
    resource_file = work_dir / f"{target.stem}-icon.rsrc"
    resource_file.write_bytes(description)

    subprocess.run(
        ["Rez", "-append", str(resource_file), "-o", str(target)], check=True
    )
    subprocess.run(["SetFile", "-a", CUSTOM_ICON_FLAG, str(target)], check=True)
