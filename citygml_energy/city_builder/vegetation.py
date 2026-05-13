"""City-build vegetation step: load + clip + cross-reference + attach.

This module owns the tree story end-to-end, mirroring the shape of
:mod:`citygml_energy.city_builder.postcode6` rather than scattering
the steps across ``pipeline.py``. The user story is:

1. Load CFTree reconstructions from a merged CityJSON 2.0 file.
2. Clip to the build bbox and optional boundary polygon.
3. Cross-reference against authoritative tree registers (BGT
   ``vegetatieobject_punt`` and Gemeente Emmen's BOR layer) in
   parallel.
4. Materialise one ``veg:SolitaryVegetationObject`` per tree, carrying
   any matched register enrichments, and attach the lot to the city
   model.

Two public entry points implement that:

* :func:`fetch_and_match_trees` — produces a :class:`TreeBundle`
  (trees + register matches). I/O happens here.
* :func:`attach_trees_to_model` — materialises and attaches xsdata
  features, returning the appearance-target ids the pipeline feeds to
  :func:`citygml_energy.city_builder.appearance.append_vegetation_appearance`.

The lower-level pure-Python helpers (:func:`load_trees_in_bbox`,
:func:`filter_trees_by_boundary`) stay public for direct unit testing
and for callers that want to skip the register cross-references.

The xsdata construction step is one level down at
:func:`citygml_energy.city_builder.builders.build_solitary_vegetation_object`,
so this module imports xsdata only via that builder; it never touches
the bindings directly.

Why one module, not two: the postcode6 step demonstrates that owning
"fetch + filter + build + attach" behind one seam reads better than
threading per-helper kwargs through the orchestrator. The CFTree path
followed the same shape as the BGT/BOR matchers, just split across
``pipeline.py`` and several helpers; consolidation here matches the
postcode6 precedent and shrinks the pipeline orchestrator from a
recipe + sub-recipes to a recipe of seam calls.
"""

from __future__ import annotations

import concurrent.futures
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._step import Coord3D
from .cityjson_trees_parse import ParsedTree, parse_cftree_tile_file
from .config import BuildContext
from .fetchers.bgt import BgtTree, fetch_bgt_trees
from .fetchers.emmen_bor import BorTree, fetch_bor_trees
from .http import CachedSession
from .tree_matching import MATCH_RADIUS_M, match_nearest_within

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

__all__ = [
    "EMPTY_BUNDLE",
    "TreeBundle",
    "VegetationSource",
    "attach_trees_to_model",
    "fetch_and_match_trees",
    "filter_trees_by_boundary",
    "load_trees_in_bbox",
]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VegetationSource:
    """Declarative pointer to a merged CFTree CityJSON file.

    ``slots=True`` mirrors the :class:`PvPanelsSource` pattern: these
    sources are small, immutable, and shared across the city-build
    worker pool, so the per-instance dict is pure overhead.

    :attr:`path`: absolute or already-resolved path to a CityJSON 2.0
        file produced by :mod:`tools.merge_cftree_tiles`, holding every
        ``SolitaryVegetationObject`` for the AOI with globally-unique
        ``T_<n>`` ids.
    """

    path: Path


@dataclass(frozen=True, slots=True)
class TreeBundle:
    """CFTree trees plus their authoritative-register cross-references.

    Produced by :func:`fetch_and_match_trees` and consumed by
    :func:`attach_trees_to_model`. Carrying both register dicts
    alongside the trees keeps the cross-reference lookup local to the
    attach step (one ``dict.get`` per tree) and makes ``TreeBundle``
    the single picklable handle the city builder threads through its
    assembly pass.

    The two register dicts are keyed by :attr:`ParsedTree.gtid`. Empty
    dicts are valid and indicate either "no matches inside the bbox"
    or "register fetch was skipped"; the build proceeds with plain
    CFTree geometry in both cases.
    """

    trees: tuple[ParsedTree, ...]
    bgt_matches: Mapping[str, BgtTree]
    bor_matches: Mapping[str, BorTree]

    @property
    def is_empty(self) -> bool:
        """True when the bundle holds no trees (no work for the attach step)."""
        return not self.trees


