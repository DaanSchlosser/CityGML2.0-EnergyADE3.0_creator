"""Building appearance painters: the seam that chooses how buildings are coloured.

The orchestrator used to branch inline between two ways of painting the
Buildings: by averaged EP-Online label, or singling out the Panden a
query targeted against a white context. This module turns that choice
into a :class:`BuildingPainter` with two adapters, so the assembly step
calls ``painter.paint(model, build_results)`` once and never inspects the
mode.

Both painters consume the per-Pand :class:`PandArtifacts` the executor
already produced (``pand_id``, ``building``, ``resolved``, ``targets``),
so nothing new crosses the worker-pool boundary, and both delegate to the
low-level ``append_*`` builders in :mod:`.appearance`, so the emitted GML
is byte-identical to the inline version. Two adapters make this a real
seam; a third painter (paint by build year, by construction type, a
uniform colour) is one more class selected the same way. The
solar-collector and vegetation appearances are always-on and orthogonal,
so they stay in the assembly step and are not painters here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .appearance import (
    SURROUNDINGS_DIFFUSE_COLOR,
    TARGET_BUILDING_DIFFUSE_COLOR,
    append_building_highlight_appearance,
    append_energy_label_appearance,
)

if TYPE_CHECKING:
    from .pand_executor import PandArtifacts

__all__ = [
    "BuildingPainter",
    "EnergyLabelPainter",
    "HighlightPainter",
]

_LOG = logging.getLogger(__name__)


class BuildingPainter(Protocol):
    """Appends one building-theme ``app:Appearance`` to an assembled model.

    Pure, in-process, post-assembly: an implementation reads only the
    per-Pand *build_results* and mutates *model* by appending to
    ``model.xsd.appearance_member``. It does no I/O and is a no-op when
    it has no surfaces to paint.
    """

    def paint(self, model: Any, build_results: list[PandArtifacts]) -> None: ...


@dataclass(frozen=True, slots=True)
class EnergyLabelPainter:
    """Paint every Building by its averaged EP-Online label (the default)."""

    def paint(self, model: Any, build_results: list[PandArtifacts]) -> None:
        pairs = [(art.building, art.resolved) for art in build_results]
        targets_by_gml_id = {art.building.id: art.targets for art in build_results}
        append_energy_label_appearance(model, pairs, targets_by_gml_id=targets_by_gml_id)


@dataclass(frozen=True, slots=True)
class HighlightPainter:
    """Contrast the singled-out Panden with their surroundings.

    Partitions the per-Pand surface targets by whether the Pand is one
    the run singled out (:attr:`target_pand_ids`), then paints the two
    groups in :attr:`target_color` and :attr:`surroundings_color` under
    one toggleable theme.
    """

    target_pand_ids: frozenset[str]
    target_color: tuple[float, float, float] = TARGET_BUILDING_DIFFUSE_COLOR
    surroundings_color: tuple[float, float, float] = SURROUNDINGS_DIFFUSE_COLOR

    def paint(self, model: Any, build_results: list[PandArtifacts]) -> None:
        target_surface_ids: list[str] = []
        surrounding_surface_ids: list[str] = []
        built_target_ids: set[str] = set()
        for art in build_results:
            if art.pand_id in self.target_pand_ids:
                target_surface_ids.extend(art.targets)
                built_target_ids.add(art.pand_id)
            else:
                surrounding_surface_ids.extend(art.targets)
        target_count = len(built_target_ids)
        _LOG.info(
            "Building highlight: %d target building(s), %d surrounding",
            target_count,
            len(build_results) - target_count,
        )
        # A pand the query singled out can be resolved against BAG yet never
        # reach the build: it can fall outside the final extent box, or have
        # no 3DBAG geometry. Warn (not just INFO) so a user who asked to
        # highlight a building learns it is missing rather than getting an
        # all-surroundings model with nothing standing out.
        missing = self.target_pand_ids - built_target_ids
        if missing:
            _LOG.warning(
                "%d of %d singled-out building(s) did not reach the extract and are not "
                "highlighted (outside the extent box, or no 3DBAG geometry): %s",
                len(missing),
                len(self.target_pand_ids),
                ", ".join(sorted(missing)),
            )
        append_building_highlight_appearance(
            model,
            target_surface_ids=target_surface_ids,
            surrounding_surface_ids=surrounding_surface_ids,
            target_color=self.target_color,
            surroundings_color=self.surroundings_color,
        )
