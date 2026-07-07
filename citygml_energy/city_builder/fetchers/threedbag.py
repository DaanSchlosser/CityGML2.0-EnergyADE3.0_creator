"""Fetch 3DBAG LoD 0/1/2 tiles as CityJSON.

Procedure:

1. Query the tile index via HTTP range requests on the FlatGeoBuf file
   ``tile_index.fgb`` using ``flatgeobuf.HTTPReader`` with the municipality
   bounding box, so only the relevant spatial slice of the index is transferred.
2. Refine to tiles whose geometry actually intersects the municipality polygon
   (not just the bbox) to avoid downloading corner tiles.
3. For each matching tile, GET its ``cj_download`` URL. The server
   serves the file gzipped; we sniff the magic number and decompress when
   needed.

The ``flatgeobuf`` package (included in the ``[city]`` extras) handles the
HTTP range request protocol for the FlatGeoBuf index file efficiently.
"""

from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import json
import logging
import os
import pickle
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ..cityjson_parse import ParsedBuilding, parse_buildings
from ..http import CachedSession, loads_json

_LOG = logging.getLogger(__name__)
# Cap concurrency to avoid flooding data.3dbag.nl and to keep CPU use sane
# on shared machines. Real speedup plateaus around 4–8 on broadband; higher
# counts just add contention. Overridable via ``CITYGML_ENERGY_3DBAG_WORKERS``,
# parsed leniently at fetch time by :func:`_tile_fetch_worker_cap`.
_TILE_FETCH_DEFAULT_WORKERS = 6

# Bump when the parsed-tile output shape changes in a way that older cache
# entries would silently propagate. The content digest of the upstream ZIP
# does not invalidate on parser-only code changes, so this stamp is the
# parser's contribution to the cache key. Pre-stamp .pkl files (no segment
# in the filename) are treated as a different key and naturally re-parse.
#   v2 — 2026-05-27: ring dedup tightened from mm to µm precision
#                    (citygml_energy.city_builder.cityjson_parse._ring_from_indices)
#   v3 — 2026-05-27: sliver-area threshold raised from 1e-4 to 1e-3 m^2
#                    (citygml_energy.city_builder.cityjson_parse.MIN_FACE_AREA_M2);
#                    v2 caches still contain residual slivers in
#                    [1e-4, 1e-3) m^2 and need a re-parse to drop them.
_PARSED_TILE_SCHEMA_VERSION = "v3"

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

# 3DBAG tile index: FlatGeoBuf with HTTP range request support.
TILE_INDEX_FGB_URL = "https://data.3dbag.nl/latest/tile_index.fgb"


@dataclass(frozen=True)
class Tile:
    """Metadata for a single 3DBAG CityJSON tile."""

    tile_id: str
    download_url: str
    bbox: tuple[float, float, float, float]  # EPSG:28992, from tile geometry


def _tile_fetch_worker_cap() -> int:
    """Return the tile-fetch concurrency cap, honouring the env override.

    Same contract as :func:`citygml_energy.city_builder.pand_executor.
    assembly_worker_count`: a malformed ``CITYGML_ENERGY_3DBAG_WORKERS``
    never breaks a run. A non-integer value falls back to the default
    with a warning; ``0`` and negative values mean "sequential" and
    clamp to ``1`` (the previous ``int(...)`` at module import crashed
    the import on garbage and ``ThreadPoolExecutor`` on ``0``).
    """
    raw = os.environ.get("CITYGML_ENERGY_3DBAG_WORKERS", "").strip()
    if not raw:
        return _TILE_FETCH_DEFAULT_WORKERS
    try:
        requested = int(raw)
    except ValueError:
        _LOG.warning(
            "CITYGML_ENERGY_3DBAG_WORKERS=%r is not an integer; using the default of %d",
            raw,
            _TILE_FETCH_DEFAULT_WORKERS,
        )
        return _TILE_FETCH_DEFAULT_WORKERS
    return max(1, requested)


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
    bounds_key = "_".join(str(round(v)) for v in bounds)
    index_cache = session.cache_dir / f"3dbag_tile_index.{bounds_key}.json"
    if session.use_cache and index_cache.exists():
        cached = _try_load_tile_index(index_cache)
        if cached is not None:
            return cached

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
        _try_save_tile_index(index_cache, tiles)
    return tiles


