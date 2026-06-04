"""Tests for the concave-polygon boundary loader + pipeline filter.

Covers:

* :func:`load_boundary_polygon` reads a single GeoJSON Feature, accepts
  a single-feature ``FeatureCollection`` (the QGIS default export shape),
  and raises actionable errors on empty / multi-feature collections,
  wrong CRS, or bad geometry.
* :func:`filter_buildings_by_boundary` keeps only buildings whose 2D LoD 0
  footprint intersects the polygon, using "any overlap" semantics.
* Config validation rejects ``bbox`` + ``boundary`` set simultaneously,
  rejects non-GeoJSON paths, and accepts a ``boundary`` block on its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("shapely")

from shapely.geometry import Polygon

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.boundary import (
    BoundarySource,
    load_boundary_polygon,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.config import CityBuildError, load_city_config
from citygml_energy.city_builder.pipeline import filter_buildings_by_boundary

# ---------------------------------------------------------------------------
# load_boundary_polygon
# ---------------------------------------------------------------------------


def test_load_boundary_polygon_heals_concave_self_intersecting_ring(tmp_path: Path) -> None:
    """Hand-drawn concave rings sometimes come out of QGIS slightly
    non-noded; the loader must heal them with ``buffer(0)`` rather than
    propagating an invalid geometry into the intersection test.
    """
    import json

    # Bowtie ring: crosses itself at (1, 0.5). Shapely marks that invalid.
    path = tmp_path / "boundary.geojson"
    doc = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [2, 0], [0, 1], [2, 1], [0, 0]]],
        },
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    geom = load_boundary_polygon(BoundarySource(path=path))
    assert geom.is_valid


# ---------------------------------------------------------------------------
# filter_buildings_by_boundary
# ---------------------------------------------------------------------------


def _lod0_footprint(pand_id: str, coords: list[tuple[float, float]]) -> ParsedBuilding:
    """Build a ParsedBuilding with a single LoD 0 footprint at z=0."""
    return ParsedBuilding(
        pand_id=pand_id,
        attributes={"identificatie": pand_id},
        geometries={
            "0": [
                SemanticPolygon(
                    polygon=GeometryPolygon(
                        exterior=[(x, y, 0.0) for (x, y) in coords],
                        interiors=[],
                    ),
                    surface_type="GroundSurface",
                ),
            ],
        },
    )


def testfilter_buildings_by_boundary_keeps_overlapping_drops_disjoint() -> None:
    # C-shaped concave boundary: outside rectangle with a notch cut out
    # of the right side. A small square in the notch is "outside" the
    # boundary even though it falls inside the bbox.
    c_shape = Polygon(
        [(0, 0), (10, 0), (10, 3), (6, 3), (6, 7), (10, 7), (10, 10), (0, 10), (0, 0)]
    )
    inside = _lod0_footprint("inside_1", [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)])
    straddling = _lod0_footprint(
        # Half in the C's left arm, half sticking into the notch.
        "straddle_1",
        [(5, 4), (7, 4), (7, 6), (5, 6), (5, 4)],
    )
    in_notch = _lod0_footprint(
        # Fully inside the notch → outside the boundary.
        "notch_1",
        [(7, 4), (8, 4), (8, 5), (7, 5), (7, 4)],
    )
    outside = _lod0_footprint(
        "far_away_1", [(100, 100), (101, 100), (101, 101), (100, 101), (100, 100)]
    )
    parsed_by_id = {pb.pand_id: pb for pb in (inside, straddling, in_notch, outside)}
    kept = filter_buildings_by_boundary(parsed_by_id, c_shape)
    # Any-overlap semantics: inside + straddling are kept; notch + far are dropped.
    assert set(kept) == {"inside_1", "straddle_1"}


def testfilter_buildings_by_boundary_drops_buildings_without_lod0() -> None:
    """Defensive: a building with no LoD 0 footprint cannot be tested for
    boundary membership, so it is dropped rather than silently kept.
    """
    pb = ParsedBuilding(
        pand_id="no_lod0",
        attributes={"identificatie": "no_lod0"},
        geometries={},
    )
    kept = filter_buildings_by_boundary(
        {"no_lod0": pb},
        Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
    )
    assert kept == {}


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, **extras: object) -> Path:
    import json

    config = {
        "municipality": "Emmen",
        "output": "out.gml",
        "cache_dir": "cache",
        "include_energy_labels": False,
        **extras,
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_config_accepts_boundary_block(tmp_path: Path) -> None:
    geojson = tmp_path / "area.geojson"
    _write_geojson(geojson, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    path = _write_config(tmp_path, boundary={"path": str(geojson)})
    config = load_city_config(path)
    assert config.boundary_source is not None
    assert config.boundary_source.path == geojson


def test_config_rejects_bbox_and_boundary_together(tmp_path: Path) -> None:
    geojson = tmp_path / "area.geojson"
    _write_geojson(geojson, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    path = _write_config(
        tmp_path,
        bbox=[0.0, 0.0, 100.0, 100.0],
        boundary={"path": str(geojson)},
    )
    with pytest.raises(CityBuildError, match="mutually exclusive"):
        load_city_config(path)


# ---------------------------------------------------------------------------
# GeoJSON boundary reader
# ---------------------------------------------------------------------------


def _write_geojson(
    path: Path,
    coords: list[tuple[float, float]],
    *,
    crs: str | None = "urn:ogc:def:crs:EPSG::28992",
    geojson_type: str = "Feature",
    feature_count: int = 1,
) -> None:
    """Write a minimal GeoJSON file in the given CRS.

    *geojson_type* controls the root ``type`` field (``Feature`` or
    ``FeatureCollection``). *feature_count* controls how many features
    a FeatureCollection carries; ignored when *geojson_type* is
    ``Feature``.
    """
    import json

    geometry = {"type": "Polygon", "coordinates": [[list(p) for p in coords]]}
    feature = {"type": "Feature", "properties": {}, "geometry": geometry}
    if geojson_type == "Feature":
        doc: dict = feature
    else:
        doc = {
            "type": geojson_type,
            "features": [feature for _ in range(feature_count)],
        }
    if crs is not None:
        doc["crs"] = {"type": "name", "properties": {"name": crs}}
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_load_boundary_from_geojson_feature(tmp_path: Path) -> None:
    path = tmp_path / "area.geojson"
    _write_geojson(path, [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    geom = load_boundary_polygon(BoundarySource(path=path))
    assert geom.bounds == (0.0, 0.0, 10.0, 10.0)


def test_load_boundary_accepts_single_feature_collection(tmp_path: Path) -> None:
    """QGIS' "Export selected features" default emits a single-Feature
    FeatureCollection even for one polygon; the loader unwraps it
    rather than forcing every author to hand-edit the file.
    """
    path = tmp_path / "area.geojson"
    _write_geojson(
        path,
        [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
        geojson_type="FeatureCollection",
        feature_count=1,
    )
    geom = load_boundary_polygon(BoundarySource(path=path))
    assert geom.bounds == (0.0, 0.0, 10.0, 10.0)


def test_load_boundary_rejects_empty_feature_collection(tmp_path: Path) -> None:
    """A FeatureCollection with no features is an authoring slip, not a
    valid boundary; it must fail loudly rather than silently producing
    an empty extent that would drop every building.
    """
    path = tmp_path / "area.geojson"
    _write_geojson(
        path,
        [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)],
        geojson_type="FeatureCollection",
        feature_count=0,
    )
    with pytest.raises(ValueError, match="empty FeatureCollection"):
        load_boundary_polygon(BoundarySource(path=path))


def test_load_boundary_rejects_multi_feature_collection(tmp_path: Path) -> None:
    """The build extent is a single, deliberately authored polygon, so a
    FeatureCollection with two or more features must be rejected
    rather than silently picking the first.
    """
    path = tmp_path / "area.geojson"
    _write_geojson(
        path,
        [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)],
        geojson_type="FeatureCollection",
        feature_count=2,
    )
    with pytest.raises(ValueError, match="2 features"):
        load_boundary_polygon(BoundarySource(path=path))


def test_load_boundary_from_geojson_rejects_non_rd_crs(tmp_path: Path) -> None:
    """A WGS84-tagged GeoJSON must not silently misalign with RD-based 3DBAG data."""
    path = tmp_path / "area.geojson"
    _write_geojson(
        path,
        [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)],
        crs="urn:ogc:def:crs:EPSG::4326",
    )
    with pytest.raises(ValueError, match="EPSG:28992"):
        load_boundary_polygon(BoundarySource(path=path))


def test_load_boundary_from_geojson_accepts_missing_crs(tmp_path: Path) -> None:
    """GeoJSON without a ``crs`` block is silently accepted (see boundary.py docstring)."""
    path = tmp_path / "area.geojson"
    _write_geojson(path, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)], crs=None)
    geom = load_boundary_polygon(BoundarySource(path=path))
    assert geom.is_valid


def test_config_accepts_geojson_boundary(tmp_path: Path) -> None:
    geojson = tmp_path / "area.geojson"
    _write_geojson(geojson, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    cfg = _write_config(tmp_path, boundary={"path": str(geojson)})
    loaded = load_city_config(cfg)
    assert loaded.boundary_source is not None
    assert loaded.boundary_source.path == geojson


def test_config_rejects_gpkg_boundary(tmp_path: Path) -> None:
    """Only .geojson is accepted; .gpkg must fail at config-load time."""
    cfg = _write_config(tmp_path, boundary={"path": "some.gpkg"})
    with pytest.raises(CityBuildError, match=r"\.geojson"):
        load_city_config(cfg)
