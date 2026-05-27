"""Unit tests for the CityJSON parser used by the city-scale pipeline."""

from __future__ import annotations

from citygml_energy.city_builder.cityjson_parse import (
    CityJSONTile,
    SemanticPolygon,
    parse_buildings,
)


def _minimal_tile() -> dict:
    """One Building with two BuildingParts: LoD0 MultiSurface + LoD2.2 Solid.

    Vertices are stored as pre-transformed floats (transform = identity)
    so the test reads like a human-authored CityJSON sample.
    """
    return {
        "type": "CityJSON",
        "version": "1.1",
        "transform": {"scale": [1.0, 1.0, 1.0], "translate": [0.0, 0.0, 0.0]},
        "metadata": {"referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/28992"},
        "vertices": [
            [0, 0, 0],  # 0
            [1, 0, 0],  # 1
            [1, 1, 0],  # 2
            [0, 1, 0],  # 3
            [0, 0, 3],  # 4
            [1, 0, 3],  # 5
            [1, 1, 3],  # 6
            [0, 1, 3],  # 7
        ],
        "CityObjects": {
            "NL.IMBAG.Pand.0503100000000001": {
                "type": "Building",
                "attributes": {
                    "identificatie": "0503100000000001",
                    "oorspronkelijkbouwjaar": 1985,
                },
                "children": ["NL.IMBAG.Pand.0503100000000001_part_lod0",
                             "NL.IMBAG.Pand.0503100000000001_part_lod2"],
            },
            "NL.IMBAG.Pand.0503100000000001_part_lod0": {
                "type": "BuildingPart",
                "parents": ["NL.IMBAG.Pand.0503100000000001"],
                "attributes": {},
                "geometry": [
                    {
                        "type": "MultiSurface",
                        "lod": "0",
                        "boundaries": [[[0, 1, 2, 3]]],  # one square face
                    },
                ],
            },
            "NL.IMBAG.Pand.0503100000000001_part_lod2": {
                "type": "BuildingPart",
                "parents": ["NL.IMBAG.Pand.0503100000000001"],
                "attributes": {},
                "geometry": [
                    {
                        "type": "Solid",
                        "lod": "2.2",
                        # Shell with 6 square faces forming a unit cube 1x1x3.
                        "boundaries": [[
                            [[0, 3, 2, 1]],  # bottom  → GroundSurface
                            [[4, 5, 6, 7]],  # top     → RoofSurface
                            [[0, 1, 5, 4]],  # front   → WallSurface
                            [[1, 2, 6, 5]],  # right   → WallSurface
                            [[2, 3, 7, 6]],  # back    → WallSurface
                            [[3, 0, 4, 7]],  # left    → WallSurface
                        ]],
                        "semantics": {
                            "surfaces": [
                                {"type": "GroundSurface"},
                                {"type": "RoofSurface"},
                                {"type": "WallSurface"},
                            ],
                            "values": [[0, 1, 2, 2, 2, 2]],
                        },
                    },
                ],
            },
        },
    }


def test_parse_buildings_returns_one_per_pand() -> None:
    buildings = parse_buildings(_minimal_tile())
    assert len(buildings) == 1
    building = buildings[0]
    assert building.pand_id == "0503100000000001"
    assert building.attributes["oorspronkelijkbouwjaar"] == 1985


def test_parse_buildings_aggregates_parts_by_lod() -> None:
    buildings = parse_buildings(_minimal_tile())
    geoms = buildings[0].geometries
    assert "0" in geoms and len(geoms["0"]) == 1
    # LoD 2.2 is aliased to "2"; all 6 faces of the cube are present.
    assert "2" in geoms and len(geoms["2"]) == 6
    # Every entry is a SemanticPolygon.
    assert all(isinstance(sp, SemanticPolygon) for sp in geoms["2"])


def test_parse_buildings_lod2_semantic_types() -> None:
    buildings = parse_buildings(_minimal_tile())
    geoms = buildings[0].geometries["2"]
    types = [sp.surface_type for sp in geoms]
    assert types.count("GroundSurface") == 1
    assert types.count("RoofSurface") == 1
    assert types.count("WallSurface") == 4


def test_transform_scale_and_translate_are_applied() -> None:
    tile = _minimal_tile()
    tile["transform"] = {"scale": [0.001, 0.001, 0.001], "translate": [85000.0, 446000.0, 0.0]}
    tile["vertices"] = [[0, 0, 0], [1000, 0, 0], [1000, 1000, 0], [0, 1000, 0]]
    tile["CityObjects"] = {
        "P": {
            "type": "Building",
            "attributes": {"identificatie": "P"},
            "children": ["P_part"],
        },
        "P_part": {
            "type": "BuildingPart",
            "parents": ["P"],
            "geometry": [
                {"type": "MultiSurface", "lod": "0", "boundaries": [[[0, 1, 2, 3]]]},
            ],
        },
    }
    buildings = parse_buildings(tile)
    ring = buildings[0].geometries["0"][0].polygon.exterior
    # scale * vertex + translate  →  0.001 * [1000, 0, 0] + [85000, 446000, 0]
    assert ring[1] == (85001.0, 446000.0, 0.0)


def test_cityjson_tile_rejects_non_cityjson() -> None:
    import pytest

    with pytest.raises(ValueError, match="CityJSON"):
        CityJSONTile.from_dict({"type": "Something else"})


def test_degenerate_ring_at_output_precision_is_dropped() -> None:
    """Vertices that collapse at the output µm grid must be dropped.

    3DBAG triangle indices a/b/c whose raw coords differ at sub-mm scale
    survive a mm-precision dedup but quantise to identical strings in the
    GML — producing a 3-point degenerate ``gml:LinearRing`` that XSD does
    not catch (the 4-point minimum is enforced on ``gml:pos`` children,
    not on ``gml:posList`` content). Dedup must therefore run at the
    output grid (1 µm).
    """
    from citygml_energy.gml_builders import _COORD_DECIMALS

    sub_mum = 0.5 * 10 ** -(_COORD_DECIMALS + 1)
    tile = {
        "type": "CityJSON",
        "version": "1.1",
        "transform": {"scale": [1.0, 1.0, 1.0], "translate": [0.0, 0.0, 0.0]},
        "metadata": {"referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/28992"},
        "vertices": [
            [85000.0, 446000.0, 0.0],
            [85000.0 + sub_mum, 446000.0 + sub_mum, sub_mum],
            [85000.0 - sub_mum, 446000.0 - sub_mum, -sub_mum],
            [85000.0 + 1.0, 446000.0, 0.0],
            [85000.0 + 1.0, 446000.0 + 1.0, 0.0],
            [85000.0, 446000.0 + 1.0, 0.0],
        ],
        "CityObjects": {
            "P": {
                "type": "Building",
                "attributes": {"identificatie": "P"},
                "children": ["P_part"],
            },
            "P_part": {
                "type": "BuildingPart",
                "parents": ["P"],
                "geometry": [
                    {
                        "type": "MultiSurface",
                        "lod": "2.2",
                        "boundaries": [
                            [[0, 1, 2]],
                            [[0, 3, 4, 5]],
                        ],
                        "semantics": {
                            "surfaces": [{"type": "WallSurface"}],
                            "values": [[0, 0]],
                        },
                    },
                ],
            },
        },
    }
    buildings = parse_buildings(tile)
    polygons = buildings[0].geometries["2"]
    rings = [p.polygon.exterior for p in polygons]
    assert len(rings) == 1
    assert len(rings[0]) == 4
