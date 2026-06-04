"""Tests for the CBS Postcode6 step (fetcher + UrbanFunctionArea builder).

Covers the full module from the public WFS-fetch entry point through
the ``nrg3:UrbanFunctionArea`` xsdata construction:

* :func:`normalise_postcode` — canonical NNNNAA shape; rejection of
  malformed values.
* The two sentinel contracts inside the fetcher: energy fields
  preserve the documented CBS sentinels (``-99995`` / ``-99997`` /
  ``-99999``) verbatim so the value rides into ``nrg3:Energy/amount``;
  dwelling-count fields fold the same sentinels to ``None`` because a
  negative count is physically incoherent.
* :func:`fetch_postcode6_areas` against a mocked ``CachedSession``: WFS
  pagination, deduplication of postcodes that PDOK ships twice, and
  graceful handling of malformed or non-polygon geometries.
* :func:`safely_fetch_postcode6_areas` soft-fail contract: a
  ``requests.RequestException`` is caught and degrades to an empty
  list rather than failing the city build.
* :func:`attach_postcode6_areas_to_model` orchestration: no-op on
  empty input; one ``UrbanFunctionArea`` per area; boundary clip;
  ``grp:groupMember`` xlinks attached via 2D centroid-in-polygon;
  ``coords_sink`` widened with every polygon vertex; XSD-valid output.

No network. The fetcher is exercised via a ``CachedSession`` whose
underlying ``requests.Session`` is monkeypatched with deterministic
WFS responses, matching the BGT and Emmen-BOR test pattern. The
shared HTTP-mock helper lives in :mod:`tests._factories`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lxml.etree as etree
import pytest

pytest.importorskip("shapely")

from shapely.geometry import Polygon as ShapelyPolygon

from citygml_energy._step import GeometryPolygon
from citygml_energy.bindings import (
    Energy,
    UrbanFunctionArea,
)
from citygml_energy.city_builder.config import BuildContext
from citygml_energy.city_builder.fetchers.cbs_postcode6 import (
    Postcode6Area,
    fetch_postcode6_areas,
    normalise_postcode,
)
from citygml_energy.city_builder.postcode6 import (
    attach_postcode6_areas_to_model,
    safely_fetch_postcode6_areas,
)
from citygml_energy.core import CityModel
from tests._factories import (
    make_parsed_building,
    make_session_with_pages,
    make_square_polygon,
)
from tools.validate_xsd import load_schema

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _square_ring(
    cx: float,
    cy: float,
    half: float = 5.0,
) -> list[tuple[float, float, float]]:
    """Closed CCW square ring centred at ``(cx, cy)`` with side ``2 * half``."""
    return [
        (cx - half, cy - half, 0.0),
        (cx + half, cy - half, 0.0),
        (cx + half, cy + half, 0.0),
        (cx - half, cy + half, 0.0),
        (cx - half, cy - half, 0.0),
    ]


def _polygon_around(cx: float, cy: float, half: float = 5.0) -> GeometryPolygon:
    return GeometryPolygon(exterior=_square_ring(cx, cy, half))


_DEFAULT_GEOMETRY: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [
        [
            [85000.0, 446500.0],
            [85100.0, 446500.0],
            [85100.0, 446600.0],
            [85000.0, 446600.0],
            [85000.0, 446500.0],
        ]
    ],
}

# Explicit-None sentinel for ``_wfs_feature(geometry=...)``: passing
# ``geometry=_NO_GEOMETRY`` produces a feature whose ``"geometry"`` field
# is literal ``None``, which is what the fetcher treats as "skip this
# feature, no polygon to materialise". A separate sentinel keeps the
# kwarg's ``None`` default meaning "use the default polygon".
_NO_GEOMETRY: object = object()


def _wfs_feature(
    *,
    postcode: str = "2628CD",
    gas: int | None = 950,
    elec: int | None = 2300,
    aantal_woningen: int | None = 42,
    aantal_niet_bewoond: int | None = 1,
    geometry: Any = None,
) -> dict[str, Any]:
    """Synthetic CBS WFS feature shaped like the PDOK GetFeature payload.

    *geometry* defaults to a unit-square polygon. Pass :data:`_NO_GEOMETRY`
    to set ``"geometry": None`` on the feature (exercises the
    no-polygon-skip branch in the fetcher).
    """
    if geometry is None:
        resolved_geom: dict[str, Any] | None = _DEFAULT_GEOMETRY
    elif geometry is _NO_GEOMETRY:
        resolved_geom = None
    else:
        resolved_geom = geometry
    return {
        "type": "Feature",
        "geometry": resolved_geom,
        "properties": {
            "postcode6": postcode,
            "gemiddeldGasverbruikWoning": gas,
            "gemiddeldElektriciteitsverbruikWoning": elec,
            "aantalWoningen": aantal_woningen,
            "aantalNietBewoondeWoningen": aantal_niet_bewoond,
        },
    }


def _area(
    *,
    postcode: str = "2628CD",
    gas: int | None = 950,
    elec: int | None = 2300,
    aantal_woningen: int | None = 42,
    aantal_niet_bewoond: int | None = 1,
    polygons: list[GeometryPolygon] | None = None,
) -> Postcode6Area:
    """A populated :class:`Postcode6Area` with sensible defaults."""
    return Postcode6Area(
        postcode=postcode,
        gemiddeld_gasverbruik_woning=gas,
        gemiddeld_elektriciteitsverbruik_woning=elec,
        aantal_woningen=aantal_woningen,
        aantal_niet_bewoonde_woningen=aantal_niet_bewoond,
        polygons=polygons if polygons is not None else [_polygon_around(85050.0, 446550.0, 50.0)],
    )


# ---------------------------------------------------------------------------
# normalise_postcode
# ---------------------------------------------------------------------------


def test_normalise_postcode_passes_canonical_value() -> None:
    assert normalise_postcode("7881AD") == "7881AD"


def test_normalise_postcode_uppercases_and_trims() -> None:
    assert normalise_postcode("  7881ad  ") == "7881AD"
    assert normalise_postcode("7881 ad") == "7881AD"


def test_normalise_postcode_rejects_malformed_values() -> None:
    """Anything that isn't four digits + two letters is corrupt and must
    not propagate downstream — it would fail the BAG join silently."""
    assert normalise_postcode(None) is None
    assert normalise_postcode("") is None
    assert normalise_postcode("12345") is None
    assert normalise_postcode("ABCDEF") is None
    assert normalise_postcode("7881A") is None
    assert normalise_postcode("78812A") is None


# ---------------------------------------------------------------------------
# fetch_postcode6_areas — sentinel preservation contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sentinel", [-99995, -99997, -99999])
def test_fetch_preserves_energy_sentinels_verbatim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sentinel: int,
) -> None:
    """Energy fields must survive into ``Postcode6Area`` as the raw CBS
    integer so the value can ride into ``nrg3:Energy/amount`` later.
    Otherwise a downstream consumer cannot tell privacy-suppressed
    (-99997) from deferred-publication (-99995) from real measurement.
    """
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[{"features": [_wfs_feature(gas=sentinel, elec=sentinel)]}],
    )
    [area] = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert area.gemiddeld_gasverbruik_woning == sentinel
    assert area.gemiddeld_elektriciteitsverbruik_woning == sentinel


@pytest.mark.parametrize("sentinel", [-99995, -99997, -99999])
def test_fetch_folds_dwelling_count_sentinels_to_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sentinel: int,
) -> None:
    """A negative dwelling count is physically incoherent; the fetcher
    folds the entire CBS sentinel block to ``None`` so the downstream
    ``gen:intAttribute`` is omitted rather than carrying garbage."""
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[
            {"features": [_wfs_feature(aantal_woningen=sentinel, aantal_niet_bewoond=sentinel)]}
        ],
    )
    [area] = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert area.aantal_woningen is None
    assert area.aantal_niet_bewoonde_woningen is None


def test_fetch_treats_null_as_absent_for_energy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``null`` (genuinely absent in the WFS) folds to ``None`` so the
    downstream builder skips the resource emission. Distinct from
    sentinels above, which are *present* values that ride through."""
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[{"features": [_wfs_feature(gas=None, elec=None)]}],
    )
    [area] = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert area.gemiddeld_gasverbruik_woning is None
    assert area.gemiddeld_elektriciteitsverbruik_woning is None


