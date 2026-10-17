"""Check a built AppDir: every bundled library resolves, and the app can lay out and export a PDF.

Run with the AppDir's own Python:  AppDir/usr/python/bin/python3 -I check_bundle.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

BUNDLED_PREFIXES = ("libQt6", "libpyside6", "libshiboken6", "libicu", "libpython")


def needed(library: Path) -> list[str]:
    output = subprocess.run(["readelf", "-d", str(library)], capture_output=True, text=True, check=True).stdout
    return re.findall(r"\(NEEDED\)\s+Shared library: \[(.+?)\]", output)


def check_links(site: Path) -> list[str]:
    """Qt/PySide/ICU/Python libraries that something needs but the bundle lacks.

    Reads the ELF dependencies instead of using ldd, so Qt libraries installed on the build
    machine can't hide a missing one.
    """
    available = {f.name for f in Path(sys.prefix, "lib").rglob("*.so*")}
    problems = []
    for library in site.rglob("*.so*"):
        if library.is_file():
            missing = [n for n in needed(library) if n.startswith(BUNDLED_PREFIXES) and n not in available]
            problems += [f"{library.relative_to(site)}: {name}" for name in missing]
    return problems


def check_app() -> None:
    from PySide6.QtGui import QColor, QImage, QImageReader
    from PySide6.QtWidgets import QApplication

    from printlayout import output
    from printlayout.document import Document
    from printlayout.imagecache import image_extensions
    from printlayout.ui.main_window import MainWindow

    app = QApplication([])  # noqa: F841 (must stay alive)
    assert {"jpg", "png", "webp"} <= set(image_extensions()), image_extensions()
    assert b"svg" in [bytes(f.data()) for f in QImageReader.supportedImageFormats()]

    with tempfile.TemporaryDirectory() as tmp:
        photo = Path(tmp, "photo.jpg")
        image = QImage(600, 400, QImage.Format.Format_RGB32)
        image.fill(QColor("tomato"))
        assert image.save(str(photo))
        document = Document()
        window = MainWindow(document)
        window.add_paths([str(photo)] * 3)
        pdf = Path(tmp, "out.pdf")
        assert output.export_pdf(document.project, str(pdf), window)
        assert pdf.stat().st_size > 1000 and pdf.read_bytes().startswith(b"%PDF")


def main() -> None:
    site = next(Path(sys.prefix, "lib").glob("python3.*")) / "site-packages"
    problems = check_links(site)
    if problems:
        sys.exit("Missing bundled libraries:\n  " + "\n  ".join(problems))
    check_app()
    print("Bundle check passed.")


if __name__ == "__main__":
    main()
