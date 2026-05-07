"""Tests for the Emmen BOR (`bor_groen_bomen_beschermd`) tree enrichment.

Mirrors :mod:`tests.test_city_bgt`. Covers:

* :func:`fetch_bor_trees` against a mocked ``CachedSession``: ArcGIS
  REST attribute parsing, ``resultOffset`` pagination, and graceful
  degradation on HTTP errors.
* :func:`match_trees_to_bor` nearest-neighbour logic at the 4 m radius.
* :func:`build_solitary_vegetation_object` with a BOR match attached:
  emits ``veg:species`` (the only typed CityGML 2.0 vegetation slot
  the source can fill honestly), an ``int_attribute name="plantingYear"``,
  ``string_attribute`` siblings for the remaining fields (protection
  status, growth form, height/diameter class bands, etc.), a second
  ``core:externalReference``, and the whole thing XSD-validates
  side-by-side with the BGT cross-reference.

No network. The fetcher is exercised via a ``CachedSession`` whose
underlying ``requests.Session`` is monkeypatched with deterministic
ArcGIS REST responses, matching the ``test_city_bgt.py`` pattern.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

import pytest

pytest.importorskip("shapely")

from citygml_energy.bindings import (
    CodeType,
    ExternalReferenceType1,
    IntAttribute,
    SolitaryVegetationObject,
    StringAttribute,
)
from citygml_energy.city_builder.builders import build_solitary_vegetation_object
from citygml_energy.city_builder.config import BuildContext
from citygml_energy.city_builder.cityjson_trees_parse import ParsedTree
from citygml_energy.city_builder.fetchers.bgt import BgtTree
from citygml_energy.city_builder.fetchers.emmen_bor import (
    BOR_INFORMATION_SYSTEM_URL,
    BorTree,
    bor_feature_uri,
    fetch_bor_trees,
)
from citygml_energy.city_builder.http import CachedSession
from citygml_energy.city_builder.tree_matching import (
    MATCH_RADIUS_M,
    match_nearest_within,
)
from citygml_energy.core import CityModel
from citygml_energy.gml_builders import build_envelope
from citygml_energy.namespaces import CS_EMMEN_BOR_TREES


from tests._factories import make_parsed_tree, make_session_with_pages


def match_trees_to_bor(
    trees: Iterable[ParsedTree],
    bor_trees: Iterable[BorTree],
    *,
    radius_m: float = MATCH_RADIUS_M,
) -> dict[str, BorTree]:
    """Local test helper: thin shim around :func:`match_nearest_within`.

    Production no longer carries a BOR-typed wrapper (the inline
    pipeline call shoulders the kwargs); this shim keeps the test
    bodies short for the ~4 calls below.
    """
    return match_nearest_within(
        trees, bor_trees,
        candidate_xy=lambda b: (b.x_rd, b.y_rd),
        radius_m=radius_m,
        register_label="Emmen BOR",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _bor_feature(
    boom_id: int,
    x: float,
    y: float,
    *,
    soortnaam: str | None = "Quercus palustris",
    soortnaam_ned: str | None = "Moeraseik",
    jaarvanaanleg: int | None = 1960,
    boomhoogteklasseactueel: str | None = "18 tot 24 m.",
    stamdiameterklasse: str | None = "0,5 tot 0,75 m.",
    beschermingsstatus: str | None = "Bijzondere boom",
    beschermingsstatus_detail: str | None = "Bomenstructuur boom",
    type_: str | None = "Boom vrij uitgroeiend",
    standplaats: str | None = "Gras- en kruidachtigen",
    standplaats_detail: str | None = "Gazon",
) -> dict[str, Any]:
    return {
        "geometry": {"x": x, "y": y},
        "attributes": {
            "boom_id": boom_id,
            "soortnaam": soortnaam,
            "soortnaam_ned": soortnaam_ned,
            "jaarvanaanleg": jaarvanaanleg,
            "boomhoogteklasseactueel": boomhoogteklasseactueel,
            "stamdiameterklasse": stamdiameterklasse,
            "beschermingsstatus": beschermingsstatus,
            "beschermingsstatus_detail": beschermingsstatus_detail,
            "type": type_,
            "standplaats": standplaats,
            "standplaats_detail": standplaats_detail,
        },
    }


_make_session = make_session_with_pages


def _parsed_tree(gtid: str, x: float, y: float) -> ParsedTree:
    return make_parsed_tree(gtid=gtid, x=x, y=y)


def _bor(boom_id: str, x: float, y: float, **overrides: Any) -> BorTree:
    base: dict[str, Any] = dict(
        boom_id=boom_id,
        x_rd=x,
        y_rd=y,
        species_latin="Quercus palustris",
        species_dutch="Moeraseik",
        planting_year=1960,
        height_class="18 tot 24 m.",
        trunk_diameter_class="0,5 tot 0,75 m.",
        protection_status="Bijzondere boom",
        protection_status_detail="Bomenstructuur boom",
        growth_form="Boom vrij uitgroeiend",
        stand_location="Gras- en kruidachtigen",
        stand_location_detail="Gazon",
    )
    base.update(overrides)
    return BorTree(**base)


# ---------------------------------------------------------------------------
# fetch_bor_trees
# ---------------------------------------------------------------------------


def test_fetch_bor_trees_parses_arcgis_attribute_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _make_session(
        tmp_path, monkeypatch,
        pages=[{
            "features": [_bor_feature(1, 264100.0, 537800.0)],
            "exceededTransferLimit": False,
        }],
    )
    trees = fetch_bor_trees(session, bbox=(264000, 537700, 264200, 537900))
    assert len(trees) == 1
    t = trees[0]
    assert t.boom_id == "1"
    assert t.species_latin == "Quercus palustris"
    assert t.species_dutch == "Moeraseik"
    assert t.planting_year == 1960
    assert t.protection_status == "Bijzondere boom"
    assert t.growth_form == "Boom vrij uitgroeiend"
    assert (t.x_rd, t.y_rd) == (264100.0, 537800.0)


def test_fetch_bor_trees_drops_records_without_boom_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A record without a stable ``boom_id`` cannot be cross-referenced;
    it must not produce a ``BorTree`` so downstream consumers never see
    a ``None`` handle."""
    feat = _bor_feature(0, 1, 2)
    feat["attributes"]["boom_id"] = None
    session = _make_session(
        tmp_path, monkeypatch,
        pages=[{"features": [feat], "exceededTransferLimit": False}],
    )
    assert fetch_bor_trees(session, bbox=(0, 0, 10, 10)) == []