def _try_load_tile_index(cache_path: Path) -> list[Tile] | None:
    """Load the tile-index JSON cache, returning ``None`` on any failure.

    Same contract as :func:`_try_load_parsed_tile`: a truncated write or
    a hand-mangled file re-queries the index instead of failing the next
    run on an unhandled ``JSONDecodeError``.
    """
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return [
            Tile(
                tile_id=str(d["tile_id"]),
                download_url=str(d["download_url"]),
                bbox=tuple(d["bbox"]),
            )
            for d in data
        ]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _LOG.warning(
            "3DBAG tile-index cache %s unreadable (%s); re-querying the index",
            cache_path.name,
            exc,
        )
        return None


def _try_save_tile_index(cache_path: Path, tiles: list[Tile]) -> None:
    """Persist the tile index atomically. Best-effort: OSError is logged and swallowed.

    pid-suffixed temp + ``Path.replace`` mirrors the body-cache write in
    :mod:`citygml_energy.city_builder.http`: two builds sharing a cache
    dir each write their own temp file, and the rename is atomic, so a
    reader never sees a half-written index.
    """
    payload = json.dumps(
        [
            {"tile_id": t.tile_id, "download_url": t.download_url, "bbox": list(t.bbox)}
            for t in tiles
        ]
    )
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(cache_path)
    except OSError as exc:
        _LOG.warning(
            "3DBAG tile-index cache write to %s failed (%s); continuing without cache",
            cache_path.name,
            exc,
        )


def fetch_tile_cityjson(session: CachedSession, tile: Tile) -> dict[str, Any]:
    """Download one 3DBAG tile and return the parsed CityJSON dict."""
    raw = _fetch_tile_bytes(session, tile)
    _raw, tile_data = _decode_tile(session, tile, raw)
    return tile_data


def _tile_cache_key(tile: Tile) -> str:
    """Cache key for a tile body; slashes in the id break filenames."""
    return f"3dbag_{tile.tile_id.replace('/', '_')}"


def _fetch_tile_bytes(session: CachedSession, tile: Tile) -> bytes:
    """GET one tile body through the cache, keeping error pages off disk."""
    return session.get_bytes(
        tile.download_url,
        cache_key=_tile_cache_key(tile),
        validate=_validate_tile_body,
    )


def _validate_tile_body(body: bytes) -> None:
    """Raise when *body* is neither gzip nor JSON, keeping error pages uncached.

    3DBAG serves tiles as gzipped CityJSON (magic ``1f 8b``) or plain
    JSON; an HTML maintenance page is neither and must never be memoised,
    or every later run would crash on the same cached garbage.
    """
    if body[:2] == b"\x1f\x8b":
        return
    if body.lstrip()[:1] == b"{":
        return
    snippet = body[:160].decode("utf-8", "replace").strip()
    raise ValueError(f"3DBAG tile returned neither gzip nor JSON: {snippet!r}")


def _decode_tile(session: CachedSession, tile: Tile, raw: bytes) -> tuple[bytes, dict[str, Any]]:
    """Decode *raw* to CityJSON, self-healing an undecodable cache entry.

    Returns ``(body, parsed)`` where *body* is the bytes that decoded
    (usually *raw*, or the refetched replacement). The pre-cache sniff in
    :func:`_validate_tile_body` only checks the magic bytes, so a cached
    body can still turn out truncated or otherwise undecodable; that
    entry is evicted and refetched once instead of being re-served on
    every later run. A second failure propagates.
    """
    # :func:`loads_json` uses orjson when available, else stdlib json.
    try:
        return raw, cast("dict[str, Any]", loads_json(_decompress_if_gzipped(raw)))
    except (ValueError, EOFError, OSError, zlib.error) as exc:
        cache_key = _tile_cache_key(tile)
        session.evict(cache_key)
        _LOG.warning(
            "3DBAG tile %s body is undecodable (%s); evicting the cache entry and refetching",
            tile.tile_id,
            exc,
        )
        raw = _fetch_tile_bytes(session, tile)
        return raw, cast("dict[str, Any]", loads_json(_decompress_if_gzipped(raw)))


