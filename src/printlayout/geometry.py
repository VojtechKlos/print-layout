"""Layout geometry in millimetres. Pure Python, no Qt."""

from __future__ import annotations

from dataclasses import dataclass

from .formats import CellFormat
from .model import FitMode

_EPS = 1e-6

# A straight line (x0, y0, x1, y1).
Segment = tuple[float, float, float, float]


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom


@dataclass(frozen=True)
class SheetLayout:
    rows: int
    cols: int
    cells: list[Rect]  # row-major
    rotated: bool = False  # exact-size cells turned sideways because more fit that way

    @property
    def count(self) -> int:
        return len(self.cells)


def sheet_layout(
    page_w: float,
    page_h: float,
    margin: float,
    gap: float,
    rows: int,
    cols: int,
    fmt: CellFormat | None = None,
) -> SheetLayout:
    """Cells of a sheet, centred on the page.

    Without a format the rows × columns grid fills the area inside the margins. An aspect-ratio
    format shapes each grid cell to that ratio. An exact-size format ignores rows and columns
    and fits as many cells of that size as possible, turned sideways if more fit that way.
    """
    usable_w, usable_h = page_w - 2 * margin, page_h - 2 * margin
    if fmt is not None and fmt.exact:
        rows, cols, cell_w, cell_h = fit_exact(usable_w, usable_h, gap, fmt.width, fmt.height)
        rotated = abs(cell_w - fmt.width) > _EPS
        return SheetLayout(rows, cols, grid_block(page_w, page_h, rows, cols, cell_w, cell_h, gap), rotated)
    cell_w = max(0.0, (usable_w - (cols - 1) * gap) / cols)
    cell_h = max(0.0, (usable_h - (rows - 1) * gap) / rows)
    if fmt is not None:
        cell_w, cell_h = fit_ratio(cell_w, cell_h, fmt.width, fmt.height)
    return SheetLayout(rows, cols, grid_block(page_w, page_h, rows, cols, cell_w, cell_h, gap))


def cell_rects(
    page_w: float, page_h: float, margin: float, gap: float, rows: int, cols: int
) -> list[Rect]:
    """Cells of a grid filling the area inside the margins. Sizes clamp to 0 if they don't fit."""
    return sheet_layout(page_w, page_h, margin, gap, rows, cols).cells


def grid_block(
    page_w: float, page_h: float, rows: int, cols: int, cell_w: float, cell_h: float, gap: float
) -> list[Rect]:
    """A rows × columns block of equal cells, centred on the page."""
    x0 = (page_w - cols * cell_w - (cols - 1) * gap) / 2
    y0 = (page_h - rows * cell_h - (rows - 1) * gap) / 2
    return [
        Rect(x0 + c * (cell_w + gap), y0 + r * (cell_h + gap), cell_w, cell_h)
        for r in range(rows)
        for c in range(cols)
    ]


def fit_ratio(box_w: float, box_h: float, ratio_w: float, ratio_h: float) -> tuple[float, float]:
    """Largest rectangle of the given aspect ratio, either way round, that fits in the box."""
    best = (0.0, 0.0)
    for w, h in ((ratio_w, ratio_h), (ratio_h, ratio_w)):
        scale = min(box_w / w, box_h / h)
        if (scale * w) * (scale * h) > best[0] * best[1] + _EPS:
            best = (scale * w, scale * h)
    return best


def fit_exact(usable_w: float, usable_h: float, gap: float, w: float, h: float) -> tuple[int, int, float, float]:
    """Most w × h cells that fit, either way round (ties keep w × h). Returns rows, cols, w, h."""
    best = (0, 0, w, h)
    for cell_w, cell_h in ((w, h), (h, w)):
        cols = max(0, int((usable_w + gap + _EPS) // (cell_w + gap)))
        rows = max(0, int((usable_h + gap + _EPS) // (cell_h + gap)))
        if rows * cols > best[0] * best[1]:
            best = (rows, cols, cell_w, cell_h)
    return best


def rotated_size(w: float, h: float, rotation: int) -> tuple[float, float]:
    return (h, w) if rotation % 180 == 90 else (w, h)


def effective_rotation(
    img_w: float, img_h: float, cell_w: float, cell_h: float, user_rotation: int, auto_rotate: bool
) -> int:
    """Clockwise rotation to draw a photo with.

    Auto-rotate turns the photo 90° when its orientation (landscape/portrait) doesn't match the
    cell's; the user's own rotation is applied on top, so "rotate right" always turns the photo
    as currently shown.
    """
    auto = 0
    if (
        auto_rotate
        and abs(img_w - img_h) > _EPS
        and abs(cell_w - cell_h) > _EPS
        and (img_w > img_h) != (cell_w > cell_h)
    ):
        auto = 90
    return (auto + user_rotation) % 360


def placement(img_w: float, img_h: float, cell: Rect, fit: FitMode) -> tuple[Rect, Rect]:
    """Where an (already rotated) image goes inside a cell.

    Returns (source rect in image pixels, target rect in page mm).
    FIT shows the whole image centred in the cell; FILL covers the cell with a centred crop.
    """
    if fit is FitMode.FIT:
        scale = min(cell.w / img_w, cell.h / img_h)
        tw, th = img_w * scale, img_h * scale
        target = Rect(cell.x + (cell.w - tw) / 2, cell.y + (cell.h - th) / 2, tw, th)
        return Rect(0, 0, img_w, img_h), target
    scale = max(cell.w / img_w, cell.h / img_h)
    sw, sh = cell.w / scale, cell.h / scale
    return Rect((img_w - sw) / 2, (img_h - sh) / 2, sw, sh), cell


def _unique(values: list[float]) -> list[float]:
    return sorted({round(v, 6) for v in values})


def _free_intervals(occupied: list[tuple[float, float]], length: float) -> list[tuple[float, float]]:
    free: list[tuple[float, float]] = []
    pos = 0.0
    for start, end in sorted(occupied):
        if start - pos > _EPS:
            free.append((pos, start))
        pos = max(pos, end)
    if length - pos > _EPS:
        free.append((pos, length))
    return free


def cut_segments(cells: list[Rect], page_w: float, page_h: float) -> list[Segment]:
    """Cut guides along the cell edges, extended to the paper edge.

    Lines are drawn only in the margins and gaps, never across a photo.
    """
    if not cells or cells[0].w <= 0 or cells[0].h <= 0:
        return []
    col_spans = list({(round(c.x, 6), round(c.right, 6)) for c in cells})
    row_spans = list({(round(c.y, 6), round(c.bottom, 6)) for c in cells})
    segments: list[Segment] = []
    for x in _unique([c.x for c in cells] + [c.right for c in cells]):
        segments += [(x, y0, x, y1) for y0, y1 in _free_intervals(row_spans, page_h)]
    for y in _unique([c.y for c in cells] + [c.bottom for c in cells]):
        segments += [(x0, y, x1, y) for x0, x1 in _free_intervals(col_spans, page_w)]
    return segments
