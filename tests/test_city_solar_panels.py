"""End-to-end test of the solar-panel integration in the city pipeline.

Covers:

* Config parsing of the optional ``solar_panels`` block.
* Full pipeline path with :func:`load_panels_in_bbox` mocked to return
  fixture shapely polygons, asserting that the emitted ``CityModel``
  carries ``nrg3:GenericSolarCollector`` features with the right
  ``lod2MultiSurface`` Z, ``moduleArea``, and ``installedOn`` xlink
  back to the matched per-planar RoofSurface. The city pipeline emits
  ``GenericSolarCollector`` (technology-agnostic) rather than
  ``PhotovoltaicCollector`` because the aerial-imagery source has no
  cell-type metadata.
* XSD validity of the serialised GML.
* Panels that overlap no LoD 2 roof are silently skipped.

No network, no real GeoPackage: :func:`load_panels_in_bbox` is patched
so the test exercises ``match_and_project_panels``,
``attach_solar_collectors_to_building``, and the pipeline wiring, not
GPKG parsing (that path is covered by a narrower unit test).
"""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

import lxml.etree as etree
import pytest

pytest.importorskip("shapely")

from shapely.geometry import Polygon

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder import build_city_model
from citygml_energy.city_builder.config import BuildContext
from citygml_energy.city_builder import pipeline as pipeline_module
from citygml_energy.city_builder import solar_panels as solar_panels_module
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.config import load_city_config
from citygml_energy.city_builder.fetchers import (
    bag as bag_fetchers,
)
from citygml_energy.city_builder.fetchers import (
    eponline as eponline_fetchers,
)
from citygml_energy.city_builder.fetchers import (
    municipality as muni_fetchers,
)
from citygml_energy.city_builder.fetchers.bag import Pand, Verblijfsobject
from citygml_energy.city_builder.fetchers.municipality import MunicipalityOutline
from citygml_energy.city_builder.solar_panels import (
    DEFAULT_Z_OFFSET_M,
    ProjectedPanel,
    SolarPanelsSource,
    attach_solar_collectors_to_building,
    match_and_project_panels,
)
from tools.validate_xsd import load_schema

# The roof sits at z=3 for the cube fixture so projected panels land at
# z=3.1 with the default offset. Keeping the Pand id / VBO id literals
# close to the city-pipeline test for readability.
_PAND_ID = "0503100000000042"
_VBO_ID = "0503010000000042"
_BBOX = (84000.0, 445000.0, 86000.0, 447000.0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cube_shell_at(origin_x: float, origin_y: float) -> list[SemanticPolygon]:
    """A 1x1x3 m cube shell with the ground face on z=0 and roof on z=3."""
    p = [
        (origin_x, origin_y, 0.0),
        (origin_x + 1.0, origin_y, 0.0),
        (origin_x + 1.0, origin_y + 1.0, 0.0),
        (origin_x, origin_y + 1.0, 0.0),
        (origin_x, origin_y, 3.0),
        (origin_x + 1.0, origin_y, 3.0),
        (origin_x + 1.0, origin_y + 1.0, 3.0),
        (origin_x, origin_y + 1.0, 3.0),
    ]
    faces = [
        ([p[0], p[3], p[2], p[1]], "GroundSurface"),
        ([p[4], p[5], p[6], p[7]], "RoofSurface"),
        ([p[0], p[1], p[5], p[4]], "WallSurface"),
        ([p[1], p[2], p[6], p[5]], "WallSurface"),
        ([p[2], p[3], p[7], p[6]], "WallSurface"),
        ([p[3], p[0], p[4], p[7]], "WallSurface"),
    ]
    return [
        SemanticPolygon(polygon=GeometryPolygon(exterior=v), surface_type=st)
        for v, st in faces
    ]


def _fixture_parsed_building() -> ParsedBuilding:
    shell = _cube_shell_at(85000.0, 446000.0)
    ground = next(s for s in shell if s.surface_type == "GroundSurface")
    return ParsedBuilding(
        pand_id=_PAND_ID,
        attributes={"oorspronkelijkbouwjaar": 1985, "identificatie": _PAND_ID},
        geometries={
            "0": [ground],
            "1": shell,
            "2": shell,
        },
    )


def _fixture_outline() -> MunicipalityOutline:
    return MunicipalityOutline(
        name="Delft",
        cbs_code="0503",
        feature={
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [_BBOX[0], _BBOX[1]],
                    [_BBOX[2], _BBOX[1]],
                    [_BBOX[2], _BBOX[3]],
                    [_BBOX[0], _BBOX[3]],
                    [_BBOX[0], _BBOX[1]],
                ]],
            },
        },
        bbox=_BBOX,
    )


