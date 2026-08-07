#!/usr/bin/env bash
# Build a LatencyLab Flatpak bundle, then install it.
#
# The manifest, launcher, desktop entry, metainfo and prune script are generated
# here rather than committed, so there is one place where the app's identity is
# written and no second copy to fall out of step with it.
#
# Dependencies are installed offline from wheels downloaded on the host first,
# which is why the sandbox never needs network access at build time and the
# finished application never asks for it at all.
#
# Usage: ./build_flatpak.sh [--user | --system] [--no-install]
#
#   --user        install the finished bundle for this user only (the default)
#   --system      install it for every user on the machine (needs root)
#   --no-install  build and bundle only, install nothing
#
# This is a build script. It is exempt from the size cap and the coverage gate.

set -euo pipefail

APP_ID="uk.codecrafter.LatencyLab"
APP_NAME="LatencyLab"
APP_COMMAND="latencylab"
APP_SUMMARY="Design-time latency exploration for event-driven systems"

RUNTIME="org.freedesktop.Platform"
SDK="org.freedesktop.Sdk"
RUNTIME_VERSION="25.08"
# Must match the runtime: freedesktop 25.08 ships Python 3.13.
PYTHON_DIR="python3.13"
PYTHON_VERSION="3.13"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${PROJECT_ROOT}/.flatpak-build"
REPO_DIR="${PROJECT_ROOT}/.flatpak-repo"
WHEELS_DIR="${PROJECT_ROOT}/.flatpak-wheels"
PACKAGING_DIR="${PROJECT_ROOT}/packaging"
MANIFEST="${PROJECT_ROOT}/${APP_ID}.yml"
BUNDLE="${PROJECT_ROOT}/latencylab.flatpak"
PRUNE_SCRIPT="prune_flatpak_tree.py"

# Pinned by hash, and fetched by flatpak-builder on the host rather than inside
# the sandbox, so the build stays as offline as the wheels above make it.
# 1.22 or newer: earlier releases still carry pre-C23 declarations that the
# SDK's compiler rejects outright.
KRB5_URL="https://kerberos.org/dist/krb5/1.22/krb5-1.22.1.tar.gz"
KRB5_SHA256="1a8832b8cad923ebbf1394f67e2efcf41e3a49f460285a66e35adec8fa0053af"

ICON_SIZES=(16 24 32 48 64 96 128 256 512)

# Where the finished bundle is installed, and whether it is installed at all.
INSTALL_SCOPE="user"
INSTALL_BUNDLE=1

usage() {
    cat <<USAGE
Usage: $(basename "${BASH_SOURCE[0]}") [--user | --system] [--no-install]

  --user        install the finished bundle for this user only (the default)
  --system      install it for every user on the machine (needs root)
  --no-install  build and bundle only, install nothing
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --user) INSTALL_SCOPE="user" ;;
        --system) INSTALL_SCOPE="system" ;;
        --no-install) INSTALL_BUNDLE=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# A system installation writes outside the user's home, so it needs root; a user
# one never does. Everything downstream goes through this one decision.
as_scope_root() {
    if [ "${INSTALL_SCOPE}" = "system" ]; then
        sudo "$@"
    else
        "$@"
    fi
}

section() {
    printf '\n%s\n' "$(tput bold 2>/dev/null || true)=== $1 ===$(tput sgr0 2>/dev/null || true)"
}

install_if_missing() {
    local command_name="$1" package="$2"
    if command -v "${command_name}" >/dev/null 2>&1; then
        return
    fi
    echo "${command_name} is missing; installing ${package}"
    if command -v apt >/dev/null 2>&1; then sudo apt install -y "${package}"
    elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y "${package}"
    elif command -v pacman >/dev/null 2>&1; then sudo pacman -S --noconfirm "${package}"
    elif command -v zypper >/dev/null 2>&1; then sudo zypper install -y "${package}"
    else
        echo "No supported package manager found. Install ${package} yourself." >&2
        exit 1
    fi
}

