"""Distributing photos into sheets."""

from __future__ import annotations

from collections.abc import Collection

from .model import Sheet


def autofill(photo_ids: list[str], cells_per_sheet: int, fill_sheet: Collection[str] = ()) -> list[Sheet]:
    """Fill cells in order, adding sheets as needed. Always returns at least one sheet.

    Photos in `fill_sheet` get a sheet of their own with the photo in every cell; the other
    photos keep flowing around them, so no cells are left empty in between.
    """
    n = cells_per_sheet
    if n <= 0:  # the cell format doesn't fit on the paper
        return [[]]
    sheets: list[Sheet] = []
    current: Sheet = []
    used = n  # cells taken on `current`; n means the next photo starts a new sheet
    for photo_id in photo_ids:
        if photo_id in fill_sheet:
            sheets.append([photo_id] * n)
            continue
        if used == n:
            current = [None] * n
            sheets.append(current)
            used = 0
        current[used] = photo_id
        used += 1
    return sheets or [[None] * n]


def reflow(sheets: list[Sheet], cells_per_sheet: int) -> list[Sheet]:
    """Fit manually arranged sheets into a new grid size.

    Each sheet keeps its photos in order; photos that no longer fit go onto extra sheets
    inserted right after it. Empty sheets stay empty.
    """
    result: list[Sheet] = []
    for sheet in sheets:
        result += autofill([p for p in sheet if p is not None], cells_per_sheet)
    return result or [[None] * cells_per_sheet]
