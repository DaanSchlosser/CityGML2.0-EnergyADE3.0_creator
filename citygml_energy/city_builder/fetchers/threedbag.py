"""Fetch 3DBAG LoD 0/1/2 tiles as CityJSON.

Procedure:

1. Query the tile index via HTTP range requests on the FlatGeoBuf file
   ``tile_index.fgb`` using ``flatgeobuf.HTTPReader`` with the municipality
   bounding box — only the relevant spatial slice of the index is transferred.
2. Refine to tiles whose geometry actually intersects the municipality polygon
   (not just the bbox) to avoid downloading corner tiles.
3. For each matching tile, GET its ``cj_download`` URL. The server
   serves the file gzipped; we sniff the magic number and decompress when
   needed.

The ``flatgeobuf`` package (included in the ``[city]`` extras) handles the
HTTP range request protocol for the FlatGeoBuf index file efficiently.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from ..cityjson_parse import ParsedBuilding, parse_buildings
from ..http import CachedSession

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

# 3DBAG tile index — FlatGeoBuf with HTTP range request support.
TILE_INDEX_FGB_URL = "https://data.3dbag.nl/latest/tile_index.fgb"


@dataclass(frozen=True)
class Tile:
    """Metadata for a single 3DBAG CityJSON tile."""

    tile_id: str
    download_url: str
    bbox: tuple[float, float, float, float]  # EPSG:28992, from tile geometry


def fetch_tile_index(session: CachedSession, outline: BaseGeometry) -> list[Tile]:
    """Return every tile from the 3DBAG index that intersects *outline*.

    Uses ``flatgeobuf.HTTPReader`` with the outline bounding box so only the
    relevant part of the index is transferred via HTTP range requests.
    Polygon-level filtering against *outline* removes tiles that only share
    a bbox corner.

    The resulting tile list is cached as JSON in the session cache dir keyed
    by the outline bounding box (rounded to metres). Delete
    ``<cache_dir>/3dbag_tile_index.*.json`` to force a re-query of the index.
    """
    bounds = outline.bounds  # (minx, miny, maxx, maxy) in EPSG:28992
    bounds_key = "_".join(str(int(round(v))) for v in bounds)
    index_cache = session.cache_dir / f"3dbag_tile_index.{bounds_key}.json"
    if session.use_cache and index_cache.exists():
        data = json.loads(index_cache.read_text(encoding="utf-8"))
        return [Tile(tile_id=d["tile_id"], download_url=d["download_url"], bbox=tuple(d["bbox"])) for d in data]  # type: ignore[arg-type]

    try:
        import flatgeobuf as fgb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "3DBAG tile fetching needs flatgeobuf; install with: pip install -e .[city]"
        ) from exc

    tiles: list[Tile] = []
    for feature in fgb.HTTPReader(TILE_INDEX_FGB_URL, bbox=bounds):
        props = feature.properties or {}
        tile_id = str(props.get("tile_id") or "").strip()
        download_url = str(props.get("cj_download") or "").strip()
        if not tile_id or not download_url:
            continue

        # Polygon-level filter: skip tiles whose geometry only touches the bbox
        # corner without actually overlapping the municipality polygon.
        tile_geom = _fgb_geometry_to_shapely(feature.geometry)
        if tile_geom is not None and not outline.intersects(tile_geom):
            continue

        bbox = tile_geom.bounds if tile_geom is not None else bounds
        tiles.append(Tile(tile_id=tile_id, download_url=download_url, bbox=bbox))

    if session.use_cache:
        index_cache.write_text(
            json.dumps([{"tile_id": t.tile_id, "download_url": t.download_url, "bbox": list(t.bbox)} for t in tiles]),
            encoding="utf-8",
        )
    return tiles


def fetch_tile_cityjson(session: CachedSession, tile: Tile) -> dict[str, Any]:
    """Download one 3DBAG tile and return the parsed CityJSON dict."""
    raw = session.get_bytes(
        tile.download_url,
        cache_key=f"3dbag_{tile.tile_id.replace('/', '_')}",
    )
    text = _decompress_if_gzipped(raw).decode("utf-8")
    return cast("dict[str, Any]", json.loads(text))


def fetch_buildings_for_outline(
    session: CachedSession,
    *,
    outline: BaseGeometry,
) -> list[ParsedBuilding]:
    """End-to-end convenience: tile index → download → parse.

    Returns every :class:`ParsedBuilding` within the intersecting tiles.
    The caller is responsible for filtering further by ``pand_id`` set
    (derived from the BAG Pand fetch) — a few buildings beyond the
    municipality boundary may appear in edge tiles and are discarded at
    that step.
    """
    tiles = fetch_tile_index(session, outline)
    buildings: list[ParsedBuilding] = []
    for tile in tiles:
        tile_data = fetch_tile_cityjson(session, tile)
        buildings.extend(parse_buildings(tile_data))
    return buildings


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _decompress_if_gzipped(raw: bytes) -> bytes:
    """Transparently decompress gzipped payloads.

    3DBAG serves tiles as ``.city.json.gz``; sniff the magic number so
    either plain JSON or a raw gz body produces valid CityJSON bytes.
    """
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw


def _fgb_geometry_to_shapely(geometry: Any) -> BaseGeometry | None:
    """Convert a flatgeobuf geometry (WKB bytes or GeoJSON dict) to Shapely.

    Returns ``None`` on *recoverable* decode failures — malformed WKB or a
    GeoJSON object shapely cannot interpret — because the caller just
    skips the tile. ``ImportError`` propagates so missing optional deps
    fail loudly instead of silently empty-matching every tile.
    """
    if geometry is None:
        return None
    from shapely import wkb
    from shapely.errors import ShapelyError
    from shapely.geometry import shape as shapely_shape

    try:
        if isinstance(geometry, (bytes, bytearray)):
            return wkb.loads(bytes(geometry))
        if isinstance(geometry, dict):
            return shapely_shape(geometry)
    except (ShapelyError, ValueError, TypeError):
        return None
    return None
