import pytest

from printlayout.document import Document
from printlayout.model import LayoutMode


@pytest.fixture
def doc(qapp):
    document = Document()
    document.add_photos([f"/photos/{i}.jpg" for i in range(6)])
    return document


def ids(doc):
    return [p.id for p in doc.project.photos]


def test_auto_mode_reflows_on_add_and_grid_change(doc):
    assert len(doc.project.sheets) == 2  # 6 photos in 2×2
    doc.set_grid(3, 3)
    assert len(doc.project.sheets) == 1
    assert doc.project.sheets[0][:6] == ids(doc)


def test_removing_photo_in_auto_mode_closes_the_gap(doc):
    first = ids(doc)[0]
    doc.remove_photos([first])
    assert doc.project.sheets[0][0] == ids(doc)[0]


def test_switch_to_manual_keeps_arrangement(doc):
    before = [list(s) for s in doc.project.sheets]
    doc.set_mode(LayoutMode.MANUAL)
    assert doc.project.sheets == before
    assert not doc.auto_layout_differs()


def test_placing_a_photo_switches_to_manual(doc):
    messages = []
    doc.message.connect(messages.append)
    photo = ids(doc)[5]
    doc.place_photos(0, 0, [photo])
    assert doc.project.mode is LayoutMode.MANUAL
    assert doc.project.sheets[0][0] == photo
    assert messages
    assert doc.auto_layout_differs()


def test_place_multiple_continues_into_empty_cells(doc):
    doc.set_mode(LayoutMode.MANUAL)
    sheet = doc.add_sheet()
    doc.clear_cell(sheet, 2)
    a, b, c = ids(doc)[:3]
    doc.place_photos(sheet, 1, [a, b, c])
    assert doc.project.sheets[sheet] == [None, a, b, c]


def test_manual_grid_change_keeps_sheets(doc):
    doc.set_mode(LayoutMode.MANUAL)
    doc.add_sheet()
    doc.set_grid(1, 1)
    # Sheet 1 had 4 photos, sheet 2 had 2, sheet 3 was empty.
    assert len(doc.project.sheets) == 4 + 2 + 1


def test_move_cell_in_auto_mode_reorders_photo_list(doc):
    a, b = ids(doc)[:2]
    doc.move_cell(0, 0, 1)
    assert ids(doc)[:2] == [b, a]
    assert doc.project.sheets[0][:2] == [b, a]


def test_move_cell_to_empty_cell_in_auto_mode_moves_photo_to_end(doc):
    before = ids(doc)
    doc.move_cell(1, 0, 3)  # sheet 2 holds photos 4 and 5 in cells 0-1; cell 3 is empty
    assert ids(doc) == before[:4] + [before[5], before[4]]


def test_move_cell_in_manual_mode_swaps(doc):
    doc.set_mode(LayoutMode.MANUAL)
    a, b = doc.project.sheets[0][:2]
    doc.move_cell(0, 0, 1)
    assert doc.project.sheets[0][:2] == [b, a]


def test_fill_empty_cells_repeats_one_photo(doc):
    doc.set_mode(LayoutMode.MANUAL)
    sheet = doc.add_sheet()
    photo = ids(doc)[0]
    doc.fill_empty_cells(sheet, photo)
    assert doc.project.sheets[sheet] == [photo] * 4


def test_remove_photo_in_manual_mode_leaves_empty_cell(doc):
    doc.set_mode(LayoutMode.MANUAL)
    first = ids(doc)[0]
    doc.remove_photos([first])
    assert doc.project.sheets[0][0] is None


def test_duplicate_inserts_copy_after_original(doc):
    original = doc.project.photos[1]
    doc.duplicate_photos([original.id])
    copy = doc.project.photos[2]
    assert copy.path == original.path and copy.id != original.id


def test_rotation_wraps(doc):
    photo = doc.project.photos[0]
    doc.rotate_photos([photo.id], -90)
    assert photo.rotation == 270


def test_dirty_flag_and_save(doc, tmp_path):
    assert doc.dirty
    doc.save(str(tmp_path / "x.plproj"))
    assert not doc.dirty
    doc.set_cut_lines(True)
    assert doc.dirty


def test_fill_sheet_per_photo_stays_in_auto_mode(doc):
    first = ids(doc)[0]
    doc.set_photo_fill_sheet([first], True)
    assert doc.project.mode is LayoutMode.AUTO
    # Own sheet for the first photo; the other five flow onto two more sheets.
    assert doc.project.sheets[0] == [first] * 4
    assert doc.project.sheets[1:] == [ids(doc)[1:5], [ids(doc)[5], None, None, None]]


def test_global_fill_sheets_with_one_photo(qapp):
    document = Document()
    document.add_photos(["/photos/id.jpg"])
    document.set_fill_sheets(True)
    assert document.project.sheets == [[ids(document)[0]] * 4]


def test_global_fill_sheets_gives_every_photo_a_sheet(doc):
    doc.set_fill_sheets(True)
    assert doc.project.sheets == [[pid] * 4 for pid in ids(doc)]
    doc.add_photos(["/photos/new.jpg"])
    assert doc.project.sheets[-1] == [ids(doc)[-1]] * 4


def test_fill_sheets_kept_when_switching_to_manual(doc):
    doc.set_fill_sheets(True)
    before = [list(s) for s in doc.project.sheets]
    doc.set_mode(LayoutMode.MANUAL)
    assert doc.project.sheets == before
    assert not doc.auto_layout_differs()


def test_move_cell_in_auto_mode_with_a_filled_sheet(doc):
    first = ids(doc)[0]
    doc.set_photo_fill_sheet([first], True)
    a, b = ids(doc)[1:3]
    doc.move_cell(1, 0, 1)  # sheet 2 holds the flowing photos
    assert doc.project.sheets[1][:2] == [b, a]
    before = ids(doc)
    doc.move_cell(0, 0, 1)  # inside the filled sheet: same photo, nothing to do
    assert ids(doc) == before


def test_duplicate_keeps_fill_sheet(doc):
    first = ids(doc)[0]
    doc.set_photo_fill_sheet([first], True)
    doc.duplicate_photos([first])
    assert doc.project.photos[1].fill_sheet
