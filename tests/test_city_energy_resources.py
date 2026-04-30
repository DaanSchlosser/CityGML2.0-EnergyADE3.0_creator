"""Unit tests for the EP-online energy-flow domain (P2b).

Covers ``nrg3:Energy`` resource construction (BENG-1, BENG-2,
Warmtebehoefte, BerekendeEnergieverbruik, with BENG-2 carrying
``co2Equivalent``) and the per-BuildingUnit thermal-zone QualifiedArea
that sits alongside the BAG ``oppervlakte`` area. Locks the field-level
shape committed in
[`docs/ep_online_data_model_mapping.md`](../docs/ep_online_data_model_mapping.md)
§ 5h, § 5i, § 5j, § 5k, including the regime-aware unit handling
introduced in the v2 mapping (NTA 8800 in kWh/(m²·yr) vs. legacy NEN 7120
in MJ/yr total).
"""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.builders import build_building_unit
from citygml_energy.city_builder.energy_resources import (
    _UOM_KG_PER_A,
    _UOM_KG_PER_M2_PER_A,
    _UOM_KWH_PER_M2_PER_A,
    _UOM_MJ_PER_A,
    attach_energy_resources_to_building_unit,
)
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel

# A canonical NTA 8800 Berekeningstype string. Tests that exercise the
# four-resource emission path use this so the regime classifier resolves
# to ``nta8800``; legacy regime tests override with their own string.
_NTA8800_BEREKENINGSTYPE = "NTA 8800:2024 (basisopname woningbouw)"


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
        berekeningstype=_NTA8800_BEREKENINGSTYPE,
    )
    base.update(fields)
    return EnergyLabel(**base)


def _resolved(label: EnergyLabel | None) -> ResolvedAddress:
    return ResolvedAddress(vbo=_vbo(), energy_label=label)


def _desc(energy) -> str:
    """Return the inner string of ``energy.description`` (gml:Description wrapper)."""
    return (energy.description.value or "") if energy.description is not None else ""


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
# NTA 8800 regime: four resources, kWh/(m²·yr), no normalizationValue
# ---------------------------------------------------------------------------


