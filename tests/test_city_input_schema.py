"""Drift check for the committed city-build JSON Schema."""

from __future__ import annotations

import json

import pytest

from tools.generate_city_input_schema import SCHEMA_PATH, build_schema


def _committed_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_committed_city_schema_matches_generator() -> None:
    generated = build_schema()
    committed = _committed_schema()
    if generated != committed:
        pytest.fail(
            "Committed city JSON schema is out of date. Run:\n\n"
            "    python tools/generate_city_input_schema.py\n\n"
            "and commit the regenerated schemas/city_input.schema.json."
        )


def test_committed_city_schema_is_canonically_formatted() -> None:
    committed = _committed_schema()
    expected = json.dumps(committed, indent=2, ensure_ascii=False) + "\n"
    on_disk = SCHEMA_PATH.read_text(encoding="utf-8")
    if on_disk != expected:
        pytest.fail(
            "schemas/city_input.schema.json is not canonically formatted. "
            "Regenerate it with tools/generate_city_input_schema.py."
        )