def _fixture_pand() -> Pand:
    return Pand(identificatie=_PAND_ID, bouwjaar=1985, status=None, properties={})


def _fixture_vbo() -> Verblijfsobject:
    return Verblijfsobject(
        identificatie=_VBO_ID,
        pand_identificatie=_PAND_ID,
        gebruiksdoel=["woonfunctie"],
        oppervlakte=85.0,
        status=None,
        postcode="2628CD",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam="Mekelweg",
        woonplaats=None,
        point=(85000.0, 446500.0),
        properties={},
    )


# Two panels over the cube roof (area 0.36 m² and 0.04 m²) and one
# completely outside the bbox of the building (should be skipped).
_PANEL_ON_ROOF_1 = Polygon([
    (85000.2, 446000.2),
    (85000.8, 446000.2),
    (85000.8, 446000.8),
    (85000.2, 446000.8),
    (85000.2, 446000.2),
])
_PANEL_ON_ROOF_2 = Polygon([
    (85000.4, 446000.4),
    (85000.6, 446000.4),
    (85000.6, 446000.6),
    (85000.4, 446000.6),
    (85000.4, 446000.4),
])
_PANEL_OFF_ROOF = Polygon([
    (85500.0, 446500.0),
    (85500.5, 446500.0),
    (85500.5, 446500.5),
    (85500.0, 446500.5),
    (85500.0, 446500.0),
])


def _fixture_panels() -> list[tuple[int, Polygon]]:
    return [
        (1, _PANEL_ON_ROOF_1),
        (2, _PANEL_ON_ROOF_2),
        (9, _PANEL_OFF_ROOF),
    ]


def _write_config(tmp_path: Path, *, with_pv: bool) -> Path:
    data: dict = {
        "municipality": "Delft",
        "bbox": list(_BBOX),
        "lods": [0, 1, 2],
        "include_addresses": True,
        "include_energy_labels": False,
        "cache_dir": str(tmp_path / "cache"),
        "output": str(tmp_path / "out.gml"),
    }
    if with_pv:
        # A non-existent path is fine: load_panels_in_bbox is mocked in
        # the integration test, and existence is checked lazily only
        # when the loader actually runs.
        data["solar_panels"] = {
            "path": "panels.gpkg",
            "layer": "solar_panels",
            "z_offset_m": 0.25,
        }
    source = tmp_path / "city.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
    return source


@pytest.fixture
def mocked_fetchers(monkeypatch: pytest.MonkeyPatch):
    """Patch every network fetcher to return fixture data."""
    monkeypatch.setattr(
        muni_fetchers,
        "fetch_municipality_outline",
        lambda session, *, name: _fixture_outline(),
    )
    monkeypatch.setattr(
        bag_fetchers,
        "fetch_panden",
        lambda session, *, bbox, cbs_code=None: [_fixture_pand()],
    )
    monkeypatch.setattr(
        bag_fetchers,
        "fetch_verblijfsobjecten",
        lambda session, *, bbox, cbs_code=None: [_fixture_vbo()],
    )
    monkeypatch.setattr(
        eponline_fetchers,
        "fetch_energy_labels",
        lambda session, *, api_key, wanted_ids=None, wanted_keys=None: [],
    )
    monkeypatch.setattr(
        pipeline_module,
        "_fetch_parsed_buildings",
        lambda session, *, outline, bbox: [_fixture_parsed_building()],
    )


