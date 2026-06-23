"""Tests for the 3D Basisvoorziening semantic-landcover path.

Covers the five seams in isolation, no network:

* :mod:`citygml_energy.city_builder.fetchers.threedbv` index parsing,
  latest-vintage selection, tile unzip, and soft-fail / cache self-heal.
* :mod:`citygml_energy.city_builder.landcover_class` the keep-or-drop
  decision, type-to-feature mapping, and label cleaning in one place.
* :mod:`citygml_energy.city_builder.cityjson_landcover_parse` vertex
  transform, building skip, AOI clip, and attribute pass-through.
* :mod:`citygml_energy.city_builder.builders.landcover` disposition
  rendering, BGT-to-CodeType classification, provenance, and XSD validity.
* :mod:`citygml_energy.city_builder.landcover` seam (null-source short
  circuit; attach count + envelope corners).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.appearance import (
    LANDCOVER_BRIDGE_DIFFUSE_COLOR,
    LANDCOVER_GENERIC_DIFFUSE_COLOR,
    LANDCOVER_PLANT_DIFFUSE_COLOR,
    LANDCOVER_ROAD_DIFFUSE_COLOR,
    LANDCOVER_TERRAIN_DIFFUSE_COLOR,
    LANDCOVER_THEME,
    LANDCOVER_WATER_DIFFUSE_COLOR,
    append_landcover_appearance,
    count_landcover_members,
)
from citygml_energy.city_builder.builders.landcover import build_landcover_object
from citygml_energy.city_builder.cityjson_landcover_parse import ParsedLandcover, parse_landcover
from citygml_energy.city_builder.config import BuildContext
from citygml_energy.city_builder.fetchers import threedbv
from citygml_energy.city_builder.http import CachedSession
from citygml_energy.city_builder.landcover import (
    LandcoverSource,
    attach_landcover_to_model,
    fetch_landcover,
)
from citygml_energy.city_builder.landcover_class import (
    LANDCOVER_FEATURE_QNAMES,
    classify_landcover,
)
from citygml_energy.core import CityModel
from citygml_energy.gml_builders import build_envelope
from citygml_energy.schema_types import (
    BRIDGE,
    GENERIC_CITY_OBJECT,
    LAND_USE,
    PLANT_COVER,
    ROAD,
    WATER_BODY,
)
from tools.validate_xsd import load_schema

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _square(z: float = 0.0, origin: tuple[float, float] = (0.0, 0.0)) -> GeometryPolygon:
    ox, oy = origin
    ring = [(ox, oy, z), (ox + 10, oy, z), (ox + 10, oy + 10, z), (ox, oy + 10, z)]
    return GeometryPolygon(exterior=ring, interiors=[])


def _parsed(
    object_id: str,
    object_type: str,
    attrs: dict[str, Any],
    polys: list[GeometryPolygon],
) -> ParsedLandcover:
    """Build a ParsedLandcover the way the parser does, with a real disposition.

    The builder and attach seams consume the disposition that
    ``classify_landcover`` resolves, so the tests carry the same decision the
    pipeline would. None of the object types used in these tests is a building,
    so the disposition is always present.
    """
    disposition = classify_landcover(object_type, attrs)
    assert disposition is not None
    return ParsedLandcover(object_id, object_type, attrs, polys, disposition)


def _index_feature(bladnr: str, year: int, link: str, size: int = 1000) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": []},
        "properties": {
            "bladnr": bladnr,
            "startdatum": f"{year}-01-01T00:00:00Z",
            "download_link": link,
            "download_size_bytes": size,
        },
    }


def _zip_of(cityjson_bytes: bytes, name: str = "tile.city.json") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, cityjson_bytes)
    return buf.getvalue()


def _synthetic_tile() -> dict[str, Any]:
    """A small CityJSON 2.0 tile: a LandUse + Road in the AOI, a Building to
    skip, a LandUse tagged ``3df_class`` ``Building`` to skip by class, and a
    LandUse far outside the AOI to be clipped."""
    return {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {"scale": [1.0, 1.0, 1.0], "translate": [0.0, 0.0, 0.0]},
        "vertices": [
            [0, 0, 0],
            [10, 0, 0],
            [10, 10, 0],
            [0, 10, 0],
            [500, 500, 0],
            [510, 500, 0],
            [510, 510, 0],
            [500, 510, 0],
        ],
        "CityObjects": {
            "01LANDUSE": {
                "type": "LandUse",
                "attributes": {"3df_class": "Terrain", "bgt_type": "oever, slootkant"},
                "geometry": [
                    {"type": "MultiSurface", "lod": "1.2", "boundaries": [[[0, 1, 2, 3]]]}
                ],
            },
            "01ROAD": {
                "type": "Road",
                "attributes": {"bgt_functie": "rijbaan lokale weg"},
                "geometry": [
                    {"type": "MultiSurface", "lod": "1.2", "boundaries": [[[0, 1, 2, 3]]]}
                ],
            },
            "01BUILDING": {
                "type": "Building",
                "attributes": {},
                "geometry": [
                    {"type": "MultiSurface", "lod": "1.2", "boundaries": [[[0, 1, 2, 3]]]}
                ],
            },
            "01LU_BUILDING": {
                # A building filed under the LandUse type, tagged Building by
                # 3df_class: must be skipped like a real Building, not rendered
                # as ground.
                "type": "LandUse",
                "attributes": {"3df_class": "Building"},
                "geometry": [
                    {"type": "MultiSurface", "lod": "1.2", "boundaries": [[[0, 1, 2, 3]]]}
                ],
            },
            "01FAR": {
                "type": "LandUse",
                "attributes": {},
                "geometry": [
                    {"type": "MultiSurface", "lod": "1.2", "boundaries": [[[4, 5, 6, 7]]]}
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# Fetcher: pure helpers
# ---------------------------------------------------------------------------


def test_year_of_parses_leading_year_and_rejects_garbage() -> None:
    assert threedbv._year_of("2022-01-01T00:00:00Z") == 2022
    assert threedbv._year_of("xx") is None
    assert threedbv._year_of(None) is None
    assert threedbv._year_of(2022) is None  # not a string


def test_parse_index_skips_rows_without_link_or_year() -> None:
    index = {
        "features": [
            _index_feature("a", 2022, "https://x/a.zip"),
            {"type": "Feature", "properties": {"bladnr": "b"}},  # no link
            {"type": "Feature", "properties": {"download_link": "https://x/c.zip"}},  # no year
        ]
    }
    refs = threedbv._parse_index(index)
    assert [r.bladnr for r in refs] == ["a"]
    assert refs[0].year == 2022


def test_unzip_cityjson_returns_member_bytes() -> None:
    payload = b'{"type":"CityJSON"}'
    assert threedbv._unzip_cityjson(_zip_of(payload)) == payload


def test_unzip_cityjson_raises_without_cityjson_member() -> None:
    other = io.BytesIO()
    with zipfile.ZipFile(other, "w") as zf:
        zf.writestr("readme.txt", b"hello")
    with pytest.raises(ValueError, match="no CityJSON member"):
        threedbv._unzip_cityjson(other.getvalue())


def test_unzip_cityjson_prefers_city_json_over_a_sidecar() -> None:
    # A sidecar metadata.json listed before the tile must not be selected: it
    # parses as JSON and then crashes the parser. _unzip_cityjson prefers the
    # *.city.json member over a bare *.json.
    tile = b'{"type":"CityJSON","version":"2.0"}'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("metadata.json", b'{"type":"FeatureCollection","features":[]}')
        zf.writestr("tile.city.json", tile)
    assert threedbv._unzip_cityjson(buf.getvalue()) == tile


def test_validate_bodies_reject_error_pages() -> None:
    with pytest.raises(ValueError, match="non-JSON"):
        threedbv._validate_index_body(b"<html>oops</html>")
    with pytest.raises(ValueError, match="non-zip"):
        threedbv._validate_zip_body(b"<ows:ExceptionReport/>")
    # Valid shapes do not raise.
    threedbv._validate_index_body(b'  {"type":"FeatureCollection"}')
    threedbv._validate_zip_body(threedbv._ZIP_MAGIC + b"rest")


# ---------------------------------------------------------------------------
# Fetcher: discovery + tile fetch (session methods monkeypatched, no network)
# ---------------------------------------------------------------------------


def _session(tmp_path: Path) -> CachedSession:
    return CachedSession(cache_dir=tmp_path / "cache", use_cache=False)


def test_discover_keeps_only_latest_vintage_deduped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two sheets at the 2020 vintage and the single 2022 RD-grid tile that
    # supersedes them: discovery must return only 2022, once.
    index = {
        "features": [
            _index_feature("30fz1", 2020, "https://x/30fz1_2020.zip", 400_000_000),
            _index_feature("30hn1", 2020, "https://x/30hn1_2020.zip", 440_000_000),
            _index_feature("90000_462000", 2022, "https://x/v_2022.zip", 37_000_000),
        ]
    }
    session = _session(tmp_path)
    monkeypatch.setattr(session, "get_json", lambda *a, **k: index)
    refs = threedbv.discover_landcover_tiles(session, (91059, 462341, 91309, 462591))
    assert refs is not None
    assert [r.download_link for r in refs] == ["https://x/v_2022.zip"]
    assert refs[0].year == 2022


def test_discover_soft_fails_on_network_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import requests as _requests

    session = _session(tmp_path)

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise _requests.ConnectionError("simulated outage")

    monkeypatch.setattr(session, "get_json", _boom)
    assert threedbv.discover_landcover_tiles(session, (0, 0, 1, 1)) is None


def test_discover_returns_none_for_empty_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session(tmp_path)
    monkeypatch.setattr(session, "get_json", lambda *a, **k: {"features": []})
    assert threedbv.discover_landcover_tiles(session, (0, 0, 1, 1)) is None


def test_fetch_tile_unzips_cityjson(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b'{"type":"CityJSON","version":"2.0"}'
    session = _session(tmp_path)
    monkeypatch.setattr(session, "get_bytes", lambda *a, **k: _zip_of(payload))
    ref = threedbv.LandcoverTileRef("x", 2022, "https://x/v.zip", 100)
    assert threedbv.fetch_tile_cityjson(session, ref) == payload


def test_fetch_tile_evicts_and_soft_fails_on_corrupt_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session(tmp_path)
    # Magic-valid (passes the validate hook) but truncated -> BadZipFile.
    monkeypatch.setattr(session, "get_bytes", lambda *a, **k: threedbv._ZIP_MAGIC + b"truncated")
    evicted: list[str] = []
    monkeypatch.setattr(session, "evict", lambda key: evicted.append(key))
    ref = threedbv.LandcoverTileRef("x", 2022, "https://x/v.zip", 100)
    assert threedbv.fetch_tile_cityjson(session, ref) is None
    assert evicted == [threedbv.tile_cache_key("https://x/v.zip")]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parse_landcover_keeps_aoi_objects_skips_buildings_and_clips() -> None:
    objects = parse_landcover(_synthetic_tile(), aoi_bbox=(0, 0, 20, 20))
    by_id = {o.object_id: o for o in objects}
    # Building (by type) and the LandUse tagged 3df_class=Building both skipped,
    # far object clipped.
    assert set(by_id) == {"01LANDUSE", "01ROAD"}
    land = by_id["01LANDUSE"]
    assert land.object_type == "LandUse"
    assert land.attributes["bgt_type"] == "oever, slootkant"
    assert len(land.polygons) == 1
    assert len(land.polygons[0].exterior) == 4


def test_parse_landcover_skips_landuse_tagged_building_by_class() -> None:
    # 3DBV files building geometry under LandUse objects tagged 3df_class
    # Building; those must not leak into the ground layer (the 3DBAG path owns
    # buildings). Regression for a Leiden tile where two thirds of LandUse was
    # actually building geometry standing on end.
    objects = parse_landcover(_synthetic_tile(), aoi_bbox=(0, 0, 20, 20))
    assert "01LU_BUILDING" not in {o.object_id for o in objects}
    assert all(o.attributes.get("3df_class") != "Building" for o in objects)


def test_parse_landcover_applies_transform() -> None:
    # Mirror the real 3DBV encoding: integer vertices + a mm scale + translate.
    # The square's edges are 10000 quanta = 10 m after scaling, so it stays well
    # above the sliver threshold (the 01FAR object lands ~500 m away and clips).
    tile = _synthetic_tile()
    tile["transform"] = {"scale": [0.001, 0.001, 0.001], "translate": [1000.0, 2000.0, 0.0]}
    tile["vertices"] = [
        [0, 0, 0],
        [10000, 0, 0],
        [10000, 10000, 0],
        [0, 10000, 0],
        [500000, 500000, 0],
        [510000, 500000, 0],
        [510000, 510000, 0],
        [500000, 510000, 0],
    ]
    objects = parse_landcover(tile, aoi_bbox=(1000.0, 2000.0, 1010.0, 2010.0))
    # Vertex 0 = (0,0,0) -> 0*0.001 + 1000 = 1000.0, the square's SW corner.
    land = next(o for o in objects if o.object_id == "01LANDUSE")
    x0, y0, _ = land.polygons[0].exterior[0]
    assert x0 == pytest.approx(1000.0)
    assert y0 == pytest.approx(2000.0)
    assert {o.object_id for o in objects} == {"01LANDUSE", "01ROAD"}  # 01FAR clipped


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def test_classify_landcover_drops_buildings() -> None:
    # The explicit Building / BuildingPart types and a LandUse object tagged
    # 3df_class Building are all dropped, so the 3DBAG path stays the only
    # source of buildings. One judgement, both signals.
    assert classify_landcover("Building", {}) is None
    assert classify_landcover("BuildingPart", {}) is None
    assert classify_landcover("LandUse", {"3df_class": "Building"}) is None


def test_classify_landcover_maps_known_types() -> None:
    cases = {
        "LandUse": (LAND_USE, "landuse"),
        "Road": (ROAD, "road"),
        "WaterBody": (WATER_BODY, "water"),
        "PlantCover": (PLANT_COVER, "plantcover"),
        "Bridge": (BRIDGE, "bridge"),
    }
    for object_type, (qname, id_kind) in cases.items():
        disposition = classify_landcover(object_type, {})
        assert disposition is not None
        assert disposition.feature_qname == qname
        assert disposition.id_kind == id_kind


def test_classify_landcover_falls_back_to_generic_for_unknown_type() -> None:
    # OtherConstruction (and any future type) is kept as a generic city object,
    # not dropped, so "convert everything in the tile" never silently loses one.
    disposition = classify_landcover("OtherConstruction", {})
    assert disposition is not None
    assert disposition.feature_qname == GENERIC_CITY_OBJECT
    assert disposition.id_kind == "landobject"


def test_classify_landcover_reads_and_cleans_labels() -> None:
    disposition = classify_landcover(
        "Road",
        {
            "3df_class": "Road",
            "bgt_functie": "rijbaan lokale weg",
            "bgt_type": "  ",  # whitespace-only, dropped
            "bgt_fysiekvoorkomen": "gesloten verharding",
        },
    )
    assert disposition is not None
    assert disposition.class_value == "Road"
    # bgt_functie kept, the blank bgt_type dropped; order preserved.
    assert disposition.function_values == ("rijbaan lokale weg",)
    assert disposition.usage_value == "gesloten verharding"


def test_classify_landcover_treats_empty_class_as_absent() -> None:
    disposition = classify_landcover("LandUse", {"3df_class": ""})
    assert disposition is not None
    assert disposition.class_value is None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def test_build_landcover_maps_each_type_and_classification() -> None:
    bc = BuildContext()
    cases = {
        "LandUse": "lod1_multi_surface",
        "Road": "lod1_multi_surface",
        "WaterBody": "lod1_multi_surface",
        "PlantCover": "lod1_multi_surface",
        "Bridge": "lod1_multi_surface",
        "OtherConstruction": "lod1_geometry",  # generic fallback
    }
    for otype, geom_attr in cases.items():
        parsed = _parsed(
            f"01{otype}",
            otype,
            {
                "3df_class": "X",
                "bgt_functie": "f",
                "bgt_type": "t",
                "bgt_fysiekvoorkomen": "fv",
                "bronhouder": "G0001",
                "bgt_status": "bestaand",
            },
            [_square()],
        )
        obj = build_landcover_object(parsed, bc)
        assert getattr(obj, geom_attr) is not None
        assert obj.class_value.value == "X"
        assert [c.value for c in obj.function] == ["f", "t"]
        assert [c.value for c in obj.usage] == ["fv"]
        assert obj.external_reference[0].external_object.name == f"01{otype}"
        assert {a.name for a in obj.string_attribute} == {"bronhouder", "bgtStatus"}


def test_build_landcover_renders_only_present_classification() -> None:
    # A disposition with no class label and one function leaves obj.class_value
    # unset and emits just the present function CodeType.
    parsed = _parsed(
        "01A",
        "LandUse",
        {"3df_class": "", "bgt_functie": "   ", "bgt_type": "waterloop"},
        [_square()],
    )
    obj = build_landcover_object(parsed, BuildContext())
    assert obj.class_value is None  # cleaned away upstream, nothing to render
    assert [c.value for c in obj.function] == ["waterloop"]


def test_landcover_model_validates_against_xsd() -> None:
    bc = BuildContext()
    # A WaterBody with an island hole exercises interior rings end to end.
    outer = [(0.0, 0.0, 0.0), (40.0, 0.0, 0.0), (40.0, 40.0, 0.0), (0.0, 40.0, 0.0)]
    inner = [(10.0, 10.0, 0.0), (20.0, 10.0, 0.0), (20.0, 20.0, 0.0), (10.0, 20.0, 0.0)]
    holed = GeometryPolygon(exterior=outer, interiors=[inner])
    objects = [
        _parsed("01LU", "LandUse", {"3df_class": "Terrain"}, [_square()]),
        _parsed("01RD", "Road", {"bgt_functie": "rijbaan"}, [_square(origin=(20, 0))]),
        _parsed("01WB", "WaterBody", {"bgt_type": "waterloop"}, [holed]),
        _parsed("01PC", "PlantCover", {"bgt_fysiekvoorkomen": "groen"}, [_square()]),
        _parsed("01BR", "Bridge", {"3df_class": "Bridge"}, [_square()]),
        _parsed("01OC", "OtherConstruction", {"3df_class": "Other"}, [_square()]),
    ]
    model = CityModel(gml_name="landcover")
    sink: list[tuple[float, float, float]] = []
    attach_landcover_to_model(model, bc, objects=objects, coords_sink=sink)
    append_landcover_appearance(model)
    # The landcover appearance is present and the whole document stays XSD-valid.
    assert any(m.appearance.theme == LANDCOVER_THEME for m in model.xsd.appearance_member)
    model.set_envelope(build_envelope(sink, srs_name=bc.srs_name, srs_dimension=bc.srs_dimension))
    schema = load_schema()
    schema.assertValid(etree.fromstring(model.to_string().encode("utf-8")))


# ---------------------------------------------------------------------------
# Appearance
# ---------------------------------------------------------------------------


def test_landcover_appearance_paints_each_class_in_one_theme() -> None:
    objects = [
        _parsed("01LU", "LandUse", {}, [_square()]),
        _parsed("01RD", "Road", {}, [_square(origin=(20, 0))]),
        _parsed("01WB", "WaterBody", {}, [_square(origin=(40, 0))]),
        _parsed("01PC", "PlantCover", {}, [_square(origin=(60, 0))]),
        _parsed("01BR", "Bridge", {}, [_square(origin=(80, 0))]),
        _parsed("01OC", "OtherConstruction", {}, [_square(origin=(100, 0))]),
    ]
    model = CityModel(gml_name="landcover")
    attach_landcover_to_model(model, BuildContext(), objects=objects, coords_sink=[])
    append_landcover_appearance(model)

    [member] = model.xsd.appearance_member
    appearance = member.appearance
    assert appearance.theme == LANDCOVER_THEME
    # One material per class present, each targeting only its lod1 MultiSurface.
    assert len(appearance.surface_data_member) == 6
    by_color = {
        tuple(p.x3_dmaterial.diffuse_color): p.x3_dmaterial.target
        for p in appearance.surface_data_member
    }
    expected = {
        LANDCOVER_TERRAIN_DIFFUSE_COLOR: "landuse",
        LANDCOVER_ROAD_DIFFUSE_COLOR: "road",
        LANDCOVER_WATER_DIFFUSE_COLOR: "water",
        LANDCOVER_PLANT_DIFFUSE_COLOR: "plantcover",
        LANDCOVER_BRIDGE_DIFFUSE_COLOR: "bridge",
        LANDCOVER_GENERIC_DIFFUSE_COLOR: "landobject",
    }
    for color, fragment in expected.items():
        targets = by_color[tuple(color)]
        assert len(targets) == 1
        assert targets[0].startswith("#")
        assert fragment in targets[0]
        assert targets[0].endswith("_lod1ms")
        assert "_poly_" not in targets[0]


def test_landcover_appearance_noop_without_landcover() -> None:
    model = CityModel()
    append_landcover_appearance(model)
    assert model.xsd.appearance_member == []


def test_every_landcover_qname_has_a_palette_color() -> None:
    # The palette and the count both derive from LANDCOVER_FEATURE_QNAMES, so a
    # new taxonomy row without a colour would ship an unpainted feature. Guard
    # the coverage here, loudly, rather than discovering it in the GML.
    from citygml_energy.city_builder.appearance import _LANDCOVER_COLOR_BY_QNAME

    missing = [q for q in LANDCOVER_FEATURE_QNAMES if q not in _LANDCOVER_COLOR_BY_QNAME]
    assert missing == []


def test_count_landcover_members_counts_each_feature_via_the_registry() -> None:
    objects = [
        _parsed("01LU", "LandUse", {}, [_square()]),
        _parsed("01RD", "Road", {}, [_square(origin=(20, 0))]),
        _parsed("01OC", "OtherConstruction", {}, [_square(origin=(40, 0))]),
    ]
    model = CityModel()
    attach_landcover_to_model(model, BuildContext(), objects=objects, coords_sink=[])
    assert count_landcover_members(model) == 3


# ---------------------------------------------------------------------------
# Seam
# ---------------------------------------------------------------------------


def test_fetch_landcover_short_circuits_without_source(tmp_path: Path) -> None:
    assert fetch_landcover(_session(tmp_path), source=None, bbox=(0, 0, 1, 1)) is None


def _tile_bytes(tile: dict[str, Any]) -> bytes:
    """Serialise a CityJSON dict the way the unzip step hands it to the parser."""
    return json.dumps(tile).encode()


@pytest.mark.parametrize(
    "member_json",
    [
        # Valid JSON, wrong document type: passes loads_json, then
        # CityJSONTile.from_dict raises ValueError.
        b'{"type":"FeatureCollection","features":[]}',
        # CityJSON-typed but a short vertex under a non-identity transform:
        # from_dict raises IndexError indexing v[2]. The wider except tuple
        # must catch it too.
        b'{"type":"CityJSON","version":"2.0",'
        b'"transform":{"scale":[2,2,2],"translate":[0,0,0]},'
        b'"vertices":[[1,2]],"CityObjects":{}}',
    ],
)
def test_fetch_landcover_soft_fails_and_evicts_on_unusable_tile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member_json: bytes
) -> None:
    # An opt-in input must degrade, not crash: a magic-valid archive whose
    # member is valid JSON but not a usable CityJSON document used to raise out
    # of fetch_landcover and abort the whole city build.
    import citygml_energy.city_builder.landcover as landcover_mod

    session = _session(tmp_path)
    ref = threedbv.LandcoverTileRef("x", 2022, "https://x/v.zip", 100)
    monkeypatch.setattr(landcover_mod, "discover_landcover_tiles", lambda *a, **k: [ref])
    monkeypatch.setattr(landcover_mod, "fetch_tile_cityjson", lambda *a, **k: member_json)
    evicted: list[str] = []
    monkeypatch.setattr(session, "evict", lambda key: evicted.append(key))

    result = fetch_landcover(session, source=LandcoverSource(), bbox=(0, 0, 1, 1))

    assert result == []  # soft-failed the sheet instead of raising
    # The poisoned cache entry is evicted so the next run re-fetches.
    assert evicted == [threedbv.tile_cache_key("https://x/v.zip")]


def test_fetch_landcover_clip_to_box_cuts_only_for_a_viewport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # One LandUse square 0..40 straddling a 0..20 AOI box. A viewport
    # (clip_to_box=True) cuts it at the box; a whole-area build keeps it whole,
    # mirroring the building clip on BuildExtent.clip_to_box so the two layers
    # cannot drift apart.
    import citygml_energy.city_builder.landcover as landcover_mod

    tile = {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {"scale": [1.0, 1.0, 1.0], "translate": [0.0, 0.0, 0.0]},
        "vertices": [[0, 0, 0], [40, 0, 0], [40, 40, 0], [0, 40, 0]],
        "CityObjects": {
            "01BIG": {
                "type": "LandUse",
                "attributes": {},
                "geometry": [
                    {"type": "MultiSurface", "lod": "1.2", "boundaries": [[[0, 1, 2, 3]]]}
                ],
            },
        },
    }
    session = _session(tmp_path)
    ref = threedbv.LandcoverTileRef("x", 2022, "https://x/v.zip", 100)
    monkeypatch.setattr(landcover_mod, "discover_landcover_tiles", lambda *a, **k: [ref])
    monkeypatch.setattr(landcover_mod, "fetch_tile_cityjson", lambda *a, **k: _tile_bytes(tile))
    bbox = (0.0, 0.0, 20.0, 20.0)

    clipped = fetch_landcover(session, source=LandcoverSource(), bbox=bbox, clip_to_box=True)
    whole = fetch_landcover(session, source=LandcoverSource(), bbox=bbox, clip_to_box=False)

    assert clipped is not None and whole is not None
    [clipped_obj] = clipped
    [whole_obj] = whole
    clipped_max_x = max(pt[0] for poly in clipped_obj.polygons for pt in poly.exterior)
    whole_max_x = max(pt[0] for poly in whole_obj.polygons for pt in poly.exterior)
    assert clipped_max_x == pytest.approx(20.0)
    assert whole_max_x == pytest.approx(40.0)


def test_attach_landcover_counts_and_pushes_envelope_corners() -> None:
    sink: list[tuple[float, float, float]] = []
    objects = [
        _parsed("01A", "LandUse", {}, [_square(z=5.0)]),
        _parsed("01B", "Road", {}, [_square(z=-2.0)]),
    ]
    n = attach_landcover_to_model(CityModel(), BuildContext(), objects=objects, coords_sink=sink)
    assert n == 2
    # Two bbox corners per object; the z extremes reach the sink for the envelope.
    assert len(sink) == 4
    zs = [c[2] for c in sink]
    assert max(zs) == pytest.approx(5.0)
    assert min(zs) == pytest.approx(-2.0)


def test_attach_landcover_noop_on_empty() -> None:
    sink: list[tuple[float, float, float]] = []
    assert attach_landcover_to_model(CityModel(), objects=None, coords_sink=sink) == 0
    assert attach_landcover_to_model(CityModel(), objects=[], coords_sink=sink) == 0
    assert sink == []
