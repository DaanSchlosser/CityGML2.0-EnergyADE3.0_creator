"""Concave-boundary polygon support for the city-build pipeline.

Lets a user constrain the build to a free-form (concave) polygon drawn
in a GeoPackage, not just the rectangular ``bbox``. The pipeline uses
the polygon's bounds to drive the BAG / 3DBAG fetchers and then keeps
only those buildings whose 2D footprint actually intersects the
polygon, so a concave drawn area trims cleanly.

Reads the polygon directly with ``sqlite3`` + the GPKG binary header
stripped by :func:`_strip_gpkg_header` from :mod:`.pv_panels`: the
dependency footprint stays the same (``shapely`` only), and there is
no need for ``fiona``/``pyogrio``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

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


@dataclass(frozen=True)
class BoundarySource:
    """Declarative pointer to one polygon feature in a GeoPackage.

    :attr:`path`: absolute or already-resolved path to the ``.gpkg``.
    :attr:`layer`: the features table name that holds the boundary
        polygon(s).
    :attr:`fid`: the GeoPackage ``fid`` of the polygon feature to use.
        Required so a single GPKG can carry multiple candidate areas
        (e.g. the user's ``grid2.gpkg`` with two hand-drawn shapes)
        without ambiguity.
    """

    path: Path
    layer: str
    fid: int


def load_boundary_polygon(source: BoundarySource) -> BaseGeometry:
    """Return the shapely (Multi)Polygon selected by ``source.fid``.

    Raises :class:`ValueError` with actionable detail when the layer is
    missing, the fid is absent, the feature has no geometry, or the
    layer's SRS id is neither EPSG:28992 (RD New, matching 3DBAG) nor
    ``0 / -1`` (undefined). Any other failure bubbles up as the
    underlying ``sqlite3`` / ``shapely`` exception so the pipeline
    surfaces the real cause.
    """
    try:
        from shapely import wkb as shapely_wkb
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "Boundary polygon support needs shapely; install with: pip install -e .[city]"
        ) from exc

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
            raise ValueError(
                f"boundary.layer {source.layer!r} is not declared in "
                f"gpkg_contents of {source.path}"
            )
        data_type, srs_id = meta
        if data_type != "features":
            raise ValueError(
                f"boundary.layer {source.layer!r} is not a features table "
                f"(data_type={data_type!r}) in {source.path}"
            )
        if srs_id != _EXPECTED_SRS_ID and srs_id not in _UNDEFINED_SRS_IDS:
            raise ValueError(
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
        raise ValueError(
            f"boundary.fid={source.fid} not found in layer "
            f"{source.layer!r} of {source.path}"
        )
    blob = row[0]
    if blob is None:
        raise ValueError(
            f"boundary feature fid={source.fid} in {source.path} has no geometry"
        )

    geom = shapely_wkb.loads(_strip_gpkg_header(blob))
    if geom.is_empty:
        raise ValueError(
            f"boundary feature fid={source.fid} in {source.path} is empty"
        )
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(
            f"boundary feature fid={source.fid} must be (Multi)Polygon, "
            f"got {geom.geom_type!r}"
        )
    # ``buffer(0)`` heals self-intersecting hand-drawn rings without
    # changing the polygon's overall shape when it is already valid;
    # cheap insurance against a non-noded vertex slipping through QGIS.
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom
