"""Lookup a Dutch municipality outline from PDOK ``bestuurlijkegebieden``.

We request the whole ``Gemeentegebied`` layer, filter by
case-insensitive name match, and return the matching feature as a
GeoJSON dict plus a (minx, miny, maxx, maxy) bounding box in EPSG:28992.
The whole layer is ~345 features nation-wide and fits one WFS page;
the paginator handles the rare case where PDOK changes that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..http import CachedSession
from ..pdok_wfs import DEFAULT_PAGE_SIZE, paginate_features

MUNICIPALITY_WFS_URL = "https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0"
MUNICIPALITY_LAYER = "bestuurlijkegebieden:Gemeentegebied"
MUNICIPALITY_PAGE_SIZE = DEFAULT_PAGE_SIZE

# Cache identity is the layer itself, not the name being searched for.
# Embedding the name in the cache key would cache the same WFS response
# separately for every name lookup (one cache file per Delft / Emmen /
# … lookup), defeating disk caching across runs that look up different
# municipalities.
_CACHE_PREFIX = "pdok_gemeentegebied"


@dataclass(frozen=True)
class MunicipalityOutline:
    """A municipality boundary + attributes in EPSG:28992."""

    name: str
    cbs_code: str  # e.g. "0503" for Delft; first 4 chars of BAG identificatie
    feature: dict[str, Any]  # GeoJSON Feature
    bbox: tuple[float, float, float, float]


def fetch_municipality_outline(session: CachedSession, *, name: str) -> MunicipalityOutline:
    """Return the outline of municipality *name* (case-insensitive).

    Raises :class:`ValueError` if no match is found.
    """
    target = name.strip().lower()
    features = paginate_features(
        session,
        MUNICIPALITY_WFS_URL,
        type_names=MUNICIPALITY_LAYER,
        cache_prefix=_CACHE_PREFIX,
        page_size=MUNICIPALITY_PAGE_SIZE,
    )
    for feature in features:
        props = feature.get("properties") or {}
        naam = str(props.get("naam") or "").strip()
        naam_officieel = str(props.get("naam_officieel") or "").strip()
        # Both spellings are acceptable lookups: a user typing the
        # official name ("'s-Gravenhage") must match a feature whose
        # common name differs ("Den Haag"), not just fall back to the
        # official field when the common one is absent.
        candidates = {n.lower() for n in (naam, naam_officieel) if n}
        if target in candidates:
            return _build_outline(naam or naam_officieel, feature, props)
    raise ValueError(f"Municipality {name!r} not found in PDOK bestuurlijkegebieden")


def _build_outline(
    name: str, feature: dict[str, Any], props: dict[str, Any]
) -> MunicipalityOutline:
    cbs_code = _normalise_cbs_code(props.get("code"))
    bbox = _feature_bbox(feature)
    return MunicipalityOutline(name=name, cbs_code=cbs_code, feature=feature, bbox=bbox)


def _normalise_cbs_code(value: Any) -> str:
    """BAG identificaties embed the 4-digit CBS municipality code at the start."""
    raw = str(value or "").strip()
    # PDOK returns codes like "GM0503" or "0503" depending on vintage. Keep the digits.
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 4:
        return digits[-4:]
    return digits


def _feature_bbox(feature: dict[str, Any]) -> tuple[float, float, float, float]:
    """Axis-aligned bbox in the feature's native CRS (EPSG:28992 from this WFS)."""
    geometry = feature.get("geometry") or {}
    coords = _flatten_coords(geometry.get("coordinates"))
    if not coords:
        raise ValueError(f"Municipality feature has no geometry: {feature.get('id')!r}")
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return (min(xs), min(ys), max(xs), max(ys))


def _flatten_coords(node: Any) -> list[tuple[float, float]]:
    """Recursively flatten GeoJSON coordinate arrays into ``[(x, y), ...]``."""
    out: list[tuple[float, float]] = []
    if isinstance(node, (list, tuple)):
        if node and isinstance(node[0], (int, float)):
            out.append((float(node[0]), float(node[1])))
        else:
            for child in node:
                out.extend(_flatten_coords(child))
    return out
