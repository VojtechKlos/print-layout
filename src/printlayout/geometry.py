"""Layout geometry in millimetres. Pure Python, no Qt."""

from __future__ import annotations

from dataclasses import dataclass

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


def cell_rects(
    page_w: float, page_h: float, margin: float, gap: float, rows: int, cols: int
) -> list[Rect]:
    """Cells of a uniform grid in row-major order. Sizes clamp to 0 if margins/gaps don't fit."""
    cell_w = max(0.0, (page_w - 2 * margin - (cols - 1) * gap) / cols)
    cell_h = max(0.0, (page_h - 2 * margin - (rows - 1) * gap) / rows)
    return [
        Rect(margin + c * (cell_w + gap), margin + r * (cell_h + gap), cell_w, cell_h)
        for r in range(rows)
        for c in range(cols)
    ]


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