def test_fetch_bor_trees_normalises_empty_string_and_none_placeholders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emmen sometimes ships ``""`` and ``"None"`` for unpopulated cells.
    Both must collapse to Python ``None`` so the GML output stays clean.
    """
    feat = _bor_feature(
        7, 1, 2,
        soortnaam="",
        soortnaam_ned="None",
        beschermingsstatus_detail=None,
    )
    session = _make_session(
        tmp_path, monkeypatch,
        pages=[{"features": [feat], "exceededTransferLimit": False}],
    )
    trees = fetch_bor_trees(session, bbox=(0, 0, 10, 10))
    assert len(trees) == 1
    t = trees[0]
    assert t.species_latin is None
    assert t.species_dutch is None
    assert t.protection_status_detail is None


def test_fetch_bor_trees_follows_resultoffset_pagination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ArcGIS REST signals further pages via ``exceededTransferLimit``
    plus the same-sized page count. The fetcher must walk both pages.
    """
    page1 = {
        "features": [
            _bor_feature(i, float(i), 0.0, soortnaam=f"sp_{i}")
            for i in range(2000)
        ],
        "exceededTransferLimit": True,
    }
    page2 = {
        "features": [_bor_feature(9999, 1.0, 1.0, soortnaam="sp_last")],
        "exceededTransferLimit": False,
    }
    session = _make_session(tmp_path, monkeypatch, pages=[page1, page2])
    trees = fetch_bor_trees(session, bbox=(0, 0, 10, 10))
    assert len(trees) == 2001
    assert trees[-1].boom_id == "9999"


