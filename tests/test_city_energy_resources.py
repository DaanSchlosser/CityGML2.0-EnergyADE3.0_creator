"""Unit tests for the EP-online energy-flow domain (P2b).

Covers ``nrg3:Energy`` resource construction (BENG-1, BENG-2,
Warmtebehoefte, BerekendeEnergieverbruik, with BENG-2 carrying
``co2Equivalent``) and the per-BuildingUnit thermal-zone QualifiedArea
that sits alongside the BAG ``oppervlakte`` area. Locks the field-level
shape committed in
[`docs/ep_online_data_model_mapping.md`](../docs/ep_online_data_model_mapping.md)
§ 5h, § 5i, § 5j, § 5k.
"""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.builders import build_building_unit
from citygml_energy.city_builder.energy_resources import (
    _UOM_KG_PER_M2_PER_A,
    _UOM_KWH_PER_M2_PER_A,
    attach_energy_resources_to_building_unit,
)
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel


def _vbo(vbo_id: str = "0114010000000042") -> Verblijfsobject:
    return Verblijfsobject(
        identificatie=vbo_id,
        pand_identificatie="0114100000000001",
        gebruiksdoel=["woonfunctie"],
        oppervlakte=85.0,
        status="Verblijfsobject in gebruik",
        postcode="7881AA",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam="Hoofdkanaal WZ",
        point=None,
        properties={},
    )


def _label(**fields) -> EnergyLabel:
    base: dict = dict(
        postcode="7881AA",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=None,
        energieklasse="A++",
        registratiedatum=date(2024, 5, 14),
        opnamedatum=date(2024, 5, 1),
        geldig_tot=date(2034, 5, 13),
    )
    base.update(fields)
    return EnergyLabel(**base)


def _resolved(label: EnergyLabel | None) -> ResolvedAddress:
    return ResolvedAddress(vbo=_vbo(), energy_label=label)


# ---------------------------------------------------------------------------
# Thermal-zone QualifiedArea on the BuildingUnit
# ---------------------------------------------------------------------------


def test_thermal_zone_area_attaches_alongside_bag_oppervlakte() -> None:
    """A label with thermal-zone area adds a second QualifiedArea on the BuildingUnit.

    Locks the multi-source pattern: both QualifiedArea entries use type
    ``netFloorArea``; the EP-online source string is what makes them
    distinguishable from the BAG ``oppervlakte`` entry.
    """
    label = _label(gebruiksoppervlakte_thermische_zone=112.5)
    unit = build_building_unit(_resolved(label))

    assert len(unit.area) == 2
    sources = [qap.qualified_area.source or "" for qap in unit.area]
    assert any("BAG" in s for s in sources)
    assert any("EP-online" in s for s in sources)

    ep_qa = next(
        qap.qualified_area for qap in unit.area
        if "EP-online" in (qap.qualified_area.source or "")
    )
    assert ep_qa.value.value == 112.5
    assert ep_qa.value.uom == "m2"
    assert ep_qa.type_value.value == "netFloorArea"
    assert ep_qa.type_value.code_space.endswith("AreaTypeValue.xml")


def test_thermal_zone_area_skipped_when_label_missing() -> None:
    """No EP label → only the BAG ``oppervlakte`` QualifiedArea is emitted."""
    unit = build_building_unit(_resolved(None))
    assert len(unit.area) == 1
    assert "BAG" in (unit.area[0].qualified_area.source or "")


def test_thermal_zone_area_skipped_when_label_has_no_area() -> None:
    """A label without ``GebruiksoppervlakteThermischeZone`` adds no second area."""
    label = _label(gebruiksoppervlakte_thermische_zone=None)
    unit = build_building_unit(_resolved(label))
    assert len(unit.area) == 1
    assert "BAG" in (unit.area[0].qualified_area.source or "")


def test_thermal_zone_area_skipped_for_zero_or_negative() -> None:
    """Zero / negative thermal area is data noise and must not emit an area."""
    for bad in (0.0, -10.0):
        label = _label(gebruiksoppervlakte_thermische_zone=bad)
        unit = build_building_unit(_resolved(label))
        ep_areas = [
            qap for qap in unit.area
            if "EP-online" in (qap.qualified_area.source or "")
        ]
        assert ep_areas == [], f"area={bad} should not emit an EP-online QualifiedArea"


# ---------------------------------------------------------------------------
# Energy-resource construction
# ---------------------------------------------------------------------------


def test_four_energy_resources_emitted_when_all_metrics_set() -> None:
    """A complete EP-online label produces all four NTA-8800 Energy resources.

    Lock the resource count + their type-value distribution: BENG-1
    (netEnergy / Energiebehoefte), Warmtebehoefte (netEnergy), BENG-2
    (primaryEnergy + co2Equivalent), and finalEnergy
    (BerekendeEnergieverbruik). The order is documentation-only and not
    asserted; the sibling pattern is what matters.
    """
    label = _label(
        gebruiksoppervlakte_thermische_zone=112.5,
        energiebehoefte=28.5,
        warmtebehoefte=25.1,
        primaire_fossiele_energie=63.0,
        berekende_co2_emissie=14.7,
        berekende_energieverbruik=35.4,
    )
    unit = build_building_unit(_resolved(label))

    energies = [r.energy for r in unit.resource if r.energy is not None]
    assert len(energies) == 4

    by_type = {}
    for e in energies:
        by_type.setdefault(e.type_value.value, []).append(e)
    assert sorted(by_type) == ["finalEnergy", "netEnergy", "primaryEnergy"]
    assert len(by_type["netEnergy"]) == 2  # BENG-1 + Warmtebehoefte


