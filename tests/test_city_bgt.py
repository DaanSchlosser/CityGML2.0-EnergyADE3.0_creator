"""Tests for the BGT ``vegetatieobject_punt`` cross-reference path.

Covers:

* :func:`fetch_bgt_trees` against a mocked ``CachedSession`` payload —
  the plus_type filter, ``voormalig`` status filter, pagination
  follow, and graceful degradation on HTTP errors.
* :func:`match_trees_to_bgt` nearest-neighbour logic at the
  4 m radius.
* :func:`build_solitary_vegetation_object` with a BGT match attached —
  emits ``core:externalReference`` (with ``informationSystem`` +
  ``externalObject.name`` + ``externalObject.uri``) and
  ``gen:dateAttribute name="bgtCreationDate"``, and the whole thing
  XSD-validates.

No network. The fetcher is exercised via a ``CachedSession`` whose
underlying ``requests.Session`` is monkeypatched with deterministic
responses, matching the existing ``test_city_bag.py`` pattern.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

pytest.importorskip("shapely")

from citygml_energy.bindings import (
    DateAttribute,
    ExternalReferenceType1,
    SolitaryVegetationObject,
)
from citygml_energy.city_builder.bgt_match import (
    MATCH_RADIUS_M,
    match_trees_to_bgt,
)
from citygml_energy.city_builder.builders import build_solitary_vegetation_object
from citygml_energy.city_builder.cityjson_trees_parse import ParsedTree
from citygml_energy.city_builder.fetchers.bgt import (
    BGT_INFORMATION_SYSTEM_URL,
    BgtTree,
    bgt_feature_uri,
    fetch_bgt_trees,
)
from citygml_energy.city_builder.http import CachedSession
from citygml_energy.core import CityModel
from citygml_energy.gml_builders import build_envelope

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _bgt_feature(
    lokaal_id: str,
    x: float,
    y: float,
    *,
    plus_type: str = "boom",
    status: str = "bestaand",
    creation_date: str | None = "2022-03-01T00:00:00Z",
    bronhouder: str = "G0114",
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [x, y]},
        "properties": {
            "lokaal_id": lokaal_id,
            "plus_type": plus_type,
            "status": status,
            "creation_date": creation_date,
            "bronhouder": bronhouder,
        },
    }


def _make_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pages: list[dict[str, Any]],
) -> CachedSession:
    """Build a ``CachedSession`` whose ``requests.Session.request`` returns
    *pages* in order. Caching is disabled so every test sees a fresh call.
    """
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=False)
    calls = iter(pages)

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]):
            self.status_code = 200
            self._payload = payload

        @property
        def content(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    class _FakeSession:
        headers: ClassVar[dict[str, str]] = {}

        def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(next(calls))

    monkeypatch.setattr(session, "_session", _FakeSession())
    return session


# ---------------------------------------------------------------------------
# fetch_bgt_trees
# ---------------------------------------------------------------------------


def test_fetch_bgt_trees_parses_minimum_feature_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _make_session(
        tmp_path, monkeypatch,
        pages=[{"features": [_bgt_feature("G0114.abc", 267050.0, 537780.0)], "links": []}],
    )
    trees = fetch_bgt_trees(session, bbox=(267000, 537700, 267100, 537800))
    assert len(trees) == 1
    assert trees[0].lokaal_id == "G0114.abc"
    assert trees[0].x_rd == 267050.0
    assert trees[0].y_rd == 537780.0
    assert trees[0].creation_date == _dt.date(2022, 3, 1)
    assert trees[0].bronhouder == "G0114"


def test_fetch_bgt_trees_filters_non_boom_plus_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The vegetatieobject_punt collection carries more than just trees —
    e.g. ``boomstronk`` (tree stumps). The fetcher must retain only live
    trees (``plus_type == "boom"``) so downstream joins are clean.
    """
    session = _make_session(
        tmp_path, monkeypatch,
        pages=[{
            "features": [
                _bgt_feature("G0114.tree", 267050.0, 537780.0, plus_type="boom"),
                _bgt_feature("G0114.stump", 267051.0, 537780.0, plus_type="boomstronk"),
            ],
            "links": [],
        }],
    )
    trees = fetch_bgt_trees(session, bbox=(267000, 537700, 267100, 537800))
    assert [t.lokaal_id for t in trees] == ["G0114.tree"]


