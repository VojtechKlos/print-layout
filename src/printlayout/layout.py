"""The cell layout of a project's sheets."""

from __future__ import annotations

from .formats import FORMATS
from .geometry import SheetLayout, sheet_layout
from .model import Project
from .paper import page_size_mm


def project_layout(project: Project) -> SheetLayout:
    """Cells for the project's paper, margins, gap, grid and cell format."""
    page_w, page_h = page_size_mm(project.page)
    return sheet_layout(
        page_w,
        page_h,
        project.page.margin_mm,
        project.page.gap_mm,
        project.grid.rows,
        project.grid.cols,
        FORMATS.get(project.grid.format),
    )
