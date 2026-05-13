"""Build ``nrg3:Energy`` resources from EP-online metrics.

Phase-2b of the EP-online integration. Implements the energy-flow
domain documented in
[`docs/mapping_city.md`](../../../docs/mapping_city.md) § 6:
``nrg3:Energy`` resources parented under the *BuildingUnit* via the
``nrg3:resource`` substitution element
(``core:_GenericApplicationPropertyOfCityObject``, XSD line 1366).

Emission is regime-aware (§ 5i of the mapping doc — "Calculation regimes
and field availability"). The ``Berekeningstype`` column is classified
once via :meth:`EnergyLabel.calculation_regime` and the per-row shape
follows from the regime:

* ``nta8800`` (NTA 8800:2018-2024): up to four resources — Energiebehoefte
  (BENG-1, ``net``, ``endUse=otherOrCombination`` because BENG-1 mixes
  heating + cooling), Warmtebehoefte (NTA 8800 net heating demand, also
  ``net`` but ``endUse=spaceHeating`` because it is heating-only),
  PrimaireFossieleEnergie (BENG-2, ``primary`` with
  ``endUse=otherOrCombination`` because BENG-2 aggregates every NTA-8800
  demand category, carrying ``co2Equivalent``), and
  BerekendeEnergieverbruik (delivered/finaal ``final``,
  ``endUse=otherOrCombination`` for the same reason). The ``final``
  classification is supported by RVO's own description of the column on
  the live EP-online v5 PublicAPI:
  *"Het berekende totale energieverbruik in kilowattuur per vierkante
  meter per jaar (kWh/m2·jaar)."*
  (https://public.ep-online.nl/swagger/v5/swagger.json, component
  schemas → BerekendeEnergieverbruik). The wording is "totale
  energieverbruik" (total consumption, summed across carriers) rather
  than "primair fossiel" — the latter has its own dedicated column
  (``PrimaireFossieleEnergie``, BENG-2). The two NTA-8800 columns would
  duplicate each other if both reported primary energy, so the
  delivered/final reading is the only one that keeps them
  semantically distinct. All NTA-8800 values land in **kWh/(m²·yr)**;
  ``isAmountNormalized=True`` and the per-m² basis is encoded by the
  uom itself, so ``normalizationValue`` is omitted.
* ``legacy_total`` (Definitief Energielabel v1.2, Nader Voorschrift,
  ISSO 75.3 / 82.3): a single ``primary`` resource (``endUse=otherOrCombination``)
  carrying the raw ``BerekendeEnergieverbruik`` in **MJ/yr (total annual
  primary fossil energy, not per-m²)**. ``isAmountNormalized=False``
  because the value is an absolute total. ``co2Equivalent`` rides on
  this same resource in **kg/yr (total)** when the row is from the Nader
  Voorschrift / ISSO branch (genuine data); the Definitief Energielabel
  branch's placeholder ``0,00`` is filtered via
  :meth:`EnergyLabel.co2_is_placeholder`.

  Why ``primary`` and not ``final`` for legacy, when NTA 8800 uses
  ``final`` for the same column name? The legacy regime descends from
  NEN 7120 (§5 formula 5.9), which defines its headline output as the
  *"karakteristiek primair (fossiel) energiegebruik EP_tot"* — a
  primary-energy figure with per-fuel weighting factors applied. RVO's
  own ``Handleiding EP-online: opvragen van bestanden`` (v1.0, feb 2025)
  does not define ``BerekendeEnergieverbruik`` for the legacy regime in
  Bijlage 2, but the field is the only NEN-7120 numeric output exposed
  on the public mutatiebestand and the magnitude distribution
  (median ~93 000 MJ/yr across 1.44 M Definitief Energielabel v1.2
  certs; see :meth:`EnergyLabel.calculation_regime`'s docstring) is
  consistent with NEN 7120's per-building total primary figure and not
  with a delivered-energy reading. RVO did not re-align this column's
  semantics when NTA 8800 took over; the legacy values remain primary
  fossil totals while the NTA 8800 regime fills the same column with a
  delivered per-m² value. This module preserves the regime divergence
  rather than collapsing both into one value: the Energy ADE 3.0
  ``EnergyTypeValue`` codelist (``net`` / ``primary`` / ``actual`` /
  ``secondary`` / ``final`` / ``useful``) lets us tag each value with
  the right energy stage.
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

# EnergyTypeValue.xml members for the partition the Dutch BENG metrics
# fall under. The codelist (``net | primary | actual | secondary | final
# | useful``) is the live vocabulary at
# ``http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyTypeValue.xml``.
# Per-metric routing:
#
# * Energiebehoefte (BENG-1, NTA 8800)            -> ``net``
# * Warmtebehoefte  (NTA 8800)                    -> ``net``
# * PrimaireFossieleEnergie (BENG-2, NTA 8800)    -> ``primary``
# * BerekendeEnergieverbruik (NTA 8800)           -> ``final``  (delivered/finaal)
# * BerekendeEnergieverbruik (legacy NEN 7120)    -> ``primary``  (NEN 7120 §5.9 EP_tot)
#
# The two ``BerekendeEnergieverbruik`` rows differ: same column name,
# different semantics across regimes. The module-level docstring above
# explains the divergence and cites the sources.
_ENERGY_TYPE_NET: str = "net"
_ENERGY_TYPE_PRIMARY: str = "primary"
_ENERGY_TYPE_FINAL: str = "final"

# EnergyEndUseValue.xml: spaceHeating, spaceCooling, ventilation,
# domesticHotWater, lighting, electricalAppliances, cooking, process,
# construction, mobility, otherOrCombination, unknown. Routed per
# metric per § 5l of the mapping doc:
#
# * Warmtebehoefte is genuinely heating-only -> ``spaceHeating``.
# * Energiebehoefte (BENG-1 = net heating + cooling) and the two NTA
#   8800 / legacy aggregates that span every demand category
#   (PrimaireFossieleEnergie, BerekendeEnergieverbruik) -> ``otherOrCombination``,
#   the codelist's documented bucket for multi-end-use figures.
#
# The codelist has no "spaceHeatingAndCooling" entry that would fit
# BENG-1 cleanly; ``otherOrCombination`` is the schema-honest fallback.
# A future Energy-ADE codelist extension that introduced an explicit
# combined-thermal-demand value should be picked up here automatically
# (would-be-codelist-member entries are XSD-valid as-is per
# memory/feedback_codelists.md). The mapping doc § 5l flags this as a
# candidate for vocabulary extension.
_END_USE_SPACE_HEATING: str = "spaceHeating"
_END_USE_OTHER_OR_COMBINATION: str = "otherOrCombination"

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
#
# Public so :mod:`citygml_energy.city_builder.builders.epc` can populate
# ``EnergyPerformanceCertificate.value`` with the same uom string as the
# matching ``nrg3:Energy.amount`` resource it parallels (NTA 8800 regime).
UOM_KWH_PER_M2_PER_A: str = "kWh/m2/a"

# Per-area annual CO₂ emission (NTA 8800 convention). FZK UOMList has
# ``kg`` but not ``kg/m2/a``. Introduced for NL convention; documented in
# § 7 of the mapping doc.
_UOM_KG_PER_M2_PER_A: str = "kg/m2/a"

# Total annual energy (legacy regime, NEN 7120 lineage). The
# ``BerekendeEnergieverbruik`` column for legacy methods is the absolute
# annual primary fossil energy — not a per-m² intensity. FZK UOMList has
# ``MWh/a``; ``MJ/a`` is introduced here for the NL legacy convention.
# § 7 of the mapping doc records this addition.
#
# Public for the same reason as :data:`UOM_KWH_PER_M2_PER_A`: the EPC
# builder mirrors this token on ``EnergyPerformanceCertificate.value``
# for legacy-regime certs.
UOM_MJ_PER_A: str = "MJ/a"

# Total annual CO₂ emission (legacy Nader Voorschrift / ISSO branch). The
# CO₂ column for those legacy methods is total kg/yr, not per-m².
# Companion to ``UOM_MJ_PER_A``; § 7 of the mapping doc records the
# addition alongside the regime asymmetry.
_UOM_KG_PER_A: str = "kg/a"

# Total annual natural-gas volume. Used by the CBS Postcode6
# ``UrbanFunctionArea`` resources for ``gemiddeldGasverbruikWoning`` (per-
# postcode average across occupied dwellings). FZK UOMList lacks ``m3/a``;
# introduced here for the NL convention. § 12 of the mapping doc records
# this addition alongside the postcode-aggregate semantics.
#
# Public so the UrbanFunctionArea builder can populate the ``amount`` slot
# on the gas resource without reaching into a private constant.
UOM_M3_PER_A: str = "m3/a"

# Total annual electrical energy. Used by the CBS Postcode6 electricity
# resource alongside ``UOM_M3_PER_A``. Distinct from
# ``UOM_KWH_PER_M2_PER_A`` (NTA 8800 per-area intensity): ``kWh/a`` is
# the absolute annual figure CBS publishes per dwelling.
UOM_KWH_PER_A: str = "kWh/a"


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
    * ``legacy_total``: at most one resource (``final``) in MJ/yr
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

    Per-metric ``nrg3:type`` routing follows the codelist semantics:
    BENG-1 and Warmtebehoefte are ``net`` (demand before any
    primary-energy weighting), BENG-2 is ``primary`` (with per-carrier
    weighting factors applied), and BerekendeEnergieverbruik is ``final``
    (delivered/finaal energy summed across carriers; see the module
    docstring for the RVO Swagger citation that anchors this reading).

    Per-metric ``endUse`` routing: only Warmtebehoefte is genuinely
    heating-only (``spaceHeating``); the other three are multi-end-use
    figures (BENG-1 = heating + cooling demand, BENG-2 = primary energy
    across every NTA-8800 category, BerekendeEnergieverbruik = delivered
    final energy across every NTA-8800 category) and land in
    ``otherOrCombination``.
    """
    primary = _build_per_area_energy(
        amount=label.primaire_fossiele_energie,
        type_value=_ENERGY_TYPE_PRIMARY,
        end_use=_END_USE_OTHER_OR_COMBINATION,
        description="PrimaireFossieleEnergie (BENG-2)",
        co2_equivalent=label.berekende_co2_emissie,
    )
    if primary is not None:
        unit.resource.append(Resource(energy=primary))

    energiebehoefte = _build_per_area_energy(
        amount=label.energiebehoefte,
        type_value=_ENERGY_TYPE_NET,
        end_use=_END_USE_OTHER_OR_COMBINATION,
        description="Energiebehoefte (BENG-1, heating + cooling)",
    )
    if energiebehoefte is not None:
        unit.resource.append(Resource(energy=energiebehoefte))

    warmtebehoefte = _build_per_area_energy(
        amount=label.warmtebehoefte,
        type_value=_ENERGY_TYPE_NET,
        end_use=_END_USE_SPACE_HEATING,
        description="Warmtebehoefte (NTA 8800 net heating demand)",
    )
    if warmtebehoefte is not None:
        unit.resource.append(Resource(energy=warmtebehoefte))

    final_energy = _build_per_area_energy(
        amount=label.berekende_energieverbruik,
        type_value=_ENERGY_TYPE_FINAL,
        end_use=_END_USE_OTHER_OR_COMBINATION,
        description="BerekendeEnergieverbruik (delivered final energy)",
    )
    if final_energy is not None:
        unit.resource.append(Resource(energy=final_energy))


