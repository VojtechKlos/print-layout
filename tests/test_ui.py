import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QDropEvent, QImage

from printlayout.document import Document
from printlayout.imagecache import ImageCache
from printlayout.model import LayoutMode
from printlayout.ui.photo_list import PhotoList
from printlayout.ui.settings_panel import PRESETS, SettingsPanel
from printlayout.ui.sheet_view import CELL_MIME, PHOTO_MIME, SheetView


@pytest.fixture
def photo_files(tmp_path):
    paths = []
    for i in range(6):
        image = QImage(60, 40, QImage.Format.Format_RGB32)
        image.fill(QColor.fromHsv(i * 50, 200, 200))
        path = tmp_path / f"img_{i}.png"
        image.save(str(path))
        paths.append(str(path))
    return paths


@pytest.fixture
def doc(qapp, photo_files):
    document = Document()
    document.add_photos(photo_files[:4])
    return document


@pytest.fixture
def view(qtbot, doc):
    widget = SheetView(doc, ImageCache())
    qtbot.addWidget(widget)
    widget.resize(500, 700)
    widget.show()
    return widget


def drop(view, cell, mime):
    centre = view._cell_rects()[cell].center()
    event = QDropEvent(
        QPointF(centre), Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )  # fmt: skip
    view.dropEvent(event)
    return event


def test_drop_photo_from_list_places_it_and_switches_to_manual(view, doc):
    photo = doc.project.photos[3]
    mime = QMimeData()
    mime.setData(PHOTO_MIME, photo.id.encode())
    assert drop(view, 0, mime).isAccepted()
    assert doc.project.mode is LayoutMode.MANUAL
    assert doc.project.sheets[0][0] == photo.id


def test_drop_cell_on_cell_swaps(view, doc):
    doc.set_mode(LayoutMode.MANUAL)
    a, b = doc.project.sheets[0][:2]
    mime = QMimeData()
    mime.setData(CELL_MIME, b"0:0")
    drop(view, 1, mime)
    assert doc.project.sheets[0][:2] == [b, a]


def test_drop_files_from_file_manager_adds_and_places(view, doc, photo_files):
    doc.set_mode(LayoutMode.MANUAL)
    doc.clear_cell(0, 2)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(photo_files[5]), QUrl.fromLocalFile("/not/an/image.txt")])
    drop(view, 2, mime)
    assert len(doc.project.photos) == 5
    assert doc.project.photo(doc.project.sheets[0][2]).path == photo_files[5]


def test_cell_hit_testing_ignores_margins(view):
    assert view._cell_at(QPointF(1, 1)) is None
    assert view._cell_at(view._cell_rects()[3].center()) == 3


def test_photo_list_drag_data_and_reorder(qtbot, doc):
    widget = PhotoList(doc)
    qtbot.addWidget(widget)
    ids = [p.id for p in doc.project.photos]
    items = [widget.item(2), widget.item(0)]
    assert bytes(widget.mimeData(items).data(PHOTO_MIME).data()).decode().split() == [ids[0], ids[2]]

    widget.model().moveRow(widget.model().index(0, 0).parent(), 0, widget.model().index(0, 0).parent(), 3)
    widget._sync_order()
    assert [p.id for p in doc.project.photos] == [ids[1], ids[2], ids[0], ids[3]]
    assert [widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(4)] == [p.id for p in doc.project.photos]


def test_photo_list_shows_usage(qtbot, doc):
    widget = PhotoList(doc)
    qtbot.addWidget(widget)
    assert widget.item(0).text().endswith("Sheet 1")
    doc.set_mode(LayoutMode.MANUAL)
    doc.clear_cell(0, 0)
    assert widget.item(0).text().endswith("Not placed")


def test_settings_panel_controls_document(qtbot, doc):
    panel = SettingsPanel(doc)
    qtbot.addWidget(panel)
    index = next(i for i, (_, r, c) in enumerate(PRESETS) if (r, c) == (3, 3))
    panel._preset.activated.emit(index)
    assert (doc.project.grid.rows, doc.project.grid.cols) == (3, 3)
    assert panel._rows.value() == 3

    panel._cols.setValue(5)
    assert doc.project.grid.cols == 5
    assert panel._preset.currentText() == "Custom"

    panel._margin.setValue(12.5)
    assert doc.project.page.margin_mm == 12.5

    panel._orientation.setCurrentIndex(1)
    assert doc.project.page.orientation.value == "landscape"

    doc.set_mode(LayoutMode.MANUAL)
    assert panel._manual.isChecked()
