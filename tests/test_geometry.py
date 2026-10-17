import pytest

from printlayout.geometry import (
    Rect,
    cell_rects,
    cut_segments,
    effective_rotation,
    placement,
    rotated_size,
)
from printlayout.model import FitMode, Orientation, PageSettings
from printlayout.paper import page_size_mm


def approx_rect(rect: Rect, x, y, w, h):
    assert (rect.x, rect.y, rect.w, rect.h) == pytest.approx((x, y, w, h))


def test_page_size_respects_orientation():
    assert page_size_mm(PageSettings(paper="A4")) == (210, 297)
    assert page_size_mm(PageSettings(paper="A4", orientation=Orientation.LANDSCAPE)) == (297, 210)
    assert page_size_mm(PageSettings(paper="10x15")) == (101.6, 152.4)


def test_single_cell_fills_area_inside_margins():
    (cell,) = cell_rects(210, 297, margin=10, gap=5, rows=1, cols=1)
    approx_rect(cell, 10, 10, 190, 277)


def test_two_by_two_a4_portrait():
    cells = cell_rects(210, 297, margin=10, gap=5, rows=2, cols=2)
    assert len(cells) == 4
    approx_rect(cells[0], 10, 10, 92.5, 136)
    approx_rect(cells[1], 107.5, 10, 92.5, 136)
    approx_rect(cells[2], 10, 151, 92.5, 136)
    approx_rect(cells[3], 107.5, 151, 92.5, 136)
    assert cells[3].right == pytest.approx(200)
    assert cells[3].bottom == pytest.approx(287)


def test_two_by_two_a4_landscape():
    cells = cell_rects(297, 210, margin=10, gap=5, rows=2, cols=2)
    approx_rect(cells[0], 10, 10, 136, 92.5)
    approx_rect(cells[3], 151, 107.5, 136, 92.5)


def test_three_by_three_without_margins():
    cells = cell_rects(210, 297, margin=0, gap=0, rows=3, cols=3)
    assert len(cells) == 9
    approx_rect(cells[4], 70, 99, 70, 99)
    assert cells[8].right == pytest.approx(210)


def test_oversized_margins_clamp_to_zero():
    cells = cell_rects(100, 150, margin=80, gap=0, rows=1, cols=1)
    assert cells[0].w == 0 and cells[0].h == 0


def test_fit_letterboxes_whole_image():
    cell = Rect(10, 10, 100, 100)
    source, target = placement(300, 100, cell, FitMode.FIT)
    approx_rect(source, 0, 0, 300, 100)
    approx_rect(target, 10, 10 + (100 - 100 / 3) / 2, 100, 100 / 3)


def test_fill_crops_centre():
    cell = Rect(0, 0, 100, 100)
    source, target = placement(300, 100, cell, FitMode.FILL)
    approx_rect(source, 100, 0, 100, 100)
    assert target == cell


def test_rotated_size():
    assert rotated_size(300, 200, 0) == (300, 200)
    assert rotated_size(300, 200, 90) == (200, 300)
    assert rotated_size(300, 200, 180) == (300, 200)
    assert rotated_size(300, 200, 270) == (200, 300)


@pytest.mark.parametrize(
    "img, cell, user, auto, expected",
    [
        ((300, 200), (90, 130), 0, True, 90),  # landscape photo, portrait cell
        ((300, 200), (130, 90), 0, True, 0),  # orientations match
        ((300, 200), (90, 130), 0, False, 0),  # auto-rotate off
        ((200, 200), (90, 130), 0, True, 0),  # square photo never auto-rotates
        ((300, 200), (100, 100), 0, True, 0),  # square cell never auto-rotates
        ((300, 200), (90, 130), 90, True, 180),  # user rotation is added on top
        ((300, 200), (130, 90), 270, True, 270),
    ],
)
def test_effective_rotation(img, cell, user, auto, expected):
    assert effective_rotation(*img, *cell, user, auto) == expected


def test_cut_segments_with_gap_stay_in_margins_and_gaps():
    cells = cell_rects(210, 297, margin=10, gap=5, rows=2, cols=2)
    segments = cut_segments(cells, 210, 297)
    # 4 vertical edge positions × (top margin, middle gap, bottom margin), same horizontally.
    assert len(segments) == 24
    for x0, y0, x1, y1 in segments:
        for cell in cells:
            # No segment runs through the inside of a cell.
            mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
            inside = cell.x < mid_x < cell.right and cell.y < mid_y < cell.bottom
            assert not inside


def test_cut_segments_without_gap_share_edges():
    cells = cell_rects(210, 297, margin=10, gap=0, rows=2, cols=2)
    assert len(cut_segments(cells, 210, 297)) == 12  # 3 positions × 2 margins × 2 directions


def test_cut_segments_none_when_borderless():
    cells = cell_rects(210, 297, margin=0, gap=0, rows=2, cols=2)
    assert cut_segments(cells, 210, 297) == []
