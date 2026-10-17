#!/usr/bin/env bash
# Build dist/PrintLayout-<version>-x86_64.AppImage.
#
# The AppImage contains uv's portable Python (python-build-standalone) and the PySide6 wheels
# with their own Qt; nothing is copied from the build machine's system. It runs on distros with
# glibc 2.34 or newer (Ubuntu 22.04+, Debian 12+, Fedora 35+, current Arch, ...), the minimum
# of the PySide6 wheels.
set -euo pipefail

APP_ID=io.github.VojtechKlos.PrintLayout
PYTHON_VERSION=3.12
APPIMAGETOOL_VERSION=1.9.1
APPIMAGETOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/packaging/appimage"
DATA="$ROOT/data"
BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/AppDir"
APPIMAGETOOL="$BUILD/tools/appimagetool-$APPIMAGETOOL_VERSION-x86_64.AppImage"

cd "$ROOT"
VERSION="$(uv version --short)"
OUTPUT="$ROOT/dist/PrintLayout-$VERSION-x86_64.AppImage"

echo "==> Preparing AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr" "$(dirname "$APPIMAGETOOL")" "$ROOT/dist"

echo "==> Bundling Python $PYTHON_VERSION"
uv python install "$PYTHON_VERSION"
PYTHON_BIN="$(cd / && uv python find --managed-python "$PYTHON_VERSION")"
cp -a "$(dirname "$(dirname "$(readlink -f "$PYTHON_BIN")")")" "$APPDIR/usr/python"
PY="$APPDIR/usr/python/bin/python3"

echo "==> Installing PrintLayout and its locked dependencies"
uv export --frozen --no-dev --no-emit-project --format requirements.txt --output-file "$BUILD/requirements.txt" >/dev/null
INSTALL=(uv pip install --python "$PY" --break-system-packages --no-cache --link-mode copy --compile-bytecode)
"${INSTALL[@]}" --requirements "$BUILD/requirements.txt"
"${INSTALL[@]}" --no-deps "$ROOT"
uv pip uninstall --python "$PY" --break-system-packages pip >/dev/null 2>&1 || true

echo "==> Removing unused parts of Python and Qt"
du -sh "$APPDIR"
"$PY" -I "$HERE/prune.py" "$APPDIR/usr/python"
du -sh "$APPDIR"

echo "==> Adding launcher, desktop entry, icon and metadata"
install -m 755 "$HERE/AppRun" "$APPDIR/AppRun"
install -m 644 "$DATA/$APP_ID.desktop" "$APPDIR/$APP_ID.desktop"
install -D -m 644 "$DATA/$APP_ID.desktop" "$APPDIR/usr/share/applications/$APP_ID.desktop"
install -D -m 644 "$DATA/$APP_ID.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -D -m 644 "$DATA/$APP_ID.metainfo.xml" "$APPDIR/usr/share/metainfo/$APP_ID.appdata.xml"
QT_QPA_PLATFORM=offscreen "$PY" -I -c '
import sys
from PySide6.QtGui import QGuiApplication, QIcon
app = QGuiApplication([])
assert QIcon(sys.argv[1]).pixmap(256, 256).save(sys.argv[2])
' "$DATA/$APP_ID.svg" "$APPDIR/$APP_ID.png"
ln -sf "$APP_ID.png" "$APPDIR/.DirIcon"

echo "==> Checking the bundle"
"$PY" -I "$HERE/check_bundle.py"

echo "==> Packing AppImage"
if ! echo "$APPIMAGETOOL_SHA256  $APPIMAGETOOL" | sha256sum --check --status 2>/dev/null; then
    curl --fail --location --silent --show-error --output "$APPIMAGETOOL.part" \
        "https://github.com/AppImage/appimagetool/releases/download/$APPIMAGETOOL_VERSION/appimagetool-x86_64.AppImage"
    echo "$APPIMAGETOOL_SHA256  $APPIMAGETOOL.part" | sha256sum --check --quiet
    chmod +x "$APPIMAGETOOL.part"
    mv "$APPIMAGETOOL.part" "$APPIMAGETOOL"
fi
# Extract-and-run: works without FUSE (containers, CI). Pack to a temporary file and rename it,
# so the build also works while the previous AppImage is still running.
rm -f "$OUTPUT.part"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --no-appstream "$APPDIR" "$OUTPUT.part"
mv -f "$OUTPUT.part" "$OUTPUT"

echo "==> Done: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