# ---------------------------------------------------------------------------
# Unit tests: matching + projection + attach
# ---------------------------------------------------------------------------


def test_match_and_project_flat_roof_has_zero_inclination_and_null_azimuth() -> None:
    parsed = [_fixture_parsed_building()]
    matches, skipped = match_and_project_panels(
        panels=_fixture_panels(),
        parsed_buildings=parsed,
        z_offset_m=DEFAULT_Z_OFFSET_M,
    )
    assert skipped == 1  # _PANEL_OFF_ROOF
    assert set(matches) == {_PAND_ID}
    projected = matches[_PAND_ID]
    assert len(projected) == 2
    assert {p.original_fid for p in projected} == {1, 2}

    # Horizontal roof: every vertex lands at roof_z + offset, inclination
    # is 0, azimuth undefined, and the reference point matches the
    # centroid z.
    for panel in projected:
        assert panel.inclination_deg == pytest.approx(0.0, abs=1e-6)
        assert panel.azimuth_deg is None
        for geom in panel.lod2_polygons:
            zs = {round(v[2], 6) for v in geom.exterior}
            assert zs == {round(3.0 + DEFAULT_Z_OFFSET_M, 6)}
        assert panel.reference_point[2] == pytest.approx(3.0 + DEFAULT_Z_OFFSET_M, abs=1e-6)


def test_match_and_project_sloped_roof_sets_azimuth_and_inclination_and_lifts_with_slope() -> None:
    """A roof slope that rises in +Y has a normal pointing into -Y.

    Expected orientation: azimuth 180° (south-facing, because the normal's
    horizontal component is -Y), inclination 45° (rise:run = 1:1).
    Every panel vertex must end up on the plane at exactly (0.1 m offset
    along the unit normal), not at a flat Z.
    """
    # Square roof facet, NW corner at z=3, NE at z=3, SW at z=4, SE at z=4:
    # slope rises towards +Y. Newell of this ring yields (0, -2, 2), i.e.
    # normal (0, -1/√2, 1/√2) after normalisation.
    sloped = SemanticPolygon(
        polygon=GeometryPolygon(
            exterior=[
                (0.0, 0.0, 3.0),
                (1.0, 0.0, 3.0),
                (1.0, 1.0, 4.0),
                (0.0, 1.0, 4.0),
            ],
            interiors=[],
        ),
        surface_type="RoofSurface",
    )
    parsed = [
        ParsedBuilding(
            pand_id="999999999",
            attributes={"identificatie": "999999999"},
            geometries={"2": [sloped]},
        )
    ]
    panel = Polygon([(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)])
    matches, skipped = match_and_project_panels(
        panels=[(1, panel)],
        parsed_buildings=parsed,
        z_offset_m=DEFAULT_Z_OFFSET_M,
    )
    assert skipped == 0
    [p] = matches["999999999"]

    # Orientation (tight tolerance: pure geometry, no FP noise sources).
    assert p.inclination_deg == pytest.approx(45.0, abs=1e-6)
    assert p.azimuth_deg == pytest.approx(180.0, abs=1e-6)

    # Slope-follow check: panel vertex Zs vary with Y exactly as the
    # roof does (dz/dy = 1), not as a flat stamp. Using the two ends of
    # the exterior ring where y differs.
    ring = p.lod2_polygons[0].exterior
    ys = sorted({round(v[1], 6) for v in ring})
    # Pick vertices at the min-y and max-y rows.
    y_lo, y_hi = ys[0], ys[-1]
    z_lo = next(v[2] for v in ring if round(v[1], 6) == y_lo)
    z_hi = next(v[2] for v in ring if round(v[1], 6) == y_hi)
    # Roof z(y) = 3 + y. Offset along +Z/-Y normal shifts y by
    # -0.1/√2 and z by +0.1/√2. So panel z at original (x, y_lo=0.2):
    # z_plane = 3 + (0.2 - 0.1/√2) ≈ 3.1293; lifted z = that + 0.1/√2 ≈ 3.2.
    # Easier sanity: the slope dz/dy on the panel ring is still 1.
    assert (z_hi - z_lo) == pytest.approx((y_hi - y_lo), abs=1e-9)

    # Reference point lies on the offset plane, 0.1 m perpendicular above
    # the roof's plane-Z at (0.5, 0.5).
    _rx, ry, rz = p.reference_point
    # Inverse of the offset: undoing the shift should place the point
    # back on the roof plane (z = 3 + y).
    y_on_roof = ry + DEFAULT_Z_OFFSET_M / (2 ** 0.5)  # normal_y = -1/√2
    z_on_roof = rz - DEFAULT_Z_OFFSET_M / (2 ** 0.5)
    assert z_on_roof == pytest.approx(3.0 + y_on_roof, abs=1e-9)


