"""Unit tests for the xsdata construction helpers in the city builder."""

from __future__ import annotations

from datetime import date

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.builders import (
    attach_building_units_to_building,
    build_address,
    build_building,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel


def _square(z: float, surface_type: str | None = None) -> SemanticPolygon:
    return SemanticPolygon(
        polygon=GeometryPolygon(
            exterior=[(0.0, 0.0, z), (1.0, 0.0, z), (1.0, 1.0, z), (0.0, 1.0, z)],
        ),
        surface_type=surface_type,
    )


def _parsed() -> ParsedBuilding:
    return ParsedBuilding(
        pand_id="0503100000000001",
        attributes={"oorspronkelijkbouwjaar": 1985},
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(0.0), _square(3.0)],
        },
    )


def _vbo(
    street: str = "Mekelweg",
    point: tuple[float, float] | None = None,
) -> Verblijfsobject:
    return Verblijfsobject(
        identificatie="0503010000000042",
        pand_identificatie="0503100000000001",
        gebruiksdoel=["woonfunctie"],
        oppervlakte=85.0,
        status="Verblijfsobject in gebruik",
        postcode="2628CD",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam=street,
        point=point,
        properties={},
    )


def _resolved(energy: str | None = None, street: str = "Mekelweg") -> ResolvedAddress:
    label = None
    if energy is not None:
        label = EnergyLabel(
            postcode="2628CD",
            huisnummer=42,
            huisletter=None,
            toevoeging=None,
            bag_verblijfsobject_id=None,
            energieklasse=energy,
            registratiedatum=date(2024, 1, 1),
            opnamedatum=None,
            geldig_tot=date(2034, 1, 1),
        )
    return ResolvedAddress(vbo=_vbo(street=street), energy_label=label)


# ---------------------------------------------------------------------------
# build_building
# ---------------------------------------------------------------------------


def test_build_building_sets_id_and_year_of_construction() -> None:
    building = build_building(_parsed())
    # BAG identificaties are pure digits → not valid xs:ID; builder prepends
    # a semantic kind prefix ("pand") to stay schema-valid.
    assert building.id == "pand_0503100000000001"
    assert str(building.year_of_construction) == "1985"


def test_build_building_attaches_only_requested_lods() -> None:
    only_lod0 = build_building(_parsed(), lods=(0,))
    assert only_lod0.lod0_foot_print is not None
    assert only_lod0.lod1_solid is None


def test_build_building_lod1_is_solid_with_composite_surface() -> None:
    building = build_building(_parsed(), lods=(1,))
    shell = building.lod1_solid.solid.exterior.composite_surface
    assert shell.id.endswith("_lod1_shell")


def _posns_of_lod0(building) -> list[list[float]]:
    """Flatten every gml:posList value in the LoD 0 MultiSurface."""
    return [
        poly.polygon.exterior.linear_ring.pos_list.value
        for poly in building.lod0_foot_print.multi_surface.surface_member
    ]


def test_build_building_lifts_lod0_to_b3_h_maaiveld() -> None:
    """3DBAG publishes LoD 0 at NAP=0 while LoD 1/2 sit on the
    terrain height ``b3_h_maaiveld``. In elevated areas (e.g. Emmer-
    Compascuum at ~13 m NAP) the two representations are otherwise
    rendered metres apart vertically. The builder must re-anchor every
    LoD 0 vertex to the maaiveld.
    """
    parsed = ParsedBuilding(
        pand_id="0114100000202121",
        attributes={"oorspronkelijkbouwjaar": 1985, "b3_h_maaiveld": 13.35},
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(13.35), _square(16.9)],
        },
    )
    building = build_building(parsed, lods=(0,))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 13.35 for z in zs), f"expected all z=13.35, got {zs}"


def test_build_building_lod0_falls_back_to_min_lod1_when_maaiveld_missing() -> None:
    """Without ``b3_h_maaiveld`` we still avoid a below-ground LoD 0:
    the builder falls back to the minimum Z observed on LoD 1 (or 2).
    """
    parsed = ParsedBuilding(
        pand_id="0114100000000001",
        attributes={"oorspronkelijkbouwjaar": 1985},  # no maaiveld
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(12.1), _square(16.4)],
        },
    )
    building = build_building(parsed, lods=(0,))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 12.1 for z in zs), f"expected all z=12.1, got {zs}"


def test_build_building_lod0_leaves_geometry_untouched_when_no_ground_hint() -> None:
    """No maaiveld, no LoD 1, no LoD 2: return the polygons as-is
    rather than invent a ground plane.
    """
    parsed = ParsedBuilding(
        pand_id="x",
        attributes={},
        geometries={"0": [_square(0.0, "GroundSurface")]},
    )
    building = build_building(parsed, lods=(0,))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 0.0 for z in zs)


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------


def test_build_address_composes_xal_structure() -> None:
    address = build_address(_resolved())
    assert address is not None
    locality = address.xal_address.address_details.locality
    assert locality is not None
    assert locality.thoroughfare.thoroughfare_name[0].content[0] == "Mekelweg"
    assert locality.thoroughfare.thoroughfare_number[0].content[0] == "42"
    assert locality.postal_code.postal_code_number[0].content[0] == "2628CD"


def test_build_address_returns_none_without_street() -> None:
    resolved = _resolved(street="")
    assert build_address(resolved) is None


# ---------------------------------------------------------------------------
# BuildingUnit + EPC
# ---------------------------------------------------------------------------


def test_attach_building_units_creates_one_per_address() -> None:
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved("A"), _resolved("B")])
    assert len(building.building_unit) == 2


def test_building_unit_without_label_omits_epc() -> None:
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved(None)])
    unit = building.building_unit[0].building_unit
    assert unit.energy_performance_certificate == []


def test_building_unit_with_label_emits_epc_with_valid_from() -> None:
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved("A")])
    unit = building.building_unit[0].building_unit
    epc = unit.energy_performance_certificate[0].energy_performance_certificate
    assert epc.label == "A"
    assert epc.valid_from is not None
