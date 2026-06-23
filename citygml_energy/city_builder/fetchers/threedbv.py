"""3D Basisvoorziening fetcher: semantic landcover CityJSON for the AOI.

PDOK's 3D Basisvoorziening OGC API exposes a CityJSON product
(``basisbestand_gebouwen_terreinen``) that carries the Dutch ground as
classified, draped surfaces: terrain (``LandUse``), roads, water,
vegetation, and bridges, each tagged with its BGT class. That product is
the source of the pipeline's semantic terrain.

The ``/items`` endpoint is **not** a feature stream, it is a download
index: each feature is a map-sheet polygon carrying a ``download_link`` to
a zipped CityJSON tile plus a ``startdatum`` vintage and a ``bladnr`` sheet
id. The fetch therefore has two steps:

1. :func:`discover_landcover_tiles` bbox-queries the index for the AOI and
   keeps the sheet(s) of the *latest* vintage that cover it. The newest
   tiling is a 2 km RD-coordinate grid (~37 MB zip per tile), far smaller
   than the legacy 1:5000 sheets (200-450 MB), so picking the latest vintage
   is also the cheapest download.
2. :func:`fetch_tile_cityjson` downloads + unzips one sheet to its raw
   CityJSON bytes for the parser.

Like the AHN and BGT fetchers this is opportunistic: any predictable
failure (PDOK outage, an AOI outside coverage, a non-JSON index, a non-zip
body, a corrupt archive) degrades to ``None`` after a warning so a 3DBV
outage never fails the city build. The endpoint is public, so no API key or
``.env`` entry is needed. A magic-valid but corrupt archive is evicted from
the disk cache so a poisoned entry self-heals on the next run rather than
being re-served forever.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass

from .._helpers import bbox_cache_key
from ..http import CachedSession

__all__ = [
    "THREEDBV_INFORMATION_SYSTEM_URL",
    "THREEDBV_OGC_URL",
    "LandcoverTileRef",
    "discover_landcover_tiles",
    "fetch_tile_cityjson",
    "tile_cache_key",
]

_LOG = logging.getLogger(__name__)

# Root of the Kadaster/PDOK 3D Basisvoorziening OGC API. Pinned so a URL
# change surfaces as one constant rather than spread across the codebase.
THREEDBV_OGC_URL: str = "https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1"

# Written into ``core:externalReference/informationSystem`` by the landcover
# builder so a reader can identify the source authority. The PDOK dataset
# page is a more durable "system identity" than the raw API endpoint.
THREEDBV_INFORMATION_SYSTEM_URL: str = (
    "https://www.pdok.nl/introductie/-/article/3d-basisvoorziening-1"
)

# The CityJSON product collection (buildings + terrain + roads + water).
_COLLECTION: str = "basisbestand_gebouwen_terreinen"

# OGC CRS identifier for RD New. Passed as both ``bbox-crs`` (so the AOI
# bbox is read in RD, not the WGS84 default) and ``crs``. It is a vocabulary
# identifier, not a fetched URL, so the ``http`` scheme is intentional.
_RD_CRS_URI: str = "http://www.opengis.net/def/crs/EPSG/0/28992"

# First bytes of a PKZIP archive (``PK\x03\x04``). The download host serves a
# zipped CityJSON; an error answers with HTML/JSON, so the body is sniffed
# before it is decoded.
_ZIP_MAGIC: bytes = b"PK\x03\x04"


@dataclass(frozen=True, slots=True)
class LandcoverTileRef:
    """One map-sheet entry from the 3DBV download index.

    Attributes:
        bladnr: the sheet id (legacy ``30fz1`` or the newer RD-grid
            ``90000_462000``).
        year: vintage year parsed from the feature's ``startdatum``; the
            discovery step keeps only the most recent.
        download_link: the URL of the zipped CityJSON tile.
        size_bytes: the advertised archive size, for logging the download
            weight before it happens.
    """

    bladnr: str
    year: int
    download_link: str
    size_bytes: int


def tile_cache_key(download_link: str) -> str:
    """Return the disk-cache key for a tile download, keyed by its filename.

    The archive filename embeds the vintage and sheet (e.g.
    ``volledig_2022_90000_462000.zip``), so it is a stable identity that
    survives a host or path change on the download server.
    """
    name = download_link.rsplit("/", 1)[-1] or download_link
    return f"3dbv_tile_{name}"


def discover_landcover_tiles(
    session: CachedSession,
    bbox: tuple[float, float, float, float],
) -> list[LandcoverTileRef] | None:
    """Return the latest-vintage 3DBV sheet(s) covering *bbox*, or ``None``.

    *bbox* is ``(xmin, ymin, xmax, ymax)`` in EPSG:28992 (RD New). Queries
    the download index, parses the covering sheets, and keeps only those of
    the most recent vintage (the newest tiling is both the most current and
    the smallest download). Returns ``None`` on any network / HTTP / non-JSON
    response, or when the index has no usable entry for the AOI, after
    logging a warning. The result is keyed for disk caching by bbox.
    """
    import requests as _requests

    xmin, ymin, xmax, ymax = bbox
    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "bbox-crs": _RD_CRS_URI,
        "crs": _RD_CRS_URI,
        "f": "json",
        "limit": "100",
    }
    url = f"{THREEDBV_OGC_URL}/collections/{_COLLECTION}/items"
    try:
        index = session.get_json(
            url,
            params=params,
            cache_key=bbox_cache_key("3dbv_index", bbox),
            validate=_validate_index_body,
        )
    except (_requests.RequestException, OSError, ValueError, KeyError) as exc:
        _LOG.warning(
            "3DBV index fetch failed (%s); skipping semantic terrain for this build",
            exc,
        )
        return None

    refs = _parse_index(index)
    if not refs:
        _LOG.warning("3DBV index returned no usable sheet for the AOI; skipping semantic terrain")
        return None

    latest = max(ref.year for ref in refs)
    by_link: dict[str, LandcoverTileRef] = {}
    for ref in refs:
        if ref.year == latest:
            by_link.setdefault(ref.download_link, ref)
    chosen = sorted(by_link.values(), key=lambda r: r.download_link)
    total_mb = sum(r.size_bytes for r in chosen) / 1e6
    _LOG.info(
        "3DBV: %d sheet(s) at the %d vintage cover the AOI (%.0f MB total to download)",
        len(chosen),
        latest,
        total_mb,
    )
    return chosen


def fetch_tile_cityjson(
    session: CachedSession,
    ref: LandcoverTileRef,
) -> bytes | None:
    """Download and unzip one 3DBV sheet to its raw CityJSON bytes, or ``None``.

    Downloads the zipped tile (keyed for disk caching by filename), validates
    the archive magic, and returns the bytes of the single ``*.city.json``
    member. A network / HTTP error, a non-zip body, or a corrupt archive
    degrades to ``None`` after a warning; a magic-valid but undecodable
    archive is evicted from the cache so the next run re-fetches a good one.
    """
    import requests as _requests

    cache_key = tile_cache_key(ref.download_link)
    try:
        archive = session.get_bytes(
            ref.download_link,
            cache_key=cache_key,
            validate=_validate_zip_body,
        )
    except (_requests.RequestException, OSError, ValueError, KeyError) as exc:
        _LOG.warning(
            "3DBV sheet %s download failed (%s); skipping this sheet",
            ref.bladnr,
            exc,
        )
        return None

    try:
        return _unzip_cityjson(archive)
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        # The body passed only a magic sniff before it was cached, so an
        # archive that is truncated or otherwise undecodable would be
        # re-served on every later run; evict it so the next run re-fetches.
        session.evict(cache_key)
        _LOG.warning(
            "3DBV sheet %s could not be unzipped (%s); skipping this sheet",
            ref.bladnr,
            exc,
        )
        return None


def _parse_index(index: dict[str, object]) -> list[LandcoverTileRef]:
    """Turn the GeoJSON download index into a list of :class:`LandcoverTileRef`.

    Features without a ``download_link`` or a parseable ``startdatum`` year
    are skipped rather than raising: the index is treated as best-effort
    metadata, so one malformed row never sinks the whole discovery.
    """
    features = index.get("features")
    if not isinstance(features, list):
        return []
    refs: list[LandcoverTileRef] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        if not isinstance(props, dict):
            continue
        link = props.get("download_link")
        if not isinstance(link, str) or not link:
            continue
        year = _year_of(props.get("startdatum"))
        if year is None:
            continue
        size = props.get("download_size_bytes")
        refs.append(
            LandcoverTileRef(
                bladnr=str(props.get("bladnr") or "?"),
                year=year,
                download_link=link,
                size_bytes=int(size) if isinstance(size, (int, float)) else 0,
            )
        )
    return refs


def _year_of(start: object) -> int | None:
    """Parse the leading ``YYYY`` of an ISO date string, or ``None``."""
    if not isinstance(start, str) or len(start) < 4:
        return None
    try:
        return int(start[:4])
    except ValueError:
        return None


def _unzip_cityjson(archive: bytes) -> bytes:
    """Return the bytes of the single ``*.city.json`` member of *archive*.

    Raises :class:`ValueError` when the archive holds no CityJSON member, and
    propagates :class:`zipfile.BadZipFile` for a corrupt archive; both are
    turned into a soft-fail by :func:`fetch_tile_cityjson`.
    """
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        names = zf.namelist()
        # Prefer a ``*.city.json`` member; fall back to a bare ``*.json`` only
        # when none exists. A single ``endswith((".city.json", ".json"))``
        # collapses to "ends with .json" and returns the first match, so a
        # sidecar ``metadata.json`` listed before the real tile would be handed
        # to the parser (and then crash it).
        member = next((n for n in names if n.lower().endswith(".city.json")), None) or next(
            (n for n in names if n.lower().endswith(".json")), None
        )
        if member is None:
            raise ValueError(f"3DBV archive holds no CityJSON member: {names}")
        return zf.read(member)


def _validate_index_body(body: bytes) -> None:
    """Raise when *body* is not a JSON object, keeping error pages uncached."""
    if body.lstrip()[:1] != b"{":
        snippet = body[:160].decode("utf-8", "replace").strip()
        raise ValueError(f"3DBV index returned a non-JSON body: {snippet!r}")


def _validate_zip_body(body: bytes) -> None:
    """Raise when *body* is not a PKZIP archive, keeping error pages uncached."""
    if not body.startswith(_ZIP_MAGIC):
        snippet = body[:160].decode("utf-8", "replace").strip()
        raise ValueError(f"3DBV download returned a non-zip body: {snippet!r}")
