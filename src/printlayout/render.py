"""Drawing a sheet with QPainter, shared by the preview, printing and PDF export."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QTransform

from .geometry import (
    Rect,
    cut_segments,
    effective_rotation,
    placement,
    rotated_size,
)
from .layout import project_layout
from .model import Photo, Project, Sheet
from .paper import page_size_mm

MM_PER_INCH = 25.4
MAX_IMAGE_DPI = 300  # photos are downscaled to this before drawing; enough for photo printers
CUT_LINE_WIDTH_MM = 0.2
CUT_LINE_COLOR = QColor(140, 140, 140)

ImageGetter = Callable[[str], QImage | None]


def sheet_cells(project: Project) -> list[Rect]:
    return project_layout(project).cells


def render_sheet(
    painter: QPainter,
    project: Project,
    sheet: Sheet,
    px_per_mm: float,
    get_image: ImageGetter,
    placeholders: bool = False,
    empty_text: str = "",
    missing_text: str = "Missing file",
) -> None:
    """Draw one sheet with the painter's origin at the paper's top-left corner.

    `px_per_mm` maps mm to the painter's logical units. `placeholders` outlines empty cells
    and marks missing files (preview only, never printed).
    """
    cells = sheet_cells(project)
    device_scale = painter.device().devicePixelRatio() if painter.device() else 1.0
    image_px_per_mm = min(px_per_mm * device_scale, MAX_IMAGE_DPI / MM_PER_INCH)
    empty: list[Rect] = []
    missing: list[Rect] = []

    painter.save()
    painter.scale(px_per_mm, px_per_mm)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, cell in enumerate(cells):
        photo = project.photo(sheet[index] if index < len(sheet) else None)
        image = get_image(photo.path) if photo else None
        if cell.w <= 0 or cell.h <= 0:
            continue
        if photo and image:
            _draw_photo(painter, project, photo, image, cell, image_px_per_mm)
        elif photo:
            missing.append(cell)
        else:
            empty.append(cell)

    if project.cut_lines:
        pen = QPen(CUT_LINE_COLOR, CUT_LINE_WIDTH_MM)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        for x0, y0, x1, y1 in cut_segments(cells, *page_size_mm(project.page)):
            painter.drawLine(QLineF(x0, y0, x1, y1))
    painter.restore()

    if placeholders:
        _draw_placeholders(painter, px_per_mm, empty, missing, empty_text, missing_text)


def _draw_photo(
    painter: QPainter,
    project: Project,
    photo: Photo,
    image: QImage,
    cell: Rect,
    image_px_per_mm: float,
) -> None:
    rotation = effective_rotation(
        image.width(), image.height(), cell.w, cell.h, photo.rotation, project.auto_rotate
    )
    fit = project.fit_for(photo)
    # Downscale to the resolution the output actually needs (smaller PDFs, faster printing),
    # then rotate the small copy.
    source, target = placement(*rotated_size(image.width(), image.height(), rotation), cell, fit)
    needed = target.w * image_px_per_mm / source.w  # output pixels per image pixel
    if needed < 1:
        image = image.scaled(
            max(1, round(image.width() * needed)),
            max(1, round(image.height() * needed)),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    if rotation:
        image = image.transformed(QTransform().rotate(rotation))
    source, target = placement(image.width(), image.height(), cell, fit)
    painter.drawImage(_qrect(target), image, _qrect(source))


def _draw_placeholders(
    painter: QPainter,
    px_per_mm: float,
    empty: list[Rect],
    missing: list[Rect],
    empty_text: str,
    missing_text: str,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    dashed = QPen(QColor(170, 170, 170), 1, Qt.PenStyle.DashLine)
    for cell in empty + missing:
        rect = _qrect(cell, px_per_mm).adjusted(0.5, 0.5, -0.5, -0.5)
        is_missing = cell in missing
        if is_missing:
            painter.fillRect(rect, QColor(255, 225, 225))
        painter.setPen(QPen(QColor(200, 60, 60), 1) if is_missing else dashed)
        painter.drawRect(rect)
        text = missing_text if is_missing else empty_text
        if text and rect.width() > 40 and rect.height() > 20:
            painter.setPen(QColor(200, 60, 60) if is_missing else QColor(150, 150, 150))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
    painter.restore()


def _qrect(rect: Rect, scale: float = 1.0) -> QRectF:
    return QRectF(rect.x * scale, rect.y * scale, rect.w * scale, rect.h * scale)