def test_fetch_bgt_trees_drops_terminated_features(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``status == 'voormalig'`` = feature removed from the landscape and
    must not count against CFTree's live reconstruction.
    """
    session = _make_session(
        tmp_path, monkeypatch,
        pages=[{
            "features": [
                _bgt_feature("G0114.alive", 267050.0, 537780.0, status="bestaand"),
                _bgt_feature("G0114.dead", 267051.0, 537780.0, status="voormalig"),
            ],
            "links": [],
        }],
    )
    trees = fetch_bgt_trees(session, bbox=(267000, 537700, 267100, 537800))
    assert [t.lokaal_id for t in trees] == ["G0114.alive"]


def test_fetch_bgt_trees_follows_next_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a response carries a RFC-5005 ``rel="next"`` link we must
    walk every page until the link is gone or the page is empty.
    """
    session = _make_session(
        tmp_path, monkeypatch,
        pages=[
            {
                "features": [_bgt_feature("G0114.p1", 267050.0, 537780.0)],
                "links": [
                    {"rel": "next", "href": "https://host/next-cursor"},
                ],
            },
            {
                "features": [_bgt_feature("G0114.p2", 267051.0, 537781.0)],
                "links": [],
            },
        ],
    )
    trees = fetch_bgt_trees(session, bbox=(267000, 537700, 267100, 537800))
    assert sorted(t.lokaal_id for t in trees) == ["G0114.p1", "G0114.p2"]


def test_fetch_bgt_trees_degrades_gracefully_on_http_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PDOK outage must not fail the city build -- empty list + log warning.

    The fetcher retries on ``requests.RequestException`` (the base class for
    every requests-level network failure) and after exhausting retries the
    outer ``fetch_bgt_trees`` catches anything and returns ``[]``. Patching
    ``time.sleep`` keeps the retry backoff instantaneous -- the test used
    to wait ~9s for real backoff.
    """
    import requests as _requests

    session = CachedSession(
        cache_dir=tmp_path / "cache",
        use_cache=False,
        # Zero seconds between retries would still let the stdlib ``sleep(0)``
        # yield; setting ``backoff_seconds`` to 0 keeps the intent explicit.
        backoff_seconds=0.0,
    )

    class _BoomSession:
        headers: ClassVar[dict[str, str]] = {}

        def request(self, method: str, url: str, **kwargs: Any) -> None:
            raise _requests.ConnectionError("simulated network failure")

    monkeypatch.setattr(session, "_session", _BoomSession())
    trees = fetch_bgt_trees(session, bbox=(267000, 537700, 267100, 537800))
    assert trees == []


def test_bgt_feature_uri_has_stable_shape() -> None:
    """The cross-reference URI is a contract; test pins the shape."""
    url = bgt_feature_uri("G0114.abc")
    assert url == (
        "https://api.pdok.nl/lv/bgt/ogc/v1"
        "/collections/vegetatieobject_punt/items/G0114.abc"
    )


# ---------------------------------------------------------------------------
# match_trees_to_bgt
# ---------------------------------------------------------------------------


def _parsed_tree(gtid: str, x: float, y: float) -> ParsedTree:
    return ParsedTree(gtid=gtid, centroid=(x, y, 0.0), polygons=[], attributes={})


def _bgt(lokaal_id: str, x: float, y: float, **kw: Any) -> BgtTree:
    return BgtTree(
        lokaal_id=lokaal_id,
        x_rd=x,
        y_rd=y,
        creation_date=kw.get("creation_date"),
        bronhouder=kw.get("bronhouder", "G0114"),
    )


def test_match_pairs_closest_within_radius() -> None:
    trees = [_parsed_tree("1", 100.0, 100.0), _parsed_tree("2", 200.0, 100.0)]
    bgt = [
        _bgt("G0114.a", 101.0, 100.0),   # 1 m from tree 1
        _bgt("G0114.b", 200.5, 100.5),   # ~0.7 m from tree 2
        _bgt("G0114.c", 500.0, 500.0),   # far away — should match nothing
    ]
    matches = match_trees_to_bgt(trees, bgt)
    assert matches["1"].lokaal_id == "G0114.a"
    assert matches["2"].lokaal_id == "G0114.b"
    # Tree without a BGT neighbour within radius is absent from the dict.
    assert "3" not in matches


def test_match_drops_trees_beyond_radius() -> None:
    """A CFTree tree with no BGT point within the 4 m radius gets no entry."""
    trees = [_parsed_tree("alone", 1000.0, 1000.0)]
    bgt = [_bgt("G0114.far", 1010.0, 1010.0)]  # ~14 m away
    assert match_trees_to_bgt(trees, bgt, radius_m=MATCH_RADIUS_M) == {}


def test_match_ties_broken_by_input_order() -> None:
    """Two BGT points at equal distance: the first in input order wins.

    Keeps the join deterministic across re-runs when the sources
    haven't changed — important for diff-based reviews of the output.
    """
    trees = [_parsed_tree("1", 0.0, 0.0)]
    bgt = [
        _bgt("G0114.first", 1.0, 0.0),
        _bgt("G0114.second", -1.0, 0.0),
    ]
    assert match_trees_to_bgt(trees, bgt)["1"].lokaal_id == "G0114.first"


def test_match_allows_same_bgt_to_match_two_trees() -> None:
    """If CFTree over-reconstructs a single canopy as two objects, both
    reference the same BGT trunk — that is the most honest encoding.
    """
    trees = [
        _parsed_tree("double_1", 0.0, 0.0),
        _parsed_tree("double_2", 0.5, 0.0),
    ]
    bgt = [_bgt("G0114.one", 0.25, 0.0)]
    matches = match_trees_to_bgt(trees, bgt)
    assert matches["double_1"].lokaal_id == "G0114.one"
    assert matches["double_2"].lokaal_id == "G0114.one"


def test_match_empty_inputs_return_empty_dict() -> None:
    assert match_trees_to_bgt([], [_bgt("x", 0, 0)]) == {}
    assert match_trees_to_bgt([_parsed_tree("1", 0, 0)], []) == {}


# ---------------------------------------------------------------------------
# build_solitary_vegetation_object with BGT cross-reference
# ---------------------------------------------------------------------------


def _tree_with_polygons() -> ParsedTree:
    from citygml_energy._step import GeometryPolygon

    # Minimal triangle + triangle so the MultiSurface has two members.
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


def test_build_tree_emits_bgt_external_reference() -> None:
    tree = _tree_with_polygons()
    bgt = _bgt("G0114.abcdef", 0.3, 0.3, creation_date=_dt.date(2020, 4, 15))
    obj = build_solitary_vegetation_object(tree, bgt_match=bgt)
    assert isinstance(obj, SolitaryVegetationObject)
    assert len(obj.external_reference) == 1
    ref = obj.external_reference[0]
    assert isinstance(ref, ExternalReferenceType1)
    assert ref.information_system == BGT_INFORMATION_SYSTEM_URL
    assert ref.external_object.uri == (
        "https://api.pdok.nl/lv/bgt/ogc/v1/collections/"
        "vegetatieobject_punt/items/G0114.abcdef"
    )


def test_build_tree_bgt_ref_emits_only_uri_not_name() -> None:
    """``ExternalObjectReferenceType`` is an ``xs:choice`` — setting both
    ``name`` and ``uri`` yields an XSD-invalid file. This regression test
    pins the choice so a future refactor does not silently re-add the
    ``name`` branch.
    """
    tree = _tree_with_polygons()
    bgt = _bgt("G0114.xyz", 0.3, 0.3)
    obj = build_solitary_vegetation_object(tree, bgt_match=bgt)
    ext = obj.external_reference[0].external_object
    assert ext.uri is not None
    # ``name`` must be ``None`` so xsdata's xs:choice serialization
    # emits only <uri>, not <name>.
    assert ext.name is None


def test_build_tree_emits_bgt_creation_date_as_generic_attribute() -> None:
    tree = _tree_with_polygons()
    bgt = _bgt("G0114.x", 0.3, 0.3, creation_date=_dt.date(2018, 7, 5))
    obj = build_solitary_vegetation_object(tree, bgt_match=bgt)
    dates = {a.name: a.value for a in obj.date_attribute if isinstance(a, DateAttribute)}
    assert "bgtCreationDate" in dates
    assert str(dates["bgtCreationDate"]) == "2018-07-05"


def test_build_tree_without_bgt_match_has_no_external_reference() -> None:
    tree = _tree_with_polygons()
    obj = build_solitary_vegetation_object(tree)  # bgt_match defaulted to None
    assert obj.external_reference == []
    assert obj.date_attribute == []


def test_build_tree_with_bgt_no_creation_date_still_emits_external_reference() -> None:
    """BGT features without a populated creation_date must still produce
    the cross-reference link — only the date attribute is optional.
    """
    tree = _tree_with_polygons()
    bgt = _bgt("G0114.x", 0.3, 0.3, creation_date=None)
    obj = build_solitary_vegetation_object(tree, bgt_match=bgt)
    assert len(obj.external_reference) == 1
    assert obj.date_attribute == []


def test_bgt_cross_referenced_tree_round_trip_validates() -> None:
    """Smoke test: a tree with the BGT cross-reference attached serialises
    to XSD-valid CityGML. If any binding name drifts, this breaks first.
    """
    import subprocess
    import sys

    tree = _tree_with_polygons()
    bgt = _bgt("G0114.valid", 0.3, 0.3, creation_date=_dt.date(2021, 1, 1))
    obj = build_solitary_vegetation_object(
        tree,
        bgt_match=bgt,
        srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
        srs_dimension=3,
    )
    model = CityModel(gml_name="bgt_rt")
    model.add(obj)
    model.set_envelope(
        build_envelope(
            [p for poly in tree.polygons for p in poly.exterior],
            srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
            srs_dimension=3,
        )
    )
    out = Path("generated/_bgt_smoke.gml")
    out.parent.mkdir(exist_ok=True)
    model.write(out)
    result = subprocess.run(
        [sys.executable, "tools/validate_xsd.py", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert "VALID" in result.stdout, (result.stdout, result.stderr)
