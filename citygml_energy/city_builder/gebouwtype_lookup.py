"""Map RVO ``Gebouwtype`` values to Energy ADE 3.0 ``BuildingTypeValue`` codes.

EP-online's ``Gebouwtype`` column ships the Dutch RVO NTA-8800 typology
("Rijwoning hoek", "Vrijstaande woning", "Kantoorgebouw", …); the
Energy ADE 3.0 ``BuildingTypeValue.xml`` codelist is in English
("singleFamilyHouse", "office", …). This module is the only place that
crosses the language gap, so a future change to either side is local.

**Unmapped values do not fall through to a generic attribute.** Per the
Phase-0 specification (`docs/ep_online_data_model_mapping.md` §5e), an
unmapped ``Gebouwtype`` is logged at WARNING and dropped. The user can
extend the table and re-run; we never emit an unmapped Dutch term as an
``nrg3:bdgType`` because that would corrupt the BuildingTypeValue
vocabulary, and we never emit it as a ``gen:stringAttribute`` because
the §5e direction is "no generic-attribute clutter for Skip-(latent)
fields."

The codelist URL the emitted CodeType points at is
:data:`citygml_energy.namespaces.CS_NRG3_BUILDING_TYPE`. Per the project
memory note on the codespace convention, that URL is flat at
``.../energy/3.0/BuildingTypeValue.xml`` (no ``/codelists/`` segment).
"""

from __future__ import annotations

import logging

__all__ = [
    "GEBOUWTYPE_TO_BDG_TYPE",
    "lookup_bdg_type",
]

_LOG = logging.getLogger(__name__)


# Dutch RVO Gebouwtype → English Energy ADE BuildingTypeValue.
#
# Source: the RVO NTA-8800 enumeration as published in the EP-online
# Mutatiebestand (the Gebouwtype column lists each Dutch term verbatim).
# The English target values follow the Energy ADE 3.0
# ``BuildingTypeValue.xml`` codelist convention; the project memory
# notes that the codelist file lives at
# ``http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/BuildingTypeValue.xml``
# (verified against the live host, not the bundled XSD).
#
# Conservative coverage: the mappings below cover the residential and
# common utility-building types observed on the Emmer-Compascuum dataset
# and the Dutch national mutation file. Less common types (industrial,
# specialised healthcare subtypes, etc.) intentionally fall through to
# the unmapped path so they show up as warnings during the first
# city-scale run that hits them, prompting a deliberate code change
# rather than a silent miscategorisation.
GEBOUWTYPE_TO_BDG_TYPE: dict[str, str] = {
    # --- residential (Woningen) -----------------------------------------
    # Free-standing single-family residence. The canonical use of
    # singleFamilyHouse in the Energy ADE codelist.
    "Vrijstaande woning": "singleFamilyHouse",
    # Semi-detached: two homes sharing a single party wall. Matches
    # singleFamilyHouse semantically (one dwelling per unit) but with the
    # shared-wall thermal context implicit; the codelist has no
    # semiDetachedHouse member, so we collapse to singleFamilyHouse and
    # rely on Gebouwsubtype (Skip-(latent), §5e) to recover the nuance
    # if a future analysis needs it. RVO ships several typographic
    # variants of the same term; map each one observed in the
    # production CSV.
    "2 onder 1 kap woning": "singleFamilyHouse",
    "2-onder-1-kapwoning": "singleFamilyHouse",
    "Twee-onder-een-kap": "singleFamilyHouse",
    "Twee-onder-één-kap": "singleFamilyHouse",
    # Hybrid types where RVO records a slash-separated dual classification
    # (a corner unit on a row of terraced houses that's also a 2-onder-
    # 1-kap with the next row, for example). Both variants resolve to
    # singleFamilyHouse on the same logic as the unitary terraced /
    # semi-detached entries above.
    "Twee-onder-een-kap / rijwoning hoek": "singleFamilyHouse",
    "Twee-onder-één-kap / rijwoning hoek": "singleFamilyHouse",
    # Terraced houses: row of three or more dwellings sharing party walls.
    # NTA 8800 distinguishes corner units ("hoek") from middle units
    # ("tussen") because they have different envelope-loss profiles, but
    # both are single-family dwellings in the Energy ADE typology.
    "Rijwoning hoek": "singleFamilyHouse",
    "Rijwoning tussen": "singleFamilyHouse",
    "Hoekwoning": "singleFamilyHouse",
    "Tussenwoning": "singleFamilyHouse",
    # Stacked dwellings: galerijflat / portiekflat / appartement /
    # maisonnette all map to multiFamilyHouse (a single building hosting
    # multiple dwelling units).
    "Galerijflat": "multiFamilyHouse",
    "Galerijwoning": "multiFamilyHouse",
    "Portiekflat": "multiFamilyHouse",
    "Portiekwoning": "multiFamilyHouse",
    "Appartement": "multiFamilyHouse",
    "Appartementengebouw": "multiFamilyHouse",
    "Flatgebouw": "multiFamilyHouse",
    # "Flatwoning (overig)" is RVO's catch-all for stacked dwellings that
    # don't fit galerij / portiek / appartement explicitly. Still a
    # multi-dwelling building from the Energy ADE typology's standpoint.
    "Flatwoning (overig)": "multiFamilyHouse",
    "Maisonnette": "multiFamilyHouse",
    "Woongebouw": "multiFamilyHouse",
    # --- utility (Utiliteitsbouw) ---------------------------------------
    "Kantoorgebouw": "office",
    "Kantoor": "office",
    "Winkelgebouw": "commercial",
    "Winkel": "commercial",
    "Horecagebouw": "commercial",
    "Logiesgebouw": "hotel",
    "Hotelgebouw": "hotel",
    "Onderwijsgebouw": "educational",
    "Schoolgebouw": "educational",
    "Sportgebouw": "sportsHall",
    "Sporthal": "sportsHall",
    "Gezondheidszorggebouw": "healthcare",
    "Bijeenkomstgebouw": "assembly",
    "Industriegebouw": "industrial",
    "Industrieel": "industrial",
}


def lookup_bdg_type(gebouwtype: str | None) -> str | None:
    """Return the Energy ADE ``BuildingTypeValue`` for *gebouwtype*, or ``None``.

    Returns ``None`` for any of:

    * an empty / whitespace-only / ``None`` input,
    * a Gebouwtype value that is not in :data:`GEBOUWTYPE_TO_BDG_TYPE`.

    The unmapped case logs a WARNING naming the missing Gebouwtype so a
    city-scale run surfaces every newly-encountered RVO term explicitly;
    the table can be extended and the run re-tried without changing call
    sites. This matches the Phase-0 spec direction "fail loudly during
    implementation rather than silently miscategorising."
    """
    if not gebouwtype:
        return None
    key = gebouwtype.strip()
    if not key:
        return None
    bdg_type = GEBOUWTYPE_TO_BDG_TYPE.get(key)
    if bdg_type is None:
        _LOG.warning(
            "EP-online Gebouwtype %r has no Energy ADE BuildingTypeValue "
            "lookup; nrg3:bdgType not emitted. Add a mapping to "
            "citygml_energy.city_builder.gebouwtype_lookup if this term "
            "should land in the output.",
            key,
        )
    return bdg_type
