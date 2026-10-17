#!/usr/bin/env bash
# Publish a GitHub release of the current version with the AppImage and Flatpak attached.
#
# Before running: bump `version` in pyproject.toml, add a matching <release> entry to
# data/io.github.VojtechKlos.PrintLayout.metainfo.xml and commit. The script then checks the
# tree, runs the tests, builds both packages, tags v<version>, pushes the branch and the tag,
# and creates the release. Needs gh logged in to GitHub (gh auth login).
set -euo pipefail

APP_ID=io.github.VojtechKlos.PrintLayout
REPO=VojtechKlos/print-layout

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VERSION="$(uv version --short)"
TAG="v$VERSION"
APPIMAGE="dist/PrintLayout-$VERSION-x86_64.AppImage"
FLATPAK="dist/PrintLayout-$VERSION.flatpak"
OUT="build/release"

fail() {
    echo "error: $*" >&2
    exit 1
}

echo "==> Checking release $TAG"
command -v gh >/dev/null || fail "gh is not installed (sudo pacman -S github-cli)"
gh auth status --hostname github.com >/dev/null 2>&1 || fail "gh is not logged in (gh auth login)"
[[ -z "$(git status --porcelain)" ]] || fail "commit or stash your changes first"
! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null || fail "tag $TAG already exists"
grep -q "<release version=\"$VERSION\"" "data/$APP_ID.metainfo.xml" ||
    fail "data/$APP_ID.metainfo.xml has no <release version=\"$VERSION\"> entry"
BRANCH="$(git branch --show-current)"
PREVIOUS="$(git describe --tags --abbrev=0 2>/dev/null || true)"

echo "==> Running tests"
uv run pytest -q

echo "==> Building packages"
packaging/appimage/build.sh
packaging/flatpak/build.sh
mkdir -p "$OUT"
(cd dist && sha256sum "$(basename "$APPIMAGE")" "$(basename "$FLATPAK")") >"$OUT/SHA256SUMS"

echo "==> Writing release notes"
{
    echo "## Changes"
    if [[ -n "$PREVIOUS" ]]; then
        git log --reverse --no-merges --invert-grep --grep='^Bump version to ' --pretty='- %s' "$PREVIOUS..HEAD"
    else
        echo "- First release"
    fi
    cat <<EOF

## Install

**AppImage** — any x86-64 distro with glibc 2.34 or newer (Ubuntu 22.04+, Debian 12+, Fedora 35+, Arch, …):

\`\`\`sh
chmod +x PrintLayout-$VERSION-x86_64.AppImage
./PrintLayout-$VERSION-x86_64.AppImage
\`\`\`

**Flatpak** — native look on KDE Plasma; the KDE runtime comes from Flathub automatically:

\`\`\`sh
flatpak install --user PrintLayout-$VERSION.flatpak
flatpak run $APP_ID
\`\`\`

Checksums: \`SHA256SUMS\`.
EOF
} >"$OUT/notes.md"

echo "==> Tagging and pushing $TAG"
git tag -a "$TAG" -m "PrintLayout $VERSION"
git push origin "$BRANCH" "$TAG"

echo "==> Creating the GitHub release"
gh release create "$TAG" --repo "$REPO" --verify-tag --title "PrintLayout $VERSION" \
    --notes-file "$OUT/notes.md" "$APPIMAGE" "$FLATPAK" "$OUT/SHA256SUMS"
