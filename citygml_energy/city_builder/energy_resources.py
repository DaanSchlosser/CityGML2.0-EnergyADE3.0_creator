"""Build ``nrg3:Energy`` resources from EP-online metrics.

Phase-2b of the EP-online integration. Implements the energy-flow
domain documented in
[`docs/ep_online_data_model_mapping.md`](../../../docs/ep_online_data_model_mapping.md):
up to four ``nrg3:Energy`` resources per VBO, parented under the
*BuildingUnit* via the ``nrg3:resource`` substitution element
(``core:_GenericApplicationPropertyOfCityObject``, XSD line 1366):
``Energiebehoefte`` (BENG-1, ``netEnergy``), ``Warmtebehoefte``
(NTA 8800 net heating demand, also ``netEnergy``),
``PrimaireFossieleEnergie`` (BENG-2, ``primaryEnergy`` with the BENG-2
Energy resource also carrying the per-VBO ``co2Equivalent``), and
``BerekendeEnergieverbruik`` (delivered ``finalEnergy``).

uom convention follows the FZK UOMList where it can and adds two
NL-domain tokens (``kWh/m2/a``, ``kg/m2/a``) where it cannot. § 7 of the
mapping doc records the rationale; the user is in contact with the FZK
developers to extend the UOMList upstream.

The renewable-energy share (BENG-3) is **not** in this module: it lives
as a ``gen:measureAttribute`` on the BuildingUnit in
:mod:`citygml_energy.city_builder.builders` because Energy ADE has no
native renewable-share slot. The thermal-zone floor area
(``GebruiksoppervlakteThermischeZone``) is also encoded by ``builders``,
as a second ``QualifiedArea`` on the BuildingUnit (alongside the
BAG ``oppervlakte``) so both numbers stay queryable side-by-side
without an intermediate ``nrg3:Zone`` wrapper.
"""

from __future__ import annotations

from typing import Any

from ..bindings import (
    CodeType,
    Energy,
    MeasureType,
    Resource,
)
from ..namespaces import (
    CS_NRG3_ENERGY_END_USE,
    CS_NRG3_ENERGY_TYPE,
    CS_NRG3_REFERENCE_PERIOD,
    CS_NRG3_RESOURCE_OPERATION_TYPE,
)
from .fetchers.eponline import EnergyLabel

__all__ = [
    "attach_energy_resources_to_building_unit",
]


# ---------------------------------------------------------------------------
# Codelist values (Energy ADE 3.0 enumerations)
# ---------------------------------------------------------------------------

# EnergyTypeValue.xml: net / primary / final partition of the Dutch BENG
# metrics. ``netEnergy`` is BENG-1 (and Warmtebehoefte); ``primaryEnergy``
# is BENG-2; ``finalEnergy`` is the delivered-energy figure.
_ENERGY_TYPE_NET: str = "netEnergy"
_ENERGY_TYPE_PRIMARY: str = "primaryEnergy"
_ENERGY_TYPE_FINAL: str = "finalEnergy"

# EnergyEndUseValue.xml: every BENG metric is for "spaceHeating" in the
# Energy ADE 3.0 vocabulary because the codelist has no "combined heating
# + cooling" entry. The ``description`` field on each Energy element
# carries the unambiguous Dutch source name so a downstream reader can
# tell Energiebehoefte (heating + cooling) from Warmtebehoefte
# (heating only).
_END_USE_SPACE_HEATING: str = "spaceHeating"

# ResourceOperationTypeValue.xml: every EP-online Energy resource is a
# building-side demand (the figure RVO publishes is what the building
# *consumes*, not what it produces).
_OPERATION_DEMANDS: str = "demands"

# ReferencePeriodValue.xml: NTA 8800 metrics are annual.
_REFERENCE_YEAR: str = "year"


# ---------------------------------------------------------------------------
# uom tokens introduced by this module
# ---------------------------------------------------------------------------

# Per-area annual energy. NTA 8800 reports BENG metrics in kWh/m²·jaar;
# the FZK UOMList has ``kWh/m2`` (no per-annum) and ``MWh/a`` (no per-area)
# but not the composed token. Introduced here for NL convention; the user
# is in contact with the FZK developers to extend UOMList.xml upstream.
_UOM_KWH_PER_M2_PER_A: str = "kWh/m2/a"

# Per-area annual CO₂ emission. Same FZK UOMList situation: ``kg`` is
# present, ``kg/m2`` and ``kg/m2/a`` are not. Introduced for NL
# convention; documented in § 7 of the mapping doc.
_UOM_KG_PER_M2_PER_A: str = "kg/m2/a"

