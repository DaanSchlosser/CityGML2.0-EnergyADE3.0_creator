"""Tests for the CFTree-vegetation branch of the city-build pipeline.

Covers what the pv-panels and boundary tests cover for their feature:

* :func:`cityjson_trees_parse.parse_cftree_tile` on a fixture CityJSON
  payload — quantization, centroid, Solid-to-polygons flattening.
* :func:`vegetation.load_trees_in_bbox` — single-file load, bbox
  half-open clip, malformed-file skip, missing-file fallback.
* :func:`vegetation.filter_trees_by_boundary` — centroid-in-polygon.
* :func:`builders.build_solitary_vegetation_object` — XSD-valid
  round-trip, native vs. generic attribute split.
* :func:`appearance.append_vegetation_appearance` — target collection,
  no-op when there are no trees.
* :func:`config._validate_vegetation` — valid / invalid config blocks.

These tests never touch the network: every fixture is hand-built.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("shapely")

from shapely.geometry import Polygon as ShapelyPolygon

from citygml_energy.bindings import (
    LengthType,
    MultiSurface,
    SolitaryVegetationObject,
)
from citygml_energy.city_builder.appearance import (
    VEGETATION_DIFFUSE_COLOR,
    VEGETATION_THEME,
    append_vegetation_appearance,
)
from citygml_energy.city_builder.builders import build_solitary_vegetation_object
from citygml_energy.city_builder.cityjson_trees_parse import (
    ParsedTree,
    parse_cftree_tile,
    parse_cftree_tile_file,
)
from citygml_energy.city_builder.config import BuildContext, CityBuildError, load_city_config
from citygml_energy.city_builder.vegetation import (
    VegetationSource,
    filter_trees_by_boundary,
    load_trees_in_bbox,
)
from citygml_energy.core import CityModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _tri(*points: tuple[float, float, float]) -> dict[str, Any]:
    """Helper: a single CityJSON Solid with one triangular face per vertex ring."""
    return {
        "type": "Solid",
        "lod": 3.0,
        "boundaries": [[[list(points)]]],
    }


def _cftree_cityjson(
    *,
    gtid: int = 1,
    # Absolute RD coords, will be quantized with transform below.
    crown_pts: tuple[tuple[float, float, float], ...] = (
        (267050.0, 537780.0, 15.0),
        (267051.0, 537780.0, 17.0),
        (267050.5, 537780.5, 17.0),
    ),
    trunk_pts: tuple[tuple[float, float, float], ...] = (
        (267050.5, 537780.0, 12.0),
        (267050.7, 537780.2, 14.0),
        (267050.6, 537780.3, 14.0),
    ),
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimal CFTree CityJSON 2.0 payload with one SolitaryVegetationObject.

    Uses the same quantization (``scale = 0.001``, ``translate = min``)
    that CFTree's :func:`write_cityjson.finalize_cityjson` emits.
    """
    all_pts = list(crown_pts) + list(trunk_pts)
    tx, ty, tz = (min(p[i] for p in all_pts) for i in range(3))
    scale = 0.001

    def quantize(pts: tuple[tuple[float, float, float], ...]) -> list[list[int]]:
        return [
            [
                round((x - tx) / scale),
                round((y - ty) / scale),
                round((z - tz) / scale),
            ]
            for (x, y, z) in pts
        ]

    crown_q = quantize(crown_pts)
    trunk_q = quantize(trunk_pts)
    vertices = crown_q + trunk_q
    crown_idx = list(range(3))
    trunk_idx = list(range(3, 6))
    default_attrs: dict[str, Any] = {
        "gtid": gtid,
        "tile_id": "18AZ2_22",
        "crown_width_m": 2.5,
        "crown_median_z": 17.0,
        "crown_r50_m": 0.14,
        "crown_porosity": 0.45,
        "trunk_H_m": 6.0,
        "trunk_DBH_m": 0.12,
        "trunk_radius_m": 0.06,
        "trunk_base_height_m": 12.0,
    }
    if attributes:
        default_attrs.update(attributes)
    return {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {"scale": [scale, scale, scale], "translate": [tx, ty, tz]},
        "metadata": {
            "referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/28992",
            "presentLoDs": [3.0],
        },
        "CityObjects": {
            f"T_{gtid}": {
                "type": "SolitaryVegetationObject",
                "geometry": [
                    {
                        "type": "Solid",
                        "lod": 3.0,
                        "boundaries": [[[crown_idx]]],
                    },
                    {
                        "type": "Solid",
                        "lod": 3.0,
                        "boundaries": [[[trunk_idx]]],
                    },
                ],
                "attributes": default_attrs,
            },
        },
        "vertices": vertices,
    }