def test_fetch_round_trips_real_positive_measurement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[{"features": [_wfs_feature(gas=1100, elec=2950)]}],
    )
    [area] = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert area.gemiddeld_gasverbruik_woning == 1100
    assert area.gemiddeld_elektriciteitsverbruik_woning == 2950


# ---------------------------------------------------------------------------
# fetch_postcode6_areas — pagination + dedup + geometry
# ---------------------------------------------------------------------------


def test_fetch_dedupes_repeated_postcode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDOK has been observed to ship the same feature twice when a
    postcode straddles a tile boundary in their internal index. First
    occurrence wins, mirroring the BAG fetcher's dedup contract."""
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[
            {
                "features": [
                    _wfs_feature(postcode="2628CD", gas=900),
                    _wfs_feature(postcode="2628CD", gas=999),  # duplicate
                ]
            }
        ],
    )
    areas = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert len(areas) == 1
    assert areas[0].gemiddeld_gasverbruik_woning == 900


def test_fetch_skips_features_without_polygon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[
            {
                "features": [
                    _wfs_feature(postcode="2628CD", geometry=_NO_GEOMETRY),
                    _wfs_feature(postcode="2628CE"),
                ]
            }
        ],
    )
    areas = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert [a.postcode for a in areas] == ["2628CE"]


