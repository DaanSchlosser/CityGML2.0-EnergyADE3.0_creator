"""Negative-test suite: every invalid input must be rejected, not silently dropped.

Each test starts from a valid reference input (parameterized over the full
owner-occupier fixture and the shareable sample) and applies one targeted mutation.
The mutation creates a well-defined invalidity -- missing required field,
dangling reference, wrong type, cyclic parent, unknown target id -- and the
test asserts that :class:`InputFileError` fires with a message that names the
broken field. "Silent drop" (input passes through and output is missing
data) is the failure mode these tests guard against, so every assertion
checks the error path.

Error-message specificity matters: a loose ``match="id"`` would pass on any
message containing the letters "id" and could hide a regression where the
wrong field is actually the one being rejected. Patterns therefore anchor
on the full field path where the loader's message format allows it.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import lxml.etree as etree
import pytest

from citygml_energy import (
    InputFileError,
    build_city_model_from_feature_collection,
    generate_city_model,
    load_feature_collection,
)
from examples.create_building import INPUT
from tools.validate_xsd import load_schema

_SAMPLE_INPUT = INPUT.parent / "owner_occupier_building_sample.json"

_NEGATIVE_INPUTS = [INPUT]
if _SAMPLE_INPUT.exists():
    _NEGATIVE_INPUTS.append(_SAMPLE_INPUT)


@pytest.fixture(
    scope="module",
    params=_NEGATIVE_INPUTS,
    ids=[p.stem for p in _NEGATIVE_INPUTS],
)
def base_data(request) -> dict[str, Any]:
    """A freshly-loaded, still-valid canonical input.

    Re-run once per parameter so tests exercise every available fixture
    (catches regressions where a mutation only bites one specific shape).
    """
    return load_feature_collection(request.param)


@pytest.fixture(scope="module")
def base_path() -> Path:
    return INPUT.parent


def _find_feature(data: dict[str, Any], feature_id: str) -> dict[str, Any]:
    for feature in data["features"]:
        if feature.get("id") == feature_id:
            return feature
    raise LookupError(f"{feature_id!r} not in fixture")


def _first_of_type(data: dict[str, Any], type_code: str) -> dict[str, Any]:
    for feature in data["features"]:
        if feature.get("type") == type_code:
            return feature
    raise LookupError(f"no feature of type {type_code!r}")


def _build(data: dict[str, Any], base_path: Path) -> None:
    """Re-run the full loader pipeline on a mutated dict."""
    build_city_model_from_feature_collection(data, base_path=base_path)


# ---------------------------------------------------------------------------
# Anchor: the unmodified fixture is still valid end-to-end.
# Without this, a mutation-test false-positive ("rejection") caused by an
# unrelated defect (bad deepcopy, path resolution, etc.) would never be
# caught because every downstream test also errors.
# ---------------------------------------------------------------------------


def test_unmutated_fixture_is_still_valid(base_data: dict[str, Any], base_path: Path) -> None:
    _build(deepcopy(base_data), base_path)


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------


def test_rejects_unknown_top_level_key(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["rogue_section"] = {"anything": True}
    with pytest.raises(InputFileError, match=r"unexpected top-level key.*rogue_section"):
        _build(data, base_path)


def test_rejects_non_object_city_model(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["city_model"] = "just a string"
    with pytest.raises(InputFileError, match=r"city_model must be an object"):
        _build(data, base_path)


def test_rejects_unknown_city_model_key(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["city_model"]["unexpected_meta"] = "hi"
    with pytest.raises(InputFileError, match=r"city_model.*unexpected_meta"):
        _build(data, base_path)


def test_rejects_features_not_a_list(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["features"] = {"not": "a list"}
    with pytest.raises(InputFileError, match=r"features must be an array"):
        _build(data, base_path)


# ---------------------------------------------------------------------------
# Feature-level validation
# ---------------------------------------------------------------------------


def test_rejects_feature_missing_id(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    del data["features"][0]["id"]
    with pytest.raises(InputFileError, match=r"features\[0\]\.id must be a non-empty string"):
        _build(data, base_path)


def test_rejects_feature_whitespace_only_id(base_data: dict[str, Any], base_path: Path) -> None:
    """NCName check must fire even when a non-empty string is all whitespace."""
    data = deepcopy(base_data)
    data["features"][0]["id"] = "   "
    with pytest.raises(InputFileError, match=r"features\[0\]\.id must be a non-empty string"):
        _build(data, base_path)


def test_rejects_feature_missing_type(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    del data["features"][0]["type"]
    with pytest.raises(InputFileError, match=r"features\[0\]\.type must be"):
        _build(data, base_path)


def test_rejects_unknown_feature_type(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["features"][0]["type"] = "nrg3:DefinitelyNotAThing"
    with pytest.raises(InputFileError, match=r"Unknown type 'nrg3:DefinitelyNotAThing'"):
        _build(data, base_path)


def test_rejects_duplicate_feature_ids(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    stolen_id = data["features"][0]["id"]
    data["features"][1]["id"] = stolen_id
    with pytest.raises(InputFileError, match=rf"features\[1\]\.id duplicates '{stolen_id}'"):
        _build(data, base_path)


def test_rejects_id_that_is_not_ncname(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["features"][0]["id"] = "has a space and : colon"
    with pytest.raises(InputFileError, match=r"is not a valid XML NCName"):
        _build(data, base_path)


def test_rejects_id_starting_with_digit(base_data: dict[str, Any], base_path: Path) -> None:
    """NCName forbids leading digits; XML parsers refuse such gml:id values."""
    data = deepcopy(base_data)
    data["features"][0]["id"] = "1bad_id"
    with pytest.raises(InputFileError, match=r"NCName"):
        _build(data, base_path)


# ---------------------------------------------------------------------------
# Parent chain -- silent downstream errors before the hardening
# ---------------------------------------------------------------------------


def test_rejects_parent_pointing_at_missing_id(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    for feature in data["features"]:
        if "parent" in feature:
            feature["parent"] = "does_not_exist"
            break
    else:
        pytest.fail("fixture has no parent references")
    with pytest.raises(
        InputFileError,
        match=r"parent references missing id 'does_not_exist'",
    ):
        _build(data, base_path)


def test_rejects_self_parent(base_data: dict[str, Any], base_path: Path) -> None:
    """A feature declaring itself as parent used to raise a downstream
    ``ValueError`` from the builder with an opaque message. Must now fail
    loudly at the validator."""
    data = deepcopy(base_data)
    feat = data["features"][0]
    feat["parent"] = feat["id"]
    with pytest.raises(InputFileError, match=r"points at itself"):
        _build(data, base_path)


def test_rejects_cyclic_parent_chain(base_data: dict[str, Any], base_path: Path) -> None:
    """A->B and B->A must be rejected with a cycle-specific message.

    Uses schedule features (which carry no parent-type whitelist entry)
    so the cycle check fires before any type-level rejection. Reparenting
    two ZoneParts at each other would also cycle, but the parent-type
    check catches ZonePart-without-Zone-parent first.
    """
    data = deepcopy(base_data)
    schedules = [f for f in data["features"] if f.get("type") == "nrg3:ConstantValueSchedule"]
    if len(schedules) < 2:
        pytest.skip("fixture has fewer than two schedules to form a cycle")
    schedules[0]["parent"] = schedules[1]["id"]
    schedules[1]["parent"] = schedules[0]["id"]
    with pytest.raises(InputFileError, match=r"cyclic parent relation"):
        _build(data, base_path)


def test_rejects_empty_string_parent(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    for feature in data["features"]:
        if "parent" in feature:
            feature["parent"] = "   "
            break
    else:
        pytest.fail("fixture has no parent references")
    with pytest.raises(InputFileError, match=r"parent must be a non-empty string"):
        _build(data, base_path)


def test_rejects_zonepart_parented_to_building(base_data: dict[str, Any], base_path: Path) -> None:
    """Energy ADE requires Building -> Zone -> ZonePart. The XSD permits the
    shortcut Building -> ZonePart via ZonePropertyType's substitution group,
    so silent acceptance would produce output that validates but corrupts
    the thermal-zone hierarchy. The validator must refuse it."""
    data = deepcopy(base_data)
    building_id = _first_of_type(data, "bldg:Building")["id"]
    target = None
    for feature in data["features"]:
        if feature.get("type") == "nrg3:ZonePart":
            feature["parent"] = building_id
            target = feature
            break
    if target is None:
        pytest.skip("fixture has no ZonePart to reparent")

    with pytest.raises(
        InputFileError,
        match=r"nrg3:ZonePart.*cannot have a parent of type 'bldg:Building'",
    ):
        _build(data, base_path)


def test_accepts_zonepart_parented_to_zone(base_data: dict[str, Any], base_path: Path) -> None:
    """Positive control: the canonical Zone -> ZonePart hierarchy is accepted.

    Without this sibling test, the whitelist could get over-tightened to
    reject everything and the negative test would still pass."""
    # The fixture already has this hierarchy; just build without mutating.
    _build(deepcopy(base_data), base_path)


# ---------------------------------------------------------------------------
# Geometry sources
# ---------------------------------------------------------------------------


def test_rejects_geometry_source_missing_path(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    del data["geometry_sources"][0]["path"]
    with pytest.raises(
        InputFileError,
        match=r"geometry_sources\[0\]\.path must be a non-empty string",
    ):
        _build(data, base_path)


def test_rejects_geometry_source_pointing_at_nonexistent_file(
    base_data: dict[str, Any], base_path: Path
) -> None:
    data = deepcopy(base_data)
    data["geometry_sources"][0]["path"] = "no_such_stp_file.stp"
    with pytest.raises(
        InputFileError,
        match=r"geometry_sources\[0\]\.path does not exist",
    ):
        _build(data, base_path)


def test_rejects_geometry_source_path_escaping_base(
    base_data: dict[str, Any], base_path: Path
) -> None:
    """Paths resolving outside the base directory should fail -- either
    because the file doesn't exist, or because the path escapes. Either
    way, silent acceptance would let a pipeline wander off the tree."""
    data = deepcopy(base_data)
    data["geometry_sources"][0]["path"] = "../../nonexistent.stp"
    with pytest.raises(InputFileError, match=r"does not exist"):
        _build(data, base_path)


def test_rejects_geometry_source_with_unknown_type(
    base_data: dict[str, Any], base_path: Path
) -> None:
    data = deepcopy(base_data)
    data["geometry_sources"][0]["type"] = "step-unknown-lod42"
    with pytest.raises(InputFileError, match=r"geometry_sources\[0\]\.type must be one of"):
        _build(data, base_path)


def test_rejects_geometry_source_target_to_missing_building(
    base_data: dict[str, Any], base_path: Path
) -> None:
    data = deepcopy(base_data)
    data["geometry_sources"][0]["target_building_id"] = "building_that_does_not_exist"
    with pytest.raises(
        InputFileError,
        match=r"target_building_id.*'building_that_does_not_exist'",
    ):
        _build(data, base_path)


def test_rejects_unknown_target_key_on_geometry_source(
    base_data: dict[str, Any], base_path: Path
) -> None:
    """Typos in target keys (e.g. target_pv_id on a zonepart source) must fail
    loudly. Silently ignoring would route geometry nowhere."""
    data = deepcopy(base_data)
    zonepart_source = next(
        gs for gs in data["geometry_sources"] if gs["type"].startswith("step-zonepart")
    )
    zonepart_source["target_pv_id"] = "pv_panel_1"  # not valid for zonepart
    with pytest.raises(
        InputFileError,
        match=r"target key\(s\) not valid for type 'step-zonepart",
    ):
        _build(data, base_path)


def test_rejects_geometry_source_target_pointing_at_wrong_feature_type(
    base_data: dict[str, Any], base_path: Path
) -> None:
    """target_building_id pointing at a non-Building feature must fail."""
    data = deepcopy(base_data)
    pv = _find_feature(data, "pv_panel_1")
    data["geometry_sources"][0]["target_building_id"] = pv["id"]
    with pytest.raises(InputFileError, match=r"target_building_id"):
        _build(data, base_path)


# ---------------------------------------------------------------------------
# CRS controls
# ---------------------------------------------------------------------------


def test_rejects_srs_dimension_not_in_2_or_3(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["srs_dimension"] = 4
    with pytest.raises(InputFileError, match=r"srs_dimension must be 2 or 3"):
        _build(data, base_path)


def test_rejects_srs_dimension_as_bool(base_data: dict[str, Any], base_path: Path) -> None:
    """Python bool is a subclass of int. ``True`` is numerically 1 but
    clearly not a valid srs_dimension. Validator must treat this as a
    type error, not a value error."""
    data = deepcopy(base_data)
    data["srs_dimension"] = True
    with pytest.raises(InputFileError, match=r"srs_dimension"):
        _build(data, base_path)


def test_rejects_empty_srs_name(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["srs_name"] = ""
    with pytest.raises(InputFileError, match=r"srs_name must be a non-empty"):
        _build(data, base_path)


def test_rejects_whitespace_only_srs_name(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    data["srs_name"] = "  \t  "
    with pytest.raises(InputFileError, match=r"srs_name must be a non-empty"):
        _build(data, base_path)


# ---------------------------------------------------------------------------
# Cross-reference resolution (related_to, construction_mapping)
# ---------------------------------------------------------------------------


def test_rejects_installed_on_referencing_nonexistent_surface(
    base_data: dict[str, Any], base_path: Path
) -> None:
    """JSON typo in an installedOn ``related_to`` entry must be caught."""
    data = deepcopy(base_data)
    pv = _find_feature(data, "pv_panel_1")
    pv["related_to"] = [{"relation": "installedOn", "target": "NotARealRoofSurface"}]
    with pytest.raises(InputFileError, match=r"NotARealRoofSurface"):
        _build(data, base_path)


def test_rejects_related_to_not_a_list(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    pv = _find_feature(data, "pv_panel_1")
    pv["related_to"] = {"relation": "installedOn", "target": "RoofSurface_01"}  # object, not list
    with pytest.raises(InputFileError, match=r"'related_to' must be a non-empty list"):
        _build(data, base_path)


def test_rejects_unknown_relation_kind(base_data: dict[str, Any], base_path: Path) -> None:
    """``relation`` must name a registered RelationKind (e.g. installedOn, serving)."""
    data = deepcopy(base_data)
    pv = _find_feature(data, "pv_panel_1")
    pv["related_to"] = [{"relation": "bogusRelation", "target": "RoofSurface_01"}]
    with pytest.raises(InputFileError, match=r"bogusRelation.*not registered"):
        _build(data, base_path)


def test_rejects_feature_relation_with_object_target(
    base_data: dict[str, Any], base_path: Path
) -> None:
    """``serving`` targets must be plain gml:id strings; the {name, lod} form
    is intentionally rejected so a typo against a STEP surface name surfaces
    as an error instead of resolving against the surface index."""
    data = deepcopy(base_data)
    pv = _find_feature(data, "pv_panel_1")
    pv["related_to"] = [{"relation": "serving", "target": {"name": "RoofSurface_01", "lod": 2}}]
    with pytest.raises(InputFileError, match=r"'related_to'\[0\]\.target for relation 'serving'"):
        _build(data, base_path)


def test_rejects_cmap_by_id_referencing_nonexistent_construction(
    base_data: dict[str, Any], base_path: Path
) -> None:
    """Typo in a ``by_id`` target used to silently skip the surface during
    mapping, so a surface ended up with no construction in the output --
    invisible unless a downstream consumer complained.
    """
    data = deepcopy(base_data)
    data.setdefault("construction_mapping", {}).setdefault("by_id", {})["new_surface_key"] = (
        "constr_nonexistent_xyz"
    )
    with pytest.raises(
        InputFileError,
        match=r"construction_mapping.*constr_nonexistent_xyz",
    ):
        _build(data, base_path)


def test_rejects_cmap_by_type_referencing_nonexistent_construction(
    base_data: dict[str, Any], base_path: Path
) -> None:
    data = deepcopy(base_data)
    data.setdefault("construction_mapping", {}).setdefault("by_type", {})["WallSurface"] = (
        "constr_also_nonexistent"
    )
    with pytest.raises(
        InputFileError,
        match=r"construction_mapping.*constr_also_nonexistent",
    ):
        _build(data, base_path)


# ---------------------------------------------------------------------------
# Field-level type errors
# ---------------------------------------------------------------------------


def test_rejects_measure_field_as_plain_string(base_data: dict[str, Any], base_path: Path) -> None:
    """``installed_power`` expects {value, uom}; a bare string must fail at
    the build phase with the feature index identified in the message."""
    data = deepcopy(base_data)
    pv = _find_feature(data, "pv_panel_1")
    pv["installed_power"] = "five kilowatts"
    with pytest.raises(InputFileError, match=r"id='pv_panel_1'.*installed_power"):
        _build(data, base_path)


def test_rejects_integer_field_as_string(base_data: dict[str, Any], base_path: Path) -> None:
    data = deepcopy(base_data)
    building = _first_of_type(data, "bldg:Building")
    building["storeys_above_ground"] = "two"
    with pytest.raises(InputFileError, match=r"storeys_above_ground"):
        _build(data, base_path)


# ---------------------------------------------------------------------------
# XSD gate -- even if the loader is ever loosened, XSD must still refuse
# malformed output.
# ---------------------------------------------------------------------------


def test_xsd_rejects_non_numeric_coordinates(base_data: dict[str, Any], base_path: Path) -> None:
    # Only need to run once per suite; sample input is cheap and valid.
    model = generate_city_model(_SAMPLE_INPUT if _SAMPLE_INPUT.exists() else INPUT)
    xml = model.to_string()
    corrupted = xml.replace("<gml:posList>", "<gml:posList>not_a_number ", 1)
    doc = etree.fromstring(corrupted.encode("utf-8"))
    schema = load_schema()
    with pytest.raises(etree.DocumentInvalid):
        schema.assertValid(doc)