# Floor area (m²). Already used elsewhere in the pipeline; SQUARE_METRE
# id=`m2` is in the FZK UOMList.
_UOM_AREA_M2: str = "m2"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def attach_energy_resources_to_building_unit(
    unit: Any,
    label: EnergyLabel | None,
) -> None:
    """Attach EP-online ``nrg3:Energy`` resources to *unit* via ``nrg3:resource``.

    Builds up to four ``nrg3:Energy`` resources, one per (energy-type,
    end-use) pair the EP-online CSV ships:

    * ``Energiebehoefte`` (BENG-1, kWh/m²·yr) → ``type="netEnergy"``,
      ``endUse="spaceHeating"``.
    * ``Warmtebehoefte`` (NTA 8800 net heating demand, kWh/m²·yr) →
      same type/endUse codes, distinguished from BENG-1 by the
      ``description`` field. The two siblings are **not redundant**:
      Energiebehoefte = heating + cooling; Warmtebehoefte = heating only.
    * ``PrimaireFossieleEnergie`` (BENG-2, kWh/m²·yr) →
      ``type="primaryEnergy"``. When ``BerekendeCO2Emissie`` is also
      set, that value rides on the same Energy as ``co2Equivalent``
      because emissions are per primary-fossil-energy resource and
      ``AbstractResource.co2Equivalent`` is the schema's only emissions
      slot (XSD line 646).
    * ``BerekendeEnergieverbruik`` (delivered final energy, kWh/m²·yr)
      → ``type="finalEnergy"``.

    All four resources share ``operationType="demands"`` (EP-online
    publishes building-side demand, not production),
    ``referencePeriod="year"`` (NTA 8800 metrics are annual),
    ``isAmountNormalized=True``,
    ``normalizationParameter="netFloorArea"``, and a
    ``normalizationValue`` carrying the EP-online thermal-zone area
    (the same value :mod:`builders` writes as a second
    ``QualifiedArea`` on the BuildingUnit).

    A ``None`` label or one with no numeric metrics is a no-op.
    """
    if label is None:
        return
    floor_area = label.gebruiksoppervlakte_thermische_zone

    primary_energy = _build_energy_resource(
        amount=label.primaire_fossiele_energie,
        floor_area=floor_area,
        type_value=_ENERGY_TYPE_PRIMARY,
        description="PrimaireFossieleEnergie (BENG-2)",
        co2_equivalent=label.berekende_co2_emissie,
    )
    if primary_energy is not None:
        unit.resource.append(Resource(energy=primary_energy))

    energiebehoefte = _build_energy_resource(
        amount=label.energiebehoefte,
        floor_area=floor_area,
        type_value=_ENERGY_TYPE_NET,
        description="Energiebehoefte (BENG-1, heating + cooling)",
    )
    if energiebehoefte is not None:
        unit.resource.append(Resource(energy=energiebehoefte))

    warmtebehoefte = _build_energy_resource(
        amount=label.warmtebehoefte,
        floor_area=floor_area,
        type_value=_ENERGY_TYPE_NET,
        description="Warmtebehoefte (NTA 8800 net heating demand)",
    )
    if warmtebehoefte is not None:
        unit.resource.append(Resource(energy=warmtebehoefte))

    final_energy = _build_energy_resource(
        amount=label.berekende_energieverbruik,
        floor_area=floor_area,
        type_value=_ENERGY_TYPE_FINAL,
        description="BerekendeEnergieverbruik (delivered final energy)",
    )
    if final_energy is not None:
        unit.resource.append(Resource(energy=final_energy))


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _build_energy_resource(
    *,
    amount: float | None,
    floor_area: float | None,
    type_value: str,
    description: str,
    co2_equivalent: float | None = None,
) -> Energy | None:
    """Construct one ``nrg3:Energy`` resource, or return ``None`` if no data.

    Skips emission when *amount* is ``None`` (no metric) AND
    *co2_equivalent* is ``None`` — there is nothing to encode. When
    *amount* is set but *floor_area* is missing, the Energy is still
    emitted but ``isAmountNormalized=False`` so consumers know the value
    is not anchored to a floor area; this is rare and reserved for
    pathological inputs (the production CSV always ships the area
    alongside the metric).

    The CO₂ equivalent uses ``kg/m2/a`` as uom (NL convention; not in
    the FZK UOMList, see § 7 of the mapping doc). It rides only on the
    primary-energy resource per § 5k of the mapping doc; this function
    only writes it when caller passes it explicitly.
    """
    if amount is None and co2_equivalent is None:
        return None

    is_normalized = amount is not None and floor_area is not None and floor_area > 0

    energy = Energy(
        operation_type=CodeType(
            value=_OPERATION_DEMANDS, code_space=CS_NRG3_RESOURCE_OPERATION_TYPE,
        ),
        reference_period=CodeType(
            value=_REFERENCE_YEAR, code_space=CS_NRG3_REFERENCE_PERIOD,
        ),
        is_amount_normalized=is_normalized,
        type_value=CodeType(
            value=type_value, code_space=CS_NRG3_ENERGY_TYPE,
        ),
        end_use=CodeType(
            value=_END_USE_SPACE_HEATING, code_space=CS_NRG3_ENERGY_END_USE,
        ),
        description=description,
    )
    if amount is not None:
        energy.amount = MeasureType(
            value=float(amount), uom=_UOM_KWH_PER_M2_PER_A,
        )
    if is_normalized:
        # Mypy: floor_area is non-None and > 0 inside the is_normalized branch
        # but the type checker doesn't track that across the boolean composition.
        assert floor_area is not None
        energy.normalization_value = MeasureType(
            value=float(floor_area), uom=_UOM_AREA_M2,
        )
        energy.normalization_parameter = "netFloorArea"
    if co2_equivalent is not None:
        energy.co2_equivalent = MeasureType(
            value=float(co2_equivalent), uom=_UOM_KG_PER_M2_PER_A,
        )
    return energy