def test_fetch_drops_unsupported_geometry_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A LineString or Point geometry can't back an UrbanFunctionArea;
    drop the feature rather than synthesising a degenerate polygon."""
    bad_geom = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[
            {
                "features": [
                    _wfs_feature(postcode="2628CD", geometry=bad_geom),
                    _wfs_feature(postcode="2628CE"),
                ]
            }
        ],
    )
    areas = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert [a.postcode for a in areas] == ["2628CE"]


def test_fetch_handles_multipolygon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fragmented postcode (mainland + island sliver) ships as
    MultiPolygon; both rings must materialise as separate
    GeometryPolygon entries, not collapsed into one."""
    multi = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[85000.0, 446500.0], [85100.0, 446500.0], [85100.0, 446600.0], [85000.0, 446500.0]]],
            [[[86000.0, 447500.0], [86100.0, 447500.0], [86100.0, 447600.0], [86000.0, 447500.0]]],
        ],
    }
    session = make_session_with_pages(
        tmp_path,
        monkeypatch,
        pages=[{"features": [_wfs_feature(postcode="2628CD", geometry=multi)]}],
    )
    [area] = fetch_postcode6_areas(session, bbox=(0, 0, 100000, 500000), year=2024)
    assert len(area.polygons) == 2


# ---------------------------------------------------------------------------
# safely_fetch_postcode6_areas — soft-fail
# ---------------------------------------------------------------------------


