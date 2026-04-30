"""Build ``nrg3:Energy`` resources from EP-online metrics.

Phase-2b of the EP-online integration. Implements the energy-flow
domain documented in
[`docs/ep_online_data_model_mapping.md`](../../../docs/ep_online_data_model_mapping.md):
``nrg3:Energy`` resources parented under the *BuildingUnit* via the
``nrg3:resource`` substitution element
(``core:_GenericApplicationPropertyOfCityObject``, XSD line 1366).

Emission is regime-aware (§ 5i of the mapping doc — "Calculation regimes
and field availability"). The ``Berekeningstype`` column is classified
once via :meth:`EnergyLabel.calculation_regime` and the per-row shape
follows from the regime:

* ``nta8800`` (NTA 8800:2018-2024): up to four resources — Energiebehoefte
  (BENG-1, ``netEnergy``), Warmtebehoefte (NTA 8800 net heating demand,
  also ``netEnergy``), PrimaireFossieleEnergie (BENG-2, ``primaryEnergy``,
  carrying ``co2Equivalent``), and BerekendeEnergieverbruik (delivered
  ``finalEnergy``). All values land in **kWh/(m²·yr)**;
  ``isAmountNormalized=True`` and the per-m² basis is encoded by the uom
  itself, so ``normalizationValue`` is omitted.
* ``legacy_total`` (Definitief Energielabel v1.2, Nader Voorschrift,
  ISSO 75.3 / 82.3): a single ``finalEnergy`` resource carrying the raw
  ``BerekendeEnergieverbruik`` in **MJ/yr (total annual primary fossil
  energy, not per-m²)**. ``isAmountNormalized=False`` because the value
  is an absolute total. ``co2Equivalent`` rides on this same resource
  in **kg/yr (total)** when the row is from the Nader Voorschrift / ISSO
  branch (genuine data); the Definitief Energielabel branch's placeholder
  ``0,00`` is filtered via :meth:`EnergyLabel.co2_is_placeholder`.
* ``unknown``: emit nothing — the unit semantics for the ``Berekeningstype``
  string are not known to this code.

The unit divergence is intrinsic to the dataset (not a coding choice).
The 5.12 M-row magnitude analysis underpinning the regime detection lives
alongside the rules in § 5i of the mapping doc, for downstream auditors
who need to verify the empirical case.

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
    Description,
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
# is BENG-2; ``finalEnergy`` is the delivered-energy figure (and the
# legacy ``BerekendeEnergieverbruik`` total).
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

# ReferencePeriodValue.xml: NTA 8800 metrics are annual; legacy methods
# also report on an annual basis (per "jaar" in Dutch documentation).
_REFERENCE_YEAR: str = "year"


# ---------------------------------------------------------------------------
# uom tokens introduced by this module
# ---------------------------------------------------------------------------

# Per-area annual energy. NTA 8800 reports BENG metrics in kWh/m²·jaar;
# the FZK UOMList has ``kWh/m2`` (no per-annum) and ``MWh/a`` (no per-area)
# but not the composed token. Introduced here for NL convention; the user
# is in contact with the FZK developers to extend UOMList.xml upstream.
_UOM_KWH_PER_M2_PER_A: str = "kWh/m2/a"

# Per-area annual CO₂ emission (NTA 8800 convention). FZK UOMList has
# ``kg`` but not ``kg/m2/a``. Introduced for NL convention; documented in
# § 7 of the mapping doc.
_UOM_KG_PER_M2_PER_A: str = "kg/m2/a"

# Total annual energy (legacy regime, NEN 7120 lineage). The
# ``BerekendeEnergieverbruik`` column for legacy methods is the absolute
# annual primary fossil energy — not a per-m² intensity. FZK UOMList has
# ``MWh/a``; ``MJ/a`` is introduced here for the NL legacy convention.
# § 7 of the mapping doc records this addition.
_UOM_MJ_PER_A: str = "MJ/a"

# Total annual CO₂ emission (legacy Nader Voorschrift / ISSO branch). The
# CO₂ column for those legacy methods is total kg/yr, not per-m².
# Companion to ``_UOM_MJ_PER_A``; § 7 of the mapping doc records the
# addition alongside the regime asymmetry.
_UOM_KG_PER_A: str = "kg/a"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def attach_energy_resources_to_building_unit(
    unit: Any,
    label: EnergyLabel | None,
) -> None:
    """Attach EP-online ``nrg3:Energy`` resources to *unit* via ``nrg3:resource``.

    Dispatches on :meth:`EnergyLabel.calculation_regime`:

    * ``nta8800``: up to four resources, all in kWh/(m²·yr); CO₂ on the
      BENG-2 resource in kg/(m²·yr).
    * ``legacy_total``: at most one resource (``finalEnergy``) in MJ/yr
      (total). CO₂ on the same resource in kg/yr (total) when the row
      belongs to the Nader Voorschrift / ISSO branch; the Definitief
      Energielabel branch's placeholder ``0,00`` is suppressed via
      :meth:`EnergyLabel.co2_is_placeholder`.
    * ``unknown`` or ``label is None``: no-op.

    Per-resource emission rules:

    * Skip a resource entirely if its ``amount`` is ``None`` (degenerate
      "co2-only" resources are not emitted; CO₂ rides on whichever
      resource is the natural carrier for the regime).
    * For per-m² uom (kWh/m²·yr, kg/m²·yr): set
      ``isAmountNormalized=True`` and **omit** ``normalizationValue`` —
      the uom itself encodes the per-m² basis, so a redundant
      ``normalizationValue`` is unhelpful clutter.
    * For total uom (MJ/yr, kg/yr): set ``isAmountNormalized=False``.
      No ``normalizationValue``.
    """
    if label is None:
        return
    regime = label.calculation_regime()
    if regime == "nta8800":
        _attach_nta8800_resources(unit, label)
    elif regime == "legacy_total":
        _attach_legacy_total_resource(unit, label)
    # ``unknown`` falls through: no resources are attached because the
    # uom semantics of an unrecognised Berekeningstype are not known.


# ---------------------------------------------------------------------------
# Per-regime emitters
# ---------------------------------------------------------------------------


def _attach_nta8800_resources(unit: Any, label: EnergyLabel) -> None:
    """Emit up to four NTA 8800 Energy resources, all in kWh/(m²·yr).

    Each metric is independent: a row missing one numeric simply omits
    its resource. The CO₂ value (``kg/(m²·yr)``) rides on the BENG-2
    (PrimaireFossieleEnergie) resource per § 5k of the mapping doc; CO₂
    without a primary-energy reading is dropped (the data shape never
    occurs in production NTA 8800 rows: PrimaireFossieleEnergie is
    populated for ~100% of NTA 8800 certs).
    """
    primary = _build_per_area_energy(
        amount=label.primaire_fossiele_energie,
        type_value=_ENERGY_TYPE_PRIMARY,
        description="PrimaireFossieleEnergie (BENG-2)",
        co2_equivalent=label.berekende_co2_emissie,
    )
    if primary is not None:
        unit.resource.append(Resource(energy=primary))

    energiebehoefte = _build_per_area_energy(
        amount=label.energiebehoefte,
        type_value=_ENERGY_TYPE_NET,
        description="Energiebehoefte (BENG-1, heating + cooling)",
    )
    if energiebehoefte is not None:
        unit.resource.append(Resource(energy=energiebehoefte))

    warmtebehoefte = _build_per_area_energy(
        amount=label.warmtebehoefte,
        type_value=_ENERGY_TYPE_NET,
        description="Warmtebehoefte (NTA 8800 net heating demand)",
    )
    if warmtebehoefte is not None:
        unit.resource.append(Resource(energy=warmtebehoefte))

    final_energy = _build_per_area_energy(
        amount=label.berekende_energieverbruik,
        type_value=_ENERGY_TYPE_FINAL,
        description="BerekendeEnergieverbruik (delivered final energy)",
    )
    if final_energy is not None:
        unit.resource.append(Resource(energy=final_energy))


def _attach_legacy_total_resource(unit: Any, label: EnergyLabel) -> None:
    """Emit one legacy total-energy resource in MJ/yr.

    Legacy methods (NEN 7120 / NEN 8088 lineage) report
    ``BerekendeEnergieverbruik`` as the absolute annual primary fossil
    energy in **MJ per year** — not per-m². The empirical magnitude
    distribution (median ~93 000 MJ/yr across 1.44 M Definitief
    Energielabel v1.2 certs, vs. 150 kWh/(m²·yr) for NTA 8800 with
    100% thermal-zone-area coverage) is documented in § 5i of the
    mapping doc; the unit divergence is intrinsic to the dataset.

    Other regime-specific facts (also empirical, see § 5i):

    * ``GebruiksoppervlakteThermischeZone`` is empty for 100% of legacy
      rows. There is no per-m² normaliser to emit, so
      ``isAmountNormalized=False`` and no ``normalizationValue``.
    * The other three NTA 8800 BENG fields (``Energiebehoefte``,
      ``Warmtebehoefte``, ``PrimaireFossieleEnergie``) are empty for
      100% of legacy rows; only the ``finalEnergy`` total is recorded.
    * ``BerekendeCO2Emissie`` is a method-level placeholder for the
      Definitief Energielabel branch (99.997% zero across 1.44 M rows)
      and a real measurement for the Nader Voorschrift / ISSO branch.
      :meth:`EnergyLabel.co2_is_placeholder` distinguishes the two; the
      genuine value is emitted in ``kg/yr`` (total) on this same
      ``finalEnergy`` resource (the only one present in the regime).

    Skipped entirely when ``BerekendeEnergieverbruik`` is missing.
    """
    if label.berekende_energieverbruik is None:
        return

    energy = Energy(
        operation_type=CodeType(
            value=_OPERATION_DEMANDS, code_space=CS_NRG3_RESOURCE_OPERATION_TYPE,
        ),
        reference_period=CodeType(
            value=_REFERENCE_YEAR, code_space=CS_NRG3_REFERENCE_PERIOD,
        ),
        is_amount_normalized=False,
        type_value=CodeType(
            value=_ENERGY_TYPE_FINAL, code_space=CS_NRG3_ENERGY_TYPE,
        ),
        end_use=CodeType(
            value=_END_USE_SPACE_HEATING, code_space=CS_NRG3_ENERGY_END_USE,
        ),
        description=Description(
            value=(
                "BerekendeEnergieverbruik (legacy NEN 7120 method, "
                "total annual primary fossil energy in MJ)"
            ),
        ),
        amount=MeasureType(
            value=float(label.berekende_energieverbruik), uom=_UOM_MJ_PER_A,
        ),
    )

    if (
        label.berekende_co2_emissie is not None
        and not label.co2_is_placeholder()
    ):
        energy.co2_equivalent = MeasureType(
            value=float(label.berekende_co2_emissie), uom=_UOM_KG_PER_A,
        )

    unit.resource.append(Resource(energy=energy))


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _build_per_area_energy(
    *,
    amount: float | None,
    type_value: str,
    description: str,
    co2_equivalent: float | None = None,
) -> Energy | None:
    """Construct one NTA 8800 ``nrg3:Energy`` resource (kWh/(m²·yr)).

    Returns ``None`` when *amount* is ``None`` — even if a CO₂ value was
    provided. A degenerate "co2-only" Energy is never emitted: the CO₂
    rides on whichever resource is the regime's natural carrier (BENG-2
    for NTA 8800), and emitting an empty-amount Energy purely to host a
    co2Equivalent confuses any consumer that filters on Energy by amount
    or type.

    The kWh/(m²·yr) uom intrinsically encodes the per-m² normalisation,
    so we set ``isAmountNormalized=True`` but omit ``normalizationValue``
    (the value would just restate what the uom already says — "per
    square metre per annum"). Same logic for the kg/(m²·yr) CO₂ uom.
    XSD-wise: ``isAmountNormalized`` is mandatory (line 641 of
    Energy_ADE_3.0_beta8.xsd), ``normalizationValue`` is optional
    (``minOccurs="0"``, line 642), so dropping the latter is schema-clean.
    """
    if amount is None:
        return None
    energy = Energy(
        operation_type=CodeType(
            value=_OPERATION_DEMANDS, code_space=CS_NRG3_RESOURCE_OPERATION_TYPE,
        ),
        reference_period=CodeType(
            value=_REFERENCE_YEAR, code_space=CS_NRG3_REFERENCE_PERIOD,
        ),
        is_amount_normalized=True,
        type_value=CodeType(
            value=type_value, code_space=CS_NRG3_ENERGY_TYPE,
        ),
        end_use=CodeType(
            value=_END_USE_SPACE_HEATING, code_space=CS_NRG3_ENERGY_END_USE,
        ),
        description=Description(value=description),
        amount=MeasureType(value=float(amount), uom=_UOM_KWH_PER_M2_PER_A),
    )
    if co2_equivalent is not None:
        energy.co2_equivalent = MeasureType(
            value=float(co2_equivalent), uom=_UOM_KG_PER_M2_PER_A,
        )
    return energy
