"""Gemeente Emmen BOR (Beheer Openbare Ruimte) tree register.

Queries the public ArcGIS Online FeatureServer published by Gemeente
Emmen as ``bor_groen_bomen_beschermd``. Despite the ``_beschermd``
suffix, the layer is **not** restricted to the 466 ``Monumentale boom``
records — it carries the municipality's full BOR tree register
(57 503 ``Bijzondere boom`` + 466 ``Monumentale boom`` as of writing).
That makes it the per-tree attribute source the project's BGT
``vegetatieobject_punt`` layer is missing: BGT is geometry-only, while
this register adds species, planting year, height/diameter classes and
protection status per individually-registered tree.

The fetcher mirrors :mod:`citygml_energy.city_builder.fetchers.bgt`:

* **Cross-reference + attribute fetcher.** Unlike BGT, this register
  carries genuine attributes; the city pipeline calls
  :func:`citygml_energy.city_builder.tree_matching.match_nearest_within`
  inline to join BOR points to CFTree trees, and consumers in
  :mod:`citygml_energy.city_builder.builders` write the matched
  attributes into native CityGML 2.0 vegetation slots (``species``,
  ``class``, ``function``) plus ``gen:*Attribute`` siblings for fields
  that have no native slot.
* **Bbox query in EPSG:28992.** Server returns features in RD New, the
  project's working CRS, so no reprojection.
* **Disk-cached via the shared :class:`CachedSession`.** Subsequent
  builds against the same AOI skip the network entirely.
* **Soft failure.** The enrichment is opportunistic: any predictable
  network or parse error logs a warning and returns ``[]`` so the
  vegetation step degrades to plain BGT-only cross-referencing rather
  than failing the whole city build.

Scope decision: this is a Dutch government open-data source (owner
``ago@emmen``), so it satisfies the project's
"Dutch-government-data-only" policy that previously eliminated
OpenStreetMap and the Bomenstichting national register. It is also
Emmen-specific; the city pipeline's PoC is scoped to Emmer-Compascuum,
so a generic municipal-register abstraction is deliberately not
introduced here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .._helpers import bbox_cache_key, to_clean_str, to_int
from ..http import CachedSession

__all__ = [
    "BOR_FEATURESERVER_URL",
    "BOR_INFORMATION_SYSTEM_URL",
    "BorTree",
    "bor_feature_uri",
    "fetch_bor_trees",
]

_LOG = logging.getLogger(__name__)

# Canonical layer endpoint. Pinned as a constant so a future Emmen
# service relocation surfaces as one unit-testable string rather than a
# pattern spread across the codebase.
BOR_FEATURESERVER_URL: str = (
    "https://services3.arcgis.com/YaBq8GMTp0Kh437n/arcgis/rest/services/"
    "bor_groen_bomen_beschermd/FeatureServer/0"
)

# URI written into ``core:externalReference/informationSystem``. The
# public Erfgoed page documents the dataset semantics for a reader who
# follows the link, where the raw FeatureServer URL would only show
# JSON. Mirrors the BGT pattern of preferring a human-readable
# catalog page over the API endpoint.
BOR_INFORMATION_SYSTEM_URL: str = "https://gemeente.emmen.nl/erfgoed"

# ArcGIS REST query is capped at 2000 features per request by the
# server. Within Emmer-Compascuum the bbox returns ~700 features in
# total; pagination here mostly serves to cover full-municipality
# rebuilds without surprises.
_PAGE_SIZE: int = 2000

# RD New WKID, expected by the FeatureServer for both ``inSR`` and
# ``outSR``. Using the integer form (not the URL form PDOK requires)
# because ArcGIS REST uses WKIDs.
_RD_NEW_WKID: int = 28992

# We want every populated attribute that maps cleanly to CityGML 2.0
# vegetation slots or to a documented ``gen:*Attribute`` sibling. Any
# field outside this list is dropped at parse time so the downstream
# join stays light. The set tracks the columns enumerated in
# ``docs/vegetation_integration_report.md`` § 3.3 (BOR mapping table).
_OUT_FIELDS: tuple[str, ...] = (
    "boom_id",
    "soortnaam",
    "soortnaam_ned",
    "jaarvanaanleg",
    "boomhoogteklasseactueel",
    "stamdiameterklasse",
    "beschermingsstatus",
    "beschermingsstatus_detail",
    "type",
    "standplaats",
    "standplaats_detail",
)


@dataclass(frozen=True, slots=True)
class BorTree:
    """A single record from Emmen's BOR tree register.

    Only fields that carry information into the CityGML output are
    stored; ArcGIS bookkeeping (``OBJECTID``, ``GlobalID``,
    ``m_datum_tijd_ververst``, …) is dropped at parse time.
    ``slots=True`` because a full-municipality build can carry close
    to 60k of these records.

    Attributes:
        boom_id: stable Emmen-internal tree id. Becomes the cross-
            reference handle written into ``core:externalReference``;
            unlike ``OBJECTID`` it survives a server-side re-build of
            the layer.
        x_rd, y_rd: tree position in EPSG:28992 metres.
        species_latin: Latin scientific name (e.g. ``"Quercus palustris"``)
            populated for ~26 % of records. ``None`` when missing.
            Targets ``veg:species``.
        species_dutch: Dutch common name (e.g. ``"Moeraseik"``).
            Targets ``gen:stringAttribute name="speciesCommonName"``.
        planting_year: ``jaarvanaanleg`` (~93 % populated). Targets
            ``gen:intAttribute name="plantingYear"`` — the workaround
            documented in the integration report § 4.1 because CityGML
            2.0 has no native planting-date slot.
        height_class: free-form size band string (e.g. ``"18 tot 24 m."``).
            Targets ``gen:stringAttribute name="heightClass"`` because
            ``veg:height`` is ``xs:double``-typed and is already
            populated from CFTree's measured value.
        trunk_diameter_class: same shape, e.g. ``"0,5 tot 0,75 m."``.
        protection_status: ``"Bijzondere boom"`` or ``"Monumentale boom"``.
            Targets ``gen:stringAttribute name="protectionStatus"``;
            this is a legal / heritage status, not a horticultural
            ``veg:function`` (see docs/mapping_city.md).
        protection_status_detail: optional sub-classification (e.g.
            ``"Bomenlijst boom"``, ``"Bomenstructuur boom"``).
        growth_form: Emmen ``type`` field (``"Boom vrij uitgroeiend"``
            / ``"Boom niet vrij uitgroeiend"``). Targets
            ``gen:stringAttribute name="growthForm"``; canopy / growth
            form is not what ``veg:class`` is for.
        stand_location: ``standplaats`` (``"Gras- en kruidachtigen"``,
            ``"Bosplantsoen"``, ``"Houtwal"``, …).
        stand_location_detail: ``standplaats_detail``.
    """

    boom_id: str
    x_rd: float
    y_rd: float
    species_latin: str | None
    species_dutch: str | None
    planting_year: int | None
    height_class: str | None
    trunk_diameter_class: str | None
    protection_status: str | None
    protection_status_detail: str | None
    growth_form: str | None
    stand_location: str | None
    stand_location_detail: str | None


def fetch_bor_trees(
    session: CachedSession,
    bbox: tuple[float, float, float, float],
) -> list[BorTree]:
    """Fetch every Emmen BOR tree whose point falls inside *bbox*.

    *bbox* is in EPSG:28992 (RD New). Returns ``[]`` on any predictable
    network or parse failure after logging a warning: the BOR
    enrichment is opportunistic and must not abort a city build when
    Emmen's ArcGIS Online tenant is unreachable.

    Caching is keyed by bbox + page index; subsequent runs against the
    same AOI skip the network entirely.
    """
    import requests as _requests

    try:
        features = _fetch_all_pages(session, bbox)
    except (_requests.RequestException, OSError, ValueError, KeyError) as exc:
        _LOG.warning(
            "Emmen BOR fetch failed (%s); skipping tree enrichment",
            exc,
        )
        return []

    trees: list[BorTree] = []
    for feat in features:
        attrs = feat.get("attributes") or feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        x = geom.get("x")
        y = geom.get("y")
        if x is None or y is None:
            # ``f=geojson`` returns the geometry under ``coordinates``
            # rather than ``x``/``y``. Handle both shapes so the parser
            # works against either response format.
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            x, y = coords[0], coords[1]

        boom_id = attrs.get("boom_id")
        if boom_id is None:
            # Without a stable handle we cannot write a cross-reference;
            # such a record is functionally useless for enrichment.
            continue

        trees.append(
            BorTree(
                boom_id=str(boom_id),
                x_rd=float(x),
                y_rd=float(y),
                species_latin=_clean_string(attrs.get("soortnaam")),
                species_dutch=_clean_string(attrs.get("soortnaam_ned")),
                planting_year=_clean_int(attrs.get("jaarvanaanleg")),
                height_class=_clean_string(attrs.get("boomhoogteklasseactueel")),
                trunk_diameter_class=_clean_string(attrs.get("stamdiameterklasse")),
                protection_status=_clean_string(attrs.get("beschermingsstatus")),
                protection_status_detail=_clean_string(
                    attrs.get("beschermingsstatus_detail")
                ),
                growth_form=_clean_string(attrs.get("type")),
                stand_location=_clean_string(attrs.get("standplaats")),
                stand_location_detail=_clean_string(attrs.get("standplaats_detail")),
            )
        )

    _LOG.info(
        "Fetched %d Emmen BOR tree records inside bbox (%s)", len(trees), bbox,
    )
    return trees


def bor_feature_uri(boom_id: str) -> str:
    """Return the canonical query URL for one Emmen BOR feature.

    ArcGIS REST exposes per-feature dereferencing only by ``OBJECTID``,
    which is not stable across server-side rebuilds. ``boom_id`` is
    Emmen's own stable identifier, so we emit a ``query`` URL keyed on
    ``boom_id`` instead. Dereferencing it returns a single-feature
    GeoJSON / EsriJSON payload, identical to what an ``OBJECTID`` URL
    would return except that it survives a layer republish.
    """
    return (
        f"{BOR_FEATURESERVER_URL}/query"
        f"?where=boom_id%3D{boom_id}"
        f"&outFields=*&outSR={_RD_NEW_WKID}&f=geojson"
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _fetch_all_pages(
    session: CachedSession,
    bbox: tuple[float, float, float, float],
) -> list[dict[str, Any]]:
    """Walk every ``resultOffset`` page of the FeatureServer query.

    ArcGIS REST signals "no more pages" via
    ``"exceededTransferLimit": false`` (or its absence). We loop until
    a page either reports the limit was not exceeded or returns fewer
    features than requested — both are unambiguous "this is the last
    page" signals.
    """
    xmin, ymin, xmax, ymax = bbox
    base_params: dict[str, Any] = {
        "where": "1=1",
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": _RD_NEW_WKID,
        "outSR": _RD_NEW_WKID,
        "outFields": ",".join(_OUT_FIELDS),
        "returnGeometry": "true",
        "resultRecordCount": _PAGE_SIZE,
        "f": "json",
    }

    collected: list[dict[str, Any]] = []
    offset = 0
    page = 0
    url = f"{BOR_FEATURESERVER_URL}/query"

    while True:
        page += 1
        params = dict(base_params)
        params["resultOffset"] = offset
        cache_key = bbox_cache_key("emmen_bor", bbox, page=page)
        data = session.get_json(url, params=params, cache_key=cache_key)
        page_features = data.get("features") or []
        collected.extend(page_features)

        # Two complementary stop conditions: ArcGIS sets
        # ``exceededTransferLimit`` when the page was capped at the
        # server-side maximum, and a short page is the unambiguous
        # "no more rows" signal even when the flag is missing.
        more = bool(data.get("exceededTransferLimit"))
        if not more or len(page_features) < _PAGE_SIZE:
            break
        offset += len(page_features)

    return collected


def _clean_string(value: Any) -> str | None:
    """Emmen-flavour shim around :func:`_helpers.to_clean_str`.

    Drops the literal ``"None"`` / ``"null"`` placeholders that
    Emmen's ArcGIS Online tenant ships for unpopulated cells. Kept
    as a wrapper so a future tweak (e.g. dropping additional sentinels)
    lands in one place.
    """
    return to_clean_str(value, drop_literal_none=True)


def _clean_int(value: Any) -> int | None:
    """Emmen-flavour shim around :func:`_helpers.to_int`.

    Silent on parse failure: ArcGIS occasionally ships malformed
    rows, and degrading those to ``None`` is the same behaviour the
    field-level ``returnGeometry`` paths already implement.
    """
    return to_int(value)
