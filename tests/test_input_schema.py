"""Drift check for the committed JSON Schema.

The schema lives at ``schemas/citygml_energy_input.schema.json`` and is
derived from the xsdata bindings + geometry-source specs by
``tools/generate_input_schema.py``. A divergence means either the
bindings were regenerated without re-running the generator, or a new
geometry-source spec was added without updating the schema.

Both cases point to the same fix: run the generator.
"""

from __future__ import annotations

import json

import pytest

from tools.generate_input_schema import SCHEMA_PATH, build_schema


def _committed_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_committed_schema_matches_generator() -> None:
    generated = build_schema()
    committed = _committed_schema()
    if generated != committed:
        pytest.fail(
            "Committed JSON schema is out of date. Run:\n\n"
            "    python tools/generate_input_schema.py\n\n"
            "and commit the regenerated schemas/citygml_energy_input.schema.json."
        )


def test_committed_schema_is_canonically_formatted() -> None:
    """The file on disk should match ``json.dumps(..., indent=2)`` + trailing newline."""
    committed = _committed_schema()
    expected = json.dumps(committed, indent=2, ensure_ascii=False) + "\n"
    on_disk = SCHEMA_PATH.read_text(encoding="utf-8")
    if on_disk != expected:
        pytest.fail(
            "schemas/citygml_energy_input.schema.json is not canonically formatted. "
            "Regenerate it with tools/generate_input_schema.py."
        )


def test_every_geometry_source_spec_has_a_schema_branch() -> None:
    """Each spec in GEOMETRY_SOURCE_SPECS appears as a branch in the schema."""
    from citygml_energy.geometry import GEOMETRY_SOURCE_SPECS

    committed = _committed_schema()
    branches = committed["properties"]["geometry_sources"]["items"]["oneOf"]
    branch_types = {b["properties"]["type"]["const"] for b in branches}
    assert branch_types == set(GEOMETRY_SOURCE_SPECS)


def test_feature_type_enum_covers_every_registered_binding_class() -> None:
    from citygml_energy.mapping import list_available_types

    committed = _committed_schema()
    enum = committed["properties"]["features"]["items"]["properties"]["type"]["enum"]
    assert enum == list_available_types()