def fetch_buildings_for_outline(
    session: CachedSession,
    *,
    outline: BaseGeometry,
) -> list[ParsedBuilding]:
    """End-to-end convenience: tile index → download → parse.

    Returns every :class:`ParsedBuilding` within the intersecting tiles.
    The caller is responsible for filtering further by ``pand_id`` set
    (derived from the BAG Pand fetch); a few buildings beyond the
    municipality boundary may appear in edge tiles and are discarded at
    that step.

    Tiles are fetched + parsed concurrently via a thread pool; both
    gzip and orjson release the GIL, so threads are the right primitive
    here. Parsed output is additionally cached to disk per tile so a
    warm run skips re-decompressing + re-parsing. Cache entries are
    keyed on the tile's raw-ZIP content hash and invalidate
    automatically when the upstream tile changes.
    """
    tiles = fetch_tile_index(session, outline)
    if not tiles:
        return []

    buildings: list[ParsedBuilding] = []
    workers = min(_tile_fetch_worker_cap(), max(1, len(tiles)))
    if workers == 1:
        for tile in tiles:
            buildings.extend(_tile_parsed_buildings(session, tile))
        return buildings

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="3dbag-tile"
    ) as pool:
        # ``map`` preserves tile order, so the resulting ``buildings`` list
        # is deterministic across runs, which is important for stable gml:id
        # ordering in downstream CityModel output.
        for per_tile in pool.map(lambda t: _tile_parsed_buildings(session, t), tiles):
            buildings.extend(per_tile)
    return buildings


def _tile_parsed_buildings(session: CachedSession, tile: Tile) -> list[ParsedBuilding]:
    """Return parsed buildings for one tile, hitting the parsed-tile cache first.

    The on-disk cache is keyed by the tile's raw-ZIP content hash so any
    upstream change (new 3DBAG vintage, a republished tile) invalidates
    the parsed-tile pickle automatically. A corrupt pickle falls through
    to re-parse without failing the run, and an undecodable cached body
    self-heals via :func:`_decode_tile` (which may refetch, so the pickle
    is keyed on the bytes that actually decoded).
    """
    raw = _fetch_tile_bytes(session, tile)
    if session.use_cache:
        cached = _try_load_parsed_tile(_parsed_tile_cache_path(session, tile, raw))
        if cached is not None:
            return cached

    raw, tile_data = _decode_tile(session, tile, raw)
    parsed = parse_buildings(tile_data)

    if session.use_cache:
        _try_save_parsed_tile(_parsed_tile_cache_path(session, tile, raw), parsed)
    return parsed


def _parsed_tile_cache_path(session: CachedSession, tile: Tile, raw: bytes) -> Path:
    """On-disk pickle path for a tile's parsed output, keyed by content."""
    safe_id = tile.tile_id.replace("/", "_")
    content_digest = hashlib.sha256(raw).hexdigest()[:24]
    return (
        session.cache_dir
        / f"3dbag_parsed_{safe_id}.{content_digest}.{_PARSED_TILE_SCHEMA_VERSION}.pkl"
    )


def _try_load_parsed_tile(cache_path: Path) -> list[ParsedBuilding] | None:
    """Load a parsed-tile pickle, returning ``None`` on any failure."""
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("rb") as handle:
            return pickle.load(handle)
    except (pickle.UnpicklingError, EOFError, ValueError, OSError, AttributeError) as exc:
        _LOG.warning(
            "3DBAG parsed-tile cache %s unreadable (%s); re-parsing",
            cache_path.name,
            exc,
        )
        return None


def _try_save_parsed_tile(cache_path: Path, parsed: list[ParsedBuilding]) -> None:
    """Persist parsed tile to disk. Best-effort: OSError is logged and swallowed."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            pickle.dump(parsed, handle, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(cache_path)
    except OSError as exc:
        _LOG.warning(
            "3DBAG parsed-tile cache write to %s failed (%s); continuing without cache",
            cache_path.name,
            exc,
        )


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

    Returns ``None`` on *recoverable* decode failures (malformed WKB or a
    GeoJSON object shapely cannot interpret), because the caller just
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
