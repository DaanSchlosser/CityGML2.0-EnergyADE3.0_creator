"""Shared test factory functions.

Plain Python helpers, not ``@pytest.fixture``-decorated, because the
existing test bodies call them directly inside test code rather than
accepting them as injected parameters. Keeping them as plain functions
means tests just ``from tests._factories import make_vbo`` instead of
adding a fixture argument to every signature.

Each factory returns a fully-populated dataclass with sensible defaults
that the test can override per-call. Defaults are picked to be the
most common values across the tests that previously hand-rolled their
own fixtures, so a `make_vbo()` with no arguments yields the boilerplate
shape most tests want; specific tests override what they care about.

The HTTP-mock helper :func:`make_session_with_pages` is the one
non-factory in this module: it builds a :class:`CachedSession` whose
underlying ``requests.Session`` is monkeypatched to return a fixed list
of payloads. The BGT and Emmen-BOR fetcher tests both use this exact
shape; centralising the monkeypatch avoids the byte-identical copy that
previously lived in both files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.cityjson_trees_parse import ParsedTree
from citygml_energy.city_builder.fetchers.bag import Pand, Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel
from citygml_energy.city_builder.http import CachedSession

if TYPE_CHECKING:
    import pytest

__all__ = [
    "make_pand",
    "make_parsed_building",
    "make_parsed_tree",
    "make_resolved_address",
    "make_session_with_pages",
    "make_square_polygon",
    "make_vbo",
]


# ---------------------------------------------------------------------------
# Geometry primitive
# ---------------------------------------------------------------------------


def make_square_polygon(
    z: float = 0.0,
    surface_type: str | None = None,
) -> SemanticPolygon:
    """Return a unit square at elevation *z*, optionally semantically typed.

    The unit square ``(0,0)→(1,0)→(1,1)→(0,1)`` is the canonical test
    geometry across the city-builder suite: small enough to keep
    fixtures readable, large enough that downstream geometry helpers
    (boundary intersect, normal calculation) produce non-degenerate
    output.
    """
    return SemanticPolygon(
        polygon=GeometryPolygon(
            exterior=[(0.0, 0.0, z), (1.0, 0.0, z), (1.0, 1.0, z), (0.0, 1.0, z)],
        ),
        surface_type=surface_type,
    )


# ---------------------------------------------------------------------------
# BAG dataclasses
# ---------------------------------------------------------------------------


def make_vbo(
    *,
    identificatie: str = "0503010000000042",
    pand_identificatie: str = "0503100000000001",
    gebruiksdoel: list[str] | None = None,
    oppervlakte: float | None = 85.0,
    status: str | None = None,
    postcode: str = "2628CD",
    huisnummer: int = 42,
    huisletter: str | None = None,
    toevoeging: str | None = None,
    street: str = "Mekelweg",
    woonplaats: str | None = None,
    point: tuple[float, float] | None = None,
    properties: dict[str, Any] | None = None,
) -> Verblijfsobject:
    """Return a :class:`Verblijfsobject` with the canonical Delft defaults.

    Defaults match the most common shape across the city tests
    (postcode 2628CD, huisnummer 42, Mekelweg, ``woonfunctie``); each
    field is keyword-only so a test can override exactly what it needs
    without remembering positional order.
    """
    return Verblijfsobject(
        identificatie=identificatie,
        pand_identificatie=pand_identificatie,
        gebruiksdoel=list(gebruiksdoel) if gebruiksdoel is not None else ["woonfunctie"],
        oppervlakte=oppervlakte,
        status=status,
        postcode=postcode,
        huisnummer=huisnummer,
        huisletter=huisletter,
        toevoeging=toevoeging,
        openbare_ruimte_naam=street,
        woonplaats=woonplaats,
        point=point,
        properties=dict(properties) if properties is not None else {},
    )


def make_pand(
    *,
    identificatie: str = "0503100000000001",
    bouwjaar: int | None = 1985,
    status: str | None = "Pand in gebruik",
    properties: dict[str, Any] | None = None,
) -> Pand:
    """Return a :class:`Pand` with the canonical Delft defaults."""
    return Pand(
        identificatie=identificatie,
        bouwjaar=bouwjaar,
        status=status,
        properties=dict(properties) if properties is not None else {},
    )


def make_resolved_address(
    *,
    vbo: Verblijfsobject | None = None,
    energy_label: EnergyLabel | None = None,
) -> ResolvedAddress:
    """Wrap a VBO + optional EnergyLabel in a :class:`ResolvedAddress`.

    A null *vbo* falls through to :func:`make_vbo` defaults, so the
    common "any resolved address" call site is just
    ``make_resolved_address()``.
    """
    return ResolvedAddress(
        vbo=vbo if vbo is not None else make_vbo(),
        energy_label=energy_label,
    )


# ---------------------------------------------------------------------------
# Parsed CityJSON
# ---------------------------------------------------------------------------


def make_parsed_building(
    *,
    pand_id: str = "0503100000000001",
    bouwjaar: int = 1985,
    attributes: dict[str, Any] | None = None,
    geometries: dict[str, list[SemanticPolygon]] | None = None,
) -> ParsedBuilding:
    """Return a :class:`ParsedBuilding` with the canonical LoD 0 + LoD 1 cube.

    *attributes* fully replaces the default attribute dict; *geometries*
    fully replaces the default LoD layout. This matches the most common
    test pattern: either the test cares about the attribute / geometry
    payload (and overrides the field) or it does not (and the defaults
    suffice).

    Default geometry: a unit-square footprint at z=0 (LoD 0) plus two
    single-square shells at z=0 and z=3 (LoD 1).
    """
    if attributes is None:
        attributes = {"oorspronkelijkbouwjaar": bouwjaar}
    if geometries is None:
        geometries = {
            "0": [make_square_polygon(0.0, "GroundSurface")],
            "1": [make_square_polygon(0.0), make_square_polygon(3.0)],
        }
    return ParsedBuilding(
        pand_id=pand_id,
        attributes=attributes,
        geometries=geometries,
    )


def make_parsed_tree(
    *,
    gtid: str = "1",
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    polygons: list[GeometryPolygon] | None = None,
    attributes: dict[str, Any] | None = None,
) -> ParsedTree:
    """Return a :class:`ParsedTree` whose centroid sits at (x, y, z).

    Used by the BGT and Emmen-BOR tree-matching tests. A null
    *polygons* yields an empty geometry list, which is what the
    nearest-neighbour matchers need (they only consult the centroid).
    Tests that need real geometry pass a non-empty list.
    """
    return ParsedTree(
        gtid=gtid,
        centroid=(x, y, z),
        polygons=list(polygons) if polygons is not None else [],
        attributes=dict(attributes) if attributes is not None else {},
    )


# ---------------------------------------------------------------------------
# HTTP mock for fetcher tests
# ---------------------------------------------------------------------------


def make_session_with_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pages: list[dict[str, Any]],
) -> CachedSession:
    """Build a :class:`CachedSession` whose ``requests.Session.request``
    returns *pages* in order.

    Caching is disabled so every test sees a fresh call. Used by the
    BGT, Emmen-BOR, and CBS-Postcode6 fetcher tests, all of which mock
    a paginated WFS / ArcGIS response by handing in a list of payload
    dicts and asserting on the parsed output.
    """
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=False)
    calls = iter(pages)

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
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
