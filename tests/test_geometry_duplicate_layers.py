"""Duplicate STEP layer-name semantics at geometry import.

Two different rules, matching how the names are consumed:

* On the model-wide ``surface_name_index`` (building sources, the
  handle ``related_to[installedOn]`` resolves through) a duplicate
  ``(layer name, LoD)`` raises. Before the guard it last-wins
  overwrote the index, silently re-targeting device relations to
  whichever same-named shell came last in file order.
* Within a source's opening-matching records a recurring name is
  legitimate (a multi-face CAD layer exports one same-named shell per
  face; the canonical ZonePart STEPs carry two ``GroundSurface_01``
  each) and every shell's record is kept as a matching candidate. The
  end-to-end coverage for that path is ``test_reference_building``,
  which builds the canonical input with its real duplicates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from citygml_energy import build_city_model_from_feature_collection

from .test_step import _minimal_step_file


def _write_step(tmp_path: Path, name: str, *, duplicate_shell: bool = False) -> Path:
    step = _minimal_step_file()
    if duplicate_shell:
        # A second shell entity reusing the same OPEN_SHELL and the same
        # layer name, as a CAD export with two same-named layers would.
        step = step.replace(
            "ENDSEC;\nEND-ISO-10303-21;",
            "#23=SHELL_BASED_SURFACE_MODEL('WallSurface_1',(#20));\nENDSEC;\nEND-ISO-10303-21;",
        )
    path = tmp_path / name
    path.write_text(step, encoding="utf-8")
    return path


def _collection(sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "city_model": {"name": "duplicate-layer test"},
        "features": [{"type": "bldg:Building", "id": "b1"}],
        "geometry_sources": sources,
    }


def test_duplicate_layer_name_within_one_building_source_raises(tmp_path: Path) -> None:
    # Building-source names feed the installedOn index, so even a
    # within-file duplicate is ambiguous as a relation target.
    step = _write_step(tmp_path, "dup.stp", duplicate_shell=True)
    data = _collection(
        [{"type": "step-building-lod2", "path": str(step), "target_building_id": "b1"}]
    )
    with pytest.raises(ValueError, match=r"re-declares surface layer name 'WallSurface_1'"):
        build_city_model_from_feature_collection(data, base_path=tmp_path)


def test_same_layer_name_at_same_lod_across_sources_raises(tmp_path: Path) -> None:
    step = _write_step(tmp_path, "square.stp")
    data = _collection(
        [
            {"type": "step-building-lod2", "path": str(step), "target_building_id": "b1"},
            {"type": "step-building-lod2", "path": str(step), "target_building_id": "b1"},
        ]
    )
    with pytest.raises(
        ValueError, match=r"re-declares surface layer name 'WallSurface_1' at LoD 2"
    ):
        build_city_model_from_feature_collection(data, base_path=tmp_path)


def test_same_layer_name_at_different_lods_is_allowed(tmp_path: Path) -> None:
    # The documented convention: the same layer name in a LoD 2 and a
    # LoD 3 STEP names different physical faces; the LoD axis of the
    # index keeps them apart, so this must keep building.
    step = _write_step(tmp_path, "square.stp")
    data = _collection(
        [
            {"type": "step-building-lod2", "path": str(step), "target_building_id": "b1"},
            {"type": "step-building-lod3", "path": str(step), "target_building_id": "b1"},
        ]
    )
    model = build_city_model_from_feature_collection(data, base_path=tmp_path)
    assert set(model.surface_name_index) == {("WallSurface_1", 2), ("WallSurface_1", 3)}