# ---------------------------------------------------------------------------
# parse_cftree_tile
# ---------------------------------------------------------------------------


def test_parse_cftree_tile_flattens_components() -> None:
    """Crown + trunk Solids get merged into one polygon list (no per-component dict)."""
    data = _cftree_cityjson(gtid=42)
    trees = parse_cftree_tile(data)
    assert len(trees) == 1
    t = trees[0]
    assert t.gtid == "42"
    # 2 Solids × 1 triangle each = 2 polygons.
    assert len(t.polygons) == 2
    for poly in t.polygons:
        # Each triangle closes with the starting vertex (4 pts total).
        assert len(poly.exterior) == 4
        assert poly.exterior[0] == poly.exterior[-1]


def test_parse_cftree_tile_dequantizes_correctly() -> None:
    """Vertex coordinates land in absolute RD metres after dequantization."""
    data = _cftree_cityjson()
    trees = parse_cftree_tile(data)
    xs = [x for poly in trees[0].polygons for (x, _y, _z) in poly.exterior]
    ys = [y for poly in trees[0].polygons for (_x, y, _z) in poly.exterior]
    assert min(xs) == pytest.approx(267050.0, abs=1e-3)
    assert max(xs) == pytest.approx(267051.0, abs=1e-3)
    assert min(ys) == pytest.approx(537780.0, abs=1e-3)
    assert max(ys) == pytest.approx(537780.5, abs=1e-3)


def test_parse_cftree_tile_centroid_on_merged_polygons() -> None:
    """Centroid averages every unique vertex across crown + trunk."""
    data = _cftree_cityjson()
    t = parse_cftree_tile(data)[0]
    cx, cy, _cz = t.centroid
    assert 267050.0 < cx < 267051.0
    assert 537780.0 < cy < 537780.5


def test_parse_cftree_tile_preserves_attributes_verbatim() -> None:
    """Attributes pass through untouched so the builder can own their mapping."""
    data = _cftree_cityjson(attributes={"custom_future_key": 3.14})
    t = parse_cftree_tile(data)[0]
    # Every key CFTree writes today is preserved.
    for key in (
        "gtid",
        "tile_id",
        "crown_width_m",
        "crown_median_z",
        "crown_r50_m",
        "crown_porosity",
        "trunk_H_m",
        "trunk_DBH_m",
        "trunk_radius_m",
        "trunk_base_height_m",
        "custom_future_key",
    ):
        assert key in t.attributes


def test_parse_cftree_tile_skips_non_vegetation_objects() -> None:
    """A CityObject of an unexpected type must not be parsed as a tree."""
    data = _cftree_cityjson()
    data["CityObjects"]["Terrain_1"] = {
        "type": "TINRelief",
        "geometry": [],
        "attributes": {},
    }
    trees = parse_cftree_tile(data)
    assert len(trees) == 1
    assert trees[0].gtid == "1"


def test_parse_cftree_tile_file_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "trees.city.json"
    path.write_text("")
    assert parse_cftree_tile_file(path) == []


def test_parse_cftree_tile_rejects_wrong_top_level_type() -> None:
    with pytest.raises(ValueError, match="Expected CityJSON"):
        parse_cftree_tile({"type": "FeatureCollection", "features": []})


# ---------------------------------------------------------------------------
# load_trees_in_bbox
# ---------------------------------------------------------------------------


