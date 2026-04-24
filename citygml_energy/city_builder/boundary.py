"""Concave-boundary polygon support for the city-build pipeline.

Lets a user constrain the build to a free-form (concave) polygon stored
in either a GeoPackage or a GeoJSON file, not just the rectangular
``bbox``. The pipeline uses the polygon's bounds to drive the BAG /
3DBAG fetchers and then keeps only those buildings whose 2D footprint
actually intersects the polygon, so a concave drawn area trims cleanly.

Two formats are supported, auto-detected by file extension:

* ``.gpkg`` — GeoPackage, requires ``layer`` + ``fid`` to select one
  feature out of a multi-feature table. Read directly via ``sqlite3``
  + WKB with :func:`_strip_gpkg_header` from :mod:`.pv_panels`.
* ``.geojson`` / ``.json`` — GeoJSON ``FeatureCollection`` or
  ``Feature``. ``layer`` / ``fid`` are optional; when omitted the
  first feature with a (Multi)Polygon geometry is used. When present,
  ``fid`` matches the feature's ``id`` or ``properties.id`` / ``fid``.

The loader keeps the dependency footprint identical to the rest of the
city builder (``shapely`` only), with no ``fiona`` / ``pyogrio`` /
``geopandas`` requirement for simple GeoJSON reading.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..errors import CityBuildError
from .pv_panels import (
    _EXPECTED_SRS_ID,
    _UNDEFINED_SRS_IDS,
    _gpkg_geometry_column_and_rtree,
    _strip_gpkg_header,
)

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

__all__ = [
    "BoundarySource",
    "load_boundary_polygon",
]


_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundarySource:
    """Declarative pointer to one polygon feature in a GeoPackage or GeoJSON.

    :attr:`path`: absolute or already-resolved path to the boundary
        file. ``.gpkg`` and ``.geojson`` / ``.json`` are recognised;
        the extension decides which reader runs.
    :attr:`layer`: for ``.gpkg``, the features table name that holds
        the boundary polygon(s). Ignored (but accepted) for GeoJSON
        files, which have no layer concept.
    :attr:`fid`: for ``.gpkg``, the ``fid`` of the polygon feature to
        use; required because a single GPKG can hold multiple
        candidate areas. For GeoJSON, optional: when ``None`` the
        first (Multi)Polygon feature is used, which is the expected
        shape for a single-area file like
        [`inputs/emmer_compascuum_area.geojson`](../../inputs/emmer_compascuum_area.geojson).
    """

    path: Path
    layer: str | None = None
    fid: int | None = None


def load_boundary_polygon(source: BoundarySource) -> BaseGeometry:
    """Return the shapely (Multi)Polygon selected by *source*.

    Dispatches on the file extension: ``.gpkg`` → GeoPackage path,
    ``.geojson`` / ``.json`` → GeoJSON path. Raises
    :class:`CityBuildError` with actionable detail on malformed
    geometry, unknown layer / fid, or non-EPSG:28992 SRS. Any other
    failure bubbles up as the underlying ``sqlite3`` / ``shapely`` /
    ``json`` exception so the pipeline surfaces the real cause.
    """
    try:
        from shapely import wkb as shapely_wkb  # noqa: F401, import-guard
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "Boundary polygon support needs shapely; install with: pip install -e .[city]"
        ) from exc

    suffix = source.path.suffix.lower()
    if suffix == ".gpkg":
        return _load_from_gpkg(source)
    if suffix in (".geojson", ".json"):
        return _load_from_geojson(source)
    raise CityBuildError(
        f"boundary.path {source.path.name!r} has unsupported extension "
        f"{suffix!r}; expected .gpkg or .geojson"
    )


# ---------------------------------------------------------------------------
# GeoPackage reader
# ---------------------------------------------------------------------------


def _load_from_gpkg(source: BoundarySource) -> BaseGeometry:
    """Read one polygon feature from a GeoPackage.

    ``layer`` + ``fid`` are both required for GPKG because a single
    file routinely holds multiple candidate areas.
    """
    from shapely import wkb as shapely_wkb

    if not source.layer:
        raise CityBuildError(
            f"boundary.layer is required for .gpkg files ({source.path})"
        )
    if source.fid is None:
        raise CityBuildError(
            f"boundary.fid is required for .gpkg files ({source.path})"
        )

    try:
        con = sqlite3.connect(f"file:{source.path}?mode=ro", uri=True)
    except sqlite3.OperationalError as exc:
        raise FileNotFoundError(
            f"boundary.path could not be opened: {source.path}"
        ) from exc
    try:
        meta = con.execute(
            "SELECT data_type, srs_id FROM gpkg_contents WHERE table_name = ?",
            (source.layer,),
        ).fetchone()
        if meta is None:
            raise CityBuildError(
                f"boundary.layer {source.layer!r} is not declared in "
                f"gpkg_contents of {source.path}"
            )
        data_type, srs_id = meta
        if data_type != "features":
            raise CityBuildError(
                f"boundary.layer {source.layer!r} is not a features table "
                f"(data_type={data_type!r}) in {source.path}"
            )
        if srs_id != _EXPECTED_SRS_ID and srs_id not in _UNDEFINED_SRS_IDS:
            raise CityBuildError(
                f"boundary.layer {source.layer!r} has srs_id={srs_id}; expected "
                f"{_EXPECTED_SRS_ID} (Amersfoort / RD New) to match 3DBAG"
            )

        geom_col, _rtree = _gpkg_geometry_column_and_rtree(con, source.layer)
        row = con.execute(
            f'SELECT "{geom_col}" FROM "{source.layer}" WHERE fid = ?',
            (source.fid,),
        ).fetchone()
    finally:
        con.close()

    if row is None:
        raise CityBuildError(
            f"boundary.fid={source.fid} not found in layer "
            f"{source.layer!r} of {source.path}"
        )
    blob = row[0]
    if blob is None:
        raise CityBuildError(
            f"boundary feature fid={source.fid} in {source.path} has no geometry"
        )

    geom = shapely_wkb.loads(_strip_gpkg_header(blob))
    return _validate_polygon_geometry(
        geom, context=f"boundary fid={source.fid} in {source.path}",
    )


# ---------------------------------------------------------------------------
# GeoJSON reader
# ---------------------------------------------------------------------------


def _load_from_geojson(source: BoundarySource) -> BaseGeometry:
    """Read one (Multi)Polygon feature from a GeoJSON file.

    Accepts either a ``FeatureCollection`` (picks a feature by ``fid``
    if given, else the first polygonal feature) or a single ``Feature``
    (ignores ``fid`` as there is only one feature to read). The CRS,
    if present, is validated to be EPSG:28992 via URN / authority-code;
    an absent CRS is silently accepted because GeoJSON defaults to
    WGS84 but this project ships its own GeoJSON samples in RD New,
    and third-party EPSG:28992 exports often strip the ``crs`` block.
    """
    from shapely.geometry import shape

    try:
        with source.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"boundary.path could not be opened: {source.path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CityBuildError(
            f"boundary.path {source.path} is not valid JSON "
            f"(line {exc.lineno}, column {exc.colno}: {exc.msg})"
        ) from exc

    _validate_geojson_crs(data, source_path=source.path)

    kind = data.get("type")
    if kind == "Feature":
        feature = data
    elif kind == "FeatureCollection":
        feature = _select_feature(
            data.get("features") or [], fid=source.fid, source_path=source.path,
        )
    else:
        raise CityBuildError(
            f"boundary.path {source.path} must be a GeoJSON Feature or "
            f"FeatureCollection, got type={kind!r}"
        )

    geom_dict = feature.get("geometry")
    if not geom_dict:
        raise CityBuildError(
            f"boundary feature in {source.path} has no geometry"
        )
    geom = shape(geom_dict)
    return _validate_polygon_geometry(
        geom, context=f"boundary feature in {source.path}",
    )


def _select_feature(
    features: list[dict[str, Any]],
    *,
    fid: int | None,
    source_path: Path,
) -> dict[str, Any]:
    """Pick a GeoJSON feature by ``fid`` or fall back to the first polygon."""
    if not features:
        raise CityBuildError(
            f"boundary.path {source_path} has an empty FeatureCollection"
        )
    if fid is not None:
        for feat in features:
            if _feature_id(feat) == fid:
                return feat
        raise CityBuildError(
            f"boundary.fid={fid} not found in {source_path}; "
            f"available ids: {sorted({_feature_id(f) for f in features if _feature_id(f) is not None})!r}"
        )
    for feat in features:
        geom = feat.get("geometry") or {}
        if geom.get("type") in {"Polygon", "MultiPolygon"}:
            return feat
    raise CityBuildError(
        f"boundary.path {source_path} has no Polygon/MultiPolygon feature"
    )


def _feature_id(feature: dict[str, Any]) -> Any:
    """Return the feature's id, checked at the root then in properties."""
    if "id" in feature:
        return feature["id"]
    props = feature.get("properties") or {}
    for key in ("fid", "id"):
        if key in props:
            return props[key]
    return None


