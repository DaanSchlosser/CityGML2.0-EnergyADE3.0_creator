"""Load and locate CFTree tree reconstructions as :class:`ParsedTree` records.

The city-scale pipeline consumes 3DBAG + BAG + EP-online and attaches
PV panels. This module plugs a fourth geometry source on top: the
per-tile ``trees_lod3.city.json`` files produced by
`CFTree <https://github.com/NoahAlting/CFTree>`_'s reconstruction stage.

The integration deliberately mirrors the
:mod:`citygml_energy.city_builder.pv_panels` pattern:

* **Loader runs once in the main process** before per-pand work fans out.
  Tree crowns have no parent Pand by definition, so the result is not
  keyed by ``pand_id``: :func:`load_trees_in_bbox` returns a flat list
  that the pipeline appends directly to ``CityObjectMember``.
* **Path, not data.** Configs carry a
  :class:`VegetationSource` (directory + optional tree filename). The
  directory is expected to be a CFTree ``data/<case>`` output, where
  every tile lives under ``tiles/<tile_id>/trees_lod3.city.json``.
  Reading is lazy so a missing directory only errors at build time, not
  at config-validation time.
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
    "DEFAULT_TREE_FILENAME",
    "VegetationSource",
    "filter_trees_by_boundary",
    "load_trees_in_bbox",
]

_LOG = logging.getLogger(__name__)

# Filename CFTree writes under each ``tiles/<tile_id>/`` directory. Kept
# as a constant so a future CFTree that tweaks the name (e.g. adding
# version tags like ``trees_lod3.v2.city.json``) can be accommodated with
# a single config override.
DEFAULT_TREE_FILENAME: str = "trees_lod3.city.json"


@dataclass(frozen=True, slots=True)
class VegetationSource:
    """Declarative pointer to a CFTree reconstruction output directory.

    ``slots=True`` mirrors the :class:`PvPanelsSource` pattern — these
    sources are small, immutable, and shared across the city-build
    worker pool, so the per-instance dict is pure overhead.

    :attr:`path`: absolute or already-resolved path to the **case
        directory** (typically CFTree's ``data/<case>``). The loader
        walks ``path/tiles/<tile_id>/`` sub-directories and reads each
        ``trees_lod3.city.json`` it finds.
    :attr:`tree_filename`: filename to look for inside every tile dir.
        Defaults to :data:`DEFAULT_TREE_FILENAME`; overrideable for
        future CFTree versions without a code change.
    """

    path: Path
    tree_filename: str = DEFAULT_TREE_FILENAME


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_trees_in_bbox(
    source: VegetationSource,
    bbox: tuple[float, float, float, float],
) -> list[ParsedTree]:
    """Read every CFTree tile under *source* and keep trees inside *bbox*.

    The bbox is applied on the crown centroid: if the centroid falls in
    the half-open rectangle ``[xmin, xmax) × [ymin, ymax)`` the tree is
    kept, otherwise dropped. This is the same min-inclusive / max-
    exclusive convention used by the BAG and 3DBAG fetchers, so a
    building inside the bbox never loses its adjacent street tree to a
    rounding discrepancy.

    An empty / non-existent ``source.path`` returns ``[]`` with a
    warning log line: the city build should still succeed, it just
    won't carry vegetation.
    """
    case_dir = Path(source.path)
    if not case_dir.is_dir():
        _LOG.warning(
            "Vegetation source %s does not exist; skipping tree ingest",
            case_dir,
        )
        return []

    tiles_dir = case_dir / "tiles"
    if not tiles_dir.is_dir():
        _LOG.warning(
            "Vegetation source %s has no 'tiles' subdirectory; skipping tree ingest",
            case_dir,
        )
        return []

    tree_files = sorted(tiles_dir.glob(f"*/{source.tree_filename}"))
    if not tree_files:
        _LOG.warning(
            "Vegetation source %s has no tiles matching '*/%s'; skipping tree ingest",
            case_dir,
            source.tree_filename,
        )
        return []

    minx, miny, maxx, maxy = bbox
    kept: list[ParsedTree] = []
    read = 0
    for tree_file in tree_files:
        try:
            parsed = parse_cftree_tile_file(tree_file)
        except (ValueError, OSError) as exc:  # narrow: malformed JSON / unreadable
            _LOG.warning(
                "Skipping malformed CFTree tile %s: %s", tree_file, exc
            )
            continue
        read += len(parsed)
        for tree in parsed:
            cx, cy, _cz = tree.centroid
            if minx <= cx < maxx and miny <= cy < maxy:
                kept.append(tree)

    _LOG.info(
        "Vegetation: read %d trees across %d tiles, kept %d inside bbox",
        read,
        len(tree_files),
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
