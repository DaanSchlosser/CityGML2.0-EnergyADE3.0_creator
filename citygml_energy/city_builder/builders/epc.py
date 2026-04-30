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
    Metadata1,
    StringAttribute,
)
from ...mapping import resolve_class
from ...namespaces import CS_NRG3_EPC_TYPE, CS_RVO_GEBOUWTYPE
from ...schema_types import ENERGY_PERFORMANCE_CERTIFICATE
from .._helpers import safe_gml_id
from ..address_match import ResolvedAddress
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
      EP-online source. Emitted whenever ``bdgSubtypeEPOnline`` lands or
      whenever any per-VBO energy-flow values land (Energy resources,
      renewable-share measure attribute, thermal-zone area), those
      emissions live on the same BuildingUnit too, so a single
      metadata block on the unit covers all of them.

    No-op when *label* is ``None``.
    """
    if label is None:
        return

    emitted_subtype = False

    if label.gebouwsubtype:
        unit.string_attribute.append(
            StringAttribute(
                name="bdgSubtypeEPOnline",
                value=label.gebouwsubtype,
            )
        )
        emitted_subtype = True

    # The Metadata block annotates the EP-online source for every
    # per-VBO emission on this unit. We emit it whenever this VBO has
    # actually received an EP-online-derived value: ``bdgSubtypeEPOnline``
    # above, the renewable-share measure attribute (set in
    # ``build_building_unit``), the thermal-zone QualifiedArea (also set
    # in ``build_building_unit``), or any Energy resource (set by
    # :func:`energy_resources.attach_energy_resources_to_building_unit`).
    # Including the area in the trigger keeps the Metadata block paired
    # with every EP-online artefact on the unit, even for the (rare)
    # label that ships only ``gebruiksoppervlakte_thermische_zone`` and
    # no other numerics.
    #
    # The ``has_energy`` test mirrors the regime dispatch in
    # :func:`energy_resources.attach_energy_resources_to_building_unit`,
    # for ``unknown`` regimes that emitter is a no-op, so we report
    # no energy data even when the dataclass fields are populated.
    # ``berekende_co2_emissie`` is intentionally excluded from the
    # trigger because CO2 never lands on its own resource (it always
    # rides on a BENG-2 / legacy-total Energy that requires its own
    # ``amount``); a CO2-only label would otherwise emit a Metadata
    # block annotating something that did not actually land.
    has_renewable = label.aandeel_hernieuwbare_energie is not None
    has_thermal_zone_area = (
        label.gebruiksoppervlakte_thermische_zone is not None
        and label.gebruiksoppervlakte_thermische_zone > 0
    )
    regime = label.calculation_regime()
    if regime == "nta8800":
        has_energy = any(
            v is not None
            for v in (
                label.energiebehoefte,
                label.warmtebehoefte,
                label.primaire_fossiele_energie,
                label.berekende_energieverbruik,
            )
        )
    elif regime == "legacy_total":
        has_energy = label.berekende_energieverbruik is not None
    else:
        has_energy = False
    if emitted_subtype or has_renewable or has_thermal_zone_area or has_energy:
        unit.metadata.append(
            Metadata1(
                source="EP-online Mutatiebestand v4 (RVO)",
                quality_description=(
                    "Source for the EP-online-derived per-VBO emissions "
                    "on this BuildingUnit (bdgSubtypeEPOnline, "
                    "epOnlineAandeelHernieuwbareEnergie, the EP-online "
                    "thermal-zone nrg3:QualifiedArea, and the "
                    "nrg3:Energy resources hosted via nrg3:resource). "
                    "Year of construction (yearOfConstructionEPOnline) "
                    "and the primary building type (nrg3:bdgType) are "
                    "at the Building level: a Pand is constructed once "
                    "and its primary type is fixed at the structure "
                    "level."
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
    label = resolved.energy_label
    if label is None or label.energieklasse is None:
        # EPC.label is xs:string and required, so skip when we have no letter.
        return None

    from xsdata.models.datatype import XmlDateTime

    epc_cls = resolve_class(ENERGY_PERFORMANCE_CERTIFICATE)

    epc = epc_cls(
        id=safe_gml_id(gml_id_prefix, "epc", resolved.vbo.identificatie),
        type_value=CodeType(value="EP-online", code_space=CS_NRG3_EPC_TYPE),
        label=label.energieklasse,
    )
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
