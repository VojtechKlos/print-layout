"""The photo list: thumbnails in layout order, drag source for the sheet view."""

from __future__ import annotations

import os

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QDrag, QIcon, QPixmap, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyle,
    QWidget,
)

from ..document import Document
from ..imagecache import collect_image_paths, load_image
from ..model import LayoutMode, Photo
from .sheet_view import PHOTO_MIME, add_fill_sheet_action, add_fit_menu, add_menu_action

ID_ROLE = Qt.ItemDataRole.UserRole
ICON_SIZE = 96


class PhotoList(QListWidget):
    photo_activated = Signal(str)  # photo id, on double-click

    def __init__(self, document: Document, parent: QWidget | None = None):
        super().__init__(parent)
        self._doc = document
        self._icons: dict[tuple[str, int], QIcon] = {}
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setSpacing(2)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemDoubleClicked.connect(lambda item: self.photo_activated.emit(item.data(ID_ROLE)))
        document.photos_changed.connect(self.rebuild)
        document.changed.connect(self._refresh_items)
        self.rebuild()

    def selected_ids(self) -> list[str]:
        return [item.data(ID_ROLE) for item in sorted(self.selectedItems(), key=self.row)]

    # --- keeping in sync with the document ----------------------------------------------

    def rebuild(self) -> None:
        photos = self._doc.project.photos
        current = [self.item(i).data(ID_ROLE) for i in range(self.count())]
        if current != [p.id for p in photos]:
            selected = set(self.selected_ids())
            self.clear()
            for photo in photos:
                item = QListWidgetItem()
                item.setData(ID_ROLE, photo.id)
                item.setToolTip(photo.path)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
                )
                self.addItem(item)
                item.setSelected(photo.id in selected)
        self._refresh_items()

    def _refresh_items(self) -> None:
        project = self._doc.project
        for i in range(self.count()):
            item = self.item(i)
            photo = project.photo(item.data(ID_ROLE))
            if photo is None:
                continue
            item.setIcon(self._icon(photo))
            item.setText(f"{os.path.basename(photo.path)}\n{self._usage(photo)}")

    def _usage(self, photo: Photo) -> str:
        project = self._doc.project
        sheets = project.sheets_with(photo.id)
        if not sheets:
            return self.tr("Not placed")
        numbers = ", ".join(str(i + 1) for i in sheets)
        text = self.tr("Sheet {0}").format(numbers) if len(sheets) == 1 else self.tr("Sheets {0}").format(numbers)
        if project.mode is LayoutMode.AUTO and project.fills_sheet(photo):
            text += self.tr(" · whole sheet")
        return text

    def _icon(self, photo: Photo) -> QIcon:
        key = (photo.path, photo.rotation)
        if key not in self._icons:
            image = load_image(photo.path, ICON_SIZE * 2)
            if image is None:
                self._icons[key] = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            else:
                if photo.rotation:
                    image = image.transformed(QTransform().rotate(photo.rotation))
                self._icons[key] = QIcon(QPixmap.fromImage(image))
        return self._icons[key]

    # --- dragging out to the sheet view, reordering inside the list ---------------------

    def mimeData(self, items) -> QMimeData:
        mime = super().mimeData(items)
        ids = [item.data(ID_ROLE) for item in sorted(items, key=self.row)]
        mime.setData(PHOTO_MIME, "\n".join(ids).encode())
        return mime

    def startDrag(self, supported_actions) -> None:
        # Own drag instead of Qt's, so a drop on another widget never removes list items.
        items = sorted(self.selectedItems(), key=self.row)
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        pixmap = items[0].icon().pixmap(ICON_SIZE)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:
        if event.source() is not self and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.source() is not self and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.source() is self:
            super().dropEvent(event)
            # Let Qt finish moving the rows before the document rebuilds the list.
            QTimer.singleShot(0, self._sync_order)
            return
        paths = collect_image_paths(url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile())
        if paths:
            self._doc.add_photos(paths)
            event.acceptProposedAction()

    def _sync_order(self) -> None:
        self._doc.reorder_photos([self.item(i).data(ID_ROLE) for i in range(self.count())])

    # --- context menu and keys ----------------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        ids = self.selected_ids()
        if not ids:
            return
        doc = self._doc
        menu = QMenu(self)
        add_menu_action(menu, self.tr("Rotate left"), lambda: doc.rotate_photos(ids, -90), "object-rotate-left")
        add_menu_action(menu, self.tr("Rotate right"), lambda: doc.rotate_photos(ids, 90), "object-rotate-right")
        first = doc.project.photo(ids[0])
        add_fit_menu(menu, doc, ids, first.fit if first and len(ids) == 1 else None)
        menu.addSeparator()
        if doc.project.mode is LayoutMode.AUTO:
            add_fill_sheet_action(menu, doc, ids)
        add_menu_action(menu, self.tr("Add a copy"), lambda: doc.duplicate_photos(ids), "edit-copy")
        if doc.project.mode is LayoutMode.MANUAL and len(ids) == 1:
            add_menu_action(menu, self.tr("Show on sheet"), lambda: self.photo_activated.emit(ids[0]))
        menu.addSeparator()
        add_menu_action(menu, self.tr("Remove from project"), lambda: doc.remove_photos(ids), "list-remove")
        menu.exec(self.viewport().mapToGlobal(pos))

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selectedItems():
            self._doc.remove_photos(self.selected_ids())
            return
        super().keyPressEvent(event)
