"""Application entry point."""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import QApplication

from .document import Document
from .ui.main_window import MainWindow

APP_ID = "io.github.VojtechKlos.PrintLayout"


def main() -> int:
    # Use the desktop's own file dialogs (KDE's on Plasma, GNOME's on GNOME) via the XDG
    # desktop portal: the Qt bundled with PySide6 cannot load the desktop's Qt plugins.
    # Inside Flatpak, Qt comes from the runtime and uses the portal on its own.
    if sys.platform.startswith("linux") and "FLATPAK_ID" not in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", "xdgdesktopportal")

    app = QApplication(sys.argv)
    app.setApplicationName("PrintLayout")
    app.setApplicationDisplayName("PrintLayout")
    app.setOrganizationName("PrintLayout")
    # Matches the installed .desktop file, so the taskbar shows the right icon and name.
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon.fromTheme(APP_ID, QIcon.fromTheme("document-print")))
    # Allow large photos (Qt's default limit of 256 MB rejects some panoramas).
    QImageReader.setAllocationLimit(1024)

    document = Document()
    window = MainWindow(document)
    window.show()
    window.open_paths(app.arguments()[1:])
    return app.exec()
