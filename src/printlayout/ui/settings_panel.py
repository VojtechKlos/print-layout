"""Paper, grid, spacing and photo options."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..document import Document
from ..formats import FORMAT_GROUPS, FORMATS, CellFormat
from ..geometry import SheetLayout
from ..layout import project_layout
from ..model import FitMode, LayoutMode, Orientation
from ..paper import PAPERS

# (label, rows, columns)
PRESETS: list[tuple[str, int, int]] = [
    ("1 — full page", 1, 1),
    ("2 — one above the other", 2, 1),
    ("2 — side by side", 1, 2),
    ("4 — 2 × 2", 2, 2),
    ("6 — 3 rows × 2 columns", 3, 2),
    ("6 — 2 rows × 3 columns", 2, 3),
    ("8 — 4 rows × 2 columns", 4, 2),
    ("9 — 3 × 3", 3, 3),
    ("16 — 4 × 4", 4, 4),
]
MAX_GRID = 12
MIN_CELL_MM = 10


@contextmanager
def _signals_blocked(*widgets: QWidget) -> Iterator[None]:
    for widget in widgets:
        widget.blockSignals(True)
    try:
        yield
    finally:
        for widget in widgets:
            widget.blockSignals(False)


def _mm_spin_box() -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0, 50)
    spin.setDecimals(1)
    spin.setSingleStep(0.5)
    spin.setSuffix(" mm")
    spin.setKeyboardTracking(False)
    return spin


def _grid_spin_box() -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(1, MAX_GRID)
    spin.setKeyboardTracking(False)
    spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
    return spin


class SettingsPanel(QWidget):
    def __init__(self, document: Document, parent: QWidget | None = None):
        super().__init__(parent)
        self._doc = document

        # Arrangement
        self._auto = QRadioButton(self.tr("Automatic"))
        self._manual = QRadioButton(self.tr("Manual"))
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._auto)
        self._mode_group.addButton(self._manual)
        self._fill_sheets = QCheckBox(self.tr("Each photo fills a whole sheet"))
        self._fill_sheets.setToolTip(
            self.tr("Every photo gets its own sheet with the photo in every cell (automatic arrangement)")
        )
        self._mode_hint = QLabel()
        self._mode_hint.setWordWrap(True)
        self._mode_hint.setEnabled(False)  # greyed-out help text
        mode_row = QHBoxLayout()
        mode_row.addWidget(self._auto)
        mode_row.addWidget(self._manual)
        mode_row.addStretch()
        mode_box = QGroupBox(self.tr("Arrangement"))
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.addLayout(mode_row)
        mode_layout.addWidget(self._fill_sheets)
        mode_layout.addWidget(self._mode_hint)

        # Paper
        self._paper = QComboBox()
        for paper in PAPERS.values():
            self._paper.addItem(paper.label, paper.key)
        self._orientation = QComboBox()
        self._orientation.addItem(self.tr("Portrait"), Orientation.PORTRAIT.value)
        self._orientation.addItem(self.tr("Landscape"), Orientation.LANDSCAPE.value)
        paper_box = QGroupBox(self.tr("Paper"))
        paper_form = QFormLayout(paper_box)
        paper_form.addRow(self.tr("Size:"), self._paper)
        paper_form.addRow(self.tr("Orientation:"), self._orientation)

        # Layout
        self._format = QComboBox()
        self._format.addItem(self.tr("Fill the page"), "")
        for group, formats in FORMAT_GROUPS:
            self._format.insertSeparator(self._format.count())
            self._format.addItem(self.tr(group))
            self._format.model().item(self._format.count() - 1).setEnabled(False)  # heading
            for fmt in formats:
                self._format.addItem(self.tr(fmt.label), fmt.key)
        self._format.setToolTip(
            self.tr("Aspect ratios keep your rows × columns; exact sizes fit as many as the paper holds")
        )
        self._preset = QComboBox()
        for label, _, _ in PRESETS:
            self._preset.addItem(self.tr(label))
        self._preset.addItem(self.tr("Custom"))
        self._rows = _grid_spin_box()
        self._cols = _grid_spin_box()
        grid_row = QHBoxLayout()
        grid_row.addWidget(self._rows)
        grid_row.addWidget(QLabel("×"))
        grid_row.addWidget(self._cols)
        grid_row.addStretch()
        self._margin = _mm_spin_box()
        self._gap = _mm_spin_box()
        layout_box = QGroupBox(self.tr("Layout"))
        layout_form = QFormLayout(layout_box)
        layout_form.addRow(self.tr("Format:"), self._format)
        layout_form.addRow(self.tr("Photos per sheet:"), self._preset)
        layout_form.addRow(self.tr("Rows × columns:"), grid_row)
        layout_form.addRow(self.tr("Margin:"), self._margin)
        layout_form.addRow(self.tr("Gap:"), self._gap)

        # Photos
        self._fit = QRadioButton(self.tr("Fit — show whole photo"))
        self._fill = QRadioButton(self.tr("Fill — crop to cell"))
        fit_group = QButtonGroup(self)
        fit_group.addButton(self._fit)
        fit_group.addButton(self._fill)
        self._auto_rotate = QCheckBox(self.tr("Rotate photos to match cells"))
        self._cut_lines = QCheckBox(self.tr("Cut lines"))
        self._cut_lines.setToolTip(self.tr("Thin guide lines in the margins and gaps for cutting the photos apart"))
        photos_box = QGroupBox(self.tr("Photos"))
        photos_layout = QVBoxLayout(photos_box)
        for widget in (self._fit, self._fill, self._auto_rotate, self._cut_lines):
            photos_layout.addWidget(widget)

        self._info = QLabel()
        self._info.setWordWrap(True)

        layout = QVBoxLayout(self)
        for widget in (mode_box, paper_box, layout_box, photos_box, self._info):
            layout.addWidget(widget)
        layout.addStretch()

        self._mode_group.buttonClicked.connect(self._on_mode_clicked)
        self._fill_sheets.toggled.connect(document.set_fill_sheets)
        self._paper.currentIndexChanged.connect(lambda: document.set_paper(self._paper.currentData()))
        self._orientation.currentIndexChanged.connect(
            lambda: document.set_orientation(Orientation(self._orientation.currentData()))
        )
        self._format.activated.connect(lambda: document.set_format(self._format.currentData() or ""))
        self._preset.activated.connect(self._on_preset)
        self._rows.valueChanged.connect(lambda: document.set_grid(self._rows.value(), self._cols.value()))
        self._cols.valueChanged.connect(lambda: document.set_grid(self._rows.value(), self._cols.value()))
        self._margin.valueChanged.connect(document.set_margin)
        self._gap.valueChanged.connect(document.set_gap)
        self._fit.toggled.connect(lambda on: on and document.set_fit_default(FitMode.FIT))
        self._fill.toggled.connect(lambda on: on and document.set_fit_default(FitMode.FILL))
        self._auto_rotate.toggled.connect(document.set_auto_rotate)
        self._cut_lines.toggled.connect(document.set_cut_lines)
        document.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        project = self._doc.project
        page, grid = project.page, project.grid
        layout = project_layout(project)
        fmt = FORMATS.get(grid.format)
        exact = fmt is not None and fmt.exact
        # Exact sizes decide rows and columns themselves; show what fits.
        rows, cols = (layout.rows, layout.cols) if exact else (grid.rows, grid.cols)
        widgets = (
            self._auto, self._manual, self._fill_sheets, self._paper, self._orientation, self._format,
            self._preset, self._rows, self._cols, self._margin, self._gap, self._fit, self._fill,
            self._auto_rotate, self._cut_lines,
        )  # fmt: skip
        with _signals_blocked(*widgets):
            manual = project.mode is LayoutMode.MANUAL
            self._manual.setChecked(manual)
            self._auto.setChecked(not manual)
            self._fill_sheets.setChecked(project.fill_sheets)
            self._fill_sheets.setEnabled(not manual)  # manual sheets are arranged by hand
            self._paper.setCurrentIndex(self._paper.findData(page.paper))
            self._orientation.setCurrentIndex(self._orientation.findData(page.orientation.value))
            self._format.setCurrentIndex(max(0, self._format.findData(grid.format)))
            preset = next((i for i, (_, r, c) in enumerate(PRESETS) if (r, c) == (rows, cols)), len(PRESETS))
            self._preset.setCurrentIndex(preset)
            for widget in (self._preset, self._rows, self._cols):
                widget.setEnabled(not exact)
            # Only touch spin boxes whose value differs, so typing in them isn't disturbed.
            for spin, value in [
                (self._rows, rows),
                (self._cols, cols),
                (self._margin, page.margin_mm),
                (self._gap, page.gap_mm),
            ]:
                if spin.value() != value:
                    spin.setValue(value)
            self._fit.setChecked(project.fit_default is FitMode.FIT)
            self._fill.setChecked(project.fit_default is FitMode.FILL)
            self._auto_rotate.setChecked(project.auto_rotate)
            self._cut_lines.setChecked(project.cut_lines)

        self._mode_hint.setText(
            self.tr("Drag photos from the list onto cells. Drag between cells to swap.")
            if manual
            else self.tr("Photos fill the cells in list order. Drag in the list to reorder.")
        )
        self._info.setText(self._layout_info(layout, fmt))

    def _layout_info(self, layout: SheetLayout, fmt: CellFormat | None) -> str:
        if not layout.cells:
            return self.tr("⚠ {0} doesn't fit on this paper with these margins.").format(self.tr(fmt.label))
        cell = layout.cells[0]
        if cell.w < MIN_CELL_MM or cell.h < MIN_CELL_MM:
            return self.tr("⚠ Margins and gaps leave too little room for the photos.")
        text = self.tr("{0} per sheet · {1:.1f} × {2:.1f} mm each").format(layout.count, cell.w, cell.h)
        if layout.rotated:
            text += "\n" + self.tr("Turned sideways because more fit that way.")
        return text

    def _on_preset(self, index: int) -> None:
        if index < len(PRESETS):
            _, rows, cols = PRESETS[index]
            self._doc.set_grid(rows, cols)

    def _on_mode_clicked(self) -> None:
        if self._auto.isChecked():
            if self._doc.project.mode is LayoutMode.MANUAL and self._doc.auto_layout_differs():
                answer = QMessageBox.question(
                    self,
                    self.tr("Switch to automatic"),
                    self.tr(
                        "Automatic arrangement places all photos in list order and replaces "
                        "your manual arrangement.\n\nSwitch anyway?"
                    ),
                )
                if answer != QMessageBox.StandardButton.Yes:
                    self.refresh()
                    return
            self._doc.set_mode(LayoutMode.AUTO)
        else:
            self._doc.set_mode(LayoutMode.MANUAL)
