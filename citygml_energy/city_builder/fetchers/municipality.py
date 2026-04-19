"""Lookup a Dutch municipality outline from PDOK ``bestuurlijkegebieden``.

We request the whole ``Gemeentegebied`` layer paginated, filter by
case-insensitive name match, and return the first matching feature as a
GeoJSON dict plus a (minx, miny, maxx, maxy) bounding box in EPSG:28992.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..http import CachedSession

MUNICIPALITY_WFS_URL = "https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0"
MUNICIPALITY_LAYER = "bestuurlijkegebieden:Gemeentegebied"
MUNICIPALITY_PAGE_SIZE = 1000


@dataclass(frozen=True)
class MunicipalityOutline:
    """A municipality boundary + attributes in EPSG:28992."""

    name: str
    cbs_code: str  # e.g. "0503" for Delft; first 4 chars of BAG identificatie
    feature: dict[str, Any]  # GeoJSON Feature
    bbox: tuple[float, float, float, float]


def fetch_municipality_outline(
    session: CachedSession, *, name: str
) -> MunicipalityOutline:
    """Return the outline of municipality *name* (case-insensitive).

    Raises :class:`ValueError` if no match is found.
    """
    target = name.strip().lower()
    start = 0
    while True:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": MUNICIPALITY_LAYER,
            "outputFormat": "application/json",
            "srsName": "EPSG:28992",
            "count": MUNICIPALITY_PAGE_SIZE,
            "startIndex": start,
        }
        safe_name = "".join(c if c.isalnum() else "_" for c in target)
        page = session.get_json(
            MUNICIPALITY_WFS_URL,
            params=params,
            cache_key=f"municipality_{safe_name}_{start}",
        )
        features = page.get("features") or []
        if not features:
            raise ValueError(
                f"Municipality {name!r} not found in PDOK bestuurlijkegebieden"
            )
        for feature in features:
            props = feature.get("properties") or {}
            feature_name = str(props.get("naam") or props.get("naam_officieel") or "").strip()
            if feature_name.lower() == target:
                return _build_outline(feature_name, feature, props)
        if len(features) < MUNICIPALITY_PAGE_SIZE:
            raise ValueError(
                f"Municipality {name!r} not found in PDOK bestuurlijkegebieden"
            )
        start += MUNICIPALITY_PAGE_SIZE


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
