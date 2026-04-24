"""Drift check for the committed city-build JSON Schema.

Three separate invariants, one test per invariant:

1. **generator ↔ committed**: ``build_schema()`` output equals the file
   on disk. Guards against someone editing ``config.py`` and
   regenerating the generator source but forgetting to run the
   regen script. Pre-existing.
2. **canonical formatting**: the file is formatted exactly like the
   generator's JSON-dump output. Guards against manual edits to the
   JSON that would be lost on the next regen. Pre-existing.
3. **config.py allowlists ↔ generator allowlists**: the
   ``_ALLOWED_*_KEYS`` sets in the loader match the ``properties``
   keys in the generator. Guards the other half of the drift: a key
   added to the generator but not to ``config.py``'s validator is
   silently rejected at runtime with a confusing ``unexpected key``
   error; a key added to ``config.py`` but not to the generator is
   silently missing from IDE autocomplete + the JSON schema.
"""

from __future__ import annotations

import json

import pytest

from citygml_energy.city_builder.config import (
    _ALLOWED_BOUNDARY_KEYS,
    _ALLOWED_CITY_MODEL_KEYS,
    _ALLOWED_PV_PANELS_KEYS,
    _ALLOWED_TOP_LEVEL_KEYS,
    _ALLOWED_VEGETATION_KEYS,
)
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


def test_generator_and_config_allowlists_agree() -> None:
    """The ``additionalProperties=false`` keys in every generator block
    must match the corresponding ``_ALLOWED_*_KEYS`` set in ``config.py``.

    A mismatch surfaces as one of two user-facing failures:

    * A config key that validates against the schema (and so gets
      autocompleted) is rejected by the loader at runtime with
      ``unexpected key``.
    * A config key the loader silently accepts does not appear in the
      schema, so no documentation string / autocomplete exists for it.

    Both are bugs that the existing generator ↔ committed drift test
    cannot catch: they sit between the generator and the loader.
    """
    schema = build_schema()
    top = schema["properties"]

    # The ``$schema`` and ``schema_version`` keys exist in the
    # generator's top-level block but are meta-fields: they live
    # outside ``_ALLOWED_TOP_LEVEL_KEYS`` in the loader because the
    # loader has direct logic for them. Ignoring them here keeps the
    # test comparing allowlists like-for-like.
    schema_top_keys = set(top.keys())
    assert schema_top_keys == _ALLOWED_TOP_LEVEL_KEYS, (
        "Top-level keys drift:\n"
        f"  in schema but not in config._ALLOWED_TOP_LEVEL_KEYS: "
        f"{sorted(schema_top_keys - _ALLOWED_TOP_LEVEL_KEYS)}\n"
        f"  in config._ALLOWED_TOP_LEVEL_KEYS but not in schema: "
        f"{sorted(_ALLOWED_TOP_LEVEL_KEYS - schema_top_keys)}"
    )

    for name, loader_allowed in (
        ("boundary", _ALLOWED_BOUNDARY_KEYS),
        ("city_model", _ALLOWED_CITY_MODEL_KEYS),
        ("pv_panels", _ALLOWED_PV_PANELS_KEYS),
        ("vegetation", _ALLOWED_VEGETATION_KEYS),
    ):
        schema_keys = set(top[name]["properties"].keys())
        assert schema_keys == loader_allowed, (
            f"{name!r} block keys drift:\n"
            f"  in schema but not in loader: "
            f"{sorted(schema_keys - loader_allowed)}\n"
            f"  in loader but not in schema: "
            f"{sorted(loader_allowed - schema_keys)}"
        )