def _validate_geojson_crs(data: dict[str, Any], *, source_path: Path) -> None:
    """Reject GeoJSONs that declare a non-RD-New CRS.

    Accepts:

    * No ``crs`` block at all. This is a deliberate pragmatic
      concession: the GeoJSON RFC 7946 default is WGS84, but this
      project routinely ships EPSG:28992 GeoJSON exports from QGIS /
      geopandas that strip the legacy ``crs`` object. To guard against
      the silent-misalignment footgun (a genuine WGS84 file accepted
      as if it were RD New), a WARN log line is emitted — visible in
      the build log, without failing the run.
    * A CRS whose ``name`` contains ``EPSG::28992`` / ``EPSG:28992``
      (URN, OGC URL, authority-code, legacy GeoJSON CRS-1.0 dialect).

    Refuses everything else so a WGS84-tagged GeoJSON does not
    silently mis-align with the 3DBAG data which is all in RD New.
    """
    crs = data.get("crs")
    if crs is None:
        _LOG.warning(
            "boundary.path %s declares no CRS block; assuming EPSG:28992 "
            "(RD New). If the file is actually WGS84 it will silently "
            "mis-align with 3DBAG data.",
            source_path,
        )
        return
    name = ""
    if isinstance(crs, dict):
        properties = crs.get("properties") or {}
        name = str(properties.get("name") or "")
    if "28992" in name:
        return
    raise CityBuildError(
        f"boundary.path {source_path} declares CRS {name!r}; "
        f"expected EPSG:28992 (Amersfoort / RD New) to match 3DBAG"
    )


# ---------------------------------------------------------------------------
# Shared geometry validation
# ---------------------------------------------------------------------------


def _validate_polygon_geometry(geom: Any, *, context: str) -> Any:
    """Common post-load checks shared by both readers."""
    if geom.is_empty:
        raise CityBuildError(f"{context} is empty")
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise CityBuildError(
            f"{context} must be (Multi)Polygon, got {geom.geom_type!r}"
        )
    # ``buffer(0)`` heals self-intersecting hand-drawn rings without
    # changing the polygon's overall shape when it is already valid;
    # cheap insurance against a non-noded vertex slipping through QGIS.
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom
