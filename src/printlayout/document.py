"""The open project and every operation that changes it."""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal

from . import project_io
from .autofill import autofill, reflow
from .model import FitMode, LayoutMode, Orientation, Photo, Project, Sheet


class Document(QObject):
    changed = Signal()  # anything that affects what is drawn
    photos_changed = Signal()  # photos added, removed or reordered
    state_changed = Signal()  # file path or unsaved-changes flag
    message = Signal(str)  # short note for the status bar

    def __init__(self) -> None:
        super().__init__()
        self.project = Project()
        self.path: str | None = None
        self.dirty = False
        self._relayout()

    # --- file ---------------------------------------------------------------------------

    def new(self) -> None:
        self._replace(Project(), None)

    def load(self, path: str) -> None:
        self._replace(project_io.load(path), os.path.abspath(path))

    def save(self, path: str) -> None:
        project_io.save(self.project, path)
        self.path = os.path.abspath(path)
        self.dirty = False
        self.state_changed.emit()

    def _replace(self, project: Project, path: str | None) -> None:
        self.project = project
        self.path = path
        self._relayout()
        self.dirty = False
        self.photos_changed.emit()
        self.changed.emit()
        self.state_changed.emit()

    # --- photos -------------------------------------------------------------------------

    def add_photos(self, paths: list[str]) -> list[Photo]:
        photos = [Photo(path=os.path.abspath(p)) for p in paths]
        if photos:
            self.project.photos += photos
            self._touch(photos_changed=True)
        return photos

    def duplicate_photos(self, photo_ids: list[str]) -> None:
        originals = self._photos(photo_ids)
        if not originals:
            return
        last = max(self.project.photos.index(p) for p in originals)
        copies = [Photo(path=p.path, rotation=p.rotation, fit=p.fit, fill_sheet=p.fill_sheet) for p in originals]
        self.project.photos[last + 1 : last + 1] = copies
        self._touch(photos_changed=True)

    def remove_photos(self, photo_ids: list[str]) -> None:
        ids = set(photo_ids)
        self.project.photos = [p for p in self.project.photos if p.id not in ids]
        self.project.sheets = [[None if pid in ids else pid for pid in s] for s in self.project.sheets]
        self._touch(photos_changed=True)

    def reorder_photos(self, photo_ids: list[str]) -> None:
        by_id = {p.id: p for p in self.project.photos}
        if sorted(photo_ids) != sorted(by_id) or photo_ids == [p.id for p in self.project.photos]:
            return
        self.project.photos = [by_id[pid] for pid in photo_ids]
        self._touch(photos_changed=True)

    def rotate_photos(self, photo_ids: list[str], degrees: int) -> None:
        for photo in self._photos(photo_ids):
            photo.rotation = (photo.rotation + degrees) % 360
        self._touch()

    def set_photo_fit(self, photo_ids: list[str], fit: FitMode | None) -> None:
        for photo in self._photos(photo_ids):
            photo.fit = fit
        self._touch()

    def set_photo_fill_sheet(self, photo_ids: list[str], enabled: bool) -> None:
        """Automatic mode: give these photos a sheet of their own with every cell filled."""
        for photo in self._photos(photo_ids):
            photo.fill_sheet = enabled
        self._touch()

    def _photos(self, photo_ids: list[str]) -> list[Photo]:
        ids = set(photo_ids)
        return [p for p in self.project.photos if p.id in ids]

    # --- page and layout settings -------------------------------------------------------

    def set_paper(self, key: str) -> None:
        self._set(self.project.page, "paper", key)

    def set_orientation(self, orientation: Orientation) -> None:
        self._set(self.project.page, "orientation", orientation)

    def set_margin(self, mm: float) -> None:
        self._set(self.project.page, "margin_mm", mm)

    def set_gap(self, mm: float) -> None:
        self._set(self.project.page, "gap_mm", mm)

    def set_fit_default(self, fit: FitMode) -> None:
        self._set(self.project, "fit_default", fit)

    def set_auto_rotate(self, enabled: bool) -> None:
        self._set(self.project, "auto_rotate", enabled)

    def set_cut_lines(self, enabled: bool) -> None:
        self._set(self.project, "cut_lines", enabled)

    def set_fill_sheets(self, enabled: bool) -> None:
        """Automatic mode: every photo fills a sheet of its own."""
        self._set(self.project, "fill_sheets", enabled)

    def set_grid(self, rows: int, cols: int) -> None:
        grid = self.project.grid
        if (grid.rows, grid.cols) == (rows, cols):
            return
        grid.rows, grid.cols = rows, cols
        if self.project.mode is LayoutMode.MANUAL:
            self.project.sheets = reflow(self.project.sheets, grid.cells_per_sheet)
        self._touch()

    def set_mode(self, mode: LayoutMode) -> None:
        # Switching to manual keeps the current arrangement as the starting point;
        # switching to auto re-flows all photos in list order.
        self._set(self.project, "mode", mode)

    def auto_layout_differs(self) -> bool:
        """True if switching to auto mode would change the current arrangement."""
        return self._auto_sheets() != self.project.sheets

    def _set(self, target: object, name: str, value: object) -> None:
        if getattr(target, name) != value:
            setattr(target, name, value)
            self._touch()

    # --- arranging cells ----------------------------------------------------------------

    def place_photos(self, sheet_index: int, cell_index: int, photo_ids: list[str]) -> None:
        """Put photos into a cell, continuing into the following empty cells of the sheet."""
        if not photo_ids:
            return
        self._ensure_manual()
        sheet = self.project.sheets[sheet_index]
        targets = [cell_index] + [i for i in range(cell_index + 1, len(sheet)) if sheet[i] is None]
        for index, photo_id in zip(targets, photo_ids):
            sheet[index] = photo_id
        self._touch()

    def fill_empty_cells(self, sheet_index: int, photo_id: str) -> None:
        self._ensure_manual()
        sheet = self.project.sheets[sheet_index]
        self.project.sheets[sheet_index] = [photo_id if pid is None else pid for pid in sheet]
        self._touch()

    def clear_cell(self, sheet_index: int, cell_index: int) -> None:
        self.project.sheets[sheet_index][cell_index] = None
        self._touch()

    def move_cell(self, sheet_index: int, from_cell: int, to_cell: int) -> None:
        """Drag one cell onto another: the two contents swap places."""
        if from_cell == to_cell:
            return
        sheet = self.project.sheets[sheet_index]
        if self.project.mode is LayoutMode.AUTO:
            # In auto mode the arrangement follows the photo list, so reorder the list:
            # swap the two photos, or move the photo to the end when dropped on an empty cell.
            moved, target = sheet[from_cell], sheet[to_cell]
            if moved is None or moved == target:
                return
            ids = [p.id for p in self.project.photos]
            i = ids.index(moved)
            if target is None:
                ids.append(ids.pop(i))
            else:
                j = ids.index(target)
                ids[i], ids[j] = ids[j], ids[i]
            self.reorder_photos(ids)
            return
        sheet[from_cell], sheet[to_cell] = sheet[to_cell], sheet[from_cell]
        self._touch()

    def add_sheet(self) -> int:
        self._ensure_manual()
        self.project.sheets.append([None] * self.project.grid.cells_per_sheet)
        self._touch()
        return len(self.project.sheets) - 1

    def remove_sheet(self, sheet_index: int) -> None:
        if len(self.project.sheets) > 1:
            del self.project.sheets[sheet_index]
        else:
            self.project.sheets = [[None] * self.project.grid.cells_per_sheet]
        self._touch()

    def _ensure_manual(self) -> None:
        if self.project.mode is LayoutMode.AUTO:
            self.project.mode = LayoutMode.MANUAL
            self.message.emit(self.tr("Switched to manual layout."))

    # --- bookkeeping --------------------------------------------------------------------

    def _auto_sheets(self) -> list[Sheet]:
        project = self.project
        ids = [p.id for p in project.photos]
        fill = {p.id for p in project.photos if project.fills_sheet(p)}
        return autofill(ids, project.grid.cells_per_sheet, fill)

    def _relayout(self) -> None:
        if self.project.mode is LayoutMode.AUTO or not self.project.sheets:
            self.project.sheets = self._auto_sheets()

    def _touch(self, photos_changed: bool = False) -> None:
        self._relayout()
        was_dirty = self.dirty
        self.dirty = True
        if photos_changed:
            self.photos_changed.emit()
        self.changed.emit()
        if not was_dirty:
            self.state_changed.emit()