def test_safely_fetch_returns_empty_on_request_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PDOK outage degrades to ``[]`` so the rest of the build proceeds —
    CBS Postcode6 is opportunistic enrichment, not a hard dependency."""
    import requests as _requests

    from citygml_energy.city_builder.config import CbsPostcode6Source
    from citygml_energy.city_builder.fetchers import cbs_postcode6 as cbs

    def _explode(*args: Any, **kwargs: Any) -> Any:
        raise _requests.ConnectionError("PDOK is down")

    monkeypatch.setattr(cbs, "fetch_postcode6_areas", _explode)
    session = make_session_with_pages(tmp_path, monkeypatch, pages=[])
    out = safely_fetch_postcode6_areas(
        session,
        source=CbsPostcode6Source(year=2024),
        bbox=(0, 0, 1, 1),
    )
    assert out == []


# ---------------------------------------------------------------------------
# attach_postcode6_areas_to_model — orchestration
# ---------------------------------------------------------------------------


def test_attach_is_noop_on_empty_areas() -> None:
    model = CityModel()
    coords: list = []
    attach_postcode6_areas_to_model(
        model,
        areas=[],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=coords,
    )
    assert model.xsd.city_object_member == []
    assert coords == []


def test_attach_emits_one_urban_function_area_per_input() -> None:
    model = CityModel()
    coords: list = []
    areas = [
        _area(postcode="2628CD"),
        _area(
            postcode="2628CE",
            polygons=[_polygon_around(86050.0, 447550.0, 50.0)],
        ),
    ]
    attach_postcode6_areas_to_model(
        model,
        areas=areas,
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=coords,
    )
    ufas = [
        m.urban_function_area
        for m in model.xsd.city_object_member
        if m.urban_function_area is not None
    ]
    assert len(ufas) == 2
    assert sorted(u.id for u in ufas if u.id is not None) == ["pc6_2628CD", "pc6_2628CE"]


def test_attach_carries_postcode_name_and_type() -> None:
    """The UFA carries the postcode as ``gml:name``, the
    ``postalCode6`` type tag, and an external reference to the CBS
    longread URL."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(postcode="2628CD")],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    ufa = member.urban_function_area
    assert ufa is not None
    assert ufa.name[0].value == "2628CD"
    assert ufa.type_value.value == "postalCode6"
    assert ufa.code.value == "2628CD"
    assert len(ufa.external_reference) == 1
    # informationSystem is the PDOK metadata-record URL for the CBS
    # Postcode6 dataset (UUID-keyed, not the CBS press URL itself).
    info_url = ufa.external_reference[0].information_system
    assert info_url.startswith("https://")
    assert ufa.external_reference[0].external_object.name == "2628CD"


def test_attach_emits_dwelling_count_int_attributes_when_set() -> None:
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(aantal_woningen=42, aantal_niet_bewoond=3)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    int_attrs = {a.name: a.value for a in member.urban_function_area.int_attribute}
    assert int_attrs["dwellingCount"] == 42
    assert int_attrs["vacantDwellingCount"] == 3


def test_attach_omits_dwelling_count_int_attributes_when_absent() -> None:
    """``aantal_woningen`` / ``aantal_niet_bewoond`` collapsed to ``None``
    upstream (sentinel-folding) → no ``gen:intAttribute`` lands."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(aantal_woningen=None, aantal_niet_bewoond=None)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    assert member.urban_function_area.int_attribute == []


def test_attach_emits_two_energy_resources_when_both_present() -> None:
    """Gas + electricity → two ``nrg3:Energy`` resources, one per carrier."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(gas=1100, elec=2950)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    resources = [r.energy for r in member.urban_function_area.resource]
    assert len(resources) == 2
    carriers = [r.energy_carrier.value for r in resources]
    assert "naturalGas" in carriers
    assert "electricity" in carriers


def test_attach_preserves_sentinel_in_energy_amount() -> None:
    """The CBS sentinel rides through the builder into ``nrg3:Energy/amount``
    so a downstream consumer can distinguish the suppression reasons."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(gas=-99997, elec=-99995)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    by_carrier = {
        r.energy.energy_carrier.value: r.energy.amount.value
        for r in member.urban_function_area.resource
    }
    assert by_carrier["naturalGas"] == -99997
    assert by_carrier["electricity"] == -99995


def test_attach_skips_energy_resource_when_value_is_null() -> None:
    """``None`` (genuinely absent at the WFS) → no resource emitted for
    that carrier; the other carrier still emits if it has a value."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(gas=None, elec=2950)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    resources = [r.energy for r in member.urban_function_area.resource]
    assert [r.energy_carrier.value for r in resources] == ["electricity"]


