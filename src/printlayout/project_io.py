"""Saving and loading projects as JSON (*.plproj)."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from .model import (
    FitMode,
    GridLayout,
    LayoutMode,
    Orientation,
    PageSettings,
    Photo,
    Project,
    Sheet,
)
from .paper import PAPERS

FILE_FORMAT = "printlayout"
FILE_VERSION = 1
FILE_EXTENSION = ".plproj"


class ProjectError(Exception):
    pass


def to_dict(project: Project, project_path: str) -> dict[str, Any]:
    base = os.path.dirname(os.path.abspath(project_path))
    return {
        "format": FILE_FORMAT,
        "version": FILE_VERSION,
        "page": {
            "paper": project.page.paper,
            "orientation": project.page.orientation.value,
            "margin_mm": project.page.margin_mm,
            "gap_mm": project.page.gap_mm,
        },
        "grid": {"rows": project.grid.rows, "cols": project.grid.cols},
        "mode": project.mode.value,
        "fit_default": project.fit_default.value,
        "auto_rotate": project.auto_rotate,
        "cut_lines": project.cut_lines,
        "fill_sheets": project.fill_sheets,
        "photos": [
            {
                "id": photo.id,
                "path": os.path.abspath(photo.path),
                "relative_path": os.path.relpath(os.path.abspath(photo.path), base),
                "rotation": photo.rotation,
                "fit": photo.fit.value if photo.fit else None,
                "fill_sheet": photo.fill_sheet,
            }
            for photo in project.photos
        ],
        "sheets": [list(sheet) for sheet in project.sheets],
    }


def from_dict(data: dict[str, Any], project_path: str) -> Project:
    if data.get("format") != FILE_FORMAT:
        raise ProjectError("Not a PrintLayout project file.")
    if data.get("version", 0) > FILE_VERSION:
        raise ProjectError("The project was saved by a newer version of PrintLayout.")
    base = os.path.dirname(os.path.abspath(project_path))
    try:
        page_data = data["page"]
        paper = page_data["paper"] if page_data["paper"] in PAPERS else "A4"
        page = PageSettings(
            paper=paper,
            orientation=Orientation(page_data["orientation"]),
            margin_mm=float(page_data["margin_mm"]),
            gap_mm=float(page_data["gap_mm"]),
        )
        grid = GridLayout(rows=max(1, int(data["grid"]["rows"])), cols=max(1, int(data["grid"]["cols"])))
        photos = [
            Photo(
                path=_resolve_path(item.get("relative_path"), item["path"], base),
                id=str(item["id"]),
                rotation=int(item.get("rotation", 0)) % 360 // 90 * 90,
                fit=FitMode(item["fit"]) if item.get("fit") else None,
                fill_sheet=bool(item.get("fill_sheet", False)),
            )
            for item in data["photos"]
        ]
        known = {p.id for p in photos}
        n = grid.cells_per_sheet
        sheets: list[Sheet] = []
        for raw in data.get("sheets", []):
            sheet: Sheet = [pid if pid in known else None for pid in raw][:n]
            sheets.append(sheet + [None] * (n - len(sheet)))
        return Project(
            page=page,
            grid=grid,
            mode=LayoutMode(data["mode"]),
            fit_default=FitMode(data["fit_default"]),
            auto_rotate=bool(data["auto_rotate"]),
            cut_lines=bool(data["cut_lines"]),
            fill_sheets=bool(data.get("fill_sheets", False)),
            photos=photos,
            sheets=sheets,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ProjectError(f"The project file is damaged ({error}).") from error


def _resolve_path(relative: str | None, absolute: str, base: str) -> str:
    """Prefer the path relative to the project file so moved project folders keep working."""
    if relative:
        candidate = os.path.normpath(os.path.join(base, relative))
        if os.path.exists(candidate):
            return candidate
    return absolute


def save(project: Project, path: str) -> None:
    data = to_dict(project, path)
    directory = os.path.dirname(os.path.abspath(path))
    # Write to a temporary file first so a failed save never destroys the previous version.
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".plproj-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise


def load(path: str) -> Project:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as error:
        raise ProjectError(f"The project file is damaged ({error}).") from error
    if not isinstance(data, dict):
        raise ProjectError("Not a PrintLayout project file.")
    return from_dict(data, path)
