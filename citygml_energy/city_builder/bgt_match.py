"""Nearest-neighbour join of BGT ``vegetatieobject_punt`` onto CFTree trees.

Produces a ``{gtid: BgtTree}`` mapping that
:func:`citygml_energy.city_builder.builders.build_solitary_vegetation_object`
consumes to emit a ``core:externalReference`` cross-link back to the
authoritative Dutch register.

The actual nearest-neighbour algorithm lives in
:mod:`citygml_energy.city_builder.tree_matching`; this module is the
BGT-typed thin wrapper. Match radius selection:

* BGT's nominal point accuracy is 0.3 m (class D).
* CFTree reports the crown centroid; on a leaning or one-sided canopy
  this can sit 1-3 m off the trunk that BGT surveys.
* 4 m is the compromise that catches the ~95th percentile of legitimate
  crown-to-trunk offsets without pulling in the next tree in a typical
  Dutch street row (7-10 m spacing). Tuned against the Emmer-Compascuum
  small-area run: ~90% of CFTree trees get a BGT match at 4 m, diminishing
  returns beyond.
"""

from __future__ import annotations

from collections.abc import Iterable

from .cityjson_trees_parse import ParsedTree
from .fetchers.bgt import BgtTree
from .tree_matching import match_nearest_within

__all__ = [
    "MATCH_RADIUS_M",
    "match_trees_to_bgt",
]

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
    without branching.
    """
    return match_nearest_within(
        trees,
        bgt_trees,
        candidate_xy=lambda b: (b.x_rd, b.y_rd),
        radius_m=radius_m,
        register_label="BGT boom",
    )
