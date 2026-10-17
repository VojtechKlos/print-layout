"""Data model of a print layout project."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class FitMode(StrEnum):
    FIT = "fit"  # whole photo visible, empty space around it
    FILL = "fill"  # photo covers the whole cell, centre-cropped


class LayoutMode(StrEnum):
    AUTO = "auto"  # photos flow into cells in photo-list order
    MANUAL = "manual"  # the user places photos into cells


class Orientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class PageSettings:
    paper: str = "A4"
    orientation: Orientation = Orientation.PORTRAIT
    margin_mm: float = 5.0
    gap_mm: float = 5.0


@dataclass
class GridLayout:
    rows: int = 2
    cols: int = 2
    # Key into formats.FORMATS; "" fills the page. Exact-size formats ignore rows and cols,
    # so the number of cells per sheet comes from layout.project_layout(), not from here.
    format: str = ""


@dataclass
class Photo:
    path: str
    id: str = field(default_factory=new_id)
    rotation: int = 0  # clockwise degrees chosen by the user: 0, 90, 180 or 270
    fit: FitMode | None = None  # None = use the project default
    fill_sheet: bool = False  # automatic mode: own sheet with the photo in every cell


# Photo ids in row-major cell order; None marks an empty cell.
Sheet = list[str | None]


@dataclass
class Project:
    page: PageSettings = field(default_factory=PageSettings)
    grid: GridLayout = field(default_factory=GridLayout)
    mode: LayoutMode = LayoutMode.AUTO
    fit_default: FitMode = FitMode.FILL
    auto_rotate: bool = True
    cut_lines: bool = False
    fill_sheets: bool = False  # automatic mode: every photo fills a sheet of its own
    photos: list[Photo] = field(default_factory=list)
    sheets: list[Sheet] = field(default_factory=list)

    def photo(self, photo_id: str | None) -> Photo | None:
        if photo_id is None:
            return None
        return next((p for p in self.photos if p.id == photo_id), None)

    def fit_for(self, photo: Photo) -> FitMode:
        return photo.fit or self.fit_default

    def fills_sheet(self, photo: Photo) -> bool:
        return self.fill_sheets or photo.fill_sheet

    def sheets_with(self, photo_id: str) -> list[int]:
        return [i for i, sheet in enumerate(self.sheets) if photo_id in sheet]
