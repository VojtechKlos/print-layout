"""Printing and PDF export."""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import (
    QAbstractPrintDialog,
    QPrintDialog,
    QPrinter,
    QPrinterInfo,
)
from PySide6.QtWidgets import QDialog, QMessageBox, QProgressDialog, QWidget

from .imagecache import load_image
from .model import PageSettings, Project
from .paper import PAPERS, page_size_mm, qt_page_layout, qt_page_size
from .render import MM_PER_INCH, ImageGetter, render_sheet

PDF_DPI = 300
# Paper sizes this close count as the same (e.g. 10 × 15 cm vs. 4 × 6 in).
PAPER_TOLERANCE_MM = 3


def tr(text: str) -> str:
    return QCoreApplication.translate("output", text)


def printable_sheets(project: Project, first: int = 0, last: int | None = None) -> list[int]:
    """Indices of sheets in [first, last] that contain at least one photo."""
    last = len(project.sheets) - 1 if last is None else last
    return [
        i
        for i, sheet in enumerate(project.sheets)
        if first <= i <= last and any(pid is not None for pid in sheet)
    ]


def missing_files(project: Project, sheets: list[int]) -> list[str]:
    paths = {
        photo.path
        for i in sheets
        for pid in project.sheets[i]
        if (photo := project.photo(pid)) is not None
    }
    return sorted(p for p in paths if not os.path.isfile(p))


def export_pdf(project: Project, path: str, parent: QWidget) -> bool:
    sheets = printable_sheets(project)
    if not _check_sheets(parent, sheets) or not _confirm_missing(parent, project, sheets):
        return False
    writer = QPdfWriter(path)
    writer.setResolution(PDF_DPI)
    writer.setPageLayout(qt_page_layout(project.page))
    writer.setCreator("PrintLayout")
    writer.setTitle(os.path.splitext(os.path.basename(path))[0])
    painter = QPainter()
    if not painter.begin(writer):
        QMessageBox.critical(parent, tr("Export failed"), tr("Could not write {0}.").format(path))
        return False
    ok = _render_sheets(
        painter, project, sheets, PDF_DPI / MM_PER_INCH, writer.newPage, parent, tr("Exporting PDF…")
    )
    painter.end()
    if not ok:
        try:
            os.remove(path)
        except OSError:
            pass
    return ok


def print_project(project: Project, parent: QWidget, doc_name: str) -> bool:
    if not _check_sheets(parent, printable_sheets(project)):
        return False
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(doc_name)
    # Not setPageLayout(): printers reject a layout whose zero margins are below their minimum.
    printer.setPageSize(_printer_page_size(printer, project.page))
    printer.setPageOrientation(qt_page_layout(project.page).orientation())
    # Coordinates start at the physical paper corner, so layout margins are real millimetres.
    printer.setFullPage(True)
    dialog = QPrintDialog(printer, parent)
    dialog.setOption(QAbstractPrintDialog.PrintDialogOption.PrintPageRange, True)
    dialog.setMinMax(1, len(project.sheets))
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False

    if printer.printRange() == QPrinter.PrintRange.PageRange:
        sheets = printable_sheets(project, printer.fromPage() - 1, printer.toPage() - 1)
    else:
        sheets = printable_sheets(project)
    if not (
        _check_sheets(parent, sheets)
        and _confirm_paper(parent, project, printer)
        and _confirm_margins(parent, project, printer)
        and _confirm_missing(parent, project, sheets)
    ):
        return False

    painter = QPainter()
    if not painter.begin(printer):
        QMessageBox.critical(parent, tr("Printing failed"), tr("Could not start printing."))
        return False
    ok = _render_sheets(
        painter,
        project,
        sheets,
        printer.resolution() / MM_PER_INCH,
        printer.newPage,
        parent,
        tr("Printing…"),
    )
    if not ok:
        printer.abort()
    painter.end()
    return ok


