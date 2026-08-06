"""Icon helpers for the macOS DMG build.

Two jobs: turn the generated master PNG into an `.icns`, then give the mounted
disk image a custom volume icon. Both are macOS-only and both are optional in
the sense that the DMG is still valid without the volume icon.

This is a build script. It is exempt from the size cap and from the coverage
gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# The iconset sizes macOS expects, each with its @2x retina partner.
ICONSET_SIZES = (16, 32, 128, 256, 512)
RETINA_SCALE = 2

VOLUME_ICON_NAME = ".VolumeIcon.icns"

# The Finder flag that says "this volume has a custom icon".
HAS_CUSTOM_ICON_ATTRIBUTE = "com.apple.FinderInfo"


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


def set_volume_icon(dmg: Path, icns: Path, work_dir: Path) -> None:
    """Attach the image read-write, drop the icon in, then detach.

    A failure here costs the DMG its custom Finder icon and nothing else, so
    the caller is expected to treat it as non-fatal.
    """

    rw_dmg = work_dir / f"{dmg.stem}-rw.dmg"
    subprocess.run(
        ["hdiutil", "convert", str(dmg), "-format", "UDRW", "-o", str(rw_dmg)],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    mount_point = work_dir / "mount"
    mount_point.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "hdiutil",
            "attach",
            str(rw_dmg),
            "-mountpoint",
            str(mount_point),
            "-nobrowse",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    try:
        subprocess.run(
            ["cp", str(icns), str(mount_point / VOLUME_ICON_NAME)], check=True
        )
        # Set the custom-icon bit. SetFile ships with Xcode; when it is absent
        # the icon simply does not appear, which is why this is tolerated.
        subprocess.run(["SetFile", "-a", "C", str(mount_point)], check=False)
    finally:
        subprocess.run(
            ["hdiutil", "detach", str(mount_point)],
            check=False,
            stdout=subprocess.DEVNULL,
        )

    dmg.unlink()
    subprocess.run(
        ["hdiutil", "convert", str(rw_dmg), "-format", "UDZO", "-o", str(dmg)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    rw_dmg.unlink()