def test_four_energy_resources_emitted_when_all_metrics_set() -> None:
    """A complete NTA 8800 label produces all four BENG Energy resources.

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

    by_type: dict[str, list] = {}
    for e in energies:
        by_type.setdefault(e.type_value.value, []).append(e)
    assert sorted(by_type) == ["finalEnergy", "netEnergy", "primaryEnergy"]
    assert len(by_type["netEnergy"]) == 2  # BENG-1 + Warmtebehoefte


def test_energiebehoefte_has_the_expected_envelope() -> None:
    """BENG-1 Energy resource: type/end-use/uom + per-area normalisation.

    The kWh/(m²·yr) uom encodes the per-m² normalisation; we set
    ``isAmountNormalized=True`` but **omit** ``normalizationValue``
    because restating "per square metre" alongside the uom is redundant
    clutter. ``normalizationValue`` is optional in the XSD
    (``minOccurs="0"`` at line 642 of Energy_ADE_3.0_beta8.xsd).
    """
    label = _label(
        gebruiksoppervlakte_thermische_zone=112.5,
        energiebehoefte=28.5,
    )
    unit = build_building_unit(_resolved(label))

    energies = [
        r.energy for r in unit.resource
        if r.energy is not None and "Energiebehoefte" in _desc(r.energy)
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
    assert e.normalization_value is None
    assert e.normalization_parameter is None


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
    descriptions = [_desc(e) for e in netenergies]
    assert any("Energiebehoefte" in d and "BENG-1" in d for d in descriptions)
    assert any("Warmtebehoefte" in d for d in descriptions)


def test_no_metric_no_resource() -> None:
    """A label with only address + label letter produces no Energy resources."""
    label = _label()  # all energy-flow numerics default to None
    unit = build_building_unit(_resolved(label))
    assert all(r.energy is None for r in unit.resource)


def test_nta8800_normalization_value_is_omitted_regardless_of_thermal_zone_area() -> None:
    """The kWh/(m²·yr) uom is self-describing; ``normalizationValue`` stays absent.

    Even when the label carries a thermal-zone area, the per-m² basis is
    already encoded in the uom string. A redundant
    ``<nrg3:normalizationValue uom="m2">``X``</nrg3:normalizationValue>``
    next to ``<nrg3:amount uom="kWh/m2/a">``Y``</nrg3:amount>`` says
    nothing the consumer cannot read off the uom directly. Lock the
    omission so a future "let's restore it for symmetry" refactor has
    to argue with this test first.
    """
    label = _label(
        gebruiksoppervlakte_thermische_zone=112.5,
        energiebehoefte=28.5,
    )
    unit = build_building_unit(_resolved(label))

    e = next(
        r.energy for r in unit.resource
        if r.energy is not None and "Energiebehoefte" in _desc(r.energy)
    )
    assert e.is_amount_normalized is True
    assert e.normalization_value is None
    assert e.normalization_parameter is None


def test_nta8800_co2_only_does_not_emit_degenerate_energy() -> None:
    """A NTA 8800 label with ONLY CO₂ but no PrimaireFossieleEnergie emits nothing.

    CO₂ rides on the BENG-2 (PrimaireFossieleEnergie) Energy resource.
    Without that primary-energy amount there is nothing for CO₂ to ride
    on; emitting an Energy with no ``<nrg3:amount>`` purely to host a
    ``co2Equivalent`` produces a degenerate resource that confuses any
    consumer filtering on amount. (In production NTA 8800 data this case
    never arises — PrimaireFossieleEnergie is populated for ~100% of NTA
    8800 certs — but we lock the safety net regardless.)
    """
    label = _label(
        gebruiksoppervlakte_thermische_zone=112.5,
        primaire_fossiele_energie=None,
        berekende_co2_emissie=14.7,
    )
    unit = build_building_unit(_resolved(label))

    energies = [r.energy for r in unit.resource if r.energy is not None]
    assert energies == [], (
        "A CO₂-only NTA 8800 label must not emit any Energy resource"
    )


# ---------------------------------------------------------------------------
# Legacy regime: one resource in MJ/yr, optional CO₂ in kg/yr
# ---------------------------------------------------------------------------


def test_legacy_definitief_energielabel_emits_one_mj_resource_no_co2() -> None:
    """Definitief Energielabel v1.2 row → one finalEnergy resource in MJ/yr, no CO₂.

    Reproduces the real Hoofdkanaal WZ 38 (VBO 0114010000280857) shape
    that surfaced this regime asymmetry: a 2019 cert with the legacy
    Berekeningstype, BerekendeEnergieverbruik=293361.52 (MJ/yr total),
    BerekendeCO2Emissie=0.0 (placeholder), and every NTA 8800 BENG field
    empty. The 0.0 CO₂ MUST be suppressed (it is not a measurement) and
    the energy value MUST land in MJ/yr (not kWh/(m²·yr)).
    """
    label = _label(
        berekeningstype=(
            "Rekenmethodiek Definitief Energielabel, "
            "versie 1.2, 16 september 2014"
        ),
        gebruiksoppervlakte_thermische_zone=None,
        energiebehoefte=None,
        warmtebehoefte=None,
        primaire_fossiele_energie=None,
        berekende_energieverbruik=293361.52,
        berekende_co2_emissie=0.0,
    )
    unit = build_building_unit(_resolved(label))

    energies = [r.energy for r in unit.resource if r.energy is not None]
    assert len(energies) == 1
    e = energies[0]
    assert e.type_value.value == "finalEnergy"
    assert e.amount.value == 293361.52
    assert e.amount.uom == _UOM_MJ_PER_A
    assert e.is_amount_normalized is False
    assert e.normalization_value is None
    assert e.normalization_parameter is None
    # The placeholder zero must NOT round-trip as a co2Equivalent.
    assert e.co2_equivalent is None
    # Description must mark this as a legacy emission so a downstream
    # consumer cannot mistake it for the NTA 8800 finalEnergy figure.
    assert "legacy" in _desc(e).lower()


def test_legacy_nader_voorschrift_emits_co2_alongside_total_energy() -> None:
    """Nader Voorschrift / ISSO branch DOES populate CO₂ — emit it in kg/yr (total).

    The empirical signal across 1.40 M Nader Voorschrift / ISSO 75.3
    rows is real: zeros are ~0.1% of rows (vs. 99.997% for Definitief
    Energielabel). For this branch, BerekendeCO2Emissie carries genuine
    data in **kg/yr (total)**, which we surface on the same finalEnergy
    resource as the BerekendeEnergieverbruik MJ/yr value.
    """
    label = _label(
        berekeningstype="Nader Voorschrift, versie 1.0, 1 februari 2014",
        berekende_energieverbruik=68956.31,
        berekende_co2_emissie=3684.02,
    )
    unit = build_building_unit(_resolved(label))

    energies = [r.energy for r in unit.resource if r.energy is not None]
    assert len(energies) == 1
    e = energies[0]
    assert e.amount.uom == _UOM_MJ_PER_A
    assert e.amount.value == 68956.31
    assert e.co2_equivalent is not None
    assert e.co2_equivalent.value == 3684.02
    assert e.co2_equivalent.uom == _UOM_KG_PER_A


def test_legacy_no_verbruik_emits_nothing() -> None:
    """Legacy row without ``BerekendeEnergieverbruik`` emits no Energy resource.

    There is nothing schema-meaningful to attach: the legacy regime ships
    only one numeric and ``co2Equivalent`` rides on it, so without the
    energy value there is no carrier for the CO₂.
    """
    label = _label(
        berekeningstype=(
            "Rekenmethodiek Definitief Energielabel, "
            "versie 1.2, 16 september 2014"
        ),
        berekende_energieverbruik=None,
        berekende_co2_emissie=0.0,
    )
    unit = build_building_unit(_resolved(label))

    energies = [r.energy for r in unit.resource if r.energy is not None]
    assert energies == []


# ---------------------------------------------------------------------------
# Unknown regime: emit nothing
# ---------------------------------------------------------------------------


def test_unknown_calculation_method_emits_no_resources() -> None:
    """Berekeningstype this code does not recognise → no Energy resources.

    The unit semantics of an unknown method string are not knowable from
    the column values alone (legacy methods report MJ/yr totals, NTA 8800
    reports kWh/(m²·yr) per-m²). Emitting a numeric without a defensible
    uom would fabricate units we cannot defend; better to drop the row's
    energy domain than to misrepresent it.
    """
    label = _label(
        berekeningstype="A method this code has never seen",
        berekende_energieverbruik=42.0,
        berekende_co2_emissie=14.7,
    )
    unit = build_building_unit(_resolved(label))
    energies = [r.energy for r in unit.resource if r.energy is not None]
    assert energies == []


def test_missing_berekeningstype_emits_no_resources() -> None:
    """An empty Berekeningstype falls into the ``unknown`` regime."""
    label = _label(
        berekeningstype=None,
        berekende_energieverbruik=42.0,
    )
    unit = build_building_unit(_resolved(label))
    energies = [r.energy for r in unit.resource if r.energy is not None]
    assert energies == []


def test_resource_attachment_is_no_op_when_label_is_none() -> None:
    """``attach_energy_resources_to_building_unit`` tolerates ``label=None``."""
    unit = build_building_unit(_resolved(None))
    # A unit without an energy label should still serialise, with no
    # Energy resources and no measure attribute for renewable share.
    attach_energy_resources_to_building_unit(unit, None)
    assert all(r.energy is None for r in unit.resource)
