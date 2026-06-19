"""Tests for the building-painter seam (``painters.py``).

:class:`EnergyLabelPainter` and :class:`HighlightPainter` both consume
the per-Pand :class:`PandArtifacts` and append one themed appearance.
These check that each paints the right theme over the right targets,
delegating to the same ``append_*`` builders the inline orchestrator used
so the output is unchanged.
"""

from __future__ import annotations

import logging
from typing import Any

from citygml_energy.city_builder.appearance import (
    BUILDING_HIGHLIGHT_THEME,
    ENERGY_LABEL_THEME,
    SURROUNDINGS_DIFFUSE_COLOR,
    TARGET_BUILDING_DIFFUSE_COLOR,
    collect_surface_target_ids,
)
from citygml_energy.city_builder.builders import build_building
from citygml_energy.city_builder.painters import EnergyLabelPainter, HighlightPainter
from citygml_energy.city_builder.pand_executor import PandArtifacts
from citygml_energy.core import CityModel
from tests._factories import make_parsed_building


def _artifact(pand_id: str, building: Any) -> PandArtifacts:
    return PandArtifacts(
        pand_id=pand_id,
        building=building,
        resolved=[],
        targets=collect_surface_target_ids(building),
        coords=[],
    )


def test_energy_label_painter_paints_energy_label_theme() -> None:
    model = CityModel()
    building = build_building(make_parsed_building(pand_id="A"))
    model.add(building)

    EnergyLabelPainter().paint(model, [_artifact("A", building)])

    [member] = model.xsd.appearance_member
    assert member.appearance.theme == ENERGY_LABEL_THEME


def test_highlight_painter_partitions_targets_vs_surroundings() -> None:
    model = CityModel()
    target = build_building(make_parsed_building(pand_id="A"))
    other = build_building(make_parsed_building(pand_id="B"))
    model.add(target)
    model.add(other)

    HighlightPainter(target_pand_ids=frozenset({"A"})).paint(
        model, [_artifact("A", target), _artifact("B", other)]
    )

    [member] = model.xsd.appearance_member
    assert member.appearance.theme == BUILDING_HIGHLIGHT_THEME
    materials = [p.x3_dmaterial for p in member.appearance.surface_data_member]
    by_color = {tuple(m.diffuse_color): set(m.target) for m in materials}
    assert by_color[tuple(TARGET_BUILDING_DIFFUSE_COLOR)] == set(collect_surface_target_ids(target))
    assert by_color[tuple(SURROUNDINGS_DIFFUSE_COLOR)] == set(collect_surface_target_ids(other))


def test_highlight_painter_no_op_when_no_buildings() -> None:
    model = CityModel()
    HighlightPainter(target_pand_ids=frozenset({"A"})).paint(model, [])
    assert model.xsd.appearance_member == []


def test_highlight_painter_all_surroundings_and_warns_when_target_absent(caplog) -> None:
    """A singled-out pand that never reached the build paints all-surroundings and warns.

    This is the clipped-out / no-3DBAG-geometry case: target_pand_ids is
    non-empty but no build result matches, so only the surroundings material
    is emitted and the dropped target is reported loudly.
    """
    model = CityModel()
    other = build_building(make_parsed_building(pand_id="B"))
    model.add(other)

    with caplog.at_level(logging.WARNING):
        HighlightPainter(target_pand_ids=frozenset({"A"})).paint(model, [_artifact("B", other)])

    [member] = model.xsd.appearance_member
    assert member.appearance.theme == BUILDING_HIGHLIGHT_THEME
    materials = [p.x3_dmaterial for p in member.appearance.surface_data_member]
    by_color = {tuple(m.diffuse_color): set(m.target) for m in materials}
    assert tuple(SURROUNDINGS_DIFFUSE_COLOR) in by_color
    assert tuple(TARGET_BUILDING_DIFFUSE_COLOR) not in by_color  # nothing highlighted
    assert any("did not reach the extract" in r.message for r in caplog.records)
