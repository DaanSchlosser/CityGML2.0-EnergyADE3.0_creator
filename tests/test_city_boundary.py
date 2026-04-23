"""Tests for the concave-polygon boundary loader + pipeline filter.

Covers:

* :func:`load_boundary_polygon` reads one feature by ``fid`` from a
  real 1-feature GPKG, and raises actionable errors when the layer
  is missing, the fid is absent, or the SRS id is wrong.
* :func:`_filter_by_boundary` keeps only buildings whose 2D LoD 0
  footprint intersects the polygon, using "any overlap" semantics.
* Config validation rejects ``bbox`` + ``boundary`` set simultaneously
  and accepts the ``boundary`` block on its own.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest

pytest.importorskip("shapely")

from shapely.geometry import MultiPolygon, Polygon

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.boundary import (
    BoundarySource,
    load_boundary_polygon,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.config import CityBuildError, load_city_config
from citygml_energy.city_builder.pipeline import _filter_by_boundary


# ---------------------------------------------------------------------------
# Minimal GPKG fixture (mirrors test_city_pv_panels._make_minimal_gpkg so the
# two boundary + PV paths share an identical on-disk shape)
# ---------------------------------------------------------------------------


def _write_boundary_gpkg(
    path: Path,
    features: list[tuple[int, list[tuple[float, float]]]],
    *,
    srs_id: int = 28992,
) -> None:
    """Write one GPKG with N features (fid, MultiPolygon of one outer ring)."""
    from shapely import wkb as shapely_wkb

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
            CREATE TABLE grid2 (fid INTEGER PRIMARY KEY, geom BLOB);
            """
        )
        con.execute(
            "INSERT INTO gpkg_spatial_ref_sys VALUES ('RD New', 28992, 'EPSG', 28992, 'WKT', '')"
        )
        con.execute(
            "INSERT INTO gpkg_contents (table_name, data_type, srs_id) "
            "VALUES ('grid2', 'features', ?)",
            (srs_id,),
        )
        con.execute(
            "INSERT INTO gpkg_geometry_columns VALUES "
            "('grid2', 'geom', 'MULTIPOLYGON', ?, 0, 0)",
            (srs_id,),
        )
        for fid, coords in features:
            mp = MultiPolygon([Polygon(coords)])
            wkb_bytes = shapely_wkb.dumps(mp, byte_order=1, include_srid=False)
            # GPKG binary header: "GP" magic, version 0, flags 0x01 (LE), SRS id.
            header = struct.pack("<2sBBi", b"GP", 0, 0x01, srs_id)
            con.execute(
                "INSERT INTO grid2 (fid, geom) VALUES (?, ?)", (fid, header + wkb_bytes)
            )
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# load_boundary_polygon
# ---------------------------------------------------------------------------


def test_load_boundary_polygon_returns_requested_fid(tmp_path: Path) -> None:
    gpkg = tmp_path / "grid2.gpkg"
    _write_boundary_gpkg(
        gpkg,
        [
            (1, [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]),
            (2, [(100.0, 100.0), (105.0, 100.0), (105.0, 105.0), (100.0, 105.0), (100.0, 100.0)]),
        ],
    )
    geom1 = load_boundary_polygon(BoundarySource(path=gpkg, layer="grid2", fid=1))
    geom2 = load_boundary_polygon(BoundarySource(path=gpkg, layer="grid2", fid=2))
    # fid=1 is the 10x10 at origin; fid=2 is the 5x5 at (100,100). Bounds
    # are the cleanest way to tell them apart without depending on ring order.
    assert geom1.bounds == (0.0, 0.0, 10.0, 10.0)
    assert geom2.bounds == (100.0, 100.0, 105.0, 105.0)


def test_load_boundary_polygon_heals_concave_self_intersecting_ring(tmp_path: Path) -> None:
    """Hand-drawn concave rings sometimes come out of QGIS slightly
    non-noded; the loader must heal them with ``buffer(0)`` rather than
    propagating an invalid geometry into the intersection test.
    """
    gpkg = tmp_path / "boundary.gpkg"
    # Bowtie ring: crosses itself at (1, 0.5). Shapely marks that invalid.
    _write_boundary_gpkg(
        gpkg, [(1, [(0, 0), (2, 0), (0, 1), (2, 1), (0, 0)])]
    )
    geom = load_boundary_polygon(BoundarySource(path=gpkg, layer="grid2", fid=1))
    assert geom.is_valid