section "Checking the toolchain"
install_if_missing flatpak flatpak
install_if_missing flatpak-builder flatpak-builder

# The build always reads the SDK from the user installation, which needs no root.
flatpak remote-add --if-not-exists --user flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user --noninteractive flathub \
    "${RUNTIME}//${RUNTIME_VERSION}" "${SDK}//${RUNTIME_VERSION}"

# A system-wide app has to find its runtime system-wide too, or it only runs for
# whoever built it.
if [ "${INSTALL_SCOPE}" = "system" ] && [ "${INSTALL_BUNDLE}" -eq 1 ]; then
    as_scope_root flatpak remote-add --if-not-exists --system flathub \
        https://dl.flathub.org/repo/flathub.flatpakrepo
    as_scope_root flatpak install --system --noninteractive flathub \
        "${RUNTIME}//${RUNTIME_VERSION}"
fi

section "Checking the icons"
if [ ! -f "${PROJECT_ROOT}/assets/latencylab_icon_256.png" ]; then
    echo "assets/ is missing its generated icons. Run: python generate_icons.py" >&2
    exit 1
fi

section "Downloading wheels on the host"
rm -rf "${WHEELS_DIR}"
mkdir -p "${WHEELS_DIR}"
pip download --only-binary :all: \
    --python-version "${PYTHON_VERSION}" --implementation cp \
    --platform manylinux_2_34_x86_64 \
    -d "${WHEELS_DIR}" -r "${PROJECT_ROOT}/requirements.txt"

section "Writing the packaging files"
rm -rf "${PACKAGING_DIR}"
mkdir -p "${PACKAGING_DIR}"

cat > "${PACKAGING_DIR}/${APP_COMMAND}" <<'LAUNCHER'
#!/bin/sh
PYTHON_DIR_PLACEHOLDER
export PYTHONPATH="/app/lib/${PYTHON_DIR}/site-packages:/app/share/latencylab${PYTHONPATH:+:$PYTHONPATH}"
export QT_PLUGIN_PATH="/app/lib/${PYTHON_DIR}/site-packages/PySide6/Qt/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="/app/lib/${PYTHON_DIR}/site-packages/PySide6/Qt/plugins/platforms"
export QML2_IMPORT_PATH="/app/lib/${PYTHON_DIR}/site-packages/PySide6/Qt/qml"
export LATENCYLAB_ASSETS_DIR="/app/assets"
export LATENCYLAB_EXAMPLES_DIR="/app/examples"

if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$FORCE_X11" ]; then
    export QT_QPA_PLATFORM=wayland
else
    export QT_QPA_PLATFORM=xcb
fi

exec python3 /app/share/latencylab/runner.py "$@"
LAUNCHER

# The launcher is written literally so $VAR survives; only the runtime's Python
# directory is substituted; it has to match the runtime exactly.
sed -i "s|PYTHON_DIR_PLACEHOLDER|PYTHON_DIR=\"${PYTHON_DIR}\"|" \
    "${PACKAGING_DIR}/${APP_COMMAND}"
chmod 755 "${PACKAGING_DIR}/${APP_COMMAND}"

cat > "${PACKAGING_DIR}/${APP_ID}.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Comment=${APP_SUMMARY}
Exec=${APP_COMMAND}
Icon=${APP_ID}
Terminal=false
Categories=Development;Science;
DESKTOP

cat > "${PACKAGING_DIR}/${APP_ID}.metainfo.xml" <<METAINFO
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <name>${APP_NAME}</name>
  <summary>${APP_SUMMARY}</summary>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-only</project_license>
  <developer id="uk.codecrafter">
    <name>Oliver Ernster</name>
  </developer>
  <description>
    <p>
      LatencyLab is a deterministic, seeded latency simulator for event-driven
      systems. It models tasks, events, queues, delays and resource contention,
      and prices the cost of a structure before that structure hardens.
    </p>
  </description>
  <launchable type="desktop-id">${APP_ID}.desktop</launchable>
  <content_rating type="oars-1.1"/>
