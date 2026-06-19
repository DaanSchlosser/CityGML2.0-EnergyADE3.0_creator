"""PDOK Locatieserver geocoder, used for a coarse anchor only.

The address-driven extent uses this client to turn free text into an
approximate RD New (EPSG:28992) coordinate plus the authoritative
woonplaats / gemeente name. It is deliberately not used to decide which
buildings a query covers: the Locatieserver ``free`` endpoint is a fuzzy,
relevance-ranked search that reports tens of thousands of "hits" for any
query, so a returned document is trusted only after its street, house
number, and place are verified against the request. Exact
address-to-building resolution runs from authoritative BAG data instead
(see :mod:`citygml_energy.city_builder.address_extent`).

``centroide_rd`` arrives as WKT in EPSG:28992 (for example
``POINT(94092.17 464267.343)``), the same CRS the rest of the city
pipeline works in, so no reprojection is required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .._helpers import to_clean_str, to_int
from ..http import CachedSession

# PDOK Locatieserver v3_1 (the BZK-hosted endpoint that replaced the old
# Nationaal Georegister host). ``free`` is the fuzzy free-text search;
# ``fl`` selects the returned fields and ``fq`` filters by document type.
LOCATIESERVER_BASE = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"

# Fields requested from the API. Kept explicit (rather than ``*``) so the
# cache key below stays stable and the parser sees a known shape.
_FIELDS = "type,weergavenaam,centroide_rd,straatnaam,huisnummer,woonplaatsnaam,gemeentenaam"

# WKT POINT body, tolerant of leading sign and decimals on either ordinate.
_POINT_RE = re.compile(r"POINT\(\s*([-\d.]+)\s+([-\d.]+)\s*\)")


@dataclass(frozen=True, slots=True)
class GeocodeHit:
    """One Locatieserver result document, reduced to the fields we use.

    Attributes:
        type: document type, for example ``"adres"``, ``"weg"`` (a
            street), or ``"woonplaats"``.
        weergavenaam: the human-readable label PDOK assigns the hit.
        point_rd: ``(x, y)`` in EPSG:28992.
        straatnaam / huisnummer / woonplaatsnaam / gemeentenaam: address
            components, any of which may be ``None`` depending on the
            document type.
    """

    type: str
    weergavenaam: str
    point_rd: tuple[float, float]
    straatnaam: str | None
    huisnummer: int | None
    woonplaatsnaam: str | None
    gemeentenaam: str | None


def _parse_point_rd(value: object) -> tuple[float, float] | None:
    """Parse a ``POINT(x y)`` WKT string into an ``(x, y)`` tuple, or ``None``."""
    match = _POINT_RE.search(str(value or ""))
    if match is None:
        return None
    return (float(match.group(1)), float(match.group(2)))


def geocode_free(
    session: CachedSession,
    query: str,
    *,
    type_filter: str | None = "adres",
    rows: int = 10,
) -> list[GeocodeHit]:
    """Run a Locatieserver ``free`` search and return parsed hits.

    *type_filter* maps to the ``fq=type:<...>`` filter; pass ``None`` to
    search every document type. Hits without a parseable ``centroide_rd``
    are dropped. Results stay in PDOK's relevance order, so the caller is
    responsible for verifying a hit before trusting it.
    """
    params: dict[str, str] = {"q": query, "fl": _FIELDS, "rows": str(rows)}
    if type_filter:
        params["fq"] = f"type:{type_filter}"
    # ``rows`` is part of the cache identity: CachedSession keys on cache_key
    # alone, so omitting it would serve a payload written for one row count to
    # a request asking for another (first writer wins, silent truncation).
    cache_key = f"locatieserver_free_v1_{type_filter or 'any'}_r{rows}_{query.strip().lower()}"
    data = session.get_json(f"{LOCATIESERVER_BASE}/free", params=params, cache_key=cache_key)

    docs = ((data or {}).get("response") or {}).get("docs") or []
    hits: list[GeocodeHit] = []
    for doc in docs:
        point = _parse_point_rd(doc.get("centroide_rd"))
        if point is None:
            continue
        hits.append(
            GeocodeHit(
                type=str(doc.get("type") or ""),
                weergavenaam=str(doc.get("weergavenaam") or ""),
                point_rd=point,
                straatnaam=to_clean_str(doc.get("straatnaam")),
                huisnummer=to_int(doc.get("huisnummer")),
                woonplaatsnaam=to_clean_str(doc.get("woonplaatsnaam")),
                gemeentenaam=to_clean_str(doc.get("gemeentenaam")),
            )
        )
    return hits
