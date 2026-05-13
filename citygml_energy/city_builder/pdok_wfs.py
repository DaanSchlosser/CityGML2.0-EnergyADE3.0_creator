"""PDOK WFS 2.0 paginated GetFeature.

Three PDOK fetchers (BAG, CBS Postcode6, municipality bestuurlijkegebieden)
share the same request shape: WFS 2.0 GetFeature with ``startIndex + count``,
GeoJSON output, EPSG:28992 SRS, optional bbox filter. This module is the
single seam for that request shape. The fetchers stay responsible for the
post-fetch transform (their schema-specific deduplication and field
extraction); the paginator owns the wire protocol.

Bbox subdivision is BAG-only and lives at the BAG call site as a thin
recursion on top of :func:`paginate_features`. CBS deliberately does not
subdivide (~30 k features max per municipality, well below the 50 k
startIndex cap that PDOK enforces on BAG). The municipality layer fits
one page (~345 features nation-wide) so there is no bbox at all.

Other PDOK protocols are NOT in scope: the BGT endpoint uses OGC API
Features and Emmen-BOR uses ArcGIS REST, with different request
vocabularies. Folding them in here would dilute "WFS 2.0 GetFeature"
into "any paged HTTP GET" and lose the per-protocol structure
(``typeNames``, ``srsName``, ``outputFormat``) that this module captures.
"""

from __future__ import annotations

from typing import Any

from ._helpers import bbox_cache_key
from .http import CachedSession

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_SRS_NAME",
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

    *extra_params* is folded into the WFS query after the standard
    keys so a caller can add CQL filters or vendor extensions without
    touching this module. The standard keys (``service``, ``version``,
    ``typeNames``, …) are not overrideable from here.
    """
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
