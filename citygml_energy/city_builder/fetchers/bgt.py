"""BGT (Basisregistratie Grootschalige Topografie) fetcher: tree points.

Queries PDOK's BGT OGC API Features endpoint for the
``vegetatieobject_punt`` collection filtered to the build bbox,
returning one :class:`BgtTree` per feature. The collection is the
Dutch government's authoritative per-tree point register: individual
free-standing trees publicly maintained by a ``bronhouder`` (a
municipality, province, water board, Rijkswaterstaat, ...).

Scope: **point trees only** (``plus_type = "boom"``). Hedges live in
``vegetatieobject_vlak`` with ``plus_type = "haag"`` and should map to
``veg:PlantCover`` in CityGML; they are out of scope here because
:mod:`citygml_energy.city_builder.builders.build_solitary_vegetation_object`
is specific to individual trees.

The IMGeo 2.2 data catalog is quite spare for trees: the schema
carries only ``bgt_type`` + ``plus_type`` + geometry + registry
bookkeeping (``lokaal_id``, ``creation_date``, ``bronhouder``). No
species, no leaf type, no planting year, no dimensions. We therefore
don't attempt semantic enrichment; this fetcher is a **cross-reference
fetcher**, not an attribute-enrichment one. The CityGML builder emits
the BGT ``lokaal_id`` as a ``core:externalReference`` so downstream
systems keyed on BGT can dereference our trees back to the authoritative
Dutch register.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from .._helpers import bbox_cache_key
from ..http import CachedSession

__all__ = [
    "BGT_FEATURES_URL",
    "BGT_INFORMATION_SYSTEM_URL",
    "BgtTree",
    "bgt_feature_uri",
    "fetch_bgt_trees",
]

_LOG = logging.getLogger(__name__)

# Root of PDOK's BGT OGC API Features endpoint. Pinned so a PDOK URL
# change surfaces as one unit-testable constant rather than a Str.format
# spread across the codebase.
BGT_FEATURES_URL: str = "https://api.pdok.nl/lv/bgt/ogc/v1"

# URI written into ``core:externalReference/informationSystem`` so a
# reader can identify the source authority. The BGT data-catalog page
# is a better "system identity" than a raw API endpoint because it
# describes the dataset semantics even when the API URL itself
# eventually moves.
BGT_INFORMATION_SYSTEM_URL: str = (
    "https://www.pdok.nl/ogc-apis/-/article/basisregistratie-grootschalige-topografie-bgt-"
)

# The BGT OGC API Features ``items`` endpoint is capped at 1000 per
# page (PDOK's server-side limit). For any single AOI in the
# city-scale use case the small-area Emmer-Compascuum AOI returns ~715
# boom points in ~1 km², so a single page normally suffices; pagination
# below handles the rare case where a larger AOI straddles that limit.
_PAGE_SIZE: int = 1000

# Explicit URN for EPSG:28992 / RD New. PDOK's OGC API honours the
# full OGC URL form in both ``bbox-crs`` and ``crs`` — the short
# ``EPSG:28992`` syntax is not accepted.
_RD_NEW_URL: str = "http://www.opengis.net/def/crs/EPSG/0/28992"

# Filter to keep only *individual trees*. PDOK returns every plus_type
# under the ``vegetatieobject_punt`` collection; we drop anything not
# explicitly a tree so the downstream spatial join never considers,
# e.g., "boomstronk" (tree stumps, which do exist as a plus_type in
# IMGeo but are not live trees).
_BGT_TREE_PLUS_TYPE: str = "boom"


@dataclass(frozen=True, slots=True)
class BgtTree:
    """A single BGT ``vegetatieobject_punt`` with ``plus_type = "boom"``.

    Only the fields that carry genuine information are stored; the rest
    of the IMGeo bookkeeping (``lv_publicatiedatum``, ``in_onderzoek``,
    codespace URIs, ...) is dropped at parse time so the downstream
    join stays light. ``slots=True`` because a national-scale build
    could easily materialise tens of thousands of these.

    Attributes:
        lokaal_id: BGT feature id, globally unique across the Dutch
            register. Shape: ``"{bronhouder_code}.{uuid_hex}"``, e.g.
            ``"G0114.703d17f4c978045de05363ab720afc9b"`` for a tree
            maintained by the municipality of Emmen (``G0114``).
        x_rd, y_rd: tree position in EPSG:28992 metres. BGT point
            accuracy is nominally 0.3 m (class D) or better.
        creation_date: when the feature was first registered in BGT.
            Not the planting date, but a soft upper bound on tree age
            (the tree existed by at least this date).
        bronhouder: the authority responsible for the record, e.g.
            ``"G0114"`` (municipality code), ``"L0002"`` (province).
            Useful downstream when multi-municipality builds need to
            route maintenance queries to the right authority.
    """

    lokaal_id: str
    x_rd: float
    y_rd: float
    creation_date: _dt.date | None
    bronhouder: str | None


def fetch_bgt_trees(
    session: CachedSession,
    bbox: tuple[float, float, float, float],
) -> list[BgtTree]:
    """Fetch every BGT ``vegetatieobject_punt`` tree inside *bbox*.

    *bbox* is in EPSG:28992 (RD New). Returns ``[]`` on any network or
    parse error after logging a warning: the vegetation cross-reference
    is an opportunistic enrichment, not a hard requirement, so a PDOK
    outage must not fail the city build.

    The call is keyed for disk caching by the bbox. Subsequent runs
    against the same AOI skip the network entirely.
    """
    # Cross-reference is opportunistic: any predictable failure mode of
    # the underlying fetch (network, malformed JSON, unexpected shape)
    # must not fail the whole city build. Unexpected programming errors
    # (AttributeError, TypeError from refactors, KeyboardInterrupt, ...)
    # deliberately propagate so they are not masked as "PDOK outages".
    import requests as _requests

    try:
        features = _fetch_all_pages(session, bbox)
    except (_requests.RequestException, OSError, ValueError, KeyError) as exc:
        _LOG.warning(
            "BGT vegetatieobject_punt fetch failed (%s); skipping BGT cross-reference",
            exc,
        )
        return []

    trees: list[BgtTree] = []
    for feat in features:
        props = feat.get("properties") or {}
        if props.get("plus_type") != _BGT_TREE_PLUS_TYPE:
            # Defensive: the collection is "vegetatieobject_punt" which
            # in IMGeo is not exclusively trees — plus_type disambiguates.
            continue
        if props.get("status") == "voormalig":
            # ``voormalig`` = terminated / removed from the landscape.
            # Keeping these would overcount against CFTree's current-day
            # reconstructions. Safe to skip; ``bestaand`` is the live set.
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        lokaal_id = props.get("lokaal_id")
        if not lokaal_id:
            continue
        trees.append(
            BgtTree(
                lokaal_id=str(lokaal_id),
                x_rd=float(coords[0]),
                y_rd=float(coords[1]),
                creation_date=_parse_iso_date(props.get("creation_date")),
                bronhouder=(
                    str(props["bronhouder"]) if props.get("bronhouder") else None
                ),
            )
        )
    _LOG.info(
        "Fetched %d BGT boom points inside bbox (%s)", len(trees), bbox,
    )
    return trees


def bgt_feature_uri(lokaal_id: str) -> str:
    """Return the canonical OGC API Features URI for one BGT tree.

    Dereferencing this URI with ``Accept: application/geo+json`` yields
    the feature itself; with ``Accept: text/html`` yields a PDOK
    human-readable page. Stable across PDOK deployments: the BGT
    ``lokaal_id`` is the authoritative handle, not the transient
    ``version`` id that changes on every mutation.
    """
    return f"{BGT_FEATURES_URL}/collections/vegetatieobject_punt/items/{lokaal_id}"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _fetch_all_pages(
    session: CachedSession,
    bbox: tuple[float, float, float, float],
) -> list[dict[str, Any]]:
    """Walk every cursor page until exhausted, returning the combined feature list.

    OGC API Features uses RFC 5005 ``rel="next"`` links for pagination.
    We consult that link rather than the OGC-documented
    ``numberReturned``/``numberMatched`` shortcut because PDOK's
    implementation has been observed to omit the numbers in some
    responses. The link walk is the portable approach.
    """
    xmin, ymin, xmax, ymax = bbox
    params: dict[str, Any] | None = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "bbox-crs": _RD_NEW_URL,
        "crs": _RD_NEW_URL,
        "limit": _PAGE_SIZE,
        "f": "json",
    }
    collected: list[dict[str, Any]] = []
    url = f"{BGT_FEATURES_URL}/collections/vegetatieobject_punt/items"
    page = 0
    while True:
        page += 1
        cache_key = bbox_cache_key("bgt_vegetatieobject_punt", bbox, page=page)
        data = session.get_json(url, params=params, cache_key=cache_key)
        page_features = data.get("features") or []
        collected.extend(page_features)
        next_url = _find_next_link(data.get("links") or [])
        if next_url is None or not page_features:
            break
        # After page 1 we follow the 'next' link verbatim — PDOK embeds
        # the cursor token in the URL, so re-sending the original
        # ``params`` would reset pagination and loop forever.
        url = next_url
        params = None
    return collected


def _find_next_link(links: list[dict[str, Any]]) -> str | None:
    for link in links:
        if link.get("rel") == "next" and link.get("href"):
            return str(link["href"])
    return None


def _parse_iso_date(raw: Any) -> _dt.date | None:
    """Parse a BGT ISO-8601 timestamp ``"2018-07-04T22:00:00Z"`` to a date.

    BGT stores feature timestamps in UTC; for dating a tree we only
    want the calendar day, so the time part is dropped deliberately.
    """
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return _dt.date.fromisoformat(raw[:10])
    except ValueError as exc:
        _LOG.warning("BGT creation_date not ISO-8601 (%r): %s", raw, exc)
        return None