def _write_cftree_file(path: Path, cityjson: dict[str, Any]) -> None:
    """Write a merged CFTree CityJSON file to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cityjson))


def _multi_tree_cityjson(gtids: list[int]) -> dict[str, Any]:
    """Build a multi-tree CityJSON 2.0 sharing one transform.

    Each tree is offset by 5m east of the previous so spatial dedup or
    bbox tests can target individual trees deterministically.
    """
    scale = 0.001
    point_blocks: list[
        tuple[int, list[tuple[float, float, float]], list[tuple[float, float, float]]]
    ] = []
    for i, gtid in enumerate(gtids):
        ox = i * 5.0
        crown = [
            (267050.0 + ox, 537780.0, 15.0),
            (267051.0 + ox, 537780.0, 17.0),
            (267050.5 + ox, 537780.5, 17.0),
        ]
        trunk = [
            (267050.5 + ox, 537780.0, 12.0),
            (267050.7 + ox, 537780.2, 14.0),
            (267050.6 + ox, 537780.3, 14.0),
        ]
        point_blocks.append((gtid, crown, trunk))

    flat = [p for _, c, t in point_blocks for p in (*c, *t)]
    tx = min(p[0] for p in flat)
    ty = min(p[1] for p in flat)
    tz = min(p[2] for p in flat)

    vertices: list[list[int]] = []
    city_objects: dict[str, Any] = {}
    for gtid, crown, trunk in point_blocks:
        crown_idx = []
        for x, y, z in crown:
            crown_idx.append(len(vertices))
            vertices.append(
                [round((x - tx) / scale), round((y - ty) / scale), round((z - tz) / scale)]
            )
        trunk_idx = []
        for x, y, z in trunk:
            trunk_idx.append(len(vertices))
            vertices.append(
                [round((x - tx) / scale), round((y - ty) / scale), round((z - tz) / scale)]
            )
        city_objects[f"T_{gtid}"] = {
            "type": "SolitaryVegetationObject",
            "geometry": [
                {"type": "Solid", "lod": 3.0, "boundaries": [[[crown_idx]]]},
                {"type": "Solid", "lod": 3.0, "boundaries": [[[trunk_idx]]]},
            ],
            "attributes": {
                "gtid": gtid,
                "crown_width_m": 2.5,
                "crown_median_z": 17.0,
                "crown_r50_m": 0.14,
                "crown_porosity": 0.45,
                "trunk_H_m": 6.0,
                "trunk_DBH_m": 0.12,
                "trunk_radius_m": 0.06,
                "trunk_base_height_m": 12.0,
            },
        }

    return {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {"scale": [scale, scale, scale], "translate": [tx, ty, tz]},
        "metadata": {
            "referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/28992",
            "presentLoDs": [3.0],
        },
        "CityObjects": city_objects,
        "vertices": vertices,
    }


def test_load_trees_in_bbox_loads_all_trees_in_file(tmp_path: Path) -> None:
    """A merged CityJSON with N trees yields N ParsedTree records."""
    file_path = tmp_path / "trees.city.json"
    _write_cftree_file(file_path, _multi_tree_cityjson([1, 2]))
    source = VegetationSource(path=file_path)
    trees = load_trees_in_bbox(source, bbox=(267000.0, 537700.0, 267200.0, 537800.0))
    assert sorted(t.gtid for t in trees) == ["1", "2"]


def test_load_trees_in_bbox_clips_half_open(tmp_path: Path) -> None:
    """A tree whose centroid sits *on* ``maxx`` is rejected, on ``minx`` kept.

    Half-open ``[minx, maxx)`` matches the BAG / 3DBAG fetchers' convention
    so a building and its adjacent street tree never land on different
    sides of the bbox by a rounding unit.
    """
    # Centroid x ≈ 267050.5, y ≈ 537780.25 for this fixture.
    file_path = tmp_path / "trees.city.json"
    _write_cftree_file(file_path, _cftree_cityjson(gtid=1))
    source = VegetationSource(path=file_path)
    # Bounds including the centroid exactly at minx edge.
    kept = load_trees_in_bbox(source, bbox=(267050.5, 537780.0, 267051.0, 537781.0))
    assert [t.gtid for t in kept] == ["1"]
    # Bounds with centroid exactly at maxx edge.
    dropped = load_trees_in_bbox(source, bbox=(267049.0, 537780.0, 267050.5, 537781.0))
    assert dropped == []


def test_load_trees_in_bbox_skips_malformed_file(tmp_path: Path, caplog) -> None:
    """Malformed JSON in the merged file degrades to an empty list with a warning."""
    file_path = tmp_path / "trees.city.json"
    file_path.write_text("not valid json {")
    source = VegetationSource(path=file_path)
    trees = load_trees_in_bbox(source, bbox=(267000.0, 537700.0, 267100.0, 537800.0))
    assert trees == []


def test_load_trees_in_bbox_empty_when_source_missing(tmp_path: Path) -> None:
    """Config-authoring machines that have not run CFTree must still build."""
    trees = load_trees_in_bbox(
        VegetationSource(path=tmp_path / "does_not_exist.city.json"),
        bbox=(0.0, 0.0, 1.0, 1.0),
    )
    assert trees == []


# ---------------------------------------------------------------------------
# filter_trees_by_boundary
# ---------------------------------------------------------------------------


def test_filter_trees_by_boundary_centroid_in_polygon() -> None:
    """Centroid-in-polygon filter mirrors the building filter's intent for a point."""
    tree_in = ParsedTree(
        gtid="1",
        centroid=(5.0, 5.0, 0.0),
        polygons=[],
        attributes={},
    )
    tree_out = ParsedTree(
        gtid="2",
        centroid=(20.0, 5.0, 0.0),
        polygons=[],
        attributes={},
    )
    poly = ShapelyPolygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    kept = filter_trees_by_boundary([tree_in, tree_out], poly)
    assert [t.gtid for t in kept] == ["1"]