def test_load_boundary_raises_for_missing_fid(tmp_path: Path) -> None:
    gpkg = tmp_path / "grid2.gpkg"
    _write_boundary_gpkg(
        gpkg, [(1, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])]
    )
    with pytest.raises(ValueError, match="boundary.fid=99 not found"):
        load_boundary_polygon(BoundarySource(path=gpkg, layer="grid2", fid=99))


def test_load_boundary_raises_for_missing_layer(tmp_path: Path) -> None:
    gpkg = tmp_path / "grid2.gpkg"
    _write_boundary_gpkg(
        gpkg, [(1, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])]
    )
    with pytest.raises(ValueError, match="not declared in gpkg_contents"):
        load_boundary_polygon(BoundarySource(path=gpkg, layer="nope", fid=1))


def test_load_boundary_raises_for_wrong_crs(tmp_path: Path) -> None:
    """Only EPSG:28992 (or 'undefined' 0/-1) is accepted, to match 3DBAG."""
    gpkg = tmp_path / "grid2.gpkg"
    _write_boundary_gpkg(
        gpkg,
        [(1, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
        srs_id=28992,
    )
    # Force the declared SRS to WGS84.
    con = sqlite3.connect(gpkg)
    try:
        con.execute("UPDATE gpkg_contents SET srs_id = 4326 WHERE table_name = 'grid2'")
        con.commit()
    finally:
        con.close()
    with pytest.raises(ValueError, match=r"srs_id=4326"):
        load_boundary_polygon(BoundarySource(path=gpkg, layer="grid2", fid=1))


# ---------------------------------------------------------------------------
# _filter_by_boundary
# ---------------------------------------------------------------------------


def _lod0_footprint(
    pand_id: str, coords: list[tuple[float, float]]
) -> ParsedBuilding:
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


def test_filter_by_boundary_keeps_overlapping_drops_disjoint() -> None:
    # C-shaped concave boundary: outside rectangle with a notch cut out
    # of the right side. A small square in the notch is "outside" the
    # boundary even though it falls inside the bbox.
    c_shape = Polygon(
        [(0, 0), (10, 0), (10, 3), (6, 3), (6, 7), (10, 7), (10, 10), (0, 10), (0, 0)]
    )
    inside = _lod0_footprint(
        "inside_1", [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]
    )
    straddling = _lod0_footprint(
        # Half in the C's left arm, half sticking into the notch.
        "straddle_1", [(5, 4), (7, 4), (7, 6), (5, 6), (5, 4)]
    )
    in_notch = _lod0_footprint(
        # Fully inside the notch → outside the boundary.
        "notch_1", [(7, 4), (8, 4), (8, 5), (7, 5), (7, 4)]
    )
    outside = _lod0_footprint(
        "far_away_1", [(100, 100), (101, 100), (101, 101), (100, 101), (100, 100)]
    )
    parsed_by_id = {
        pb.pand_id: pb for pb in (inside, straddling, in_notch, outside)
    }
    kept = _filter_by_boundary(parsed_by_id, c_shape)
    # Any-overlap semantics: inside + straddling are kept; notch + far are dropped.
    assert set(kept) == {"inside_1", "straddle_1"}


def test_filter_by_boundary_drops_buildings_without_lod0() -> None:
    """Defensive: a building with no LoD 0 footprint cannot be tested for
    boundary membership, so it is dropped rather than silently kept.
    """
    pb = ParsedBuilding(
        pand_id="no_lod0",
        attributes={"identificatie": "no_lod0"},
        geometries={},
    )
    kept = _filter_by_boundary(
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
        "schema_version": "city-1",
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
    path = _write_config(
        tmp_path,
        boundary={
            "path": "../inputs/pv_panels/grid2.gpkg",
            "layer": "grid2",
            "fid": 1,
        },
    )
    config = load_city_config(path)
    assert config.boundary_source is not None
    assert config.boundary_source.layer == "grid2"
    assert config.boundary_source.fid == 1


def test_config_rejects_bbox_and_boundary_together(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        bbox=[0.0, 0.0, 100.0, 100.0],
        boundary={
            "path": "../inputs/pv_panels/grid2.gpkg",
            "layer": "grid2",
            "fid": 1,
        },
    )
    with pytest.raises(CityBuildError, match="mutually exclusive"):
        load_city_config(path)


def test_config_rejects_non_integer_fid(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        boundary={
            "path": "../inputs/pv_panels/grid2.gpkg",
            "layer": "grid2",
            "fid": "1",
        },
    )
    with pytest.raises(CityBuildError, match="boundary.fid must be"):
        load_city_config(path)
