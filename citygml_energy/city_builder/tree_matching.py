"""Generic nearest-neighbour spatial join for CFTree → register matching.

Both the BGT cross-reference (:mod:`citygml_energy.city_builder.bgt_match`)
and the Emmen BOR enrichment
(:mod:`citygml_energy.city_builder.tree_enrichment`) need exactly the
same algorithm: for each :class:`ParsedTree`, find the closest
candidate from a register within a fixed metric radius, with the
``gtid`` as the dictionary key. Lifting the loop here removes a
straight copy-paste between the two callers and gives the algorithm a
single home for any future tweak (e.g. switching to a KD-tree once
register sizes warrant it, or adding bidirectional uniqueness).

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

__all__ = ["match_nearest_within"]

_LOG = logging.getLogger(__name__)


def match_nearest_within[C](
    trees: Iterable[ParsedTree],
    candidates: Iterable[C],
    *,
    candidate_xy: Callable[[C], tuple[float, float]],
    radius_m: float,
    register_label: str = "register",
) -> dict[str, C]:
    """Return ``{gtid: candidate}`` for every tree within *radius_m* of one.

    For each :class:`ParsedTree`, the closest candidate by squared 2D
    distance wins; ties are broken deterministically by candidate input
    order (the first-seen candidate in :func:`enumerate` order). Trees
    with no candidate in range are absent from the returned dict so
    callers can ``.get(gtid)`` and fall through to ``None`` without
    branching.

    Reciprocal uniqueness is *not* enforced: two trees within radius of
    a single candidate both inherit it, which is the right encoding when
    CFTree over-reconstructs one canopy as two crowns. The match radius
    is the same for both directions because the registers (BGT, BOR)
    nominally place each point at the trunk, while CFTree's centroid can
    drift 1-3 m on a leaning or one-sided crown.

    *register_label* is used only in the coverage log line so a reader
    of the pipeline log can tell the BGT and BOR matches apart at a
    glance.
    """
    candidate_list = list(candidates)
    tree_list = list(trees)
    if not candidate_list or not tree_list:
        return {}

    radius_sq = radius_m * radius_m
    out: dict[str, C] = {}

    for tree in tree_list:
        cx, cy, _cz = tree.centroid
        best: C | None = None
        best_d2 = radius_sq
        for cand in candidate_list:
            x, y = candidate_xy(cand)
            dx = x - cx
            dy = y - cy
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best = cand
        if best is not None:
            out[tree.gtid] = best

    _LOG.info(
        "Matched %d of %d CFTree trees to a %s record (radius=%.1f m)",
        len(out), len(tree_list), register_label, radius_m,
    )
    return out