# ---------------------------------------------------------------------------
# build_solitary_vegetation_object
# ---------------------------------------------------------------------------


def _parsed_tree_from_cityjson(**kwargs: Any) -> ParsedTree:
    return parse_cftree_tile(_cftree_cityjson(**kwargs))[0]


def test_build_tree_populates_native_length_fields() -> None:
    tree = _parsed_tree_from_cityjson()
    obj = build_solitary_vegetation_object(
        tree,
        BuildContext(srs_name="urn:ogc:def:crs,crs:EPSG::28992", srs_dimension=3),
    )
    assert isinstance(obj, SolitaryVegetationObject)
    assert obj.id == "tree_1"
    # Native length fields with uom=m.
    assert isinstance(obj.height, LengthType)
    assert obj.height.value == 6.0
    assert obj.height.uom == "m"
    assert obj.trunk_diameter.value == 0.12
    assert obj.crown_diameter.value == 2.5


def test_build_tree_generic_attributes_cover_non_native_metrics() -> None:
    """CFTree's porosity / r50 / median_z / trunk_base_height all have no
    native CityGML slot and must land as ``gen:doubleAttribute``.

    ``trunk_radius_m`` is deliberately **not** among them: CFTree
    computes it as ``0.5 * trunk_DBH_m`` in
    ``extract_tree_metrics.estimate_trunk_dimensions``, so the value is
    already carried by ``veg:trunkDiameter``. Emitting both would
    double-signal one measurement; the pipeline drops the radius to
    keep the output minimal. Any consumer that wants the radius can
    compute it on the fly.
    """
    tree = _parsed_tree_from_cityjson()
    obj = build_solitary_vegetation_object(tree)
    named = {a.name: a.value for a in obj.double_attribute}
    assert named == {
        "crown_median_z": pytest.approx(17.0),
        "crown_r50_m": pytest.approx(0.14),
        "crown_porosity": pytest.approx(0.45),
        "trunk_base_height_m": pytest.approx(12.0),
    }
    # Cross-check: the radius is *not* present anywhere on the object,
    # but the diameter it is derived from is. A future reader should
    # be able to reconstruct the radius from the DBH without looking
    # at the generic attributes.
    assert "trunk_radius_m" not in named
    assert obj.trunk_diameter is not None
    assert obj.trunk_diameter.value == pytest.approx(0.12)


def test_build_tree_generic_attributes_emit_in_sorted_order() -> None:
    """``gen:doubleAttribute`` order must be byte-stable across runs.
    The source key set is a ``frozenset``, whose iteration order varies
    with hash randomization between processes; the builder must sort it
    so two builds of the same input produce identical bytes.
    """
    tree = _parsed_tree_from_cityjson()
    obj = build_solitary_vegetation_object(tree)
    names = [a.name for a in obj.double_attribute]
    assert names == sorted(names)


def test_build_tree_skips_nan_and_inf_values() -> None:
    """``NaN`` means CFTree could not compute the metric; it must not serialize."""
    import math

    tree = _parsed_tree_from_cityjson(
        attributes={
            "trunk_H_m": math.nan,
            "crown_porosity": math.inf,
            "crown_width_m": None,  # explicit missing
        }
    )
    obj = build_solitary_vegetation_object(tree)
    # NaN height means the native field stays unset; same for missing crown width.
    assert obj.height is None
    assert obj.crown_diameter is None
    # Inf porosity likewise excluded from generic attributes.
    names = {a.name for a in obj.double_attribute}
    assert "crown_porosity" not in names


def test_build_tree_emits_lod3_multisurface_geometry() -> None:
    tree = _parsed_tree_from_cityjson()
    obj = build_solitary_vegetation_object(tree)
    assert obj.lod3_geometry is not None
    ms = obj.lod3_geometry.multi_surface
    assert isinstance(ms, MultiSurface)
    # crown (1 triangle) + trunk (1 triangle) = 2 member polygons.
    assert len(ms.surface_member) == 2


def test_build_tree_gml_id_prefix_yields_valid_ncname() -> None:
    """CFTree's gtid is purely numeric and invalid as xs:ID; the ``tree_``
    prefix fixes that. The merged-file pipeline guarantees gtids are
    globally unique, so no tile namespacing is needed on top.
    """
    tree = _parsed_tree_from_cityjson(gtid=99)
    obj = build_solitary_vegetation_object(tree, BuildContext(gml_id_prefix="city42"))
    assert obj.id == "city42_tree_99"


