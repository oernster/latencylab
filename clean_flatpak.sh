#!/usr/bin/env bash
# Remove the Flatpak build artefacts: those alone.
#
# The Windows and macOS outputs live in dist-installer/ and dist/ and are never
# touched here, so the three delivery paths stay independent of each other.
#
# This is a build script. It is exempt from the size cap and the coverage gate.

set -euo pipefail

# Must match build_flatpak.sh.
APP_ID="uk.codecrafter.LatencyLab"
BUNDLE="latencylab.flatpak"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_ROOT}"

echo "Uninstalling ${APP_ID} if it is installed"
if flatpak list --user 2>/dev/null | grep -q "${APP_ID}"; then
    flatpak uninstall --user -y "${APP_ID}"
else
    echo "  Not installed, skipping."
fi

echo "Removing build artefacts"
rm -f "${BUNDLE}" "${APP_ID}.yml"
rm -rf .flatpak-build .flatpak-repo .flatpak-builder .flatpak-wheels packaging

echo "Done. dist-installer/ and dist/ were not touched."
