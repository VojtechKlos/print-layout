"""Supported paper sizes."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize

from .model import Orientation, PageSettings


@dataclass(frozen=True)
class Paper:
    key: str
    label: str
    width_mm: float
    height_mm: float
    qt_id: QPageSize.PageSizeId | None = None  # standard size known to printer drivers


PAPERS: dict[str, Paper] = {
    p.key: p
    for p in [
        Paper("A4", "A4 (210 × 297 mm)", 210, 297, QPageSize.PageSizeId.A4),
        Paper("A3", "A3 (297 × 420 mm)", 297, 420, QPageSize.PageSizeId.A3),
        Paper("A5", "A5 (148 × 210 mm)", 148, 210, QPageSize.PageSizeId.A5),
        # Photo paper sold as "10 × 15" and "13 × 18" is really 4 × 6 and 5 × 7 inches.
        Paper("10x15", "Photo 10 × 15 cm (4 × 6″)", 101.6, 152.4),
        Paper("13x18", "Photo 13 × 18 cm (5 × 7″)", 127, 177.8),
    ]
}


def page_size_mm(page: PageSettings) -> tuple[float, float]:
    """Paper (width, height) in mm, taking orientation into account."""
    paper = PAPERS[page.paper]
    if page.orientation is Orientation.LANDSCAPE:
        return paper.height_mm, paper.width_mm
    return paper.width_mm, paper.height_mm


def qt_page_size(key: str) -> QPageSize:
    paper = PAPERS[key]
    if paper.qt_id is not None:
        return QPageSize(paper.qt_id)
    return QPageSize(
        QSizeF(paper.width_mm, paper.height_mm),
        QPageSize.Unit.Millimeter,
        paper.label,
        QPageSize.SizeMatchPolicy.ExactMatch,
    )


def qt_page_layout(page: PageSettings) -> QPageLayout:
    orientation = (
        QPageLayout.Orientation.Landscape
        if page.orientation is Orientation.LANDSCAPE
        else QPageLayout.Orientation.Portrait
    )
    return QPageLayout(
        qt_page_size(page.paper), orientation, QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter
    )
