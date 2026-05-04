"""Pand-level attribution + EP-online classification + EPC builder.

Splits cleanly along the per-VBO / per-Pand line:

* :func:`apply_bag_year_metadata_to_building` and
  :func:`apply_eponline_pand_attribution_to_building` operate on
  Buildings. Both year-of-construction and the primary
  building-type taxonomy are Pand-level facts (a building is
  constructed once and its primary type is fixed at the structure
  level, regardless of how many VBOs it hosts), so BAG's
  ``bldg:yearOfConstruction`` lives at the Building level alongside
  its own ``nrg3:Metadata`` block, and the EP-online emissions
  (``yearOfConstructionEPOnline`` + ``nrg3:bdgType``) share a single
  ``nrg3:Metadata`` block on the Building.

* :func:`_apply_eponline_classification_to_building_unit` and
  :func:`_build_epc` operate on BuildingUnits. NTA-8800's
  ``Gebouwsubtype``, the renewable-energy share, and the EP-online
  energy resources are genuinely per-VBO (mixed-use Pand, partial
  conversion), so they live on the BuildingUnit alongside an
  EP-online-source ``nrg3:Metadata`` block.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...bindings import (
    BdgType,
    CodeType,
    IntAttribute,
    MeasureType,
    Metadata1,
    StringAttribute,
)
from ...mapping import resolve_class
from ...namespaces import (
    CS_NRG3_EPC_STATUS,
    CS_NRG3_EPC_TYPE,
    CS_RVO_GEBOUWTYPE,
)
from ...schema_types import ENERGY_PERFORMANCE_CERTIFICATE
from .._helpers import safe_gml_id
from ..address_match import ResolvedAddress
from ..energy_resources import UOM_KWH_PER_M2_PER_A, UOM_MJ_PER_A
from ..fetchers.eponline import EnergyLabel

__all__ = [
    "apply_bag_year_metadata_to_building",
    "apply_eponline_pand_attribution_to_building",
]


# ---------------------------------------------------------------------------
# Year-of-construction source attribution at the Building level
# ---------------------------------------------------------------------------


def apply_bag_year_metadata_to_building(building: Any) -> None:
    """Attach a ``nrg3:Metadata`` block documenting the BAG source of
    ``bldg:yearOfConstruction``, when the Building has the year set.

    BAG ``bouwjaar`` is structurally a Pand-level fact (one bouwjaar per
    BAG building, regardless of how many VBOs sit inside), so its
    Metadata block lives at the Building level alongside the value it
    annotates. The EP-online Pand-level emissions
    (``yearOfConstructionEPOnline`` + ``nrg3:bdgType``) ALSO live at the
    Building level for the same structural reason; see
    :func:`apply_eponline_pand_attribution_to_building`. The other
    EP-online classification fields (``Gebouwsubtype``, renewable share,
    energy metrics) are genuinely per-VBO and live on the BuildingUnit.

    No-op when the building has no ``yearOfConstruction`` (e.g. 3DBAG
    omitted ``oorspronkelijkbouwjaar`` and BAG had no ``bouwjaar`` for
    the Pand).
    """
    if building.year_of_construction is None:
        return
    building.metadata.append(
        Metadata1(
            source="BAG bag:pand.bouwjaar (PDOK WFS v2.0)",
            quality_description=(
                "Source for bldg:yearOfConstruction on this Pand."
            ),
        )
    )


def apply_eponline_pand_attribution_to_building(
    building: Any,
    addresses: list[ResolvedAddress],
) -> None:
    """Attach EP-online Pand-level fields to the Building, with shared source metadata.

    Two emissions on the Building, each guarded by its own canonical
    label pick, plus one shared ``nrg3:Metadata`` block when at least
    one was emitted:

    * ``gen:intAttribute name="yearOfConstructionEPOnline"`` from
      ``Bouwjaar``. Sits alongside (not replacing) the BAG-authoritative
      ``bldg:yearOfConstruction`` so per-Pand BAG-vs-EP-online
      disagreement is auditable directly from the GML.
    * ``nrg3:bdgType`` from ``Gebouwtype``. The Dutch RVO NTA-8800 term
      is written verbatim (no translation to the Energy ADE
      ``BuildingTypeValue.xml`` codelist, which is too coarse for the
      NTA-8800 typology); the ``@codeSpace`` is
      :data:`citygml_energy.namespaces.CS_RVO_GEBOUWTYPE`, identifying
      the official RVO landing page for the vocabulary. Exactly one
      ``nrg3:bdgType`` is emitted per Pand: the EnergyADE XSD declares
      `bdgType` with substitutionGroup ``[0..*]`` cardinality, but its
      UML ``taggedValue`` annotation pins ``maxOccurs=1`` so the
      conceptual cardinality is ``[0..1]``. The canonical-pick rule
      below is what enforces that.

    Both are Pand-level facts: a building is constructed once, and its
    primary type is fixed at the structure level. EP-online ships them
    per-VBO only because the Mutatiebestand CSV is one-row-per-cert,
    the underlying data are still per-Pand. Two certs against two VBOs
    of the same Pand should therefore record the same values; when they
    disagree, the most-recently-registered cert wins (mirroring
    :func:`citygml_energy.city_builder.address_match._label_timestamp`).

    The recency pick is *per field*: the canonical Bouwjaar may come
    from a different cert than the canonical Gebouwtype. Otherwise a
    Pand whose newest cert leaves Gebouwtype empty would emit no
    bdgType at all even when an older cert under the same Pand does
    carry one. Each pick filters to candidates that actually carry the
    field before the recency max (see
    :func:`_pick_canonical_eponline_label`).

    The per-VBO secondary qualifier ``Gebouwsubtype`` lives on the
    BuildingUnit as ``gen:stringAttribute name="bdgSubtypeEPOnline"``
    (see :func:`_apply_eponline_classification_to_building_unit`); it
    is not promoted to the Building because two VBOs in one Pand can
    legitimately carry different subtypes (mixed-use, partial
    conversion).

    No-op when no resolved address has an EP-online label or when no
    label has either ``Bouwjaar`` or ``Gebouwtype`` set.
    """
    bouwjaar_label = _pick_canonical_eponline_label(
        addresses, has_field=lambda lab: lab.bouwjaar is not None,
    )
    bdg_type_label = _pick_canonical_eponline_label(
        addresses, has_field=lambda lab: bool(lab.gebouwtype),
    )

    description_parts: list[str] = []

    if bouwjaar_label is not None:
        assert bouwjaar_label.bouwjaar is not None  # narrowed by has_field
        building.int_attribute.append(
            IntAttribute(
                name="yearOfConstructionEPOnline",
                value=int(bouwjaar_label.bouwjaar),
            )
        )
        description_parts.append(
            "gen:intAttribute name=\"yearOfConstructionEPOnline\" "
            "(picked from the most-recently-registered EP-online "
            "certificate across this Pand's VBOs that carries Bouwjaar)"
        )

    if bdg_type_label is not None:
        assert bdg_type_label.gebouwtype  # narrowed by has_field
        building.bdg_type.append(
            BdgType(
                value=bdg_type_label.gebouwtype,
                code_space=CS_RVO_GEBOUWTYPE,
            )
        )
        description_parts.append(
            "nrg3:bdgType (picked from the most-recently-registered "
            "EP-online certificate across this Pand's VBOs that carries "
            "Gebouwtype; value is the Dutch RVO NTA-8800 term verbatim, "
            "@codeSpace identifies the EP-online publication that "
            "defines the vocabulary)"
        )

    if not description_parts:
        return

    building.metadata.append(
        Metadata1(
            source="EP-online Mutatiebestand v4 (RVO)",
            quality_description=(
                "Source for the following EP-online Pand-level "
                "emissions on this Building: "
                + "; ".join(description_parts)
                + ". The per-VBO Gebouwsubtype, renewable-energy "
                "share, thermal-zone area, and Energy resources have "
                "their own EP-online Metadata block on each "
                "BuildingUnit."
            ),
        )
    )


def _pick_canonical_eponline_label(
    addresses: list[ResolvedAddress],
    *,
    has_field: Callable[[EnergyLabel], bool],
) -> EnergyLabel | None:
    """Return the most-recently-registered label among those satisfying *has_field*.

    Used by :func:`apply_eponline_pand_attribution_to_building` to pick
    one canonical label *per Pand-level field*. The filter is applied
    *before* the recency max because the alternative, selecting the
    overall newest cert and bailing when it lacks the field, silently
    drops the value for Pands whose newest cert left that field empty
    even when older certs under the same Pand do carry one.

    The per-field pick lets Bouwjaar and Gebouwtype come from different
    certs when one cert has a value the other lacks; the alternative
    (single canonical label per Pand) coupled the two emissions
    artificially.

    Tiebreak rule: ``registratiedatum`` wins, falling back to
    ``opnamedatum`` and then to "any non-null value over null". Mirrors
    :func:`citygml_energy.city_builder.address_match._label_timestamp`
    so the per-Pand reduction order matches the per-VBO de-duplication
    order seen earlier in the pipeline.
    """
    candidates = [
        addr.energy_label
        for addr in addresses
        if addr.energy_label is not None and has_field(addr.energy_label)
    ]
    if not candidates:
        return None
    return max(candidates, key=_eponline_label_recency_key)


def _eponline_label_recency_key(label: EnergyLabel) -> tuple[int, int, int]:
    """Sort key: ``(registratiedatum, opnamedatum, has_reg)``."""
    reg = label.registratiedatum
    opname = label.opnamedatum
    return (
        reg.toordinal() if reg else 0,
        opname.toordinal() if opname else 0,
        1 if reg else 0,
    )


# ---------------------------------------------------------------------------
# EP-online classification at the BuildingUnit level (per-VBO)
# ---------------------------------------------------------------------------


def _apply_eponline_classification_to_building_unit(
    unit: Any,
    label: EnergyLabel | None,
) -> None:
    """Attach per-VBO EP-online classification fields to a BuildingUnit.

    This function only handles values whose underlying physical reality
    is genuinely per-VBO. ``Bouwjaar`` and ``Gebouwtype`` are
    intentionally NOT among them: a building is constructed once and
    its primary type is fixed at the structure level, so both live at
    the Building (see
    :func:`apply_eponline_pand_attribution_to_building`).

    Two emissions on a BuildingUnit when an EP-online label is set:

    * ``gen:stringAttribute name="bdgSubtypeEPOnline"``: the Dutch RVO
      ``Gebouwsubtype`` term verbatim (e.g. ``"appartement-portiekflat"``,
      ``"rijwoning-tussen"``). Per-VBO because two VBOs in one Pand can
      carry different subtypes (mixed-use, partial conversion).
      Encoded as a generic string attribute because EnergyADE 3.0 has
      no native ``nrg3:bdgSubtype`` element; the ``EPOnline`` suffix
      flags the source vocabulary so a downstream reader does not
      mistake the Dutch term for an Energy-ADE codelist member.
    * One ``nrg3:Metadata`` block on the BuildingUnit attributing the
      EP-online source.  The ``qualityDescription`` enumerates only the
      EP-online artefacts that actually landed on *this* BuildingUnit,
      not the full universe of EP-online-derived fields the pipeline can
      attach in principle. The three calculation regimes EP-online
      covers (``nta8800``, ``legacy_total``, ``unknown``) populate
      different subsets of fields per row — e.g.
      ``GebruiksoppervlakteThermischeZone`` is empty for 100% of legacy
      rows and 100% of unknown-regime rows, and BENG-1/2/3 are only
      populated on NTA 8800 rows — so a generic boilerplate would
      promise things like "the thermal-zone QualifiedArea" on units
      where no such area was emitted. The per-cert enumeration here
      keeps the metadata honest.

    No-op when *label* is ``None``.
    """
    if label is None:
        return

    # ``description_parts`` accumulates one line per EP-online artefact
    # actually written to this unit so the Metadata block enumerates
    # only what's present, mirroring the pattern in
    # :func:`apply_eponline_pand_attribution_to_building`.
    description_parts: list[str] = []

    if label.gebouwsubtype:
        unit.string_attribute.append(
            StringAttribute(
                name="bdgSubtypeEPOnline",
                value=label.gebouwsubtype,
            )
        )
        description_parts.append(
            "gen:stringAttribute name=\"bdgSubtypeEPOnline\" "
            "(Dutch RVO Gebouwsubtype, verbatim)"
        )

    # Renewable-share, thermal-zone area, and Energy resources are
    # written elsewhere (``build_building_unit`` and
    # ``attach_energy_resources_to_building_unit``); we mirror their
    # emission predicates here so the boilerplate stays in sync.
    if label.aandeel_hernieuwbare_energie is not None:
        description_parts.append(
            "gen:measureAttribute name=\"epOnlineAandeelHernieuwbareEnergie\" "
            "(BENG-3 renewable-energy share, %)"
        )
    if (
        label.gebruiksoppervlakte_thermische_zone is not None
        and label.gebruiksoppervlakte_thermische_zone > 0
    ):
        description_parts.append(
            "nrg3:QualifiedArea type=\"netFloorArea\" sourced from "
            "GebruiksoppervlakteThermischeZone (NTA 8800 thermal-zone area)"
        )
    # The energy-resource enumeration mirrors the regime dispatch in
    # :func:`energy_resources.attach_energy_resources_to_building_unit`.
    # ``berekende_co2_emissie`` is deliberately excluded as a trigger:
    # CO2 never lands as its own resource (it rides on a BENG-2 or
    # legacy-total Energy that requires its own ``amount``), so a
    # CO2-only label would otherwise emit a Metadata block annotating
    # something that did not actually land.
    regime = label.calculation_regime()
    if regime == "nta8800":
        nta_resources = []
        if label.energiebehoefte is not None:
            nta_resources.append("Energiebehoefte (BENG-1, net)")
        if label.warmtebehoefte is not None:
            nta_resources.append("Warmtebehoefte (NTA 8800 net heating demand)")
        if label.primaire_fossiele_energie is not None:
            nta_resources.append("PrimaireFossieleEnergie (BENG-2, primary)")
        if label.berekende_energieverbruik is not None:
            nta_resources.append(
                "BerekendeEnergieverbruik (NTA 8800 delivered/finaal total)"
            )
        if nta_resources:
            description_parts.append(
                "nrg3:Energy resources via nrg3:resource: "
                + ", ".join(nta_resources)
            )
    elif regime == "legacy_total":
        if label.berekende_energieverbruik is not None:
            description_parts.append(
                "nrg3:Energy resource via nrg3:resource: "
                "BerekendeEnergieverbruik "
                "(legacy NEN 7120 / Nader Voorschrift / ISSO 75.3-82.3 "
                "primary-fossil EP_tot total, MJ/yr)"
            )
    # ``unknown`` regime: no resources are attached, nothing to add.

    if not description_parts:
        return

    unit.metadata.append(
        Metadata1(
            source="EP-online Mutatiebestand v4 (RVO)",
            quality_description=(
                "Source for the following EP-online-derived per-VBO "
                "emissions on this BuildingUnit: "
                + "; ".join(description_parts)
                + ". Year of construction (yearOfConstructionEPOnline) "
                "and the primary building type (nrg3:bdgType) are at "
                "the Building level: a Pand is constructed once and "
                "its primary type is fixed at the structure level."
            ),
        )
    )


# ---------------------------------------------------------------------------
# EnergyPerformanceCertificate
# ---------------------------------------------------------------------------


def _build_epc(
    resolved: ResolvedAddress,
    *,
    gml_id_prefix: str,
) -> Any | None:
    """Build a ``nrg3:EnergyPerformanceCertificate`` for *resolved*'s VBO.

    The EPC is parented to the BuildingUnit via
    ``nrg3:BuildingUnit/nrg3:energyPerformanceCertificate`` (XSD line 1527),
    not to the Building. This is intentional and reflects how Dutch
    energy labels actually work: EP-online issues one certificate
    per-VBO (``BAGVerblijfsobjectID`` is the join key) so that, in a
    mixed-use Pand or an apartment building, every dwelling can carry its
    own letter (e.g. one apartment "A" while another in the same Pand
    is "C"). The Energy ADE 3.0 XSD also exposes
    ``energyPerformanceCertificate`` as an ADE property of
    ``bldg:_AbstractBuilding`` (line 1627), and Alderaan
    (``Energy_ADE-3.0beta8/test_data/Alderaan_Energy_ADE_All.gml``)
    attaches its EPC there for a single-building demo — but that
    placement aggregates away the per-dwelling resolution NL needs.
    Keep this association on BuildingUnit unless the upstream certifying
    body becomes per-Pand.

    No-op when *resolved* has no matched EP-online label or when the
    label has no ``Energieklasse`` letter (``EPC.label`` is ``xs:string``
    and required by the XSD; an EPC without a letter would not validate).
    """
    label = resolved.energy_label
    if label is None or label.energieklasse is None:
        return None

    from xsdata.models.datatype import XmlDateTime

    epc_cls = resolve_class(ENERGY_PERFORMANCE_CERTIFICATE)

    # ``EnergyPerformanceCertificate.type`` is ``EPCTypeValue.xml``-typed:
    # it carries the *energy-domain scope* of the certificate (heating /
    # cooling / domesticHotWater / totalEnergyDemand / other / unknown),
    # NOT the issuing authority. NTA-8800 EPCs cover the full building
    # energy budget (heating + cooling + ventilation + DHW + lighting +
    # renewable share), so the codelist-honest scope is ``totalEnergyDemand``.
    # The legacy methods (Definitief Energielabel v1.2 / Nader Voorschrift /
    # ISSO 75.3 / 82.3) also report a total-building energy figure, so the
    # same scope applies — the unit divergence (kWh/(m²·yr) vs MJ/yr,
    # documented in mapping doc § 5i) is in the resource amounts, not in
    # the certificate scope. The "EP-online" provenance lives on the
    # accompanying ``nrg3:Metadata/source`` block emitted by
    # :func:`_apply_eponline_classification_to_building_unit` and on the
    # EPC's ``certificationMethod`` string composed below.
    epc = epc_cls(
        id=safe_gml_id(gml_id_prefix, "epc", resolved.vbo.identificatie),
        type_value=CodeType(value="totalEnergyDemand", code_space=CS_NRG3_EPC_TYPE),
        label=label.energieklasse,
    )

    # ``nrg3:status`` is inherited from ``AbstractFeatureWithLifeSpan``
    # (XSD line 479, gml:CodeType, minOccurs=0). The EPCStatusValue
    # codelist (``actual | potential | unknown``) distinguishes a
    # registered, real certificate from a simulated forecast (Alderaan's
    # demo EPCs are all ``simulated``, which is not a codelist member —
    # likely a stale draft). Every cert in the EP-online Mutatiebestand
    # is by definition the registered, legally-valid certificate for the
    # VBO ("alleen deze geregistreerde labels zijn rechtsgeldig" — RVO
    # Handleiding EP-online: opvragen van bestanden, v1.0 feb 2025, §1),
    # so ``actual`` is the correct value.
    epc.status = CodeType(value="actual", code_space=CS_NRG3_EPC_STATUS)

    # Date columns:
    #
    # * ``Opnamedatum`` (date of the on-site inspection by the energy
    #   advisor) -> ``creationDate`` (xs:date, inherited from
    #   AbstractADEFeature, line 454). The certificate object comes into
    #   existence as a document on the day of the inspection, before any
    #   subsequent registration step.
    # * ``Registratiedatum`` (date the cert was registered with RVO;
    #   "Datum van registreren van het label. Dit hoeft niet gelijk te
    #   zijn aan de opnamedatum." — RVO Handleiding § Bijlage 2) ->
    #   ``validFrom`` (xs:dateTime). The cert becomes legally valid only
    #   on registration: "alleen deze geregistreerde labels zijn
    #   rechtsgeldig" (same RVO source). Cast date->datetime at midnight
    #   Europe/Amsterdam (no offset; xsdata serialises naive dateTimes
    #   without a timezone, matching the rest of the project).
    # * ``Geldig_tot`` ("Geldigheid label = opnamedatum + 10 jaar" —
    #   same source) -> ``validTo`` (xs:dateTime, also at midnight).
    # * ``terminationDate`` (xs:date, line 455) is reserved for
    #   Stuurcode-2 deletions in the Mutatiebestand and is NOT set
    #   equal to ``validTo``: a cert that simply hits its expiry is
    #   still in the totaalbestand and should not be terminated. Left
    #   absent for active certs.
    if label.opnamedatum is not None:
        from xsdata.models.datatype import XmlDate

        epc.creation_date = XmlDate.from_string(label.opnamedatum.isoformat())
    if label.registratiedatum is not None:
        epc.valid_from = XmlDateTime.from_string(
            f"{label.registratiedatum.isoformat()}T00:00:00"
        )
    if label.geldig_tot is not None:
        epc.valid_to = XmlDateTime.from_string(
            f"{label.geldig_tot.isoformat()}T00:00:00"
        )

    method = _certification_method_string(label)
    if method is not None:
        # ``Berekeningstype`` names the NTA-8800 variant used for the
        # calculation (e.g. "NTA 8800:2024 (detailopname utiliteitsbouw)");
        # ``SoortOpname`` ("Basisopname" / "Detailopname") qualifies the
        # inspection rigour. Both ride on
        # ``nrg3:EnergyPerformanceCertificate/certificationMethod``
        # (xs:string, minOccurs=0); a " / " separator preserves the two
        # values as a single auditable string while letting downstream
        # parsers split on it. Picked over a separate field per the
        # Phase-0 spec § 5d direction.
        epc.certification_method = method

    # ``nrg3:EnergyPerformanceCertificate.value`` is ``gml:MeasureType``
    # (XSD line 1431, ``minOccurs="0"``): a single ``double`` plus a
    # required ``@uom`` attribute. The schema deliberately leaves the
    # unit unfixed so each EPC source can record its native numeric
    # alongside the right unit, rather than forcing one canonical unit
    # across heterogeneous regimes. The Alderaan reference EPC carries
    # ``<nrg3:value uom="kWh/(m^2*a)">10</nrg3:value>`` (test_data/
    # Alderaan_Energy_ADE_All.gml) — exactly this "any number with its
    # uom" pattern.
    #
    # The letter (A++++ ... G) lives on ``nrg3:label`` (xs:string,
    # required by XSD); ``value`` is the numeric backing it. Cross-regime
    # comparability of the *number* is intentionally not a goal here —
    # the regimes use different methodologies, different normalisers,
    # and different units, and the ``@uom`` attribute is exactly what
    # the schema provides to keep that auditable. Aggregate longitudinal
    # analysis that wants a single common metric should aggregate from
    # ``nrg3:resource``/``nrg3:Energy`` (where the regime-aware energy-
    # type tagging already disambiguates ``primary`` vs ``final``), not
    # from ``EPC.value``.
    #
    # Source column: ``BerekendeEnergieverbruik`` for both regimes —
    # the only EP-online numeric that is populated for >99% of certs in
    # both. Per-regime dispatch on :meth:`EnergyLabel.calculation_regime`
    # picks the correct uom:
    #
    # * ``nta8800``  -> ``kWh/(m²·yr)`` (delivered/finaal energy per m²,
    #   per RVO v5 PublicAPI Swagger). Same uom token as the matching
    #   ``nrg3:Energy.amount`` resource (``UOM_KWH_PER_M2_PER_A``); the
    #   two stay in lockstep through the shared constant.
    # * ``legacy_total``  -> ``MJ/yr`` (total annual primary fossil
    #   energy EP_tot, NEN 7120 §5 formula 5.9, NOT per-m²). Same
    #   reasoning: shared ``UOM_MJ_PER_A`` constant pins the legacy
    #   EPC.value uom to the legacy Energy.amount uom.
    # * ``unknown``  -> skip; we will not invent a uom we cannot verify.
    #
    # Skipped entirely when ``BerekendeEnergieverbruik`` is missing
    # (rare — ~0.01% of NTA 8800 rows, ~0% of legacy_total rows in the
    # production v20260401 vintage).
    if label.berekende_energieverbruik is not None:
        regime = label.calculation_regime()
        if regime == "nta8800":
            epc.value = MeasureType(
                value=float(label.berekende_energieverbruik),
                uom=UOM_KWH_PER_M2_PER_A,
            )
        elif regime == "legacy_total":
            epc.value = MeasureType(
                value=float(label.berekende_energieverbruik),
                uom=UOM_MJ_PER_A,
            )
        # ``unknown`` regime: leave value unset. Emitting a number
        # without a defensible uom would mislead downstream consumers
        # into treating one regime's units as the other's; the schema
        # makes the field optional precisely for cases like this.

    return epc


def _certification_method_string(label: EnergyLabel) -> str | None:
    """Compose the EPC ``certificationMethod`` string from EP-online inputs.

    Joins ``SoortOpname`` and ``Berekeningstype`` with `` / `` (space-slash-
    space) when both are present, returns whichever is set when only one is
    present, and returns ``None`` when neither is set. The separator
    deliberately avoids the em dash per the project's annotation
    convention; downstream tools can split on `` / `` to recover both.
    """
    parts = [
        text
        for text in (label.soort_opname, label.berekeningstype)
        if text and text.strip()
    ]
    if not parts:
        return None
    return " / ".join(p.strip() for p in parts)
