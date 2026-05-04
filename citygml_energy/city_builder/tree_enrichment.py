"""Nearest-neighbour join of Emmen's BOR tree register onto CFTree trees.

Produces a ``{gtid: BorTree}`` mapping that
:func:`citygml_energy.city_builder.builders.build_solitary_vegetation_object`
consumes to enrich the ``veg:SolitaryVegetationObject`` with a Latin
species name (``veg:species``) plus ``gen:*Attribute`` siblings for
fields that have no native CityGML 2.0 slot
(see ``docs/mapping_city.md`` and § 3.3 of
``docs/vegetation_integration_report.md``).

History note: this file was previously a documentation stub recording
that an OSM + Bomenstichting attribute-enrichment had been removed in
favour of "Dutch government data only". Emmen's
``bor_groen_bomen_beschermd`` register *is* Dutch government open data
(owner ``ago@emmen``, CC-BY licensing) and carries genuine per-tree
attributes, so the previously-scaffolded module is now repurposed for
exactly the use case its docstring predicted.

The actual nearest-neighbour algorithm lives in
:mod:`citygml_energy.city_builder.tree_matching`; this module is the
BOR-typed thin wrapper. Match radius is fixed at 4 m, the same as
:data:`bgt_match.MATCH_RADIUS_M` and for the same reason: BOR points
sit at the trunk while CFTree's centroid can drift 1-3 m on a
one-sided canopy.
"""

from __future__ import annotations

from collections.abc import Iterable

from .cityjson_trees_parse import ParsedTree
from .fetchers.emmen_bor import BorTree
from .tree_matching import match_nearest_within

__all__ = [
    "MATCH_RADIUS_M",
    "match_trees_to_bor",
]

# Identical to :data:`bgt_match.MATCH_RADIUS_M`. Kept as a sibling
# constant rather than re-exported so a future tweak of one register's
# radius does not silently move the other.
MATCH_RADIUS_M: float = 4.0


def match_trees_to_bor(
    trees: Iterable[ParsedTree],
    bor_trees: Iterable[BorTree],
    *,
    radius_m: float = MATCH_RADIUS_M,
) -> dict[str, BorTree]:
    """Return ``{gtid: BorTree}`` for CFTree trees matched to a BOR record."""
    return match_nearest_within(
        trees,
        bor_trees,
        candidate_xy=lambda b: (b.x_rd, b.y_rd),
        radius_m=radius_m,
        register_label="Emmen BOR",
    )
