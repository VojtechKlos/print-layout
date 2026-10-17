"""Main window: photo list | sheet preview | settings."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import output
from ..document import Document
from ..imagecache import ImageCache, collect_image_paths, image_extensions
from ..model import LayoutMode
from ..project_io import FILE_EXTENSION, ProjectError
from .photo_list import PhotoList
from .settings_panel import SettingsPanel
from .sheet_view import SheetView


class MainWindow(QMainWindow):
    def __init__(self, document: Document):
        super().__init__()
        self._doc = document
        self._settings = QSettings()
        self._cache = ImageCache()
        self.photo_list = PhotoList(document)
        self.sheet_view = SheetView(document, self._cache)
        self.settings_panel = SettingsPanel(document)

        self._create_actions()
        self._create_menus()
        self._create_layout()
        self._photo_count = QLabel()
        self.statusBar().addPermanentWidget(self._photo_count)

        document.changed.connect(self._on_changed)
        document.state_changed.connect(self._update_title)
        document.message.connect(lambda text: self.statusBar().showMessage(text, 5000))
        self.photo_list.photo_activated.connect(self._show_photo)

        self.resize(1280, 820)
        self._restore_settings()
        self._on_changed()
        self._update_title()

    # --- construction -------------------------------------------------------------------

    def _action(self, text: str, slot, shortcut=None, icon: str = "") -> QAction:
        action = QAction(QIcon.fromTheme(icon), text, self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda *_: slot())
        return action

    def _create_actions(self) -> None:
        sk = QKeySequence.StandardKey
        self.act_new = self._action(self.tr("&New"), self._new, sk.New, "document-new")
        self.act_open = self._action(self.tr("&Open…"), self._open, sk.Open, "document-open")
        self.act_save = self._action(self.tr("&Save"), self._save, sk.Save, "document-save")
        self.act_save_as = self._action(self.tr("Save &As…"), self._save_as, sk.SaveAs, "document-save-as")
        self.act_export = self._action(self.tr("&Export PDF…"), self._export_pdf, "Ctrl+E", "document-export")
        self.act_print = self._action(self.tr("&Print…"), self._print, sk.Print, "document-print")
        self.act_quit = self._action(self.tr("&Quit"), self.close, sk.Quit, "application-exit")
        self.act_add_photos = self._action(self.tr("Add &Photos…"), self._add_photos, "Ctrl+I", "list-add")
        self.act_add_folder = self._action(self.tr("Add &Folder…"), self._add_folder, None, "folder-open")
        self.act_remove_photos = self._action(
            self.tr("&Remove Photos"), lambda: self._doc.remove_photos(self.photo_list.selected_ids()),
            None, "list-remove",
        )  # fmt: skip
        self.act_prev = self._action(self.tr("Previous Sheet"), lambda: self._go_to(-1), "PgUp", "go-previous")
        self.act_next = self._action(self.tr("Next Sheet"), lambda: self._go_to(+1), "PgDown", "go-next")
        self.act_add_sheet = self._action(self.tr("Add Sheet"), self._add_sheet, None, "document-new")
        self.act_add_sheet.setToolTip(self.tr("Add an empty sheet (switches to manual arrangement)"))
        self.act_remove_sheet = self._action(self.tr("Remove Sheet"), self._remove_sheet, None, "edit-delete")
        self.act_about = self._action(self.tr("&About"), self._about, None, "help-about")

    def _create_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu(self.tr("&File"))
        for action in (self.act_new, self.act_open, self.act_save, self.act_save_as, None,
                       self.act_add_photos, self.act_add_folder, None,
                       self.act_export, self.act_print, None, self.act_quit):  # fmt: skip
            file_menu.addSeparator() if action is None else file_menu.addAction(action)
        sheet_menu = bar.addMenu(self.tr("&Sheet"))
        for action in (self.act_prev, self.act_next, None, self.act_add_sheet, self.act_remove_sheet):
            sheet_menu.addSeparator() if action is None else sheet_menu.addAction(action)
        bar.addMenu(self.tr("&Help")).addAction(self.act_about)

        toolbar = self.addToolBar(self.tr("Main"))
        toolbar.setObjectName("main_toolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for action in (self.act_open, self.act_save, None, self.act_add_photos, self.act_add_folder,
                       None, self.act_print, self.act_export):  # fmt: skip
            toolbar.addSeparator() if action is None else toolbar.addAction(action)

    def _create_layout(self) -> None:
        # Left: photo list with its buttons.
        photo_panel = QWidget()
        photo_layout = QVBoxLayout(photo_panel)
        photo_layout.setContentsMargins(6, 6, 0, 6)
        photo_layout.addWidget(QLabel(self.tr("<b>Photos</b>")))
        photo_layout.addWidget(self.photo_list)
        buttons = QHBoxLayout()
        for action in (self.act_add_photos, self.act_add_folder, self.act_remove_photos):
            button = QToolButton()
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            buttons.addWidget(button)
        buttons.addStretch()
        photo_layout.addLayout(buttons)

        # Centre: the sheet with navigation below it.
        self._sheet_label = QLabel()
        self._sheet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sheet_label.setMinimumWidth(110)
        nav = QHBoxLayout()
        nav.addStretch()
        for widget in (self.act_prev, self._sheet_label, self.act_next):
            if isinstance(widget, QAction):
                button = QToolButton()
                button.setDefaultAction(widget)
                widget = button
            nav.addWidget(widget)
        nav.addSpacing(24)
        for action in (self.act_add_sheet, self.act_remove_sheet):
            button = QToolButton()
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            nav.addWidget(button)
        nav.addStretch()
        centre = QWidget()
        centre_layout = QVBoxLayout(centre)
        centre_layout.setContentsMargins(0, 0, 0, 6)
        centre_layout.addWidget(self.sheet_view, 1)
        centre_layout.addLayout(nav)

        # Right: settings, scrollable on small screens.
        scroll = QScrollArea()
        scroll.setWidget(self.settings_panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(self.settings_panel.sizeHint().width() + 20)

        self._splitter = QSplitter()
        self._splitter.addWidget(photo_panel)
        self._splitter.addWidget(centre)
        self._splitter.addWidget(scroll)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setCollapsible(1, False)
        self._splitter.setSizes([270, 700, 310])
        self.setCentralWidget(self._splitter)

    # --- state --------------------------------------------------------------------------

    def _on_changed(self) -> None:
        project = self._doc.project
        count = len(project.sheets)
        index = min(self.sheet_view.sheet_index(), count - 1)
        self.sheet_view.set_sheet_index(index)
        self._sheet_label.setText(self.tr("Sheet {0} of {1}").format(index + 1, count))
        self.act_prev.setEnabled(index > 0)
        self.act_next.setEnabled(index < count - 1)
        self.act_remove_sheet.setEnabled(project.mode is LayoutMode.MANUAL)
        has_photos = bool(project.photos)
        self.act_print.setEnabled(has_photos)
        self.act_export.setEnabled(has_photos)
        self._photo_count.setText(self.tr("{0} photos · {1} sheets").format(len(project.photos), count))

    def _update_title(self) -> None:
        name = os.path.basename(self._doc.path) if self._doc.path else self.tr("Untitled")
        self.setWindowTitle(f"{name}[*]")
        self.setWindowModified(self._doc.dirty)

    def _go_to(self, delta: int) -> None:
        self._show_sheet(self.sheet_view.sheet_index() + delta)

    def _show_sheet(self, index: int) -> None:
        index = max(0, min(index, len(self._doc.project.sheets) - 1))
        self.sheet_view.set_sheet_index(index)
        self._on_changed()

    def _show_photo(self, photo_id: str) -> None:
        sheets = self._doc.project.sheets_with(photo_id)
        if sheets:
            # Repeated double-clicks cycle through every sheet the photo is on.
            later = [i for i in sheets if i > self.sheet_view.sheet_index()]
            self._show_sheet((later or sheets)[0])

    def _add_sheet(self) -> None:
        self._show_sheet(self._doc.add_sheet())

    def _remove_sheet(self) -> None:
        self._doc.remove_sheet(self.sheet_view.sheet_index())

    # --- photos -------------------------------------------------------------------------

    def _image_filter(self) -> str:
        patterns = " ".join(f"*.{ext} *.{ext.upper()}" for ext in image_extensions())
        return self.tr("Images ({0})").format(patterns)

    def _add_photos(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Add Photos"), self._settings.value("photo_dir", os.path.expanduser("~")),
            self._image_filter(),
        )  # fmt: skip
        if paths:
            self._settings.setValue("photo_dir", os.path.dirname(paths[0]))
            self.add_paths(paths)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Add Folder"), self._settings.value("photo_dir", os.path.expanduser("~"))
        )
        if folder:
            self._settings.setValue("photo_dir", folder)
            self.add_paths([folder])

    def add_paths(self, paths: list[str]) -> None:
        images = collect_image_paths(paths)
        if not images:
            self.statusBar().showMessage(self.tr("No supported images found."), 5000)
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._doc.add_photos(images)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self.statusBar().showMessage(self.tr("Added {0} photos.").format(len(images)), 5000)

    def open_paths(self, paths: list[str]) -> None:
        """Open files given on the command line: a project, or photos and folders."""
        projects = [p for p in paths if p.endswith(FILE_EXTENSION)]
        if projects:
            self.open_project(projects[0])
        others = [p for p in paths if not p.endswith(FILE_EXTENSION)]
        if others:
            self.add_paths(others)

    # --- files --------------------------------------------------------------------------

    def _project_filter(self) -> str:
        return self.tr("PrintLayout projects (*{0})").format(FILE_EXTENSION)

    def _maybe_save(self) -> bool:
        if not self._doc.dirty:
            return True
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self, self.tr("Unsaved changes"), self.tr("Save the changes to this project?"),
            buttons.Save | buttons.Discard | buttons.Cancel, buttons.Save,
        )  # fmt: skip
        if answer == buttons.Save:
            return self._save()
        return answer == buttons.Discard

    def _new(self) -> None:
        if self._maybe_save():
            self._doc.new()
            self._show_sheet(0)

    def _open(self) -> None:
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Open Project"), self._settings.value("project_dir", os.path.expanduser("~")),
            self._project_filter(),
        )  # fmt: skip
        if path:
            self.open_project(path)

    def open_project(self, path: str) -> None:
        try:
            self._doc.load(path)
        except (OSError, ProjectError) as error:
            QMessageBox.critical(self, self.tr("Cannot open project"), str(error))
            return
        self._settings.setValue("project_dir", os.path.dirname(os.path.abspath(path)))
        self._show_sheet(0)
        missing = [p for p in self._doc.project.photos if not os.path.isfile(p.path)]
        if missing:
            self.statusBar().showMessage(self.tr("{0} photos could not be found.").format(len(missing)), 8000)

    def _save(self) -> bool:
        return self._save_to(self._doc.path) if self._doc.path else self._save_as()

    def _save_as(self) -> bool:
        suggested = self._doc.path or os.path.join(
            self._settings.value("project_dir", os.path.expanduser("~")), self.tr("layout") + FILE_EXTENSION
        )
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Save Project"), suggested, self._project_filter())
        if not path:
            return False
        if not path.endswith(FILE_EXTENSION):
            path += FILE_EXTENSION
        return self._save_to(path)

    def _save_to(self, path: str) -> bool:
        try:
            self._doc.save(path)
        except OSError as error:
            QMessageBox.critical(self, self.tr("Cannot save project"), str(error))
            return False
        self._settings.setValue("project_dir", os.path.dirname(path))
        self.statusBar().showMessage(self.tr("Saved {0}.").format(path), 5000)
        return True

    # --- output -------------------------------------------------------------------------

    def _base_name(self) -> str:
        return os.path.splitext(os.path.basename(self._doc.path))[0] if self._doc.path else self.tr("photos")

    def _export_pdf(self) -> None:
        directory = self._settings.value("pdf_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export PDF"), os.path.join(directory, self._base_name() + ".pdf"), self.tr("PDF (*.pdf)")
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self._settings.setValue("pdf_dir", os.path.dirname(path))
        if output.export_pdf(self._doc.project, path, self):
            self.statusBar().showMessage(self.tr("Exported {0}.").format(path), 8000)

    def _print(self) -> None:
        if output.print_project(self._doc.project, self, self._base_name()):
            self.statusBar().showMessage(self.tr("Sent to the printer."), 5000)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            self.tr("About PrintLayout"),
            self.tr(
                "<b>PrintLayout</b><p>Print photos several to a page — full page, 2 × 2, 3 × 3 "
                "or any grid — or save the layout as PDF.</p>"
            ),
        )

    # --- window state -------------------------------------------------------------------

    def _restore_settings(self) -> None:
        if geometry := self._settings.value("geometry"):
            self.restoreGeometry(geometry)
        if state := self._settings.value("window_state"):
            self.restoreState(state)
        if splitter := self._settings.value("splitter"):
            self._splitter.restoreState(splitter)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._maybe_save():
            event.ignore()
            return
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("window_state", self.saveState())
        self._settings.setValue("splitter", self._splitter.saveState())
        event.accept()
