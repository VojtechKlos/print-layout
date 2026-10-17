import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from printlayout.model import FitMode, GridLayout, PageSettings, Photo, Project
from printlayout.render import render_sheet

PX_PER_MM = 4


def solid(w, h, color):
    image = QImage(w, h, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    return image


def two_halves(w, h, left, right):
    image = solid(w, h, left)
    painter = QPainter(image)
    painter.fillRect(w // 2, 0, w - w // 2, h, QColor(right))
    painter.end()
    return image


def render(project, images):
    w, h = 210 * PX_PER_MM, 297 * PX_PER_MM
    out = QImage(w, h, QImage.Format.Format_RGB32)
    out.fill(Qt.GlobalColor.white)
    painter = QPainter(out)
    render_sheet(painter, project, project.sheets[0], PX_PER_MM, images.get)
    painter.end()
    return out


def color_at(image, x_mm, y_mm):
    return image.pixelColor(int(x_mm * PX_PER_MM), int(y_mm * PX_PER_MM))


def assert_close(color, expected, tolerance=12):
    expected = QColor(expected)
    for a, b in [(color.red(), expected.red()), (color.green(), expected.green()), (color.blue(), expected.blue())]:
        assert abs(a - b) <= tolerance, f"{color.name()} != {expected.name()}"


@pytest.fixture
def grid_project():
    colors = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
    photos = [Photo(f"/{c}.png", id=c) for c in colors]
    project = Project(
        page=PageSettings(paper="A4", margin_mm=10, gap_mm=6),
        grid=GridLayout(2, 2),
        photos=photos,
        sheets=[[p.id for p in photos]],
    )
    images = {p.path: solid(300, 200, p.id) for p in photos}
    return project, images


def test_two_by_two_cells_get_their_photos(qapp, grid_project):
    project, images = grid_project
    out = render(project, images)
    # Cells are 92 × 135.5 mm; check each cell centre.
    centres = [(56, 77.75), (154, 77.75), (56, 219.25), (154, 219.25)]
    for (x, y), photo in zip(centres, project.photos):
        assert_close(color_at(out, x, y), photo.id)
    assert_close(color_at(out, 105, 77.75), "#ffffff")  # middle of the vertical gap
    assert_close(color_at(out, 5, 5), "#ffffff")  # margin


def test_cut_lines_only_outside_photos(qapp, grid_project):
    project, images = grid_project
    project.cut_lines = True
    out = render(project, images)
    # Left edge of the first column, inside the top margin: a grey line.
    line = out.pixelColor(10 * PX_PER_MM, 5 * PX_PER_MM)
    assert line.red() < 245
    # Same x inside the first photo: still pure red, no line drawn over it.
    assert_close(color_at(out, 10.5, 77.75), "#ff0000")


def test_fit_letterboxes_landscape_photo_on_portrait_page(qapp):
    photo = Photo("/wide.png", id="wide")
    project = Project(
        page=PageSettings(paper="A4", margin_mm=0, gap_mm=0),
        grid=GridLayout(1, 1),
        fit_default=FitMode.FIT,
        auto_rotate=False,
        photos=[photo],
        sheets=[["wide"]],
    )
    out = render(project, {photo.path: solid(300, 100, "#ff0000")})
    # 210 mm wide → 70 mm tall, centred: y from 113.5 to 183.5 mm.
    assert_close(color_at(out, 105, 148.5), "#ff0000")
    assert_close(color_at(out, 105, 100), "#ffffff")
    assert_close(color_at(out, 105, 200), "#ffffff")


def test_auto_rotate_turns_landscape_photo_clockwise(qapp):
    photo = Photo("/halves.png", id="h")
    project = Project(
        page=PageSettings(paper="A4", margin_mm=0, gap_mm=0),
        grid=GridLayout(1, 1),
        fit_default=FitMode.FILL,
        auto_rotate=True,
        photos=[photo],
        sheets=[["h"]],
    )
    out = render(project, {photo.path: two_halves(300, 200, "#ff0000", "#0000ff")})
    # Rotated clockwise, the left (red) half ends up on top.
    assert_close(color_at(out, 105, 50), "#ff0000")
    assert_close(color_at(out, 105, 250), "#0000ff")


def test_user_rotation_180_flips(qapp):
    photo = Photo("/halves.png", id="h", rotation=180)
    project = Project(
        page=PageSettings(paper="A4", margin_mm=0, gap_mm=0),
        grid=GridLayout(1, 1),
        auto_rotate=True,
        photos=[photo],
        sheets=[["h"]],
    )
    out = render(project, {photo.path: two_halves(300, 200, "#ff0000", "#0000ff")})
    assert_close(color_at(out, 105, 50), "#0000ff")
    assert_close(color_at(out, 105, 250), "#ff0000")


def test_missing_image_draws_nothing_when_printing(qapp, grid_project):
    project, images = grid_project
    images.pop("/#ff0000.png")
    out = render(project, images)
    assert_close(color_at(out, 56, 77.75), "#ffffff")
    assert_close(color_at(out, 154, 77.75), "#00ff00")
