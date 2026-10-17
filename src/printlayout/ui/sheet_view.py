"""Preview of one sheet: accepts dropped photos and lets cells be rearranged by dragging."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QActionGroup,
    QColor,
    QDrag,
    QIcon,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QMenu, QSizePolicy, QWidget

from ..document import Document
from ..imagecache import ImageCache, collect_image_paths
from ..model import FitMode, LayoutMode, Sheet
from ..paper import page_size_mm
from ..render import render_sheet, sheet_cells

PHOTO_MIME = "application/x-printlayout-photos"  # photo ids, one per line
CELL_MIME = "application/x-printlayout-cell"  # "sheet:cell"
PADDING = 24  # px around the paper


def add_menu_action(menu: QMenu, text: str, slot: Callable[[], object], icon: str = "") -> None:
    action = menu.addAction(QIcon.fromTheme(icon), text) if icon else menu.addAction(text)
    action.triggered.connect(lambda *_: slot())


def add_fit_menu(menu: QMenu, document: Document, photo_ids: list[str], current: FitMode | None) -> None:
    fit_menu = menu.addMenu(menu.tr("Photo fit"))
    group = QActionGroup(fit_menu)
    for label, value in [
        (menu.tr("Use default"), None),
        (menu.tr("Fit — show whole photo"), FitMode.FIT),
        (menu.tr("Fill — crop to cell"), FitMode.FILL),
    ]:
        action = fit_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(current == value)
        group.addAction(action)
        action.triggered.connect(lambda *_, v=value: document.set_photo_fit(photo_ids, v))


def add_fill_sheet_action(menu: QMenu, document: Document, photo_ids: list[str]) -> None:
    """Automatic mode: checkable "Fill a whole sheet" for the given photos."""
    project = document.project
    photos = [p for p in project.photos if p.id in photo_ids]
    if project.fill_sheets:
        # The global switch already applies to every photo.
        action = menu.addAction(menu.tr("Fill a whole sheet (on for all photos)"))
        action.setEnabled(False)
    else:
        action = menu.addAction(menu.tr("Fill a whole sheet"))
    action.setCheckable(True)
    action.setChecked(bool(photos) and all(project.fills_sheet(p) for p in photos))
    action.triggered.connect(lambda checked: document.set_photo_fill_sheet(photo_ids, checked))


class SheetView(QWidget):
    def __init__(self, document: Document, cache: ImageCache, parent: QWidget | None = None):
        super().__init__(parent)
        self._doc = document
        self._cache = cache
        self._sheet_index = 0
        self._selected: int | None = None
        self._drop_target: int | None = None
        self._pixmap: QPixmap | None = None
        self._pixmap_key: tuple | None = None
        self._press_pos: QPoint | None = None
        self._press_cell: int | None = None
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        document.changed.connect(self._invalidate)

    # --- current sheet ------------------------------------------------------------------

    def sheet_index(self) -> int:
        return min(self._sheet_index, len(self._doc.project.sheets) - 1)

    def set_sheet_index(self, index: int) -> None:
        if index != self._sheet_index:
            self._sheet_index = index
            self._selected = None
            self._invalidate()

    def _sheet(self) -> Sheet:
        return self._doc.project.sheets[self.sheet_index()]

    def _invalidate(self) -> None:
        self._pixmap = None
        self.update()

    # --- geometry -----------------------------------------------------------------------

    def _paper_geometry(self) -> tuple[QRectF, float]:
        page_w, page_h = page_size_mm(self._doc.project.page)
        avail_w = max(1.0, self.width() - 2 * PADDING)
        avail_h = max(1.0, self.height() - 2 * PADDING)
        px_per_mm = min(avail_w / page_w, avail_h / page_h)
        w, h = round(page_w * px_per_mm), round(page_h * px_per_mm)
        return QRectF((self.width() - w) // 2, (self.height() - h) // 2, w, h), px_per_mm

    def _cell_rects(self) -> list[QRectF]:
        paper, s = self._paper_geometry()
        return [
            QRectF(paper.x() + c.x * s, paper.y() + c.y * s, c.w * s, c.h * s)
            for c in sheet_cells(self._doc.project)
        ]

    def _cell_at(self, pos: QPointF) -> int | None:
        return next((i for i, r in enumerate(self._cell_rects()) if r.contains(pos)), None)

    # --- painting -----------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Window).darker(115))
        paper, px_per_mm = self._paper_geometry()
        painter.fillRect(paper.translated(3, 3), QColor(0, 0, 0, 60))
        painter.drawPixmap(paper.topLeft(), self._sheet_pixmap(paper.size().toSize(), px_per_mm))

        rects = self._cell_rects()
        highlight = self.palette().color(QPalette.ColorRole.Highlight)
        if self._drop_target is not None and self._drop_target < len(rects):
            fill = QColor(highlight)
            fill.setAlpha(90)
            painter.fillRect(rects[self._drop_target], fill)
        if self._selected is not None and self._selected < len(rects):
            painter.setPen(highlight)
            painter.drawRect(rects[self._selected].adjusted(1, 1, -2, -2))
            painter.drawRect(rects[self._selected].adjusted(2, 2, -3, -3))

    def _sheet_pixmap(self, size: QSize, px_per_mm: float) -> QPixmap:
        dpr = self.devicePixelRatioF()
        key = (size.width(), size.height(), self.sheet_index(), dpr)
        if self._pixmap is None or self._pixmap_key != key:
            pixmap = QPixmap(round(size.width() * dpr), round(size.height() * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.white)
            manual = self._doc.project.mode is LayoutMode.MANUAL
            painter = QPainter(pixmap)
            render_sheet(
                painter,
                self._doc.project,
                self._sheet(),
                px_per_mm,
                self._cache.get,
                placeholders=True,
                empty_text=self.tr("Drop a photo here") if manual else "",
                missing_text=self.tr("Missing file"),
            )
            painter.end()
            self._pixmap, self._pixmap_key = pixmap, key
        return self._pixmap

    # --- mouse: select, drag cells, context menu ----------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._selected = self._press_cell = self._cell_at(event.position())
            self._press_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._press_pos = self._press_cell = None

    def mouseMoveEvent(self, event) -> None:
        if self._press_pos is None or self._press_cell is None:
            return
        distance = (event.position().toPoint() - self._press_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
        photo = self._doc.project.photo(self._sheet()[self._press_cell])
        cell = self._press_cell
        self._press_pos = self._press_cell = None
        if photo is None:
            return
        mime = QMimeData()
        mime.setData(CELL_MIME, f"{self.sheet_index()}:{cell}".encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        image = self._cache.get(photo.path)
        if image is not None:
            pixmap = QPixmap.fromImage(image).scaled(
                120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        drag.exec(Qt.DropAction.MoveAction)

    def contextMenuEvent(self, event) -> None:
        cell = self._cell_at(QPointF(event.pos()))
        if cell is None:
            return
        self._selected = cell
        self.update()
        photo = self._doc.project.photo(self._sheet()[cell])
        if photo is None:
            return
        doc, sheet = self._doc, self.sheet_index()
        menu = QMenu(self)
        add_menu_action(menu, self.tr("Rotate left"), lambda: doc.rotate_photos([photo.id], -90), "object-rotate-left")
        add_menu_action(menu, self.tr("Rotate right"), lambda: doc.rotate_photos([photo.id], 90), "object-rotate-right")
        add_fit_menu(menu, doc, [photo.id], photo.fit)
        menu.addSeparator()
        manual = doc.project.mode is LayoutMode.MANUAL
        if manual:
            add_menu_action(
                menu, self.tr("Fill empty cells with this photo"), lambda: doc.fill_empty_cells(sheet, photo.id)
            )
        else:
            add_fill_sheet_action(menu, doc, [photo.id])
        menu.addSeparator()
        if manual:
            add_menu_action(menu, self.tr("Clear cell"), lambda: doc.clear_cell(sheet, cell), "edit-clear")
        else:
            add_menu_action(menu, self.tr("Remove photo"), lambda: doc.remove_photos([photo.id]), "list-remove")
        menu.exec(event.globalPos())

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self._selected is not None:
            photo_id = self._sheet()[self._selected]
            if photo_id is None:
                return
            if self._doc.project.mode is LayoutMode.MANUAL:
                self._doc.clear_cell(self.sheet_index(), self._selected)
            else:
                self._doc.remove_photos([photo_id])
            return
        super().keyPressEvent(event)

    # --- drop target --------------------------------------------------------------------

    def _accepts(self, mime: QMimeData) -> bool:
        return mime.hasFormat(CELL_MIME) or mime.hasFormat(PHOTO_MIME) or mime.hasUrls()

    def _set_drop_target(self, cell: int | None) -> None:
        if cell != self._drop_target:
            self._drop_target = cell
            self.update()

    def dragEnterEvent(self, event) -> None:
        if self._accepts(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        cell = self._cell_at(event.position())
        self._set_drop_target(cell)
        if cell is not None and self._accepts(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_drop_target(None)

    def dropEvent(self, event) -> None:
        cell = self._cell_at(event.position())
        self._set_drop_target(None)
        mime = event.mimeData()
        sheet = self.sheet_index()
        if cell is None:
            event.ignore()
            return
        if mime.hasFormat(CELL_MIME):
            from_sheet, from_cell = (int(v) for v in bytes(mime.data(CELL_MIME).data()).decode().split(":"))
            if from_sheet == sheet:
                self._doc.move_cell(sheet, from_cell, cell)
        elif mime.hasFormat(PHOTO_MIME):
            ids = bytes(mime.data(PHOTO_MIME).data()).decode().split()
            self._doc.place_photos(sheet, cell, ids)
        else:
            paths = collect_image_paths(url.toLocalFile() for url in mime.urls() if url.isLocalFile())
            if not paths:
                event.ignore()
                return
            photos = self._doc.add_photos(paths)
            if self._doc.project.mode is LayoutMode.MANUAL:
                self._doc.place_photos(sheet, cell, [p.id for p in photos])
        self._selected = cell
        event.acceptProposedAction()
