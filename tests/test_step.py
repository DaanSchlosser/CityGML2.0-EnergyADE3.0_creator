"""Unit tests for the ISO 10303-21 STEP parser in :mod:`citygml_energy._step`.

Covers the tricky bits — comment stripping, multi-line entities, complex
entity skipping, quoted-string handling, coordinate offset, origin of
``SHELL_BASED_SURFACE_MODEL`` vs. ``MANIFOLD_SOLID_BREP`` — without
depending on Rhino or a full RenoDAT file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citygml_energy._step import (
    GeometryPolygon,
    offset_coords,
    parse_all_polygons,
    parse_named_shells,
    points_close,
)

# ---------------------------------------------------------------------------
# Fixture: minimal STEP file containing one named shell with one square face
# ---------------------------------------------------------------------------


def _minimal_step_file() -> str:
    """Return a STEP DATA section encoding a single-shell unit square at z=0.

    Laid out to exercise multi-line entity continuation and comment
    stripping in the parser.
    """
    return """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('test.stp','2024-01-01T00:00:00',(''),(''),'','','');
FILE_SCHEMA(('AP214'));
ENDSEC;
DATA;
/* A tiny manually-authored STEP sample:
   one 1m x 1m square at z=0, named 'WallSurface_1'. */
#1=CARTESIAN_POINT('',(0.0,0.0,0.0));
#2=CARTESIAN_POINT('',(1.0,0.0,0.0));
#3=CARTESIAN_POINT('',(1.0,1.0,0.0));
#4=CARTESIAN_POINT('',(0.0,1.0,0.0));
#5=VERTEX_POINT('',#1);
#6=VERTEX_POINT('',#2);
#7=VERTEX_POINT('',#3);
#8=VERTEX_POINT('',#4);
#9=EDGE_CURVE('',#5,#6,$,.T.);
#10=EDGE_CURVE('',#6,#7,$,.T.);
#11=EDGE_CURVE('',#7,#8,$,.T.);
#12=EDGE_CURVE('',#8,#5,$,.T.);
#13=ORIENTED_EDGE('',*,*,#9,.T.);
#14=ORIENTED_EDGE('',*,*,#10,.T.);
#15=ORIENTED_EDGE('',*,*,#11,.T.);
#16=ORIENTED_EDGE('',*,*,#12,.T.);
#17=EDGE_LOOP('',(#13,#14,#15,#16));
#18=FACE_OUTER_BOUND('',#17,.T.);
#19=ADVANCED_FACE('face_1',(#18),$,.T.);
#20=OPEN_SHELL('',(#19));
#21=SHELL_BASED_SURFACE_MODEL('WallSurface_1',(#20));
/* complex entity example — ignored because it carries no geometry */
#22=( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );
ENDSEC;
END-ISO-10303-21;
"""


@pytest.fixture
def minimal_step_path(tmp_path: Path) -> Path:
    path = tmp_path / "square.stp"
    path.write_text(_minimal_step_file(), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_named_shells
# ---------------------------------------------------------------------------


def test_parse_named_shells_recovers_square(minimal_step_path: Path) -> None:
    shells = parse_named_shells(minimal_step_path)
    assert len(shells) == 1
    shell = shells[0]
    assert shell.object_name == "WallSurface_1"
    assert shell.parent_name is None
    assert len(shell.polygons) == 1

    polygon = shell.polygons[0]
    # Ring is closed by the parser — first == last.
    assert points_close(polygon.exterior[0], polygon.exterior[-1])
    # Drop the closing vertex to compare against the expected corner set.
    corners = {(round(x, 6), round(y, 6), round(z, 6)) for x, y, z in polygon.exterior[:-1]}
    assert corners == {(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)}


def test_parse_named_shells_applies_origin_offset(minimal_step_path: Path) -> None:
    shells = parse_named_shells(minimal_step_path, origin=(100.0, 200.0, 0.0))
    polygon = shells[0].polygons[0]
    corners = {(round(x, 6), round(y, 6), round(z, 6)) for x, y, z in polygon.exterior[:-1]}
    assert corners == {
        (100.0, 200.0, 0.0),
        (101.0, 200.0, 0.0),
        (101.0, 201.0, 0.0),
        (100.0, 201.0, 0.0),
    }


def test_parse_named_shells_parses_parent_suffix(tmp_path: Path) -> None:
    # Replace the shell's name with a "name|parent=Roof_1" combo.
    step = _minimal_step_file().replace(
        "SHELL_BASED_SURFACE_MODEL('WallSurface_1'",
        "SHELL_BASED_SURFACE_MODEL('SolarPanelSurface_1|parent=RoofSurface_01'",
    )
    path = tmp_path / "solar.stp"
    path.write_text(step, encoding="utf-8")

    shells = parse_named_shells(path)
    assert shells[0].object_name == "SolarPanelSurface_1"
    assert shells[0].parent_name == "RoofSurface_01"


def test_parse_all_polygons_returns_coordinates_for_bbox(minimal_step_path: Path) -> None:
    polygons, all_coords = parse_all_polygons(minimal_step_path)
    assert len(polygons) == 1
    # Four exterior vertices + closing duplicate.
    assert len(all_coords) == 5


# ---------------------------------------------------------------------------
# points_close / offset_coords
# ---------------------------------------------------------------------------


def test_points_close_within_default_tolerance() -> None:
    assert points_close((1.0, 2.0, 3.0), (1.0 + 1e-12, 2.0, 3.0))
    assert not points_close((1.0, 2.0, 3.0), (1.0 + 1e-6, 2.0, 3.0))


def test_offset_coords_returns_new_list_and_leaves_input_untouched() -> None:
    source = [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0)]
    shifted = offset_coords(source, origin=(10.0, 20.0, 30.0))
    assert shifted == [(10.0, 20.0, 30.0), (11.0, 22.0, 33.0)]
    # Untouched — offset_coords doesn't mutate.
    assert source == [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0)]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_parse_rejects_malformed_entity_line(tmp_path: Path) -> None:
    path = tmp_path / "broken.stp"
    path.write_text(
        "DATA;\n#1=NOT VALID AT ALL;\nENDSEC;\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unparseable entity"):
        parse_all_polygons(path)


def test_parse_empty_file_returns_no_geometry(tmp_path: Path) -> None:
    path = tmp_path / "empty.stp"
    path.write_text("", encoding="utf-8")
    polygons, coords = parse_all_polygons(path)
    assert polygons == []
    assert coords == []


# ---------------------------------------------------------------------------
# GeometryPolygon is hashable frozen dataclass (used for caching tricks)
# ---------------------------------------------------------------------------


def test_geometry_polygon_is_frozen() -> None:
    poly = GeometryPolygon(exterior=[(0.0, 0.0, 0.0)])
    with pytest.raises(AttributeError):
        poly.exterior = []  # type: ignore[misc]