def _attach_legacy_total_resource(unit: Any, label: EnergyLabel) -> None:
    """Emit one legacy total-primary-energy resource in MJ/yr.

    Legacy methods (NEN 7120 / NEN 8088 lineage) report
    ``BerekendeEnergieverbruik`` as the absolute annual **primary fossil**
    energy in **MJ per year** — not per-m², not delivered/finaal. NEN 7120
    §5 formula 5.9 defines the headline figure as the *"karakteristiek
    primair (fossiel) energiegebruik EP_tot"*; the public mutatiebestand
    column is that same figure. The empirical magnitude distribution
    (median ~93 000 MJ/yr across 1.44 M Definitief Energielabel v1.2 certs,
    vs. 150 kWh/(m²·yr) for NTA 8800 with 100% thermal-zone-area coverage)
    is documented in § 5i of the mapping doc and is consistent with a
    primary-energy reading; a delivered-energy reading would not produce
    those magnitudes. RVO did not re-align the column's semantics when
    NTA 8800 took over, so the legacy values are tagged ``primary`` here
    even though the same column name on NTA 8800 rows is ``final``
    (delivered) — see this module's docstring for the cross-regime
    rationale and the RVO Swagger citation.

    Other regime-specific facts (also empirical, see § 5i):

    * ``GebruiksoppervlakteThermischeZone`` is empty for 100% of legacy
      rows. There is no per-m² normaliser to emit, so
      ``isAmountNormalized=False`` and no ``normalizationValue``.
    * The other three NTA 8800 BENG fields (``Energiebehoefte``,
      ``Warmtebehoefte``, ``PrimaireFossieleEnergie``) are empty for
      100% of legacy rows; only the legacy total is recorded.
    * ``BerekendeCO2Emissie`` is a method-level placeholder for the
      Definitief Energielabel branch (99.997% zero across 1.44 M rows)
      and a real measurement for the Nader Voorschrift / ISSO branch.
      :meth:`EnergyLabel.co2_is_placeholder` distinguishes the two; the
      genuine value is emitted in ``kg/yr`` (total) on this same
      ``primary`` resource (the only one present in the regime).

    Skipped entirely when ``BerekendeEnergieverbruik`` is missing.
    """
    if label.berekende_energieverbruik is None:
        return

    energy = Energy(
        operation_type=CodeType(
            value=_OPERATION_DEMANDS,
            code_space=CS_NRG3_RESOURCE_OPERATION_TYPE,
        ),
        reference_period=CodeType(
            value=_REFERENCE_YEAR,
            code_space=CS_NRG3_REFERENCE_PERIOD,
        ),
        is_amount_normalized=False,
        type_value=CodeType(
            # Legacy NEN 7120 ``BerekendeEnergieverbruik`` = EP_tot
            # (karakteristiek primair fossiel energiegebruik). Tagged
            # ``primary`` not ``final``; the cross-regime divergence with
            # NTA 8800's same-named column is intentional and documented
            # in this module's top-level docstring.
            value=_ENERGY_TYPE_PRIMARY,
            code_space=CS_NRG3_ENERGY_TYPE,
        ),
        end_use=CodeType(
            # Legacy ``BerekendeEnergieverbruik`` is the total primary
            # fossil energy across every NTA-8800 demand category —
            # same multi-end-use scope as the NTA 8800 BENG-2 figure,
            # so it lands in the same ``otherOrCombination`` bucket.
            value=_END_USE_OTHER_OR_COMBINATION,
            code_space=CS_NRG3_ENERGY_END_USE,
        ),
        description=Description(
            value=(
                "BerekendeEnergieverbruik (legacy NEN 7120 method, "
                "total annual primary fossil energy EP_tot per "
                "NEN 7120 §5 formula 5.9, in MJ/yr)"
            ),
        ),
        amount=MeasureType(
            value=float(label.berekende_energieverbruik),
            uom=UOM_MJ_PER_A,
        ),
    )

    if label.berekende_co2_emissie is not None and not label.co2_is_placeholder():
        energy.co2_equivalent = MeasureType(
            value=float(label.berekende_co2_emissie),
            uom=_UOM_KG_PER_A,
        )

    unit.resource.append(Resource(energy=energy))


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _build_per_area_energy(
    *,
    amount: float | None,
    type_value: str,
    end_use: str,
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

    *end_use* is required: ``nrg3:Energy/endUse`` is mandatory in the
    XSD (no ``minOccurs="0"``), so callers must pin one. The caller is
    expected to pass a member of ``EnergyEndUseValue.xml``; see the
    ``_END_USE_*`` module constants for the routing rationale.
    """
    if amount is None:
        return None
    energy = Energy(
        operation_type=CodeType(
            value=_OPERATION_DEMANDS,
            code_space=CS_NRG3_RESOURCE_OPERATION_TYPE,
        ),
        reference_period=CodeType(
            value=_REFERENCE_YEAR,
            code_space=CS_NRG3_REFERENCE_PERIOD,
        ),
        is_amount_normalized=True,
        type_value=CodeType(
            value=type_value,
            code_space=CS_NRG3_ENERGY_TYPE,
        ),
        end_use=CodeType(
            value=end_use,
            code_space=CS_NRG3_ENERGY_END_USE,
        ),
        description=Description(value=description),
        amount=MeasureType(value=float(amount), uom=UOM_KWH_PER_M2_PER_A),
    )
    if co2_equivalent is not None:
        energy.co2_equivalent = MeasureType(
            value=float(co2_equivalent),
            uom=_UOM_KG_PER_M2_PER_A,
        )
    return energy
