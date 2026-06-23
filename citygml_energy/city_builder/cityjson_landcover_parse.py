"""CityJSON parser for 3D Basisvoorziening semantic landcover objects.

The 3DBV tile is a single CityJSON document holding the whole 2 km sheet:
buildings, terrain (``LandUse``), roads, water, vegetation, bridges, and the
odd ``OtherConstruction``. This module turns one tile into a flat list of
:class:`ParsedLandcover` records clipped to the build AOI:

* Buildings are dropped (the 3DBAG path already supplies them, in more
  detail and with energy attribution); every other CityObject type is kept.
* Each kept object's draped LoD 1.2 ``MultiSurface`` is decoded to
  :class:`citygml_energy._step.GeometryPolygon`\\ s through the shared
  :func:`citygml_energy.city_builder.cityjson_parse.iter_object_polygons`.
* The full BGT classification (``bgt_type`` / ``bgt_functie`` /
  ``bgt_fysiekvoorkomen`` / ``3df_class`` …) rides along in
  :attr:`ParsedLandcover.attributes` for the builder to map.

Like :mod:`cityjson_parse` this is a **pure parser**: standard-library
types only, no xsdata bindings, no shapely, so it is trivial to unit-test
against a small CityJSON fixture. The AOI clip is a cheap bbox-overlap test
(the 3DBV objects are BGT-segmented and small, so keeping a whole object
that overlaps the AOI gives at most a one-segment overhang, the same
"backdrop may overhang the boundary slightly" tolerance the rest of the
pipeline uses).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .._step import GeometryPolygon
from .cityjson_parse import CityJSONTile, iter_object_polygons
from .landcover_class import LandcoverDisposition, classify_landcover

_LOG = logging.getLogger(__name__)

__all__ = ["ParsedLandcover", "parse_landcover"]


@dataclass(frozen=True, slots=True)
class ParsedLandcover:
    """One kept 3DBV object: its type, attributes, polygons, and disposition.

    Attributes:
        object_id: the CityObject key (a ULID, e.g.
            ``01HP4RP361KNWTSACS9Z4Z1ANS``), reused as the stable source id
            for the emitted feature's ``gml:id`` and external reference.
        object_type: the raw 3DBV CityObject ``type`` (``LandUse``, ``Road``,
            ``WaterBody``, ``PlantCover``, ``Bridge``, ``OtherConstruction``,
            …), kept for provenance. What the object *becomes* is settled once
            in :attr:`disposition`, not re-derived from this.
        attributes: the raw CityObject attribute dict (BGT classification
            plus provenance), passed through untouched.
        polygons: the LoD 1.2 surfaces as ``GeometryPolygon``\\ s in RD + NAP.
        disposition: the resolved :class:`LandcoverDisposition`, decided once by
            :func:`classify_landcover` when the object was kept. It names the
            target CityGML feature and carries the cleaned classification
            labels, so the builder never reads the raw 3DBV tags a second time.

    A ``ParsedLandcover`` only exists for kept (non-building) objects, so
    :attr:`disposition` is always present. ``slots=True`` keeps the per-object
    footprint small: a 2 km tile carries tens of thousands of these before the
    AOI clip prunes them.
    """

    object_id: str
    object_type: str
    attributes: dict[str, Any]
    polygons: list[GeometryPolygon]
    disposition: LandcoverDisposition


def parse_landcover(
    tile_data: dict[str, Any],
    *,
    aoi_bbox: tuple[float, float, float, float],
) -> list[ParsedLandcover]:
    """Return the AOI-overlapping landcover objects from one 3DBV CityJSON tile.

    *tile_data* is the parsed CityJSON document; *aoi_bbox* is
    ``(xmin, ymin, xmax, ymax)`` in the tile's CRS (RD New / EPSG:28992).
    :func:`classify_landcover` decides each object's disposition: buildings
    (by CityObject type or by ``3df_class``) drop out, and every other object
    whose footprint overlaps *aoi_bbox* is kept carrying its resolved
    disposition. Objects with no resolvable LoD 1 geometry (an attribute-only
    or curve-only record) are dropped silently.
    """
    tile = CityJSONTile.from_dict(tile_data)

    kept: list[ParsedLandcover] = []
    skipped_empty = 0
    for object_id, obj in tile.city_objects.items():
        object_type = obj.get("type")
        attributes = dict(obj.get("attributes") or {})
        disposition = classify_landcover(object_type, attributes)
        if disposition is None:
            # A building; the 3DBAG path already supplies it, in more detail.
            continue
        polygons = iter_object_polygons(obj, tile.vertices, lod="1")
        if not polygons:
            skipped_empty += 1
            continue
        if not _overlaps_aoi(polygons, aoi_bbox):
            continue
        kept.append(
            ParsedLandcover(
                object_id=str(object_id),
                object_type=str(object_type),
                attributes=attributes,
                polygons=polygons,
                disposition=disposition,
            )
        )

    _LOG.debug(
        "3DBV tile: kept %d landcover object(s) overlapping the AOI "
        "(%d non-building object(s) had no LoD1 surface)",
        len(kept),
        skipped_empty,
    )
    return kept


def _overlaps_aoi(
    polygons: list[GeometryPolygon],
    aoi_bbox: tuple[float, float, float, float],
) -> bool:
    """Return whether any polygon's 2-D bounding box overlaps *aoi_bbox*.

    A bbox-overlap test rather than an exact polygon intersection: it needs
    no shapely (keeping this module a pure parser) and the 3DBV objects are
    BGT-segmented, so the worst case is a small object whose bbox grazes the
    AOI corner without truly intersecting. Keeping such an object is the same
    harmless overhang the relief/tree paths already tolerate, and the envelope
    still closes around it correctly.
    """
    axmin, aymin, axmax, aymax = aoi_bbox
    for polygon in polygons:
        ring = polygon.exterior
        if not ring:
            continue
        xs = [pt[0] for pt in ring]
        ys = [pt[1] for pt in ring]
        if max(xs) >= axmin and min(xs) <= axmax and max(ys) >= aymin and min(ys) <= aymax:
            return True
    return False