EMPTY_BUNDLE: TreeBundle = TreeBundle(trees=(), bgt_matches={}, bor_matches={})
"""Sentinel returned by :func:`fetch_and_match_trees` when there is no
vegetation source configured or the bbox / boundary leaves zero trees.

Lets the pipeline call :func:`attach_trees_to_model` unconditionally
without an outer ``if bundle is None`` branch."""


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
        _LOG.warning("Skipping malformed CFTree file %s: %s", file_path, exc)
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
    :func:`pipeline.filter_buildings_by_boundary` instead uses
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


# ---------------------------------------------------------------------------
# Story-level entry points
# ---------------------------------------------------------------------------


def fetch_and_match_trees(
    session: CachedSession,
    *,
    source: VegetationSource | None,
    bbox: tuple[float, float, float, float],
    boundary_geom: BaseGeometry | None,
) -> TreeBundle:
    """Load CFTree, clip to extent, and cross-reference BGT + Emmen BOR concurrently.

    A null *source* short-circuits to :data:`EMPTY_BUNDLE`. The CFTree
    load runs first (file I/O, no network) so the BGT/BOR fetches are
    skipped entirely when the bbox or boundary leaves zero trees.

    BGT and BOR fetches run on a 2-thread pool: they are independent
    network calls keyed on the same bbox, so concurrency converts two
    serial waits into one. Soft-fail semantics match the underlying
    fetchers: a PDOK or Emmen-portal outage degrades to an empty
    register dict (and, by extension, plain CFTree geometry) rather
    than failing the build.
    """
    if source is None:
        return EMPTY_BUNDLE

    _LOG.info("Loading CFTree vegetation: %s", source.path)
    trees = load_trees_in_bbox(source, bbox)
    if trees and boundary_geom is not None:
        before = len(trees)
        trees = filter_trees_by_boundary(trees, boundary_geom)
        _LOG.info("Boundary polygon kept %d / %d trees", len(trees), before)

    if not trees:
        return EMPTY_BUNDLE

    bgt_matches, bor_matches = _match_to_registers(session, trees, bbox)
    return TreeBundle(
        trees=tuple(trees),
        bgt_matches=bgt_matches,
        bor_matches=bor_matches,
    )


def attach_trees_to_model(
    model: Any,
    bundle: TreeBundle,
    build_context: BuildContext = BuildContext(),
    *,
    coords_sink: list[Coord3D],
) -> list[str]:
    """Emit one ``veg:SolitaryVegetationObject`` per tree in *bundle*.

    Returns the list of ``#<gml:id>`` references the caller passes to
    :func:`citygml_energy.city_builder.appearance.append_vegetation_appearance`,
    mirroring how the per-Pand build path returns a per-Building
    surface-id list to the energy-label appearance.

    Tree crown vertices also widen the city envelope via
    *coords_sink*: skipping them would leave a SolitaryVegetationObject
    extending past the building footprint to clip at the final
    ``gml:boundedBy`` and render with a dotted line above the camera
    in some viewers.

    A no-op (returns ``[]``) on an empty bundle so the caller does not
    need an outer ``if bundle.is_empty`` branch.
    """
    # Imported lazily to keep the module importable from ``config.py``
    # without dragging the xsdata bindings into config-validation
    # contexts that don't need them (e.g. ``load_city_config`` on a CI
    # job that only checks JSON shape).
    from .builders import build_solitary_vegetation_object

    if bundle.is_empty:
        return []

    appearance_targets: list[str] = []
    for tree in bundle.trees:
        obj = build_solitary_vegetation_object(
            tree,
            build_context,
            bgt_match=bundle.bgt_matches.get(tree.gtid),
            bor_match=bundle.bor_matches.get(tree.gtid),
        )
        model.add(obj)
        if obj.lod3_geometry is not None and obj.lod3_geometry.multi_surface is not None:
            ms = obj.lod3_geometry.multi_surface
            if ms.id:
                appearance_targets.append(f"#{ms.id}")
            appearance_targets.extend(
                f"#{member.polygon.id}"
                for member in ms.surface_member
                if member.polygon is not None and member.polygon.id
            )
        for polygon in tree.polygons:
            coords_sink.extend(polygon.exterior)
            for hole in polygon.interiors:
                coords_sink.extend(hole)
    return appearance_targets