def test_azimuth_conventions_are_compass_bearings() -> None:
    """Spot-check that normals pointing in each cardinal direction
    produce the compass bearing EnergyADE expects (0=N, 90=E, 180=S, 270=W).
    """
    from citygml_energy.city_builder.solar_panels import _azimuth_from_normal

    # Horizontal roof: undefined.
    assert _azimuth_from_normal((0.0, 0.0, 1.0)) is None
    # Normal tilting towards +Y = facing north.
    assert _azimuth_from_normal((0.0, 1.0, 1.0)) == pytest.approx(0.0, abs=1e-6)
    # Normal tilting towards +X = facing east.
    assert _azimuth_from_normal((1.0, 0.0, 1.0)) == pytest.approx(90.0, abs=1e-6)
    # Normal tilting towards -Y = facing south.
    assert _azimuth_from_normal((0.0, -1.0, 1.0)) == pytest.approx(180.0, abs=1e-6)
    # Normal tilting towards -X = facing west.
    assert _azimuth_from_normal((-1.0, 0.0, 1.0)) == pytest.approx(270.0, abs=1e-6)


def _fixture_projected_panel(
    original_fid: int = 7,
    *,
    azimuth_deg: float | None = 180.0,
    inclination_deg: float = 30.0,
    roof_index: int = 1,
) -> ProjectedPanel:
    return ProjectedPanel(
        original_fid=original_fid,
        lod2_polygons=(
            GeometryPolygon(
                exterior=[
                    (0.0, 0.0, 3.1),
                    (1.0, 0.0, 3.1),
                    (1.0, 1.0, 3.6),
                    (0.0, 1.0, 3.6),
                ],
                interiors=[],
            ),
        ),
        footprint_area_m2=1.0,
        azimuth_deg=azimuth_deg,
        inclination_deg=inclination_deg,
        reference_point=(0.5, 0.5, 3.35),
        roof_index=roof_index,
    )


