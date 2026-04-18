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