def test_build_tree_gml_id_uses_bare_gtid() -> None:
    """The merged-file pipeline ensures gtids are unique across the AOI,
    so the gml:id is just the gtid plus the ``tree_`` prefix.
    """
    tree = ParsedTree(gtid="7", centroid=(0.0, 0.0, 0.0), polygons=[], attributes={})
    obj = build_solitary_vegetation_object(tree)
    assert obj.id == "tree_7"


def test_build_tree_round_trip_serializes_and_validates() -> None:
    """Smoke test: the tree plus a fake envelope must produce XSD-valid CityGML."""
    from citygml_energy.gml_builders import build_envelope

    tree = _parsed_tree_from_cityjson()
    obj = build_solitary_vegetation_object(
        tree,
        BuildContext(
            srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
            srs_dimension=3,
        ),
    )
    model = CityModel(gml_name="tree_rt", gml_description="vegetation round-trip")
    model.add(obj)
    all_pts = [p for poly in tree.polygons for p in poly.exterior]
    model.set_envelope(
        build_envelope(
            all_pts,
            srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
            srs_dimension=3,
        )
    )
    xml = model.to_string()
    assert "<veg:SolitaryVegetationObject" in xml
    assert "<veg:lod3Geometry" in xml
    # Presence of both native and generic morphometrics.
    assert '<veg:height uom="m">6.0</veg:height>' in xml
    assert '<gen:doubleAttribute name="crown_porosity">' in xml


# ---------------------------------------------------------------------------
# append_vegetation_appearance
# ---------------------------------------------------------------------------


def test_append_vegetation_appearance_is_noop_without_trees() -> None:
    model = CityModel()
    append_vegetation_appearance(model)
    assert model.xsd.appearance_member == []


def test_append_vegetation_appearance_targets_container_only() -> None:
    """Only the MultiSurface container of each tree is targeted.

    An appearance on a ``gml:MultiSurface`` is valid for all of its
    member surfaces per the CityGML 2.0 Appearance model, so the foliage
    color propagates to the member polygons from the single container
    target (matching the Alderaan reference convention).
    """
    tree = _parsed_tree_from_cityjson()
    obj = build_solitary_vegetation_object(tree)
    model = CityModel()
    model.add(obj)
    append_vegetation_appearance(model)

    assert len(model.xsd.appearance_member) == 1
    appearance = model.xsd.appearance_member[0].appearance
    assert appearance.theme == VEGETATION_THEME
    materials = appearance.surface_data_member
    assert len(materials) == 1
    material = materials[0].x3_dmaterial
    assert material.diffuse_color == list(VEGETATION_DIFFUSE_COLOR)
    # Exactly one target: the tree's MultiSurface container, no polygons.
    assert len(material.target) == 1
    assert material.target[0].startswith("#")
    assert "_poly_" not in material.target[0]


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, extra: dict[str, Any]) -> Path:
    base = {
        "$schema": "../schemas/city_input.schema.json",
        "municipality": "Emmen",
        "bbox": [264400, 535580, 268720, 538940],
        "lods": [0, 1, 2],
        "include_addresses": False,
        "include_energy_labels": False,
        "output": "../generated/test.gml",
    }
    base.update(extra)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(base))
    return path


def test_config_accepts_vegetation_block(tmp_path: Path) -> None:
    cfg = _write_config(
        tmp_path,
        {"vegetation": {"path": "./trees.city.json"}},
    )
    loaded = load_city_config(cfg)
    assert loaded.vegetation_source is not None
    assert loaded.vegetation_source.path.name == "trees.city.json"


def test_config_rejects_non_cityjson_vegetation_path(tmp_path: Path) -> None:
    """Anything other than a .city.json file must fail loudly at load time."""
    cfg = _write_config(tmp_path, {"vegetation": {"path": "./trees.gpkg"}})
    with pytest.raises(CityBuildError, match=r"\.city\.json"):
        load_city_config(cfg)


def test_config_rejects_unknown_vegetation_key(tmp_path: Path) -> None:
    cfg = _write_config(
        tmp_path,
        {
            "vegetation": {"path": "./trees.city.json", "bogus": "x"},
        },
    )
    with pytest.raises(CityBuildError, match="unexpected vegetation key"):
        load_city_config(cfg)


def test_config_rejects_vegetation_missing_path(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, {"vegetation": {}})
    with pytest.raises(CityBuildError, match=r"vegetation\.path"):
        load_city_config(cfg)