def test_attach_solar_emits_expected_xsd_structure() -> None:
    from citygml_energy.city_builder.builders import build_building

    parsed = _fixture_parsed_building()
    ctx = BuildContext(
        srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
        srs_dimension=3,
    )
    building = build_building(parsed, ctx)
    panel = _fixture_projected_panel()
    attached = attach_solar_collectors_to_building(building, [panel], ctx)
    assert attached == 1
    assert len(building.device) == 1
    # The city pipeline emits the technology-agnostic
    # nrg3:GenericSolarCollector, not nrg3:PhotovoltaicCollector,
    # because the aerial-imagery source has no cell-type metadata.
    collector = building.device[0].generic_solar_collector
    assert collector is not None
    assert building.device[0].photovoltaic_collector is None
    assert collector.id == f"solar_{_PAND_ID}_7"
    assert collector.lod2_multi_surface is not None
    # cellType is photovoltaic-specific and does not exist on
    # GenericSolarCollectorType, so it is neither emitted nor checked.

    # uom tokens match the KIT SDM_KITModelViewer UOMList.xml primary ids
    # (m2 for SQUARE_METRE) and altIds (deg for DEGREE). An earlier version
    # of this test asserted "m^2" / "decimal degrees" which matched neither
    # the UoM XML nor the code — the viewer accepts only the canonical
    # tokens, so the test is pinned to what the pipeline actually emits.
    assert collector.module_area.uom == "m2"
    assert collector.module_area.value == 1.0
    assert collector.inclination.uom == "deg"
    assert collector.inclination.value == 30.0
    assert collector.azimuth is not None
    assert collector.azimuth.uom == "deg"
    assert collector.azimuth.value == 180.0

    # referencePoint is a single gml:Point with 3D coords.
    assert len(collector.reference_point) == 1
    pt = collector.reference_point[0].point
    assert pt.pos.value == [0.5, 0.5, 3.35]
    assert pt.srs_dimension == 3

    # installedOn href points at the specific RoofSurface polygon the
    # panel was matched to. With per-planar splitting the cube fixture
    # has exactly one RoofSurface (index 1).
    assert len(collector.related_to) == 1
    cor = collector.related_to[0].city_object_relation
    assert cor.relation_type.value == "installedOn"
    assert cor.related_to.href == f"#pand_{_PAND_ID}_roofsurface_1"


def test_attach_omits_azimuth_on_flat_roof() -> None:
    """Horizontal panels: azimuth is geometrically undefined, so the
    ``nrg3:azimuth`` element must be absent; inclination stays at 0.
    """
    from citygml_energy.city_builder.builders import build_building

    ctx = BuildContext(srs_name="x", srs_dimension=3)
    building = build_building(_fixture_parsed_building(), ctx)
    panel = _fixture_projected_panel(
        original_fid=3, azimuth_deg=None, inclination_deg=0.0
    )
    attach_solar_collectors_to_building(building, [panel], ctx)
    collector = building.device[0].generic_solar_collector
    assert collector.azimuth is None
    assert collector.inclination.value == 0.0


def test_attach_drops_panels_when_no_lod2_roof_surface() -> None:
    from citygml_energy.city_builder.builders import build_building

    parsed = _fixture_parsed_building()
    ctx = BuildContext(lods=(0, 1), srs_name="x", srs_dimension=3)
    # Force LoD 0/1 only: no RoofSurface gets emitted, so the xlink
    # target doesn't exist inside the document and the attach must
    # refuse to emit dangling hrefs.
    building = build_building(parsed, ctx)
    panel = _fixture_projected_panel(original_fid=1)
    attached = attach_solar_collectors_to_building(building, [panel], ctx)
    assert attached == 0
    assert building.device == []


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


def test_config_parses_solar_panels_block(tmp_path: Path) -> None:
    source = _write_config(tmp_path, with_pv=True)
    config = load_city_config(source)
    assert isinstance(config.solar_panels_source, SolarPanelsSource)
    assert config.solar_panels_source.layer == "solar_panels"
    assert config.solar_panels_source.z_offset_m == 0.25
    # Path is resolved relative to the config file's directory.
    assert config.solar_panels_source.path == (tmp_path / "panels.gpkg").resolve()


def test_config_without_solar_panels_block(tmp_path: Path) -> None:
    source = _write_config(tmp_path, with_pv=False)
    config = load_city_config(source)
    assert config.solar_panels_source is None


def test_config_rejects_bad_solar_panels_block(tmp_path: Path) -> None:
    source = tmp_path / "city.json"
    source.write_text(
        json.dumps({
            "municipality": "Delft",
            "include_energy_labels": False,
            "output": str(tmp_path / "out.gml"),
            "cache_dir": str(tmp_path / "cache"),
            "solar_panels": {"layer": "x"},  # missing path
        }),
        encoding="utf-8",
    )
    (tmp_path / "cache").mkdir()
    from citygml_energy.city_builder.config import CityBuildError

    with pytest.raises(CityBuildError, match=r"solar_panels\.path"):
        load_city_config(source)


