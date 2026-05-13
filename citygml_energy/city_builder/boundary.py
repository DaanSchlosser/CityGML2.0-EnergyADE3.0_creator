"""Concave-boundary polygon support for the city-build pipeline.

Lets a user constrain the build to a free-form (concave) polygon stored
in a GeoJSON file, not just the rectangular ``bbox``. The pipeline uses
the polygon's bounds to drive the BAG / 3DBAG fetchers and then keeps
only those buildings whose 2D footprint actually intersects the polygon,
so a concave drawn area trims cleanly.

Accepted format: ``.geojson`` / ``.json`` — a GeoJSON ``Feature`` (or a
``FeatureCollection`` containing exactly one Feature, the QGIS default
on "Export selected features as GeoJSON") with a ``Polygon`` or
``MultiPolygon`` geometry in EPSG:28992. Multi-feature collections are
rejected: the build extent is a single, deliberately authored polygon.

The loader keeps the dependency footprint identical to the rest of the
city builder (``shapely`` only), with no ``fiona`` / ``pyogrio`` /
``geopandas`` requirement.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..errors import CityBuildError

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

__all__ = [
    "BoundarySource",
    "load_boundary_polygon",
]


_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundarySource:
    """Declarative pointer to a single-polygon GeoJSON boundary file.

    :attr:`path`: absolute or already-resolved path to the ``.geojson``
        / ``.json`` file. The file must be a GeoJSON ``Feature`` (or a
        ``FeatureCollection`` carrying exactly one Feature, the QGIS
        default export shape) with a ``Polygon`` or ``MultiPolygon``
        geometry in EPSG:28992.
    """

    path: Path


def load_boundary_polygon(source: BoundarySource) -> BaseGeometry:
    """Return the shapely (Multi)Polygon from *source*.

    Only ``.geojson`` / ``.json`` files are accepted; the root must be
    a single GeoJSON ``Feature`` or a ``FeatureCollection`` carrying
    exactly one Feature (the QGIS default export shape — see
    :func:`_load_from_geojson` for the unwrap rationale). Raises
    :class:`CityBuildError` with actionable detail on malformed
    geometry, non-EPSG:28992 SRS, or a multi-feature collection.
    """
    try:
        from shapely import wkb as shapely_wkb  # noqa: F401, import-guard
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "Boundary polygon support needs shapely; install with: pip install -e .[city]"
        ) from exc

    suffix = source.path.suffix.lower()
    if suffix in (".geojson", ".json"):
        return _load_from_geojson(source)
    raise CityBuildError(
        f"boundary.path {source.path.name!r} has unsupported extension "
        f"{suffix!r}; expected .geojson"
    )


# ---------------------------------------------------------------------------
# GeoJSON reader
# ---------------------------------------------------------------------------


def _load_from_geojson(source: BoundarySource) -> BaseGeometry:
    """Read a single (Multi)Polygon Feature from a GeoJSON file.

    The file root must be a GeoJSON ``Feature`` or a
    ``FeatureCollection`` carrying exactly one ``Feature``. The latter
    is unwrapped to its sole member: QGIS' "Export selected features as
    GeoJSON" emits a ``FeatureCollection`` even for a single polygon, so
    rejecting it forces every author to hand-edit the file. The
    single-feature wrapper carries no information beyond what the inner
    Feature already does, so the unwrap is loss-free.

    A ``FeatureCollection`` with zero or two-plus members is still
    rejected: the build extent is a single, deliberately authored
    polygon, and silently picking the first member of a multi-feature
    collection would mask an authoring slip.

    The CRS, if present, is validated to be EPSG:28992 via URN /
    authority-code; an absent CRS is silently accepted because GeoJSON
    defaults to WGS84 but this project ships its own GeoJSON samples in
    RD New, and third-party EPSG:28992 exports often strip the ``crs``
    block.
    """
    from shapely.geometry import shape

    try:
        with source.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"boundary.path could not be opened: {source.path}") from exc
    except json.JSONDecodeError as exc:
        raise CityBuildError(
            f"boundary.path {source.path} is not valid JSON "
            f"(line {exc.lineno}, column {exc.colno}: {exc.msg})"
        ) from exc

    _validate_geojson_crs(data, source_path=source.path)

    feature = _extract_single_feature(data, source_path=source.path)

    geom_dict = feature.get("geometry")
    if not geom_dict:
        raise CityBuildError(f"boundary feature in {source.path} has no geometry")
    geom = shape(geom_dict)
    return _validate_polygon_geometry(
        geom,
        context=f"boundary feature in {source.path}",
    )


def _extract_single_feature(
    data: dict[str, Any],
    *,
    source_path: Path,
) -> dict[str, Any]:
    """Return the single GeoJSON ``Feature`` carried by *data*.

    Accepts:

    * ``{"type": "Feature", ...}`` — returned as-is.
    * ``{"type": "FeatureCollection", "features": [<one>]}`` —
      unwrapped to the sole member. The collection wrapper carries no
      authoring intent beyond what the inner Feature already does, and
      it is what QGIS' default GeoJSON export emits even for a single
      polygon.

    Anything else (a 0- or 2+-feature collection, a bare Geometry, an
    unknown ``type``) raises :class:`CityBuildError` with a message
    that names exactly what was wrong so an author can fix the file
    without guessing.
    """
    kind = data.get("type")
    if kind == "Feature":
        return data
    if kind == "FeatureCollection":
        features = data.get("features")
        if not isinstance(features, list):
            raise CityBuildError(
                f"boundary.path {source_path} is a FeatureCollection with no 'features' array"
            )
        if len(features) == 0:
            raise CityBuildError(
                f"boundary.path {source_path} is an empty FeatureCollection; "
                f"expected exactly one Feature"
            )
        if len(features) > 1:
            raise CityBuildError(
                f"boundary.path {source_path} is a FeatureCollection with "
                f"{len(features)} features; expected exactly one (the build "
                f"extent is a single, deliberately authored polygon)"
            )
        feature = features[0]
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise CityBuildError(
                f"boundary.path {source_path} has a FeatureCollection whose "
                f"sole member is not a GeoJSON Feature"
            )
        _LOG.debug(
            "Unwrapped single-feature FeatureCollection in %s (QGIS default export shape).",
            source_path,
        )
        return feature
    raise CityBuildError(
        f"boundary.path {source_path} must be a GeoJSON Feature or a "
        f"single-feature FeatureCollection, got type={kind!r}"
    )


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
# Geometry validation
# ---------------------------------------------------------------------------


def _validate_polygon_geometry(geom: Any, *, context: str) -> Any:
    """Post-load sanity checks for the loaded shapely geometry.

    Rejects empties and non-(Multi)Polygon types; heals
    self-intersecting hand-drawn rings with ``buffer(0)`` so a
    near-valid polygon does not blow up the downstream intersection
    test. *context* prefixes error messages so the author can find the
    offending file quickly.
    """
    if geom.is_empty:
        raise CityBuildError(f"{context} is empty")
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise CityBuildError(f"{context} must be (Multi)Polygon, got {geom.geom_type!r}")
    # ``buffer(0)`` heals self-intersecting hand-drawn rings without
    # changing the polygon's overall shape when it is already valid;
    # cheap insurance against a non-noded vertex slipping through QGIS.
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom
