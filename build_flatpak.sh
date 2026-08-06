#!/usr/bin/env bash
# Build a LatencyLab Flatpak bundle.
#
# The manifest, launcher, desktop entry and metainfo are generated here rather
# than committed, so there is one place where the app's identity is written and
# no second copy to fall out of step with it.
#
# Dependencies are installed offline from wheels downloaded on the host first,
# which is why the sandbox never needs network access at build time and the
# finished application never asks for it at all.
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

ICON_SIZES=(16 24 32 48 64 96 128 256 512)

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

flatpak remote-add --if-not-exists --user flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user --noninteractive flathub \
    "${RUNTIME}//${RUNTIME_VERSION}" "${SDK}//${RUNTIME_VERSION}"

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

finish-args:
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri
  # Models are opened and saved from the user's own files. No --share=network:
  # LatencyLab simulates locally and talks to nothing.
  - --filesystem=home

modules:
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
      - install -d /app/assets
      - cp -r assets/. /app/assets/
      - install -Dm755 packaging/${APP_COMMAND} /app/bin/${APP_COMMAND}
      - install -Dm644 packaging/${APP_ID}.desktop /app/share/applications/${APP_ID}.desktop
      - install -Dm644 packaging/${APP_ID}.metainfo.xml /app/share/metainfo/${APP_ID}.metainfo.xml
MANIFEST_HEAD

for size in "${ICON_SIZES[@]}"; do
    printf '      - install -Dm644 assets/latencylab_icon_%s.png /app/share/icons/hicolor/%sx%s/apps/%s.png\n' \
        "${size}" "${size}" "${size}" "${APP_ID}"
done

cat <<'MANIFEST_TAIL'
    sources:
      - type: dir
        path: .
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

section "Done"
echo "Built ${BUNDLE}"
echo "Install it with: flatpak install --user ${BUNDLE}"
echo "Run it with:     flatpak run ${APP_ID}"
