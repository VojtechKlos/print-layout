"""Distributing photos into sheets."""

from __future__ import annotations

from .model import Sheet


def autofill(photo_ids: list[str], cells_per_sheet: int) -> list[Sheet]:
    """Fill cells in order, adding sheets as needed. Always returns at least one sheet."""
    n = cells_per_sheet
    sheets: list[Sheet] = []
    for start in range(0, len(photo_ids), n):
        chunk: Sheet = list(photo_ids[start : start + n])
        sheets.append(chunk + [None] * (n - len(chunk)))
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
