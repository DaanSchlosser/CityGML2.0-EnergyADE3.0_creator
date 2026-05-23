"""Drift-detection test for ``docs/mapping_city.md``.

Asserts two invariants:

1. **Every code reference in the index resolves.** The doc cites
   modules and symbols (e.g. ``builders/vegetation.py``,
   ``_apply_bor_enrichment``) so that a reader can land on the
   implementation in one click. If a refactor renames a module or a
   symbol without updating the doc, this test fails first.

2. **Every public-ish enrichment helper in the city-builder code is
   mentioned at least once in the index.** Adding a new
   ``_apply_*`` helper or a new ``apply_*`` builder hook without
   listing it in the master mapping is the most common way for the
   doc to silently fall behind reality. The test enforces the link.

The test is intentionally loose about *form*: it does not parse the
exact tables. The point is to catch broken references, not to police
the doc's prose. Long-form rationale lives in companion docs and is
not exercised here. The per-building-pipeline mapping
(``docs/mapping_building.md``) is its own document and is not
exercised by this test.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "docs" / "mapping_city.md"
CITY_BUILDER_PKG = "citygml_energy.city_builder"


def _load_index_text() -> str:
    return INDEX_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Invariant 1: every code reference in the index resolves
# ---------------------------------------------------------------------------


def _module_paths_referenced_in_doc(text: str) -> set[Path]:
    """Find every ``[label](../citygml_energy/...py)`` link target.

    The doc uses relative links of the form
    ``[some_thing](../citygml_energy/city_builder/...py)``; we only
    care about the path part. Anchors (``#L42``) are stripped because
    the integration is at the symbol level, not the line level.
    """
    pattern = re.compile(r"\[[^\]]+\]\((\.\./[^)#]+\.py)(?:#[^)]*)?\)")
    paths: set[Path] = set()
    for match in pattern.finditer(text):
        paths.add((INDEX_PATH.parent / match.group(1)).resolve())
    return paths


def test_every_module_path_in_index_exists() -> None:
    text = _load_index_text()
    missing = sorted(p for p in _module_paths_referenced_in_doc(text) if not p.exists())
    assert not missing, (
        "docs/mapping_city.md references modules that no "
        f"longer exist: {missing}"
    )


_REFERENCED_SYMBOLS: dict[str, list[str]] = {
    # module path (relative to repo root, posix slashes) → symbols cited in the doc.
    # When the index references "X is implemented by FOO in module BAR",
    # we list FOO here so the test can verify FOO actually exists in BAR.
    "citygml_energy/city_builder/builders/building.py": [
        "build_building",
        "build_building_unit",
        "attach_building_units_to_building",
        "_apply_building_attributes",
        "_attach_lod2_thematic_surfaces",
    ],
    "citygml_energy/city_builder/builders/address.py": [
        "build_address",
    ],
    "citygml_energy/city_builder/builders/epc.py": [
        "apply_bag_year_metadata_to_building",
        "apply_eponline_pand_attribution_to_building",
        "_pick_canonical_eponline_label",
        "_eponline_label_recency_key",
        "build_epc",
        "_certification_method_string",
        "_apply_eponline_classification_to_building_unit",
    ],
    "citygml_energy/city_builder/builders/vegetation.py": [
        "build_solitary_vegetation_object",
        "_apply_cftree_morphometrics",
        "_apply_bgt_cross_reference",
        "_apply_bor_enrichment",
        "_CFTREE_NATIVE_FIELDS",
        "_CFTREE_GENERIC_DOUBLE",
    ],
    "citygml_energy/city_builder/postcode6.py": [
        "safely_fetch_postcode6_areas",
        "attach_postcode6_areas_to_model",
    ],
    "citygml_energy/city_builder/fetchers/cbs_postcode6.py": [
        "fetch_postcode6_areas",
        "Postcode6Area",
    ],
    "citygml_energy/city_builder/tree_matching.py": [
        "MATCH_RADIUS_M",
        "match_nearest_within",
    ],
    "citygml_energy/city_builder/pand_executor.py": ["_merge_attributes"],
    "citygml_energy/city_builder/energy_resources.py": [
        "attach_energy_resources_to_building_unit",
    ],
    "citygml_energy/city_builder/solar_panels.py": [
        "attach_solar_collectors_to_building",
    ],
    "citygml_energy/city_builder/fetchers/municipality.py": [
        "fetch_municipality_outline",
        "_feature_bbox",
    ],
}


@pytest.mark.parametrize(
    ("module_path", "symbols"),
    sorted(_REFERENCED_SYMBOLS.items()),
)
def test_referenced_symbols_exist_in_module(
    module_path: str, symbols: list[str],
) -> None:
    """Each symbol the index cites must be reachable in its module.

    Catches the "renamed without updating the doc" case: a search-and-
    replace in code that does not also touch
    ``docs/mapping_city.md`` fails this assertion before it
    reaches a reviewer.
    """
    full_path = REPO_ROOT / module_path
    assert full_path.exists(), f"Index points at missing file: {module_path}"

    module_dotted = module_path[: -len(".py")].replace("/", ".")
    module = importlib.import_module(module_dotted)
    missing = [s for s in symbols if not hasattr(module, s)]
    assert not missing, (
        f"Index cites symbols that are no longer in {module_path}: "
        f"{missing}"
    )


# ---------------------------------------------------------------------------
# Invariant 2: every enrichment helper is mentioned somewhere in the doc
# ---------------------------------------------------------------------------


# Helpers whose name is the canonical "this writes a source's data into
# the GML" function. Anything matching one of these prefixes in the
# city-builder package counts as a mapping entry that should be
# documented.
_ENRICHMENT_PREFIXES = (
    "_apply_bgt_",
    "_apply_bor_",
    "_apply_cftree_",
    "_apply_eponline_",
    "apply_bag_",
    "apply_eponline_",
    "build_building",
    "build_address",
    "build_solitary_vegetation_object",
    "attach_postcode6_",
)


def _walk_python_modules(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def test_every_enrichment_helper_is_documented() -> None:
    """The point of the master index is that nothing maps a source
    field to the GML without being listed here. Adding a new
    enrichment helper without updating the doc is exactly the drift
    we want to catch.
    """
    text = _load_index_text()
    package_root = REPO_ROOT / "citygml_energy" / "city_builder"

    helper_pattern = re.compile(
        r"^(def|async def)\s+(?P<name>[A-Za-z_][A-Za-z_0-9]*)\b",
        re.MULTILINE,
    )

    undocumented: list[tuple[str, str]] = []
    for module_path in _walk_python_modules(package_root):
        rel = module_path.relative_to(REPO_ROOT).as_posix()
        if rel.endswith("/__init__.py"):
            continue
        source = module_path.read_text(encoding="utf-8")
        for match in helper_pattern.finditer(source):
            name = match.group("name")
            if not any(name.startswith(prefix) for prefix in _ENRICHMENT_PREFIXES):
                continue
            if name not in text:
                undocumented.append((rel, name))

    assert not undocumented, (
        "Each helper below maps source data into the GML but is not "
        "mentioned in docs/mapping_city.md. Add a row to the "
        "appropriate section so future readers can find it:\n"
        + "\n".join(f"  {path}: {name}" for path, name in undocumented)
    )