def _render_sheets(
    painter: QPainter,
    project: Project,
    sheets: list[int],
    px_per_mm: float,
    new_page: Callable[[], bool],
    parent: QWidget,
    title: str,
) -> bool:
    progress = QProgressDialog(title, tr("Cancel"), 0, len(sheets), parent)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(400)
    for n, index in enumerate(sheets):
        progress.setValue(n)
        if progress.wasCanceled() or (n and not new_page()):
            return False
        render_sheet(painter, project, project.sheets[index], px_per_mm, _sheet_image_loader())
    progress.setValue(len(sheets))
    return True


def _sheet_image_loader() -> ImageGetter:
    """Full-resolution loader for one sheet; dropped afterwards to keep memory low."""
    images: dict[str, QImage | None] = {}

    def get_image(path: str) -> QImage | None:
        if path not in images:
            images[path] = load_image(path)
        return images[path]

    return get_image


def _printer_page_size(printer: QPrinter, page: PageSettings) -> QPageSize:
    """The printer's own size for the layout paper, so the driver picks the right media.

    Drivers name photo sizes differently ("IndexCard 10x15 cm", "Photo 2L 127x178mm"),
    so sizes are matched by dimensions.
    """
    paper = PAPERS[page.paper]
    best: tuple[float, QPageSize] | None = None
    for size in QPrinterInfo(printer).supportedPageSizes():
        mm = size.size(QPageSize.Unit.Millimeter)
        diff = max(abs(mm.width() - paper.width_mm), abs(mm.height() - paper.height_mm))
        if diff <= PAPER_TOLERANCE_MM and (best is None or diff < best[0]):
            best = (diff, size)
    return best[1] if best else qt_page_size(page.paper)


def _check_sheets(parent: QWidget, sheets: list[int]) -> bool:
    if not sheets:
        QMessageBox.information(parent, tr("Nothing to output"), tr("There are no photos on the selected sheets."))
    return bool(sheets)


def _confirm_missing(parent: QWidget, project: Project, sheets: list[int]) -> bool:
    missing = missing_files(project, sheets)
    if not missing:
        return True
    names = "\n".join(os.path.basename(p) for p in missing[:10])
    more = tr("\n…and {0} more").format(len(missing) - 10) if len(missing) > 10 else ""
    return _ask(
        parent,
        tr("Missing photos"),
        tr("These photos could not be found and their cells will stay blank:\n\n{0}{1}\n\nContinue?").format(
            names, more
        ),
    )


def _confirm_paper(parent: QWidget, project: Project, printer: QPrinter) -> bool:
    chosen = printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
    want_w, want_h = page_size_mm(project.page)
    if abs(chosen.width() - want_w) <= PAPER_TOLERANCE_MM and abs(chosen.height() - want_h) <= PAPER_TOLERANCE_MM:
        return True
    return _ask(
        parent,
        tr("Different paper size"),
        tr(
            "The print dialog is set to {0:.0f} × {1:.0f} mm paper, but the layout is made for "
            "{2:.0f} × {3:.0f} mm. The printout may be cut off or misplaced.\n\nPrint anyway?"
        ).format(chosen.width(), chosen.height(), want_w, want_h),
    )


def _confirm_margins(parent: QWidget, project: Project, printer: QPrinter) -> bool:
    layout = QPageLayout(printer.pageLayout())
    layout.setUnits(QPageLayout.Unit.Millimeter)
    m = layout.minimumMargins()
    margin = project.page.margin_mm
    sides = [(tr("left"), m.left()), (tr("top"), m.top()), (tr("right"), m.right()), (tr("bottom"), m.bottom())]
    too_close = [(side, mm) for side, mm in sides if margin + 0.05 < mm]
    if not too_close:
        return True
    needed = max(mm for _, mm in too_close)
    return _ask(
        parent,
        tr("Margin too small"),
        tr(
            "This printer cannot print within {0:.1f} mm of the paper edge ({1}), but the layout "
            "margin is {2:.1f} mm, so the photos will be cut off there.\n\n"
            "To avoid this, set the margin to at least {0:.1f} mm.\n\nPrint anyway?"
        ).format(needed, ", ".join(side for side, _ in too_close), margin),
    )


def _ask(parent: QWidget, title: str, text: str) -> bool:
    answer = QMessageBox.warning(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes
