"""Load and locate CFTree tree reconstructions as :class:`ParsedTree` records.

The city-scale pipeline consumes 3DBAG + BAG + EP-online and attaches
PV panels. This module plugs a fourth geometry source on top: a merged
CityJSON 2.0 file of tree reconstructions originally produced by
`CFTree <https://github.com/NoahAlting/CFTree>`_'s reconstruction stage.

The integration deliberately mirrors the
:mod:`citygml_energy.city_builder.pv_panels` pattern:

* **Loader runs once in the main process** before per-pand work fans out.
  Tree crowns have no parent Pand by definition, so the result is not
  keyed by ``pand_id``: :func:`load_trees_in_bbox` returns a flat list
  that the pipeline appends directly to ``CityObjectMember``.
* **Path, not data.** Configs carry a :class:`VegetationSource` (a
  single ``.city.json`` file). Pre-merging happens upstream via
  :mod:`tools.merge_cftree_tiles`, so the runtime never has to walk
  per-tile directories or resolve cross-tile duplicates.
* **Clipping is 2D, any-overlap.** Each tree's crown centroid is
  checked against the build bbox / optional boundary polygon; misses
  are dropped silently. Partial-overlap crowns are kept on the "inside"
  side by their centroid, exactly mirroring the building-boundary
  heuristic in :func:`pipeline._filter_by_boundary`.

The module is pure-Python, schema-agnostic, and has no xsdata imports.
The xsdata construction step lives in
:func:`citygml_energy.city_builder.builders.build_solitary_vegetation_object`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .cityjson_trees_parse import ParsedTree, parse_cftree_tile_file

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

__all__ = [
    "VegetationSource",
    "filter_trees_by_boundary",
    "load_trees_in_bbox",
]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VegetationSource:
    """Declarative pointer to a merged CFTree CityJSON file.

    ``slots=True`` mirrors the :class:`PvPanelsSource` pattern — these
    sources are small, immutable, and shared across the city-build
    worker pool, so the per-instance dict is pure overhead.

    :attr:`path`: absolute or already-resolved path to a CityJSON 2.0
        file produced by :mod:`tools.merge_cftree_tiles`, holding every
        ``SolitaryVegetationObject`` for the AOI with globally-unique
        ``T_<n>`` ids.
    """

    path: Path


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_trees_in_bbox(
    source: VegetationSource,
    bbox: tuple[float, float, float, float],
) -> list[ParsedTree]:
    """Read the merged CFTree CityJSON at *source* and keep trees inside *bbox*.

    The bbox is applied on the crown centroid: if the centroid falls in
    the half-open rectangle ``[xmin, xmax) × [ymin, ymax)`` the tree is
    kept, otherwise dropped. This is the same min-inclusive / max-
    exclusive convention used by the BAG and 3DBAG fetchers, so a
    building inside the bbox never loses its adjacent street tree to a
    rounding discrepancy.

    A missing or unreadable file returns ``[]`` with a warning log line:
    the city build should still succeed, it just won't carry vegetation.
    """
    file_path = Path(source.path)
    if not file_path.is_file():
        _LOG.warning(
            "Vegetation source %s does not exist; skipping tree ingest",
            file_path,
        )
        return []

    try:
        parsed = parse_cftree_tile_file(file_path)
    except (ValueError, OSError) as exc:  # narrow: malformed JSON / unreadable
        _LOG.warning(
            "Skipping malformed CFTree file %s: %s", file_path, exc
        )
        return []

    minx, miny, maxx, maxy = bbox
    kept = [
        tree
        for tree in parsed
        if minx <= tree.centroid[0] < maxx and miny <= tree.centroid[1] < maxy
    ]

    _LOG.info(
        "Vegetation: read %d trees from %s, kept %d inside bbox",
        len(parsed),
        file_path.name,
        len(kept),
    )
    return kept


def filter_trees_by_boundary(
    trees: Iterable[ParsedTree],
    boundary_geom: BaseGeometry,
) -> list[ParsedTree]:
    """Keep only trees whose crown centroid lies inside *boundary_geom*.

    Uses a **centroid-in-polygon** test, not a 2D-footprint-intersects
    test: a CFTree tree's crown "centroid" is a point, and every tree
    in the source CFTree case area already fits inside a single
    coherent AOI, so the footprint test would add cost without
    changing the result. The building filter in
    :func:`pipeline._filter_by_boundary` instead uses
    footprint-intersects because a multi-polygon building can straddle
    a concave boundary edge in a way a tree cannot.

    ``shapely.prepare`` attaches a cached PiP acceleration structure to
    the boundary in-place so the per-tree ``contains`` call runs in
    O(log n) against the boundary's segment tree rather than O(n).
    """
    try:
        from shapely import prepare
        from shapely.geometry import Point as ShapelyPoint
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "Boundary filtering needs shapely; install with: pip install -e .[city]"
        ) from exc

    prepare(boundary_geom)
    return [
        tree
        for tree in trees
        if boundary_geom.contains(ShapelyPoint(tree.centroid[0], tree.centroid[1]))
    ]