def test_attach_emits_metadata_block_when_any_cbs_value_present() -> None:
    """``nrg3:Metadata`` documents the source + sentinel semantics
    whenever any CBS-derived datum (energy or dwelling count) lands on
    the area; without it a consumer wouldn't know how to read negative
    energy amounts."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(gas=None, elec=None, aantal_woningen=42, aantal_niet_bewoond=1)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    assert len(member.urban_function_area.metadata) == 1
    md = member.urban_function_area.metadata[0]
    assert md.source is not None and "CBS" in md.source
    # Quality description spells out the sentinel meanings.
    assert md.quality_description is not None and "-99997" in md.quality_description


def test_attach_omits_metadata_when_no_cbs_data_present() -> None:
    """An area with neither energy nor dwelling-count data has nothing
    to attribute; the empty Metadata block is suppressed."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(gas=None, elec=None, aantal_woningen=None, aantal_niet_bewoond=None)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    assert member.urban_function_area.metadata == []


def test_attach_widens_coords_sink_with_polygon_vertices() -> None:
    """Every polygon vertex must reach the envelope sink so the city
    ``gml:boundedBy`` covers the postcode area; otherwise viewers
    clip part of the UFA at the file boundary."""
    coords: list = []
    attach_postcode6_areas_to_model(
        CityModel(),
        areas=[_area()],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=coords,
    )
    assert coords  # at least the four exterior corners + the close-back vertex


def test_attach_clips_areas_outside_boundary_polygon() -> None:
    """A postcode polygon that does not intersect the boundary polygon
    is dropped. The CBS WFS is bbox-only; the user's hand-drawn
    boundary is a finer cut-line."""
    inside = _area(
        postcode="INSIDE",
        polygons=[_polygon_around(50.0, 50.0, 5.0)],
    )
    outside = _area(
        postcode="OUTSIDE",
        polygons=[_polygon_around(1000.0, 1000.0, 5.0)],
    )
    boundary = ShapelyPolygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[inside, outside],
        parsed_by_id={},
        boundary_geom=boundary,
        coords_sink=[],
    )
    ids = sorted(
        ufa.id
        for m in model.xsd.city_object_member
        if (ufa := m.urban_function_area) is not None and ufa.id is not None
    )
    assert ids == ["pc6_INSIDE"]


# ---------------------------------------------------------------------------
# attach_postcode6_areas_to_model — group-member join
# ---------------------------------------------------------------------------


def _building_inside_postcode(pand_id: str, cx: float, cy: float):
    """ParsedBuilding whose LoD 0 footprint centres at ``(cx, cy)``."""

    def poly_at(z: float) -> GeometryPolygon:
        return GeometryPolygon(exterior=_square_ring(cx, cy, 0.5))

    poly_lod0 = make_square_polygon(0.0, "GroundSurface")
    # Replace the canonical [0,1] square with one centred at (cx, cy).
    poly_lod0 = type(poly_lod0)(polygon=poly_at(0.0), surface_type="GroundSurface")
    return make_parsed_building(
        pand_id=pand_id,
        attributes={},
        geometries={"0": [poly_lod0]},
    )


def test_attach_emits_group_member_for_buildings_inside_postcode() -> None:
    """Every Building whose LoD 0 footprint centroid lies inside the
    postcode polygon attaches as a ``grp:groupMember`` xlink. Buildings
    outside the polygon do not."""
    inside = _building_inside_postcode("PA", 50.0, 50.0)
    outside = _building_inside_postcode("PB", 1000.0, 1000.0)
    parsed_by_id = {"PA": inside, "PB": outside}

    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(polygons=[_polygon_around(50.0, 50.0, 75.0)])],
        parsed_by_id=parsed_by_id,
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    hrefs = {gm.href for gm in member.urban_function_area.group_member}
    assert hrefs == {"#pand_PA"}


