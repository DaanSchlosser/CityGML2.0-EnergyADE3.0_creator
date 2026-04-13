"""Load data-only feature collections into CityGML models.

Supports the schema_version 2 JSON format where each feature is a flat dict
with ``type``, ``id``, ``parent``, ``parent_field``, and xsdata field names
as keys.  All object construction is delegated to the generic ``mapping``
module — no feature-type-specific code lives here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .core import CityModel
from .geometry import apply_geometry_sources
from .mapping import attach_child, build_from_dict, resolve_class

PathLike = str | Path

# Keys that live at the feature level, not passed to build_from_dict.
_FEATURE_META_KEYS = frozenset({"type", "parent", "parent_field"})

_ALLOWED_TOP_LEVEL_KEYS = {
    "$schema",
    "schema_version",
    "city_model",
    "features",
    "geometry_sources",
    "coordinate_origin",
}
_ALLOWED_CITY_MODEL_KEYS = {"description", "name"}
_ALLOWED_GEOMETRY_SOURCE_KEYS = {
    "type",
    "path",
    "target_building_id",
    "target_pv_id",
    "target_zone_part_id",
}
_ALLOWED_GEOMETRY_SOURCE_TYPES = {f"step-renodat-lod{n}" for n in range(5)} | {
    f"step-zonepart-lod{n}" for n in range(4)
}


class InputFileError(ValueError):
    """Raised when a JSON feature input file is invalid."""


def load_feature_collection(path: PathLike) -> dict[str, Any]:
    """Load and validate a JSON feature collection from *path*."""
    input_path = Path(path)
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputFileError(f"Input file not found: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise InputFileError(
            f"Invalid JSON in {input_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    validate_feature_collection(
        data,
        source=str(input_path),
        base_path=input_path.parent,
    )
    _normalize_geometry_source_paths(data, input_path.parent)
    return data


def validate_feature_collection(
    data: Mapping[str, Any],
    *,
    source: str = "input",
    base_path: PathLike | None = None,
) -> None:
    """Validate the repository's JSON input format (schema_version 2)."""
    if not isinstance(data, dict):
        raise InputFileError(f"{source}: top-level JSON value must be an object")

    unexpected_top_level = sorted(set(data) - _ALLOWED_TOP_LEVEL_KEYS)
    if unexpected_top_level:
        raise InputFileError(
            f"{source}: unexpected top-level key(s): {', '.join(unexpected_top_level)}"
        )

    if data.get("schema_version") != 2:
        raise InputFileError(f"{source}: schema_version must be 2")

    if "$schema" in data and not isinstance(data["$schema"], str):
        raise InputFileError(f"{source}: $schema must be a string when provided")

    city_model = data.get("city_model")
    if not isinstance(city_model, dict):
        raise InputFileError(f"{source}: city_model must be an object")

    unexpected_city_model = sorted(set(city_model) - _ALLOWED_CITY_MODEL_KEYS)
    if unexpected_city_model:
        raise InputFileError(
            f"{source}: unexpected city_model key(s): {', '.join(unexpected_city_model)}"
        )

    for key, value in city_model.items():
        if not isinstance(value, str):
            raise InputFileError(f"{source}: city_model.{key} must be a string")

    features = data.get("features")
    if not isinstance(features, list):
        raise InputFileError(f"{source}: features must be an array")

    feature_ids: set[str] = set()
    feature_types_by_id: dict[str, str] = {}

    for index, feature in enumerate(features):
        _validate_feature(feature, index, source)
        gml_id = feature["id"].strip()
        if gml_id in feature_ids:
            raise InputFileError(
                f"{source}: features[{index}].id duplicates {gml_id!r}"
            )
        feature_ids.add(gml_id)
        feature_types_by_id[gml_id] = feature["type"]

    for index, feature in enumerate(features):
        parent_id = feature.get("parent")
        if parent_id is None:
            continue
        if not isinstance(parent_id, str) or not parent_id.strip():
            raise InputFileError(
                f"{source}: features[{index}].parent must be a non-empty string when provided"
            )
        if parent_id not in feature_ids:
            raise InputFileError(
                f"{source}: features[{index}].parent references missing id {parent_id!r}"
            )

    geometry_sources = data.get("geometry_sources", [])
    if not isinstance(geometry_sources, list):
        raise InputFileError(f"{source}: geometry_sources must be an array when provided")

    for index, geometry_source in enumerate(geometry_sources):
        _validate_geometry_source(
            geometry_source,
            index=index,
            source=source,
            feature_ids=feature_ids,
            feature_types_by_id=feature_types_by_id,
            base_path=Path(base_path) if base_path is not None else None,
        )