def test_fetch_bor_trees_degrades_gracefully_on_http_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Network or parse errors return ``[]``: the BOR enrichment is
    opportunistic and must not abort a city build when Emmen's tenant
    is unreachable.
    """
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=False)

    class _BoomSession:
        headers: ClassVar[dict[str, str]] = {}

        def request(self, method: str, url: str, **kwargs: Any) -> Any:
            import requests as _r
            raise _r.ConnectionError("simulated")

    monkeypatch.setattr(session, "_session", _BoomSession())
    assert fetch_bor_trees(session, bbox=(0, 0, 10, 10)) == []


def test_bor_feature_uri_keys_on_boom_id_not_objectid() -> None:
    """The ``boom_id`` URL must dereference back to one record. We
    pin the format here so a future refactor cannot quietly switch
    to the volatile ``OBJECTID`` handle.
    """
    uri = bor_feature_uri("25649")
    assert "where=boom_id%3D25649" in uri
    assert "OBJECTID" not in uri


# ---------------------------------------------------------------------------
# match_trees_to_bor
# ---------------------------------------------------------------------------


def test_match_picks_nearest_within_radius() -> None:
    trees = [_parsed_tree("1", 0.0, 0.0)]
    bor = [
        _bor("far", 10.0, 0.0),
        _bor("near", 1.0, 0.0),
    ]
    assert match_trees_to_bor(trees, bor)["1"].boom_id == "near"


def test_match_drops_trees_outside_radius() -> None:
    trees = [_parsed_tree("1", 0.0, 0.0)]
    bor = [_bor("far", 5.0, 0.0)]  # 5 m, just outside the 4 m radius
    assert match_trees_to_bor(trees, bor, radius_m=MATCH_RADIUS_M) == {}


def test_match_empty_inputs_return_empty_dict() -> None:
    assert match_trees_to_bor([], [_bor("x", 0, 0)]) == {}
    assert match_trees_to_bor([_parsed_tree("1", 0, 0)], []) == {}


# ---------------------------------------------------------------------------
# build_solitary_vegetation_object with a BOR match
# ---------------------------------------------------------------------------


def _tree_with_polygons() -> ParsedTree:
    from citygml_energy._step import GeometryPolygon

    p1 = GeometryPolygon(
        exterior=[(0, 0, 0), (1, 0, 0), (0.5, 1, 0), (0, 0, 0)]
    )
    p2 = GeometryPolygon(
        exterior=[(0, 0, 0), (0.5, 1, 0), (0.5, 0.5, 1), (0, 0, 0)]
    )
    return ParsedTree(
        gtid="42", centroid=(0.3, 0.3, 0.3),
        polygons=[p1, p2],
        attributes={"trunk_H_m": 10.0, "crown_width_m": 5.0},
    )


def test_build_tree_writes_native_species_from_bor() -> None:
    """``veg:species`` is the only typed CityGML 2.0 vegetation slot
    the BOR enrichment touches: a Latin binomial fits ``species`` by
    SIG3D convention. The other typed slots (``class`` / ``function`` /
    ``usage``) stay untouched so an SIG3D-aware viewer is not
    misled into reading a regulatory tag as a horticultural function.
    """
    tree = _tree_with_polygons()
    obj = build_solitary_vegetation_object(tree, bor_match=_bor("25649", 0.3, 0.3))
    assert isinstance(obj, SolitaryVegetationObject)
    assert isinstance(obj.species, CodeType)
    assert obj.species.value == "Quercus palustris"
    assert obj.species.code_space == CS_EMMEN_BOR_TREES
    # Regression guard: protection status and growth form must NOT
    # land in ``veg:function`` / ``veg:class``. See § 3.3 of the
    # vegetation integration report for the reasoning.
    assert obj.class_value is None
    assert obj.function == []


def test_build_tree_writes_planting_year_as_int_attribute() -> None:
    tree = _tree_with_polygons()
    obj = build_solitary_vegetation_object(tree, bor_match=_bor("x", 0.3, 0.3))
    ints = {
        a.name: a.value
        for a in obj.int_attribute
        if isinstance(a, IntAttribute)
    }
    assert ints.get("plantingYear") == 1960


def test_build_tree_writes_protection_and_growth_form_as_string_attributes() -> None:
    """Protection regime and growth form land in ``gen:stringAttribute``,
    not in the typed ``veg:function`` / ``veg:class`` slots, because
    they are not horticultural classifications. See § 3.3.
    """
    tree = _tree_with_polygons()
    obj = build_solitary_vegetation_object(tree, bor_match=_bor("x", 0.3, 0.3))
    strings = {
        a.name: a.value
        for a in obj.string_attribute
        if isinstance(a, StringAttribute)
    }
    assert strings["speciesCommonName"] == "Moeraseik"
    assert strings["heightClass"] == "18 tot 24 m."
    assert strings["trunkDiameterClass"] == "0,5 tot 0,75 m."
    assert strings["protectionStatus"] == "Bijzondere boom"
    assert strings["protectionStatusDetail"] == "Bomenstructuur boom"
    assert strings["growthForm"] == "Boom vrij uitgroeiend"
    assert strings["standLocation"] == "Gras- en kruidachtigen"
    assert strings["standLocationDetail"] == "Gazon"


def test_build_tree_omits_slots_for_missing_bor_fields() -> None:
    """A BOR record with sparse fields must not emit empty elements.
    The CityGML output should reflect exactly what the source carries.
    """
    tree = _tree_with_polygons()
    bor = _bor(
        "x", 0.3, 0.3,
        species_latin=None,
        growth_form=None,
        protection_status=None,
        planting_year=None,
        species_dutch=None,
        height_class=None,
        trunk_diameter_class=None,
        protection_status_detail=None,
        stand_location=None,
        stand_location_detail=None,
    )
    obj = build_solitary_vegetation_object(tree, bor_match=bor)
    assert obj.species is None
    assert obj.class_value is None
    assert obj.function == []
    assert obj.int_attribute == []
    assert obj.string_attribute == []
    # The cross-reference is the one slot that survives a fully-empty
    # attribute payload, because the boom_id alone is enough to link
    # back to Emmen's register.
    assert len(obj.external_reference) == 1


def test_build_tree_emits_bor_external_reference_with_boom_id_uri() -> None:
    tree = _tree_with_polygons()
    obj = build_solitary_vegetation_object(tree, bor_match=_bor("25649", 0.3, 0.3))
    assert len(obj.external_reference) == 1
    ref = obj.external_reference[0]
    assert isinstance(ref, ExternalReferenceType1)
    assert ref.information_system == BOR_INFORMATION_SYSTEM_URL
    assert ref.external_object is not None
    uri = ref.external_object.uri
    assert uri is not None
    assert "boom_id%3D25649" in uri
    # ``ExternalObjectReferenceType`` is an xs:choice — only ``uri``,
    # not ``name``, otherwise the file fails XSD validation.
    assert ref.external_object.name is None


def test_build_tree_with_both_bgt_and_bor_emits_two_external_references() -> None:
    """``core:AbstractCityObjectType.externalReference`` is unbounded;
    a tree matched against both authorities must carry both links so
    downstream consumers can dereference whichever they key on.
    """
    tree = _tree_with_polygons()
    bgt = BgtTree(
        lokaal_id="G0114.abc", x_rd=0.3, y_rd=0.3,
        creation_date=None, bronhouder="G0114",
    )
    obj = build_solitary_vegetation_object(
        tree, bgt_match=bgt, bor_match=_bor("25649", 0.3, 0.3),
    )
    info_systems = [r.information_system for r in obj.external_reference]
    assert len(info_systems) == 2
    assert any("pdok.nl" in s for s in info_systems)
    assert any("emmen.nl" in s for s in info_systems)


def test_bor_enriched_tree_round_trip_validates(tmp_path: Path) -> None:
    """Smoke test: a tree with the full BOR enrichment serialises to
    XSD-valid CityGML. If any binding name drifts (e.g. ``species`` /
    ``class_value`` / ``int_attribute`` / ``string_attribute``), this
    breaks first.
    """
    import lxml.etree as etree

    from tools.validate_xsd import load_schema

    tree = _tree_with_polygons()
    obj = build_solitary_vegetation_object(
        tree,
        BuildContext(
            srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
            srs_dimension=3,
        ),
        bor_match=_bor("25649", 0.3, 0.3),
    )
    model = CityModel(gml_name="bor_rt")
    model.add(obj)
    model.set_envelope(
        build_envelope(
            [p for poly in tree.polygons for p in poly.exterior],
            srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
            srs_dimension=3,
        )
    )
    out = tmp_path / "_bor_smoke.gml"
    model.write(out)
    schema = load_schema()
    root = etree.fromstring(out.read_bytes())
    schema.assertValid(root)
