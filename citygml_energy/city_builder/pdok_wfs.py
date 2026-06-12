"""PDOK WFS 2.0 paginated GetFeature.

Three PDOK fetchers (BAG, CBS Postcode6, municipality bestuurlijkegebieden)
share the same request shape: WFS 2.0 GetFeature with ``startIndex + count``,
GeoJSON output, EPSG:28992 SRS, optional bbox filter. This module is the
single seam for that request shape. The fetchers stay responsible for the
post-fetch transform (their schema-specific deduplication and field
extraction); the paginator owns the wire protocol.

Bbox subdivision is BAG-only and lives at the BAG call site as a thin
recursion on top of :func:`paginate_features`, steered by
:func:`count_matched_features` (a ``resultType=hits`` probe) so an
over-cap bbox is split *before* a doomed deep walk rather than after an
HTTP 400. CBS deliberately does not subdivide (~30 k features max per
municipality, well below the 50 k startIndex cap that PDOK enforces on
BAG). The municipality layer fits one page (~345 features nation-wide) so
there is no bbox at all.

Other PDOK protocols are NOT in scope: the BGT endpoint uses OGC API
Features and Emmen-BOR uses ArcGIS REST, with different request
vocabularies. Folding them in here would dilute "WFS 2.0 GetFeature"
into "any paged HTTP GET" and lose the per-protocol structure
(``typeNames``, ``srsName``, ``outputFormat``) that this module captures.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from ._helpers import bbox_cache_key
from .http import CachedSession

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_SRS_NAME",
    "count_matched_features",
    "paginate_features",
]

Bbox = tuple[float, float, float, float]

# Matches PDOK's server-side WFS 2.0 page cap. Smaller pages just mean
# more round trips for the same result.
DEFAULT_PAGE_SIZE: int = 1000

# RD New. Every PDOK WFS endpoint in scope here serves EPSG:28992
# natively; downstream consumers (3DBAG matching, boundary clipping,
# CityGML envelope) all assume metric Dutch coordinates.
DEFAULT_SRS_NAME: str = "EPSG:28992"

# Query keys the paginator owns. ``extra_params`` may not collide with
# these: overriding ``count``/``startIndex`` would desync the paging
# arithmetic, and the rest define the request identity the cache key is
# built from.
_RESERVED_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "service",
        "version",
        "request",
        "typeNames",
        "outputFormat",
        "srsName",
        "count",
        "startIndex",
        "bbox",
    }
)


def paginate_features(
    session: CachedSession,
    url: str,
    *,
    type_names: str,
    cache_prefix: str,
    bbox: Bbox | None = None,
    srs_name: str = DEFAULT_SRS_NAME,
    page_size: int = DEFAULT_PAGE_SIZE,
    extra_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Walk one WFS 2.0 layer page by page and return every feature.

    Stops when a short page (< *page_size* features) arrives — the WFS
    2.0 convention for "no more rows." Each page is cached separately
    on *session* under ``bbox_cache_key(cache_prefix, bbox, page=N)``
    when *bbox* is set, or ``f"{cache_prefix}.p{N}"`` when not. Reruns
    with the same bbox-or-layer hit the on-disk cache before the
    network.

    *cache_prefix* is the request's identity from the server's
    perspective (the layer name, or layer + vintage for CBS Postcode6).
    Do NOT embed consumer-side discriminants (e.g. a municipality name
    being searched for) into the prefix: the cache identity should be
    "what the server returns," not "what the caller is looking for."

    *extra_params* is folded into the WFS query so a caller can add CQL
    filters or vendor extensions without touching this module. The
    paginator's own keys (``service``, ``version``, ``typeNames``,
    ``count``, ``startIndex``, …) are not overrideable: a colliding key
    raises :class:`ValueError`, because overriding ``count`` or
    ``startIndex`` would silently desync the paging arithmetic.

    *page_size* must stay within ``[1, DEFAULT_PAGE_SIZE]``. PDOK clamps
    GetFeature pages at :data:`DEFAULT_PAGE_SIZE` rows regardless of the
    requested ``count``, so a larger request would make every page look
    "short", stop the walk after one page, and silently truncate the
    result; ``0`` would never see a short page and loop forever. Both
    are rejected loudly instead.
    """
    if not 1 <= page_size <= DEFAULT_PAGE_SIZE:
        raise ValueError(
            f"page_size must be in [1, {DEFAULT_PAGE_SIZE}], got {page_size}: PDOK "
            f"clamps GetFeature pages at {DEFAULT_PAGE_SIZE} rows, so a larger "
            f"request would silently truncate after one short-looking page"
        )
    if extra_params:
        clash = _RESERVED_PARAM_KEYS & extra_params.keys()
        if clash:
            raise ValueError(
                f"extra_params may not override the paginator's own WFS keys: {sorted(clash)}"
            )

    features: list[dict[str, Any]] = []
    start = 0
    while True:
        params: dict[str, Any] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": type_names,
            "outputFormat": "application/json",
            "srsName": srs_name,
            "count": page_size,
            "startIndex": start,
        }
        if bbox is not None:
            params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{srs_name}"
        if extra_params:
            params.update(extra_params)

        page_index = start // page_size
        cache_key = (
            bbox_cache_key(cache_prefix, bbox, page=page_index)
            if bbox is not None
            else f"{cache_prefix}.p{page_index}"
        )
        page = session.get_json(url, params=params, cache_key=cache_key)
        batch = page.get("features") or []
        features.extend(batch)
        if len(batch) < page_size:
            return features
        start += page_size


def count_matched_features(
    session: CachedSession,
    url: str,
    *,
    type_names: str,
    cache_prefix: str,
    bbox: Bbox | None = None,
    srs_name: str = DEFAULT_SRS_NAME,
    extra_params: dict[str, Any] | None = None,
) -> int | None:
    """Return the WFS ``numberMatched`` for *type_names* (optionally in *bbox*).

    Issues a single ``resultType=hits`` GetFeature: the server replies with
    an otherwise-empty FeatureCollection whose root element carries the
    total match count as a ``numberMatched`` attribute. One cheap round
    trip lets a caller decide, *before* spending a paged walk, whether the
    result would cross the server's ``startIndex`` window (PDOK caps BAG at
    50 000) and so needs the bbox split first.

    Returns ``None`` when the count cannot be determined -- the server
    omitted the attribute, reported ``unknown``, or the body did not parse
    as XML -- so callers fall back to walk-and-react rather than trusting a
    guessed number. PDOK serves the hits response as WFS XML regardless of
    ``outputFormat``, so this parses with stdlib ElementTree and never
    assumes GeoJSON.

    Cached under ``bbox_cache_key(f"{cache_prefix}.hits", bbox)`` so a rerun
    reuses the count without a network round trip.
    """
    params: dict[str, Any] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_names,
        "srsName": srs_name,
        "resultType": "hits",
    }
    if bbox is not None:
        params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{srs_name}"
    if extra_params:
        params.update(extra_params)

    cache_key = (
        bbox_cache_key(f"{cache_prefix}.hits", bbox) if bbox is not None else f"{cache_prefix}.hits"
    )
    raw = session.get_bytes(url, params=params, cache_key=cache_key)
    return _parse_number_matched(raw)


def _parse_number_matched(raw: bytes) -> int | None:
    """Read the ``numberMatched`` attribute off a WFS hits FeatureCollection."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    value = root.get("numberMatched")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        # GeoServer may report ``numberMatched="unknown"`` when it declines
        # to count; treat that as "unknown" so the caller walks and reacts.
        return None