def build_city_model_from_feature_collection(
    data: dict[str, Any],
    *,
    base_path: PathLike | None = None,
) -> CityModel:
    """Build a CityModel from validated feature collection data."""
    validate_feature_collection(data, base_path=base_path)
    if base_path is not None:
        _normalize_geometry_source_paths(data, Path(base_path))

    city_model_meta = data["city_model"]
    model = CityModel(
        gml_description=city_model_meta.get("description"),
        gml_name=city_model_meta.get("name"),
    )

    # Build all xsdata objects from feature definitions
    id_index: dict[str, Any] = {}
    rows: list[tuple[str | None, str | None, Any]] = []

    for feature in data["features"]:
        type_string = feature["type"]
        cls = resolve_class(type_string)

        # Extract attribute data (everything except meta keys)
        attrs = {k: v for k, v in feature.items() if k not in _FEATURE_META_KEYS}

        # "id" in the JSON maps to "id" on the xsdata class (gml:id attribute)
        obj = build_from_dict(cls, attrs)

        parent_id = feature.get("parent")
        parent_field = feature.get("parent_field")
        rows.append((parent_id, parent_field, obj))

        gml_id = feature.get("id")
        if gml_id:
            id_index[gml_id] = obj

    # Attach children to parents
    for parent_id, parent_field, obj in rows:
        if parent_id is None:
            continue
        parent_obj = id_index.get(parent_id)
        if parent_obj is None:
            raise InputFileError(
                f"parent {parent_id!r} not found "
                f"(referenced by {getattr(obj, 'id', '?')!r})"
            )
        attach_child(parent_obj, obj, field_hint=parent_field)

    # Add top-level features as cityObjectMembers
    for parent_id, _parent_field, obj in rows:
        if parent_id is None:
            model.add(obj)

    # Apply geometry
    raw_origin = data.get("coordinate_origin")
    if raw_origin is not None:
        if not isinstance(raw_origin, list) or len(raw_origin) != 3:
            raise InputFileError("coordinate_origin must be an array of 3 numbers [x, y, z]")
        origin = (float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2]))
    else:
        origin = (0.0, 0.0, 0.0)

    apply_geometry_sources(model, data.get("geometry_sources", []), origin=origin)
    return model


def load_city_model_from_feature_collection(path: PathLike) -> CityModel:
    """Load, validate, and build a CityModel from a JSON feature file."""
    input_path = Path(path)
    data = load_feature_collection(input_path)
    return build_city_model_from_feature_collection(data, base_path=input_path.parent)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_feature(
    feature: Any,
    index: int,
    source: str,
) -> None:
    if not isinstance(feature, dict):
        raise InputFileError(f"{source}: features[{index}] must be an object")

    type_string = feature.get("type")
    if not isinstance(type_string, str) or not type_string.strip():
        raise InputFileError(
            f"{source}: features[{index}].type must be a non-empty string "
            f"like 'bldg:Building' or 'nrg3:Energy'"
        )

    # Validate that the type resolves to a known xsdata class
    try:
        resolve_class(type_string)
    except ValueError as exc:
        raise InputFileError(
            f"{source}: features[{index}].type: {exc}"
        ) from exc

    gml_id = feature.get("id")
    if not isinstance(gml_id, str) or not gml_id.strip():
        raise InputFileError(
            f"{source}: features[{index}].id must be a non-empty string"
        )


def _validate_geometry_source(
    geometry_source: Any,
    *,
    index: int,
    source: str,
    feature_ids: set[str],
    feature_types_by_id: Mapping[str, str],
    base_path: Path | None,
) -> None:
    if not isinstance(geometry_source, dict):
        raise InputFileError(f"{source}: geometry_sources[{index}] must be an object")

    unexpected_keys = sorted(set(geometry_source) - _ALLOWED_GEOMETRY_SOURCE_KEYS)
    if unexpected_keys:
        raise InputFileError(
            f"{source}: geometry_sources[{index}] has unexpected key(s): {', '.join(unexpected_keys)}"
        )

    source_type = geometry_source.get("type")
    if not isinstance(source_type, str) or source_type not in _ALLOWED_GEOMETRY_SOURCE_TYPES:
        raise InputFileError(
            f"{source}: geometry_sources[{index}].type must be one of: {', '.join(sorted(_ALLOWED_GEOMETRY_SOURCE_TYPES))}"
        )

    path_value = geometry_source.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise InputFileError(f"{source}: geometry_sources[{index}].path must be a non-empty string")

    is_zonepart_type = source_type.startswith("step-zonepart-")

    if is_zonepart_type:
        target_zone_part_id = geometry_source.get("target_zone_part_id")
        if not isinstance(target_zone_part_id, str) or not target_zone_part_id.strip():
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_zone_part_id must be a non-empty string"
            )
        if target_zone_part_id not in feature_ids:
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_zone_part_id references missing id {target_zone_part_id!r}"
            )
    else:
        target_building_id = geometry_source.get("target_building_id")
        if not isinstance(target_building_id, str) or not target_building_id.strip():
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_building_id must be a non-empty string"
            )
        if target_building_id not in feature_ids:
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_building_id references missing id {target_building_id!r}"
            )

        target_pv_id = geometry_source.get("target_pv_id")
        if target_pv_id is not None:
            if not isinstance(target_pv_id, str) or not target_pv_id.strip():
                raise InputFileError(
                    f"{source}: geometry_sources[{index}].target_pv_id must be a non-empty string when provided"
                )
            if target_pv_id not in feature_ids:
                raise InputFileError(
                    f"{source}: geometry_sources[{index}].target_pv_id references missing id {target_pv_id!r}"
                )

    if base_path is not None:
        resolved_path = _resolve_geometry_source_path(path_value, base_path)
        if not resolved_path.is_file():
            raise InputFileError(
                f"{source}: geometry_sources[{index}].path does not exist: {resolved_path}"
            )


def _normalize_geometry_source_paths(data: dict[str, Any], base_path: Path) -> None:
    geometry_sources = data.get("geometry_sources")
    if not isinstance(geometry_sources, list):
        return

    for geometry_source in geometry_sources:
        path_value = geometry_source.get("path")
        if isinstance(path_value, str) and path_value.strip():
            geometry_source["path"] = str(_resolve_geometry_source_path(path_value, base_path))


def _resolve_geometry_source_path(path_value: str, base_path: Path) -> Path:
    source_path = Path(path_value)
    if not source_path.is_absolute():
        source_path = base_path / source_path
    return source_path.resolve()
