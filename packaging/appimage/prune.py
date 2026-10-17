"""Strip the parts of the bundled Python and PySide6 that PrintLayout never uses.

Usage: prune.py <python home inside the AppDir>

Qt libraries are kept only when something that is kept links to them (followed through the
ELF NEEDED entries), so required libraries can't be removed by accident.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

# PySide6 modules the app imports.
PYSIDE_MODULES = {"QtCore", "QtGui", "QtWidgets", "QtPrintSupport"}
# Qt plugin folders a desktop app needs: windowing, input methods, native dialogs,
# image formats, icons and printing.
PLUGIN_DIRS = {
    "platforms",
    "platformthemes",
    "platforminputcontexts",
    "imageformats",
    "iconengines",
    "printsupport",
    "xcbglintegrations",
    "wayland-decoration-client",
    "wayland-graphics-integration-client",
    "wayland-shell-integration",
}
PLATFORMS = {"libqxcb.so", "libqwayland.so", "libqoffscreen.so", "libqminimal.so"}
PYSIDE_UNUSED = ["doc", "glue", "include", "lib", "scripts", "typesystems",
                 "Qt/qml", "Qt/metatypes", "Qt/libexec", "Qt/translations"]  # fmt: skip
STDLIB_UNUSED = ["idlelib", "tkinter", "turtledemo", "turtle.py", "ensurepip", "lib2to3", "pydoc_data", "test"]
PYTHON_UNUSED_GLOBS = ["include", "share", "lib/pkgconfig", "lib/tcl*", "lib/tk*", "lib/itcl*",
                       "lib/thread*", "lib/Tix*"]  # fmt: skip
PYTHON_BINARIES = {"python", "python3"}


def remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def needed(library: Path) -> list[str]:
    output = subprocess.run(["readelf", "-d", str(library)], capture_output=True, text=True, check=True).stdout
    return re.findall(r"\(NEEDED\)\s+Shared library: \[(.+?)\]", output)


def linked_closure(roots: list[Path], search_dirs: list[Path]) -> set[str]:
    """File names of `roots` and every library they load from `search_dirs`, recursively."""
    by_name = {f.name: f for d in search_dirs for f in d.iterdir() if ".so" in f.name}
    keep: set[str] = set()
    todo = list(roots)
    while todo:
        library = todo.pop()
        if library.name in keep:
            continue
        keep.update({library.name, library.resolve().name})
        todo += [by_name[name] for name in needed(library) if name in by_name]
    return keep


def prune_pyside(site: Path) -> None:
    pyside, shiboken = site / "PySide6", site / "shiboken6"
    qt = pyside / "Qt"
    for path in pyside.iterdir():
        unused_module = path.name.startswith("Qt") and path.name.split(".")[0] not in PYSIDE_MODULES
        is_tool = path.is_file() and "." not in path.name  # designer, linguist, qmlls, ...
        if path.suffix == ".pyi" or is_tool or (unused_module and path.is_file()):
            remove(path)
    for name in PYSIDE_UNUSED:
        remove(pyside / name)
    for name in ["include", "lib", "Shiboken.pyi"]:
        remove(shiboken / name)

    plugins = qt / "plugins"
    for folder in plugins.iterdir():
        if folder.name not in PLUGIN_DIRS:
            remove(folder)
    for plugin in (plugins / "platforms").iterdir():
        if plugin.name not in PLATFORMS:
            remove(plugin)
    # Some plugins need Qt libraries these wheels don't ship (QtPdf, QtVirtualKeyboard). Left in,
    # they could load a different Qt version installed on the host.
    shipped = {f.name for f in (qt / "lib").iterdir()}
    for plugin in plugins.rglob("*.so"):
        if any(name.startswith("libQt6") and name not in shipped for name in needed(plugin)):
            remove(plugin)

    roots = [pyside / f"{m}.abi3.so" for m in PYSIDE_MODULES]
    roots += list(pyside.glob("libpyside6.abi3.so*")) + list(shiboken.glob("*.so*"))
    roots += [p for p in plugins.rglob("*.so") if p.is_file()]
    keep = linked_closure(roots, [qt / "lib", pyside, shiboken])
    for library in [*(qt / "lib").iterdir(), *pyside.glob("libpyside6qml*")]:
        if library.name not in keep:
            remove(library)


def prune_python(home: Path) -> None:
    stdlib = next((home / "lib").glob("python3.*"))
    for name in STDLIB_UNUSED:
        remove(stdlib / name)
    for path in (stdlib / "lib-dynload").glob("_tkinter*"):
        remove(path)
    for pattern in PYTHON_UNUSED_GLOBS:
        for path in home.glob(pattern):
            remove(path)
    for binary in (home / "bin").iterdir():
        if binary.name not in PYTHON_BINARIES and not re.fullmatch(r"python3\.\d+", binary.name):
            remove(binary)


def main() -> None:
    home = Path(sys.argv[1])
    site = next((home / "lib").glob("python3.*")) / "site-packages"
    prune_pyside(site)
    prune_python(home)


if __name__ == "__main__":
    main()