# ---------------------------------------------------------------------------
# Integration: full pipeline with mocked panel loader
# ---------------------------------------------------------------------------


def test_pipeline_attaches_solar_collectors(
    tmp_path: Path, mocked_fetchers, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_config(tmp_path, with_pv=True)
    config = load_city_config(source)

    monkeypatch.setattr(
        solar_panels_module,
        "load_panels_in_bbox",
        lambda src, bbox: _fixture_panels(),
    )

    model = build_city_model(config)
    building = model.xsd.city_object_member[0].building
    assert len(building.device) == 2  # the two on-roof panels only

    collector_ids = {d.generic_solar_collector.id for d in building.device}
    assert collector_ids == {f"solar_{_PAND_ID}_1", f"solar_{_PAND_ID}_2"}

    # Every solar collector points installedOn → the matched per-planar
    # RoofSurface id. The cube fixture has exactly one RoofSurface, so
    # both panels resolve to ``_roofsurface_1``.
    expected_href = f"#pand_{_PAND_ID}_roofsurface_1"
    expected_bu_href = f"#bu_{_VBO_ID}"
    for d in building.device:
        rels = d.generic_solar_collector.related_to
        by_type = {r.city_object_relation.relation_type.value: r.city_object_relation for r in rels}
        # The cube fixture is a single-VBO Pand, so the panels carry
        # both an installedOn xlink to the matched roof and a serving
        # xlink to the lone BuildingUnit (CONTEXT.md "Scope-based parent
        # placement"). The single-VBO case is when the served set is
        # knowable by elimination — emit it.
        assert set(by_type) == {"installedOn", "serving"}, (
            f"expected installedOn + serving relations, got {sorted(by_type)}"
        )
        assert by_type["installedOn"].related_to.href == expected_href
        assert by_type["serving"].related_to.href == expected_bu_href


def test_pipeline_skips_pv_when_lod2_disabled(
    tmp_path: Path, mocked_fetchers, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    source = tmp_path / "city.json"
    source.write_text(
        json.dumps({
            "municipality": "Delft",
            "bbox": list(_BBOX),
            "lods": [0, 1],  # no LoD 2: attach must refuse
            "include_addresses": True,
            "include_energy_labels": False,
            "cache_dir": str(tmp_path / "cache"),
            "output": str(tmp_path / "out.gml"),
            "solar_panels": {"path": "panels.gpkg", "layer": "solar_panels"},
        }),
        encoding="utf-8",
    )
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

    config = load_city_config(source)
    monkeypatch.setattr(
        solar_panels_module,
        "load_panels_in_bbox",
        lambda src, bbox: _fixture_panels(),
    )

    import logging

    with caplog.at_level(logging.WARNING, logger="citygml_energy.city_builder.pipeline"):
        model = build_city_model(config)
    building = model.xsd.city_object_member[0].building
    assert building.device == []
    assert any("LoD 2 is" in r.message for r in caplog.records), (
        "expected a WARNING-level 'LoD 2 is disabled' message on stderr"
    )


def test_pipeline_output_with_pv_validates_against_xsd(
    tmp_path: Path, mocked_fetchers, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_config(tmp_path, with_pv=True)
    config = load_city_config(source)
    monkeypatch.setattr(
        solar_panels_module,
        "load_panels_in_bbox",
        lambda src, bbox: _fixture_panels(),
    )

    model = build_city_model(config)
    xml = model.to_string()
    schema = load_schema()
    root = etree.fromstring(xml.encode("utf-8"))
    schema.assertValid(root)


# ---------------------------------------------------------------------------
# GPKG read unit test (smallest-possible real GeoPackage)
# ---------------------------------------------------------------------------


def _make_minimal_gpkg(path: Path, polygon_coords: list[tuple[float, float]]) -> None:
    """Write a 1-feature GPKG with a MultiPolygon to *path*.

    Exercises the real :func:`load_panels_in_bbox` path end-to-end
    (sqlite read + GPKG header strip + shapely WKB parse + bbox clip).
    """
    from shapely import wkb as shapely_wkb
    from shapely.geometry import MultiPolygon

    mp = MultiPolygon([Polygon(polygon_coords)])
    wkb_bytes = shapely_wkb.dumps(mp, byte_order=1, include_srid=False)
    header = struct.pack("<2sBBi", b"GP", 0, 0x01, 28992)  # no envelope
    gpkg_geom = header + wkb_bytes

    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA application_id = 1196444487")  # 'GPKG'
        con.execute("PRAGMA user_version = 10300")
        con.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER,
                definition TEXT, description TEXT
            );
            CREATE TABLE gpkg_contents (
                table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT,
                description TEXT, last_change DATETIME DEFAULT CURRENT_TIMESTAMP,
                min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE,
                srs_id INTEGER
            );
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER, z TINYINT, m TINYINT
            );
            CREATE TABLE solar_panels (fid INTEGER PRIMARY KEY, geom BLOB);
            """
        )
        con.execute(
            "INSERT INTO gpkg_spatial_ref_sys VALUES ('RD New', 28992, 'EPSG', 28992, 'WKT', '')"
        )
        con.execute(
            "INSERT INTO gpkg_contents (table_name, data_type, srs_id) "
            "VALUES ('solar_panels', 'features', 28992)"
        )
        con.execute(
            "INSERT INTO gpkg_geometry_columns VALUES "
            "('solar_panels', 'geom', 'MULTIPOLYGON', 28992, 0, 0)"
        )
        con.execute("INSERT INTO solar_panels (fid, geom) VALUES (?, ?)", (1, gpkg_geom))
        con.commit()
    finally:
        con.close()


def test_load_panels_in_bbox_roundtrip(tmp_path: Path) -> None:
    gpkg = tmp_path / "panels.gpkg"
    _make_minimal_gpkg(
        gpkg,
        [(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0), (100.0, 100.0)],
    )
    source = SolarPanelsSource(path=gpkg, layer="solar_panels", z_offset_m=0.1)
    rows = solar_panels_module.load_panels_in_bbox(source, (50.0, 50.0, 300.0, 300.0))
    assert len(rows) == 1
    assert rows[0][0] == 1
    # Outside the panel's bbox: returns nothing instead of raising.
    rows_miss = solar_panels_module.load_panels_in_bbox(source, (1000.0, 1000.0, 2000.0, 2000.0))
    assert rows_miss == []


def test_load_panels_in_bbox_rejects_wrong_crs(tmp_path: Path) -> None:
    gpkg = tmp_path / "panels.gpkg"
    _make_minimal_gpkg(
        gpkg, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]
    )
    # Force the declared srs to something we don't accept.
    con = sqlite3.connect(gpkg)
    try:
        con.execute("UPDATE gpkg_contents SET srs_id = 4326 WHERE table_name = 'solar_panels'")
        con.commit()
    finally:
        con.close()
    source = SolarPanelsSource(path=gpkg, layer="solar_panels", z_offset_m=0.1)
    with pytest.raises(ValueError, match="srs_id=4326"):
        solar_panels_module.load_panels_in_bbox(source, (0.0, 0.0, 10.0, 10.0))


def test_load_panels_missing_file_raises(tmp_path: Path) -> None:
    source = SolarPanelsSource(path=tmp_path / "nope.gpkg", layer="x", z_offset_m=0.1)
    with pytest.raises(FileNotFoundError):
        solar_panels_module.load_panels_in_bbox(source, (0.0, 0.0, 1.0, 1.0))
