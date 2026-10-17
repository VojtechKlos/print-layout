import json
import shutil

import pytest

from printlayout import project_io
from printlayout.model import (
    FitMode,
    GridLayout,
    LayoutMode,
    Orientation,
    PageSettings,
    Photo,
    Project,
)


@pytest.fixture
def project(tmp_path):
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    a, b = photos_dir / "a.jpg", photos_dir / "b.jpg"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    return Project(
        page=PageSettings(paper="10x15", orientation=Orientation.LANDSCAPE, margin_mm=3, gap_mm=2),
        grid=GridLayout(rows=1, cols=2),
        mode=LayoutMode.MANUAL,
        fit_default=FitMode.FIT,
        auto_rotate=False,
        cut_lines=True,
        photos=[Photo(str(a), id="a", rotation=90, fit=FitMode.FILL), Photo(str(b), id="b")],
        sheets=[[None, "a"], ["b", "a"]],
    )


def test_round_trip(tmp_path, project):
    path = tmp_path / "test.plproj"
    project_io.save(project, str(path))
    assert project_io.load(str(path)) == project


def test_moved_project_folder_uses_relative_paths(tmp_path, project):
    project_io.save(project, str(tmp_path / "test.plproj"))
    moved = tmp_path.parent / (tmp_path.name + "-moved")
    shutil.move(str(tmp_path), moved)
    try:
        loaded = project_io.load(str(moved / "test.plproj"))
        assert loaded.photos[0].path == str(moved / "photos" / "a.jpg")
    finally:
        shutil.rmtree(moved)


def test_missing_photo_keeps_absolute_path(tmp_path, project):
    path = tmp_path / "test.plproj"
    project_io.save(project, str(path))
    (tmp_path / "photos" / "b.jpg").unlink()
    assert project_io.load(str(path)).photos[1].path == project.photos[1].path


def test_unknown_ids_and_wrong_sheet_lengths_are_repaired(tmp_path, project):
    path = tmp_path / "test.plproj"
    data = project_io.to_dict(project, str(path))
    data["sheets"] = [["zzz", "a", "b"], ["b"]]
    path.write_text(json.dumps(data))
    assert project_io.load(str(path)).sheets == [[None, "a"], ["b", None]]


def test_rejects_other_json(tmp_path):
    path = tmp_path / "other.plproj"
    path.write_text('{"hello": 1}')
    with pytest.raises(project_io.ProjectError):
        project_io.load(str(path))


def test_rejects_newer_version(tmp_path, project):
    path = tmp_path / "test.plproj"
    data = project_io.to_dict(project, str(path))
    data["version"] = project_io.FILE_VERSION + 1
    path.write_text(json.dumps(data))
    with pytest.raises(project_io.ProjectError, match="newer"):
        project_io.load(str(path))


def test_rejects_damaged_file(tmp_path):
    path = tmp_path / "broken.plproj"
    path.write_text("{not json")
    with pytest.raises(project_io.ProjectError):
        project_io.load(str(path))
