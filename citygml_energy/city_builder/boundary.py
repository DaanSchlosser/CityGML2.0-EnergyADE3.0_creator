"""Concave-boundary polygon support for the city-build pipeline.

Lets a user constrain the build to a free-form (concave) polygon stored
in a GeoJSON file, not just the rectangular ``bbox``. The pipeline uses
the polygon's bounds to drive the BAG / 3DBAG fetchers and then keeps
only those buildings whose 2D footprint actually intersects the polygon,
so a concave drawn area trims cleanly.

Accepted format: ``.geojson`` / ``.json`` — a single GeoJSON ``Feature``
with a ``Polygon`` or ``MultiPolygon`` geometry in EPSG:28992.

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
        / ``.json`` file. The file must be a GeoJSON ``Feature`` (not a
        ``FeatureCollection``) with a ``Polygon`` or ``MultiPolygon``
        geometry in EPSG:28992.
    """

    path: Path


def load_boundary_polygon(source: BoundarySource) -> BaseGeometry:
    """Return the shapely (Multi)Polygon from *source*.

    Only ``.geojson`` / ``.json`` files containing a single GeoJSON
    ``Feature`` are accepted. Raises :class:`CityBuildError` with
    actionable detail on malformed geometry or non-EPSG:28992 SRS.
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

    The file must be a GeoJSON ``Feature`` (not a ``FeatureCollection``).
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
    if kind != "Feature":
        # FeatureCollection (even with one member) is rejected explicitly
        # rather than silently unwrapped: the build extent should be a
        # single, deliberately authored polygon, and a FeatureCollection
        # is the wrong on-disk shape regardless of cardinality.
        raise CityBuildError(
            f"boundary.path {source.path} must be a single GeoJSON Feature "
            f"with a Polygon or MultiPolygon geometry, got type={kind!r}"
        )

    geom_dict = data.get("geometry")
    if not geom_dict:
        raise CityBuildError(
            f"boundary feature in {source.path} has no geometry"
        )
    geom = shape(geom_dict)
    return _validate_polygon_geometry(
        geom, context=f"boundary feature in {source.path}",
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