def test_energiebehoefte_has_the_expected_envelope() -> None:
    """BENG-1 Energy resource: type/end-use/uom + normalisation-by-floor-area."""
    label = _label(
        gebruiksoppervlakte_thermische_zone=112.5,
        energiebehoefte=28.5,
    )
    unit = build_building_unit(_resolved(label))

    energies = [
        r.energy for r in unit.resource
        if r.energy is not None and "Energiebehoefte" in (r.energy.description or "")
    ]
    assert len(energies) == 1
    e = energies[0]
    assert e.type_value.value == "netEnergy"
    assert e.type_value.code_space.endswith("EnergyTypeValue.xml")
    assert e.end_use.value == "spaceHeating"
    assert e.end_use.code_space.endswith("EnergyEndUseValue.xml")
    assert e.operation_type.value == "demands"
    assert e.reference_period.value == "year"
    assert e.amount.value == 28.5
    assert e.amount.uom == _UOM_KWH_PER_M2_PER_A
    assert e.is_amount_normalized is True
    assert e.normalization_value.value == 112.5
    assert e.normalization_value.uom == "m2"
    assert e.normalization_parameter == "netFloorArea"


def test_co2_equivalent_rides_on_primary_energy_only() -> None:
    """``BerekendeCO2Emissie`` lives on the BENG-2 Energy, not a sibling."""
    label = _label(
        gebruiksoppervlakte_thermische_zone=112.5,
        primaire_fossiele_energie=63.0,
        berekende_co2_emissie=14.7,
        energiebehoefte=28.5,  # this resource must NOT carry co2Equivalent
    )
    unit = build_building_unit(_resolved(label))

    primary = next(
        r.energy for r in unit.resource
        if r.energy is not None and r.energy.type_value.value == "primaryEnergy"
    )
    assert primary.co2_equivalent is not None
    assert primary.co2_equivalent.value == 14.7
    assert primary.co2_equivalent.uom == _UOM_KG_PER_M2_PER_A

    net = next(
        r.energy for r in unit.resource
        if r.energy is not None and r.energy.type_value.value == "netEnergy"
    )
    assert net.co2_equivalent is None


def test_warmtebehoefte_distinguished_from_energiebehoefte_via_description() -> None:
    """Two ``netEnergy`` resources sit side by side; description disambiguates.

    The ``endUse`` codelist has no "combined heating + cooling" entry, so
    BENG-1 and Warmtebehoefte both use ``spaceHeating``. The Dutch source
    name in ``description`` is the only schema-valid disambiguator.
    """
    label = _label(
        gebruiksoppervlakte_thermische_zone=112.5,
        energiebehoefte=28.5,
        warmtebehoefte=25.1,
    )
    unit = build_building_unit(_resolved(label))

    netenergies = [
        r.energy for r in unit.resource
        if r.energy is not None and r.energy.type_value.value == "netEnergy"
    ]
    descriptions = [(e.description or "") for e in netenergies]
    assert any("Energiebehoefte" in d and "BENG-1" in d for d in descriptions)
    assert any("Warmtebehoefte" in d for d in descriptions)


def test_no_metric_no_resource() -> None:
    """A label with only address + label letter produces no Energy resources."""
    label = _label()  # all energy-flow numerics default to None
    unit = build_building_unit(_resolved(label))
    assert all(r.energy is None for r in unit.resource)


def test_floor_area_missing_drops_normalisation_but_keeps_energy() -> None:
    """Defensive: an Energy without floor-area context still serialises.

    EP-online has shipped at least one historical row where the metric
    is set but the thermal-zone area is empty. Behaviour: emit the
    Energy with ``isAmountNormalized=False`` and no ``normalizationValue``,
    so a downstream consumer can still see the value but knows it is
    not anchored.
    """
    label = _label(
        gebruiksoppervlakte_thermische_zone=None,
        energiebehoefte=28.5,
    )
    unit = build_building_unit(_resolved(label))
    e = next(
        r.energy for r in unit.resource
        if r.energy is not None and "Energiebehoefte" in (r.energy.description or "")
    )
    assert e.is_amount_normalized is False
    assert e.normalization_value is None
    assert e.normalization_parameter is None
    assert e.amount.value == 28.5


def test_resource_attachment_is_no_op_when_label_is_none() -> None:
    """``attach_energy_resources_to_building_unit`` tolerates ``label=None``."""
    unit = build_building_unit(_resolved(None))
    # A unit without an energy label should still serialise, with no
    # Energy resources and no measure attribute for renewable share.
    attach_energy_resources_to_building_unit(unit, None)
    assert all(r.energy is None for r in unit.resource)
