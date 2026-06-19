"""Tests for the building-highlight appearance painter.

Verifies that :func:`append_building_highlight_appearance` contrasts the
target buildings with their surroundings under one toggleable theme.
"""

from __future__ import annotations

from citygml_energy.city_builder.appearance import (
    BUILDING_HIGHLIGHT_THEME,
    SURROUNDINGS_DIFFUSE_COLOR,
    TARGET_BUILDING_DIFFUSE_COLOR,
    append_building_highlight_appearance,
    collect_surface_target_ids,
)
from citygml_energy.city_builder.builders import build_building
from citygml_energy.core import CityModel
from tests._factories import make_parsed_building


def test_highlight_paints_targets_and_surroundings_in_two_materials() -> None:
    model = CityModel()
    target = build_building(make_parsed_building(pand_id="A"))
    other = build_building(make_parsed_building(pand_id="B"))
    model.add(target)
    model.add(other)

    target_ids = collect_surface_target_ids(target)
    surrounding_ids = collect_surface_target_ids(other)
    append_building_highlight_appearance(
        model,
        target_surface_ids=target_ids,
        surrounding_surface_ids=surrounding_ids,
    )

    [member] = model.xsd.appearance_member
    appearance = member.appearance
    assert appearance.theme == BUILDING_HIGHLIGHT_THEME
    assert appearance.id == f"appearance_{BUILDING_HIGHLIGHT_THEME}"

    materials = [p.x3_dmaterial for p in appearance.surface_data_member]
    assert len(materials) == 2
    by_color = {tuple(m.diffuse_color): set(m.target) for m in materials}
    assert by_color[tuple(SURROUNDINGS_DIFFUSE_COLOR)] == set(surrounding_ids)
    assert by_color[tuple(TARGET_BUILDING_DIFFUSE_COLOR)] == set(target_ids)


def test_highlight_respects_custom_colors() -> None:
    model = CityModel()
    target = build_building(make_parsed_building(pand_id="A"))
    model.add(target)
    ids = collect_surface_target_ids(target)

    append_building_highlight_appearance(
        model,
        target_surface_ids=ids,
        surrounding_surface_ids=[],
        target_color=(0.1, 0.2, 0.3),
    )

    [member] = model.xsd.appearance_member
    [material_prop] = member.appearance.surface_data_member
    assert material_prop.x3_dmaterial.diffuse_color == [0.1, 0.2, 0.3]
    assert material_prop.x3_dmaterial.target == ids


def test_highlight_no_op_when_no_targets() -> None:
    model = CityModel()
    append_building_highlight_appearance(model, target_surface_ids=[], surrounding_surface_ids=[])
    assert model.xsd.appearance_member == []


def test_highlight_serialises_in_cityml_output() -> None:
    model = CityModel()
    target = build_building(make_parsed_building(pand_id="A"))
    model.add(target)
    append_building_highlight_appearance(
        model,
        target_surface_ids=collect_surface_target_ids(target),
        surrounding_surface_ids=[],
    )

    xml = model.to_string()
    assert f"<app:theme>{BUILDING_HIGHLIGHT_THEME}</app:theme>" in xml
    assert "<app:X3DMaterial>" in xml
    assert "<app:diffuseColor>" in xml
