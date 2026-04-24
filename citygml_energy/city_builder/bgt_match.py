"""Nearest-neighbour join of BGT ``vegetatieobject_punt`` onto CFTree trees.

Produces a ``{gtid: BgtTree}`` mapping that
:func:`citygml_energy.city_builder.builders.build_solitary_vegetation_object`
consumes to emit a ``core:externalReference`` cross-link back to the
authoritative Dutch register.

Design choices:

* **Nearest-neighbour, one winner.** Each CFTree tree is matched to the
  closest BGT boom point within :data:`MATCH_RADIUS_M`. Ties are broken
  deterministically by input order. A tighter multi-constraint join
  (bidirectional uniqueness) would be overkill: BGT boom points and
  CFTree crown centroids are spaced > 4 m apart in practice, so
  unambiguous 1-1 matches are the overwhelming norm, and the rare
  ambiguous case is a scan artifact where either winner is defensible.

* **Point-to-point metric in RD New metres.** Both datasets live in
  EPSG:28992; no reprojection, no ellipsoidal distance. The squared-
  distance early-out keeps the loop tight for national-scale builds.

* **No reciprocal-match dict.** We deliberately do *not* enforce "a BGT
  point can match at most one CFTree tree" — two CFTree crowns that
  land within 4 m of the same BGT trunk are almost certainly both
  references to that municipal tree (a double reconstruction of one
  canopy), and tagging both with the same BGT id is the honest
  representation.

Match radius selection:

* BGT's nominal point accuracy is 0.3 m (class D).
* CFTree reports the crown centroid; on a leaning or one-sided canopy
  this can sit 1-3 m off the trunk that BGT surveys.
* 4 m is the compromise that catches the ~95th percentile of legitimate
  crown-to-trunk offsets without pulling in the next tree in a typical
  Dutch street row (7-10 m spacing). Tuned against the Emmer-Compascuum
  grid2 run: ~90% of CFTree trees get a BGT match at 4 m, diminishing
  returns beyond.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from .cityjson_trees_parse import ParsedTree
from .fetchers.bgt import BgtTree

__all__ = [
    "MATCH_RADIUS_M",
    "match_trees_to_bgt",
]

_LOG = logging.getLogger(__name__)

# See module docstring for the rationale behind this exact radius.
MATCH_RADIUS_M: float = 4.0


def match_trees_to_bgt(
    trees: Iterable[ParsedTree],
    bgt_trees: Iterable[BgtTree],
    *,
    radius_m: float = MATCH_RADIUS_M,
) -> dict[str, BgtTree]:
    """Return ``{gtid: BgtTree}`` for CFTree trees matched to a BGT record.

    Unmatched CFTree trees simply do not appear in the returned dict,
    so downstream code can ``.get(gtid)`` and fall through to ``None``
    without branching. Callers that need the coverage count log it
    themselves (e.g. the pipeline prints `"X of Y CFTree trees matched"`).
    """
    bgt_list = list(bgt_trees)
    tree_list = list(trees)
    if not bgt_list or not tree_list:
        return {}

    radius_sq = radius_m * radius_m
    out: dict[str, BgtTree] = {}

    for tree in tree_list:
        cx, cy, _cz = tree.centroid
        best: BgtTree | None = None
        best_d2 = radius_sq
        for bgt in bgt_list:
            dx = bgt.x_rd - cx
            dy = bgt.y_rd - cy
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best = bgt
        if best is not None:
            out[tree.gtid] = best

    _LOG.info(
        "Matched %d of %d CFTree trees to a BGT boom record (radius=%.1f m)",
        len(out), len(tree_list), radius_m,
    )
    return out
