# PrintLayout

Desktop app for Linux that prints photos several to a sheet — full page, 2 × 2, 3 × 3 or any
rows × columns grid — or exports the same layout as a PDF.

- **Automatic** arrangement: photos fill the cells in list order, adding sheets as needed.
  Drag photos in the list to reorder; drag one cell onto another to swap them.
- **Manual** arrangement: drag photos from the list (or from the file manager) onto cells,
  drag between cells to swap, right-click a cell to rotate, clear, or fill the empty cells
  with the same photo.
- Paper: A4, A3, A5, photo 10 × 15 cm (4 × 6″) and 13 × 18 cm (5 × 7″), portrait or landscape.
- Margins and gaps in mm, Fit (whole photo) or Fill (crop to cell) per project or per photo,
  auto-rotation to match the cell, and optional cut lines in the margins and gaps.
- Projects are saved as `*.plproj` (JSON). Photo paths are stored relative to the project
  file, so a folder with the project and its photos can be moved.
- File dialogs are the desktop's own (KDE's, GNOME's, …) through the XDG desktop portal.
  Set `QT_QPA_PLATFORMTHEME` yourself to override this.

## Run

```sh
uv run printlayout                  # empty project
uv run printlayout ~/Pictures/trip  # start with all photos from a folder
uv run printlayout album.plproj     # open a project
```

## Install as an app

```sh
uv tool install .
cp data/io.github.VojtechKlos.PrintLayout.desktop ~/.local/share/applications/
cp data/io.github.VojtechKlos.PrintLayout.svg ~/.local/share/icons/hicolor/scalable/apps/
```

## Flatpak

```sh
./packaging/flatpak/build.sh            # → dist/PrintLayout-<version>.flatpak
./packaging/flatpak/build.sh --install  # also install it for your user
flatpak install --user dist/PrintLayout-0.1.0.flatpak   # on another machine
```

Built on the KDE runtime with the official PySide6 BaseApp from Flathub, so it gets the native
Plasma look, dialogs and icons. The app may read and write your home folder (photos can be
anywhere; drag and drop from the file manager works); printing goes through CUPS. The build
needs only `flatpak` — the builder and runtimes come from Flathub for your user on first use.

## AppImage

```sh
./packaging/appimage/build.sh      # → dist/PrintLayout-<version>-x86_64.AppImage
```

The AppImage bundles a portable Python and PySide6's own Qt, trimmed to what the app uses;
nothing is taken from the build machine, so it runs on any x86-64 distro with glibc 2.34 or
newer (Ubuntu 22.04+, Debian 12+, Fedora 35+, current Arch, …). The build needs `uv`,
`curl` and `readelf` (binutils), and downloads the pinned appimagetool on first use.

## Development

```sh
uv run pytest
```

| Module | Purpose |
| --- | --- |
| `model.py` | Project data: page settings, grid, photos, sheets |
| `geometry.py` | Pure layout maths in mm: cell rectangles, fit/fill, rotation, cut lines |
| `autofill.py` | Distributing photos into sheets |
| `render.py` | Draws a sheet with `QPainter` — the same code for preview, printer and PDF |
| `document.py` | The open project and every operation that changes it |
| `output.py` | Print dialog and PDF export |
| `project_io.py` | Saving and loading `*.plproj` files |
| `ui/` | Main window, photo list, sheet preview, settings panel |
