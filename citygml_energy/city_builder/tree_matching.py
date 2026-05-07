"""Generic nearest-neighbour spatial join for CFTree → register matching.

Both the BGT cross-reference and the Emmen BOR enrichment need
exactly the same algorithm: for each :class:`ParsedTree`, find the
closest candidate from a register within a fixed metric radius, with
the ``gtid`` as the dictionary key. The pipeline calls this function
twice — once per register — passing the register's coordinate
extractor and a label string for the coverage log line.

The function uses :class:`shapely.STRtree` (O(N log M)) — shapely is a
hard requirement of the ``[city]`` extras and is also used by every
other spatial step in the pipeline (boundary filter, PV panel match,
vegetation filter), so a separate brute-force fallback would be dead
code.

The function is deliberately register-agnostic: callers pass a
``candidate_xy`` callable that extracts the ``(x, y)`` coordinates
from whatever dataclass they want to match against. Both BGT and BOR
keep their points in EPSG:28992 metres, so the squared-distance test
runs in plain RD-New units without any reprojection.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from .cityjson_trees_parse import ParsedTree

__all__ = ["MATCH_RADIUS_M", "match_nearest_within"]

_LOG = logging.getLogger(__name__)


# Default match radius for both BGT and BOR. The two registers nominally
# place each point at the trunk; CFTree reports the crown centroid,
# which on a leaning or one-sided canopy can sit 1-3 m off the trunk.
# 4 m is the compromise that catches the ~95th percentile of legitimate
# crown-to-trunk offsets without pulling in the next tree in a typical
# Dutch street row (7-10 m spacing). Tuned against the
# Emmer-Compascuum small-area run: ~90 % of CFTree trees get a BGT
# match at 4 m, with diminishing returns beyond. Both registers use
# the same value by design — they describe the same physical thing
# (a registered urban tree position) — so it lives here as a single
# named constant rather than two co-located copies.
MATCH_RADIUS_M: float = 4.0


def match_nearest_within[C](
    trees: Iterable[ParsedTree],
    candidates: Iterable[C],
    *,
    candidate_xy: Callable[[C], tuple[float, float]],
    radius_m: float,
    register_label: str = "register",
) -> dict[str, C]:
    """Return ``{gtid: candidate}`` for every tree within *radius_m* of one.

    For each :class:`ParsedTree`, the closest candidate by 2D distance
    wins; ties are broken deterministically by candidate input order
    (first-seen candidate in enumeration order). Trees with no candidate
    in range are absent from the returned dict so callers can ``.get(gtid)``
    and fall through to ``None`` without branching.

    Reciprocal uniqueness is *not* enforced: two trees within radius of
    a single candidate both inherit it, which is the right encoding when
    CFTree over-reconstructs one canopy as two crowns. The match radius
    is the same for both directions because the registers (BGT, BOR)
    nominally place each point at the trunk, while CFTree's centroid can
    drift 1–3 m on a leaning or one-sided crown.

    *register_label* is used only in the coverage log line so a reader
    of the pipeline log can tell the BGT and BOR matches apart at a
    glance.
    """
    from shapely import STRtree
    from shapely.geometry import Point

    candidate_list = list(candidates)
    tree_list = list(trees)
    if not candidate_list or not tree_list:
        return {}

    cand_points = [Point(candidate_xy(c)) for c in candidate_list]
    strtree = STRtree(cand_points)

    out: dict[str, C] = {}
    for tree in tree_list:
        cx, cy, _cz = tree.centroid
        pt = Point(cx, cy)
        hits = strtree.query(pt, predicate="dwithin", distance=radius_m)
        if len(hits) == 0:
            continue
        # Secondary sort by input index preserves the tie-breaking
        # guarantee: when two candidates are equidistant, the one
        # that appeared first in the input list wins. STRtree does
        # not guarantee hit order, so we must enforce it explicitly.
        best_idx = int(min(hits, key=lambda j: (pt.distance(cand_points[j]), j)))
        out[tree.gtid] = candidate_list[best_idx]

    _LOG.info(
        "Matched %d of %d CFTree trees to a %s record (radius=%.1f m)",
        len(out), len(tree_list), register_label, radius_m,
    )
    return out