</component>
METAINFO

cat > "${PACKAGING_DIR}/${PRUNE_SCRIPT}" <<'PRUNE'
#!/usr/bin/env python3
"""Delete what /app carries but never runs.

The Qt wheels are built for every Qt user at once, so most of what they install
is dead weight here: LatencyLab imports QtCore, QtGui, QtWidgets, QtSvg and
QtNetwork, and nothing else. What each part of PySide6 belongs to is read from
the wheels' own install records rather than named here, so a Qt upgrade cannot
leave this list stale.

Run last, once the application itself is staged, so it sweeps that tree too.

This is a build script. It is exempt from the size cap and the coverage gate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# pip names an installed wheel's metadata directory after the distribution, so
# these are prefixes to glob for, not paths.
ADDONS_DIST_PREFIX = "pyside6_addons-"
ESSENTIALS_DIST_PREFIX = "pyside6_essentials-"

# Tooling that builds Qt applications rather than running them. `metatypes` and
# `libexec` feed the QML and resource compilers; `include`, `glue`, `doc` and
# `typesystems` exist for people binding their own C++ to Python.
BUILD_ONLY_PYSIDE_DIRS = ("Qt/metatypes", "Qt/libexec", "include", "glue", "doc", "typesystems")

BYTECODE_DIR = "__pycache__"
BYTECODE_SUFFIX = ".pyc"
STUB_SUFFIX = ".pyi"

QT_LIBRARY_PREFIX = "libQt6"
MISSING_LIBRARY_MARKER = "not found"


def _record_paths(dist_info: Path) -> set[str]:
    """Every path a wheel installed, as written in its own RECORD."""

    record = dist_info / "RECORD"
    if not record.is_file():
        return set()
    paths = set()
    for line in record.read_text(encoding="utf-8").splitlines():
        path = line.split(",", 1)[0].strip()
        if path:
            paths.add(path)
    return paths


def _remove(path: Path) -> int:
    """Delete a file or tree, reporting the bytes it occupied."""

    if path.is_symlink() or path.is_file():
        size = path.lstat().st_size
        path.unlink()
        return size
    if path.is_dir():
        size = sum(item.lstat().st_size for item in path.rglob("*") if not item.is_dir())
        shutil.rmtree(path)
        return size
    return 0


def _drop_empty_dirs(root: Path) -> None:
    """Remove directories left behind with nothing in them."""

    if not root.is_dir():
        return
    for directory in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def prune_addons(site_packages: Path) -> int:
    """Drop PySide6-Addons: WebEngine, Multimedia, Charts, Quick3D and the rest.

    Both Qt wheels ship a few of the same files, so only what Addons alone
    installed may go; deleting the shared ones would break the package that
    stays.
    """

    addons = next(site_packages.glob(f"{ADDONS_DIST_PREFIX}*.dist-info"), None)
    if addons is None:
        return 0
    essentials = next(site_packages.glob(f"{ESSENTIALS_DIST_PREFIX}*.dist-info"), None)
    shared = _record_paths(essentials) if essentials is not None else set()

    freed = 0
    for relative in sorted(_record_paths(addons) - shared):
        target = site_packages / relative
        if addons == target or addons in target.parents:
            continue
        freed += _remove(target)
    freed += _remove(addons)
    _drop_empty_dirs(site_packages / "PySide6")
    return freed


def prune_build_only(site_packages: Path) -> int:
    """Drop the Qt developer tooling that came along with the runtime."""

    pyside = site_packages / "PySide6"
    if not pyside.is_dir():
        return 0

    freed = 0
    for relative in BUILD_ONLY_PYSIDE_DIRS:
        freed += _remove(pyside / relative)

    # designer, linguist, lupdate, qmlls and friends: extensionless executables
    # sitting beside the modules, none of which the running app ever invokes.
    for entry in pyside.iterdir():
        if entry.is_file() and not entry.suffix:
            freed += _remove(entry)
    return freed


def prune_orphaned_plugins(site_packages: Path) -> int:
    """Drop the Qt plugins whose libraries went with the Addons wheel.

    The PDF image reader and the WebEngine designer widget, among others, are
    left dangling once their Qt libraries go. Qt would quietly skip them, but a
    plugin that cannot load is exactly the dead weight this script exists to
    remove. Plugins missing a non-Qt system library (a database client, say) are
    left alone: they arrived that way and nothing here made them so.
    """

    plugins = site_packages / "PySide6" / "Qt" / "plugins"
    if not plugins.is_dir():
        return 0
    environment = dict(os.environ, LD_LIBRARY_PATH=str(site_packages / "PySide6" / "Qt" / "lib"))

    freed = 0
    for plugin in sorted(plugins.rglob("*.so")):
        result = subprocess.run(
            ["ldd", str(plugin)], capture_output=True, text=True, env=environment
        )
        missing = [line for line in result.stdout.splitlines() if MISSING_LIBRARY_MARKER in line]
        if any(QT_LIBRARY_PREFIX in line for line in missing):
            freed += _remove(plugin)
    _drop_empty_dirs(plugins)
    return freed


def prune_type_stubs(site_packages: Path) -> int:
    """Drop the .pyi stubs, which serve type checkers, not the interpreter."""

    return sum(_remove(stub) for stub in sorted(site_packages.rglob(f"*{STUB_SUFFIX}")))


def prune_bytecode(*roots: Path) -> int:
    """Drop compiled bytecode, which the first run regenerates as it needs."""

    freed = 0
    for root in roots:
        if not root.is_dir():
            continue
        for cache in sorted(root.rglob(BYTECODE_DIR), reverse=True):
            freed += _remove(cache)
        for compiled in sorted(root.rglob(f"*{BYTECODE_SUFFIX}")):
            freed += _remove(compiled)
    return freed


def prune_foreign_entry_points(bin_dir: Path, app_command: str) -> int:
    """Drop every console script but the app's own launcher.

    Installing PySide6 puts pyside6-designer, pyside6-rcc and a dozen more into
    /app/bin, where they would be exported as if they were part of this app.
    """

    if not bin_dir.is_dir():
        return 0
    return sum(
        _remove(entry) for entry in sorted(bin_dir.iterdir()) if entry.name != app_command
    )


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(f"usage: {Path(argv[0]).name} <app-prefix> <python-dir> <app-command>", file=sys.stderr)
        return 2

    prefix, python_dir, app_command = Path(argv[1]), argv[2], argv[3]
    site_packages = prefix / "lib" / python_dir / "site-packages"
    app_tree = prefix / "share" / "latencylab"

    freed = prune_addons(site_packages)
    freed += prune_build_only(site_packages)
    freed += prune_orphaned_plugins(site_packages)
    freed += prune_type_stubs(site_packages)
    freed += prune_foreign_entry_points(prefix / "bin", app_command)
    freed += prune_bytecode(site_packages, app_tree)

    print(f"Pruned {freed / (1 << 20):.1f} MiB of unused build output from {prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
PRUNE
chmod 755 "${PACKAGING_DIR}/${PRUNE_SCRIPT}"

section "Writing the manifest"
{
cat <<MANIFEST_HEAD
app-id: ${APP_ID}
runtime: ${RUNTIME}
runtime-version: "${RUNTIME_VERSION}"
sdk: ${SDK}
command: ${APP_COMMAND}

build-options:
  strip: true
  no-debuginfo: true

# Nothing here is read at runtime: pip's caches and the .la/.a files a build
# leaves behind would otherwise be exported into the finished application.
cleanup:
  - /include
  - /lib/pkgconfig
  - /man
  - /share/man
  - /share/doc
  - "*.la"
  - "*.a"

finish-args:
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri
  # Models are opened and saved from the user's own files. No --share=network:
  # LatencyLab simulates locally and talks to nothing.
  - --filesystem=home

modules:
  # PySide6's libQt6Network is linked against libgssapi_krb5.so.2, which the
  # freedesktop runtime does not ship, so importing QtNetwork (the single
  # instance guard does) fails at load time and the application never starts.
  # Kerberos itself is never used: only the library has to be present.
  - name: krb5
    subdir: src
    config-opts:
      - --prefix=/app
      - --localstatedir=/var/lib
      - --sbindir=/app/bin
      - --disable-rpath
      - --disable-static
      - --without-ldap
      - --without-keyutils
    sources:
      - type: archive
        url: ${KRB5_URL}
        sha256: ${KRB5_SHA256}

  - name: python-deps
    buildsystem: simple
    build-commands:
      - python3 -m ensurepip --upgrade
      - pip3 install --no-cache-dir --no-index --find-links wheels --prefix=/app -r requirements.txt
    sources:
      - type: dir
        path: .flatpak-wheels
        dest: wheels
      - type: file
        path: requirements.txt

  - name: latencylab
    buildsystem: simple
    build-commands:
      - install -d /app/share/latencylab
      - cp -r latencylab latencylab_ui runner.py VERSION LICENSE /app/share/latencylab/
      # Only the PNGs: the .ico and .icns are for the Windows and macOS builds.
      - install -Dm644 -t /app/assets assets/*.png
      # The shipped models, so a fresh install has something to open.
      - install -Dm644 -t /app/examples examples/*.json
      - install -Dm755 packaging/${APP_COMMAND} /app/bin/${APP_COMMAND}
      - install -Dm644 packaging/${APP_ID}.desktop /app/share/applications/${APP_ID}.desktop
      - install -Dm644 packaging/${APP_ID}.metainfo.xml /app/share/metainfo/${APP_ID}.metainfo.xml
MANIFEST_HEAD

for size in "${ICON_SIZES[@]}"; do
    printf '      - install -Dm644 assets/latencylab_icon_%s.png /app/share/icons/hicolor/%sx%s/apps/%s.png\n' \
        "${size}" "${size}" "${size}" "${APP_ID}"
done

# Last, so it sweeps the staged application as well as the installed wheels.
printf '      - python3 packaging/%s /app %s %s\n' \
    "${PRUNE_SCRIPT}" "${PYTHON_DIR}" "${APP_COMMAND}"

# Only what the build commands above actually read. Naming the sources rather
# than the whole directory keeps venv/, .git/, tests/ and the other delivery
# paths' output out of the sandbox entirely.
cat <<'MANIFEST_TAIL'
    sources:
      - type: dir
        path: latencylab
        dest: latencylab
      - type: dir
        path: latencylab_ui
        dest: latencylab_ui
      - type: dir
        path: assets
        dest: assets
      - type: dir
        path: examples
        dest: examples
      - type: dir
        path: packaging
        dest: packaging
      - type: file
        path: runner.py
      - type: file
        path: VERSION
      - type: file
        path: LICENSE
MANIFEST_TAIL
} > "${MANIFEST}"

section "Building"
rm -rf "${BUILD_DIR}" "${REPO_DIR}"
flatpak-builder --user --install-deps-from=flathub --force-clean \
    --repo="${REPO_DIR}" "${BUILD_DIR}" "${MANIFEST}"

section "Bundling"
rm -f "${BUNDLE}"
flatpak build-bundle \
    --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
    "${REPO_DIR}" "${BUNDLE}" "${APP_ID}"

if [ "${INSTALL_BUNDLE}" -eq 1 ]; then
    section "Installing (${INSTALL_SCOPE})"
    as_scope_root flatpak install "--${INSTALL_SCOPE}" -y --reinstall "${BUNDLE}"
fi

section "Done"
echo "Built ${BUNDLE} ($(du -h "${BUNDLE}" | cut -f1))"
if [ "${INSTALL_BUNDLE}" -eq 1 ]; then
    echo "Installed for: ${INSTALL_SCOPE}"
else
    echo "Install it with: flatpak install --${INSTALL_SCOPE} ${BUNDLE}"
fi
echo "Run it with:     flatpak run ${APP_ID}"
