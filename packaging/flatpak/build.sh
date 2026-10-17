#!/usr/bin/env bash
# Build the Flatpak and export dist/PrintLayout-<version>.flatpak, a single-file bundle.
#
#   packaging/flatpak/build.sh            build the bundle
#   packaging/flatpak/build.sh --install  also install the app for the current user
#
# Only flatpak is needed: flatpak-builder, the KDE SDK/runtime and the PySide BaseApp are
# installed from Flathub for the current user on first use (about 2-3 GB).
set -euo pipefail

APP_ID=io.github.VojtechKlos.PrintLayout
FLATHUB=https://dl.flathub.org/repo/flathub.flatpakrepo

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/packaging/flatpak"
BUILD="$ROOT/build/flatpak"

cd "$ROOT"
VERSION="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
OUTPUT="$ROOT/dist/PrintLayout-$VERSION.flatpak"
INSTALL=()
if [[ "${1:-}" == --install ]]; then
    INSTALL=(--install)
fi

echo "==> Setting up Flathub and flatpak-builder (user installation)"
flatpak remote-add --user --if-not-exists flathub "$FLATHUB"
flatpak info --user org.flatpak.Builder >/dev/null 2>&1 ||
    flatpak install --user --noninteractive flathub org.flatpak.Builder

echo "==> Building $APP_ID"
flatpak run org.flatpak.Builder --user --install-deps-from=flathub --force-clean \
    --state-dir="$BUILD/state" --repo="$BUILD/repo" "${INSTALL[@]}" \
    "$BUILD/build-dir" "$HERE/$APP_ID.yml"

echo "==> Exporting bundle"
mkdir -p "$ROOT/dist"
flatpak build-bundle --runtime-repo="$FLATHUB" "$BUILD/repo" "$OUTPUT" "$APP_ID"

echo "==> Done: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
