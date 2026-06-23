"""Semantic terrain step: 3D Basisvoorziening landcover behind one seam.

This module owns the whole terrain concern the way
:mod:`citygml_energy.city_builder.vegetation` owns trees and
:mod:`citygml_energy.city_builder.postcode6` owns postcode areas. The
terrain is *semantic*: instead of a bare-earth relief it emits the Dutch
ground as classified, draped surfaces from the 3D Basisvoorziening (terrain
to ``luse:LandUse``, roads to ``tran:Road``, water to ``wtr:WaterBody``,
vegetation to ``veg:PlantCover``, bridges to ``brid:Bridge``, anything else
to ``gen:GenericCityObject``):

1. :func:`fetch_landcover` discovers the latest-vintage 3DBV sheet(s)
   covering the AOI, downloads + unzips each, parses the CityJSON, and clips
   it to the AOI (see :mod:`citygml_energy.city_builder.fetchers.threedbv`
   and :mod:`citygml_energy.city_builder.cityjson_landcover_parse`).
2. :func:`attach_landcover_to_model` builds each feature and adds it as a
   ``core:cityObjectMember``, widening the city envelope by each object's
   bounding box only.

**No optional extra.** The 3DBV product is CityJSON, parsed with the
standard library, so unlike the previous AHN raster path the terrain step
needs no numpy / GeoTIFF stack. **No environment keys.** The PDOK endpoints
are public, so nothing is read from ``.env``; the ``terrain`` config block is
a knob-less opt-in (its presence enables semantic terrain).

Like the other enrichment steps the whole concern soft-fails: a PDOK outage,
an AOI outside coverage, or a corrupt tile degrades to a terrainless build
with a warning rather than failing the run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any

from .box_clip import clip_landcover_polygons
from .cityjson_landcover_parse import ParsedLandcover, parse_landcover
from .config import BuildContext
from .fetchers.threedbv import discover_landcover_tiles, fetch_tile_cityjson, tile_cache_key
from .http import CachedSession, loads_json

__all__ = [
    "TerrainSource",
    "attach_landcover_to_model",
    "fetch_landcover",
]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TerrainSource:
    """Validated ``terrain`` config block: a knob-less opt-in marker.

    The 3D Basisvoorziening terrain carries every ground class at a fixed LoD
    from a single national product, so there is nothing to tune: a present
    ``terrain`` block means "fetch the semantic terrain", an absent one means
    "skip it". The class is kept (rather than a bare bool) so the config layer
    can import a stable type and a future, genuinely optional knob (a vintage
    pin, a class filter) is an additive field rather than a shape change.
    """


def fetch_landcover(
    session: CachedSession,
    *,
    source: TerrainSource | None,
    bbox: tuple[float, float, float, float],
    clip_to_box: bool = True,
) -> list[ParsedLandcover] | None:
    """Fetch + parse + clip 3DBV landcover for *bbox*, or ``None`` when unavailable.

    A null *source* short-circuits to ``None`` (terrain not requested). The
    latest-vintage sheet(s) covering the AOI are downloaded one at a time,
    parsed, and (when *clip_to_box*) clipped to *bbox*; processing a sheet
    before fetching the next keeps peak memory to a single ~170 MB CityJSON
    document rather than all sheets at once.

    *clip_to_box* mirrors the building clip so the two layers share one rule: a
    rectangular viewport (the address extract, an explicit bbox) hard-clips each
    surface to the AOI box, while a whole-gemeente build keeps each overlapping
    object whole (see
    :attr:`citygml_energy.city_builder.extent.BuildExtent.clip_to_box`).

    A PDOK outage, an AOI outside coverage, or a corrupt / unparseable tile
    degrades to ``None`` (or skips the offending sheet) after a warning, so the
    city build continues without semantic terrain. A magic-valid archive whose
    member is not a usable CityJSON document is evicted from the disk cache so a
    poisoned entry self-heals on the next run rather than re-failing from cache.
    """
    if source is None:
        return None

    refs = discover_landcover_tiles(session, bbox)
    if refs is None:
        # discover_landcover_tiles already logged the reason.
        return None

    objects: list[ParsedLandcover] = []
    for ref in refs:
        raw = fetch_tile_cityjson(session, ref)
        if raw is None:
            continue
        try:
            tile_data = loads_json(raw)
            parsed_objects = parse_landcover(tile_data, aoi_bbox=bbox)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            # The body passed only the zip-magic sniff before it was cached, so
            # a sidecar member, a truncated tile, or a future non-CityJSON
            # format reaches the parser. parse_landcover -> CityJSONTile.from_dict
            # raises on a non-CityJSON document or a malformed vertex; this is
            # the one place that escaped the soft-fail and crashed the whole
            # build. Skip the offending sheet and evict the cached archive so a
            # poisoned entry self-heals on the next run instead of re-failing.
            session.evict(tile_cache_key(ref.download_link))
            _LOG.warning(
                "3DBV sheet %s held an unusable CityJSON document (%s); skipping this sheet",
                ref.bladnr,
                exc,
            )
            continue
        for parsed in parsed_objects:
            if clip_to_box:
                # Hard-clip each surface to the AOI box so a road or terrain
                # polygon that merely overlaps the corner is cut at the boundary
                # instead of trailing past it. A surface that clips away to
                # nothing is dropped.
                clipped = clip_landcover_polygons(parsed.polygons, bbox)
                if clipped:
                    objects.append(replace(parsed, polygons=clipped))
            else:
                # Whole-area build: keep each overlapping object whole, so the
                # ground matches the (whole) buildings rather than being cut to
                # a rectangle they are not.
                objects.append(parsed)
        # Drop the big decoded document before fetching the next sheet.
        del tile_data, raw

    _LOG.info("Terrain: parsed %d 3DBV landcover object(s) inside the AOI", len(objects))
    return objects


def attach_landcover_to_model(
    model: Any,
    build_context: BuildContext = BuildContext(),
    *,
    objects: list[ParsedLandcover] | None,
    coords_sink: list[tuple[float, float, float]],
) -> int:
    """Emit one CityGML feature per landcover object; return how many were added.

    A no-op (returns ``0``) when *objects* is ``None`` or empty. Like the
    relief it replaced, each object contributes only its bounding-box corners
    (at the min and max z of its surfaces) to *coords_sink*, so the envelope
    grows to cover the terrain without the coordinate sink swelling by every
    surface vertex.
    """
    if not objects:
        return 0

    # Imported lazily so this module stays importable from ``config.py``
    # (which imports TerrainSource) without dragging the xsdata bindings into
    # JSON-shape validation contexts.
    from .builders import build_landcover_object

    count = 0
    for parsed in objects:
        feature = build_landcover_object(parsed, build_context)
        model.add(feature)
        _extend_sink_with_extent(coords_sink, parsed.polygons)
        count += 1

    _LOG.info("Terrain: attached %d semantic landcover feature(s)", count)
    return count


def _extend_sink_with_extent(
    coords_sink: list[tuple[float, float, float]],
    polygons: list[Any],
) -> None:
    """Push one object's bounding-box corners (min/max xyz) into *coords_sink*."""
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for polygon in polygons:
        for pt in polygon.exterior:
            xs.append(pt[0])
            ys.append(pt[1])
            zs.append(pt[2])
    if not xs:
        return
    coords_sink.append((min(xs), min(ys), min(zs)))
    coords_sink.append((max(xs), max(ys), max(zs)))