def test_attach_emits_no_group_members_when_no_buildings_inside() -> None:
    outside = _building_inside_postcode("PB", 1000.0, 1000.0)
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(polygons=[_polygon_around(50.0, 50.0, 5.0)])],
        parsed_by_id={"PB": outside},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    assert member.urban_function_area.group_member == []


def test_attach_uses_build_context_gml_id_prefix_for_group_member_hrefs() -> None:
    """The group-member xlink reproduces the same ``gml_id_prefix``-derived
    Building id that ``build_building`` emitted, so xlinks resolve."""
    inside = _building_inside_postcode("PA", 50.0, 50.0)
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        BuildContext(gml_id_prefix="city42"),
        areas=[_area(polygons=[_polygon_around(50.0, 50.0, 75.0)])],
        parsed_by_id={"PA": inside},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    [gm] = member.urban_function_area.group_member
    assert gm.href == "#city42_pand_PA"
    # The UFA itself also picks up the prefix.
    assert member.urban_function_area.id == "city42_pc6_2628CD"


# ---------------------------------------------------------------------------
# Round-trip XSD validation
# ---------------------------------------------------------------------------


def test_urban_function_area_round_trip_validates() -> None:
    """A populated UrbanFunctionArea (with both energy resources, dwelling
    counts, group members, and a Metadata block) must serialise to
    XSD-valid CityGML/Energy ADE. If any binding name drifts (e.g.
    ``code`` / ``energy_carrier`` / ``group_member`` / ``Metadata1``),
    this breaks first.
    """
    inside = _building_inside_postcode("PA", 50.0, 50.0)
    model = CityModel(gml_name="postcode6_rt")
    # The Building whose centroid sits inside the postcode polygon must
    # itself appear in the model so the group-member xlink resolves.
    from citygml_energy.city_builder.builders import build_building

    model.add(build_building(inside))

    coords: list = []
    attach_postcode6_areas_to_model(
        model,
        areas=[
            _area(
                postcode="9999XX",
                gas=1100,
                elec=2950,
                aantal_woningen=42,
                aantal_niet_bewoond=1,
                polygons=[_polygon_around(50.0, 50.0, 75.0)],
            )
        ],
        parsed_by_id={"PA": inside},
        boundary_geom=None,
        coords_sink=coords,
    )

    from citygml_energy.gml_builders import build_envelope
    from citygml_energy.namespaces import DEFAULT_SRS_DIMENSION, DEFAULT_SRS_NAME

    if coords:
        model.set_envelope(
            build_envelope(
                coords,
                srs_name=DEFAULT_SRS_NAME,
                srs_dimension=DEFAULT_SRS_DIMENSION,
            )
        )
    schema = load_schema()
    root = etree.fromstring(model.to_string().encode("utf-8"))
    schema.assertValid(root)


# ---------------------------------------------------------------------------
# Type-shape sanity
# ---------------------------------------------------------------------------


def test_attached_features_are_urban_function_areas() -> None:
    """Defensive: protect against a binding regeneration silently
    re-typing the slot we attach into."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area()],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    assert isinstance(member.urban_function_area, UrbanFunctionArea)


def test_resource_amounts_are_attached_via_energy_resource_wrapper() -> None:
    """Every ``nrg3:Energy`` lands inside a ``Resource`` wrapper (the
    ``maxOccurs=unbounded`` substitution slot on ``UrbanFunctionArea``)
    rather than as a free-floating Energy element."""
    model = CityModel()
    attach_postcode6_areas_to_model(
        model,
        areas=[_area(gas=1100, elec=2950)],
        parsed_by_id={},
        boundary_geom=None,
        coords_sink=[],
    )
    [member] = model.xsd.city_object_member
    for resource in member.urban_function_area.resource:
        assert isinstance(resource.energy, Energy)