# ---------------------------------------------------------------------------
# Register cross-reference internals
# ---------------------------------------------------------------------------


def _match_to_registers(
    session: CachedSession,
    trees: list[ParsedTree],
    bbox: tuple[float, float, float, float],
) -> tuple[dict[str, BgtTree], dict[str, BorTree]]:
    """Fetch BGT and Emmen BOR concurrently and nearest-join onto *trees*.

    The two fetches are independent network calls keyed on the same
    bbox; running them on a 2-thread pool collapses two serial waits
    into one. ``ThreadPoolExecutor.__exit__`` joins the workers before
    we resolve the futures, so each ``.result()`` call either returns
    immediately or re-raises the worker's exception.
    """
    _LOG.info("Fetching BGT and BOR tree register concurrently …")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fut_bgt = pool.submit(_match_to_bgt, session, trees, bbox)
        fut_bor = pool.submit(_match_to_bor, session, trees, bbox)
    return fut_bgt.result(), fut_bor.result()


def _match_to_bgt(
    session: CachedSession,
    trees: list[ParsedTree],
    bbox: tuple[float, float, float, float],
) -> dict[str, BgtTree]:
    """Fetch BGT ``vegetatieobject_punt`` and nearest-join onto *trees*.

    Soft-fails on any HTTP / parse error inside :func:`fetch_bgt_trees`,
    which logs a warning and returns ``[]``: the cross-reference is an
    authoritative-register link, not a hard dependency, so a PDOK
    outage degrades to plain geometry rather than failing the build.

    The match is logged with ``matched / total`` so users can judge
    coverage: low ratios (e.g. < 50%) suggest either that the AOI is
    private garden land (unregistered in BGT) or that CFTree is
    over-reconstructing non-tree vegetation.
    """
    _LOG.info("Fetching BGT vegetatieobject_punt (boom) …")
    bgt_trees = fetch_bgt_trees(session, bbox)
    matches = match_nearest_within(
        trees,
        bgt_trees,
        candidate_xy=lambda b: (b.x_rd, b.y_rd),
        radius_m=MATCH_RADIUS_M,
        register_label="BGT boom",
    )
    _LOG.info(
        "BGT cross-reference: %d of %d CFTree trees matched a BGT boom record "
        "(%d BGT features in bbox)",
        len(matches),
        len(trees),
        len(bgt_trees),
    )
    return matches


def _match_to_bor(
    session: CachedSession,
    trees: list[ParsedTree],
    bbox: tuple[float, float, float, float],
) -> dict[str, BorTree]:
    """Fetch Gemeente Emmen's BOR tree register and nearest-join onto *trees*.

    Behaves identically to :func:`_match_to_bgt`: soft-failed fetch on
    network or parse errors. Outside Emmen the bbox-restricted query
    returns zero features (silently logged), which is the desired
    no-op behaviour for the city pipeline's PoC scope.
    """
    _LOG.info("Fetching Gemeente Emmen BOR tree register …")
    bor_trees = fetch_bor_trees(session, bbox)
    matches = match_nearest_within(
        trees,
        bor_trees,
        candidate_xy=lambda b: (b.x_rd, b.y_rd),
        radius_m=MATCH_RADIUS_M,
        register_label="Emmen BOR",
    )
    _LOG.info(
        "BOR enrichment: %d of %d CFTree trees matched a BOR record (%d BOR features in bbox)",
        len(matches),
        len(trees),
        len(bor_trees),
    )
    return matches
