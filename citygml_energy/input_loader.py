"""Load data-only feature collections into CityGML models."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .core import CityModel
from .factory import FeatureFactory, list_feature_types
from .geometry import apply_geometry_sources
from .input_catalog import (
    FEATURE_REQUIRED_FIELDS,
    get_allowed_attribute_names,
    normalize_feature_attributes,
)

PathLike = str | Path

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
_ALLOWED_GEOMETRY_SOURCE_TYPES = {
    f"step-renodat-lod{n}" for n in range(5)
} | {
    f"step-zonepart-lod{n}" for n in range(4)
}
_ALLOWED_SCALAR_TYPES = (str, int, float, bool, type(None))


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
    """Validate the repository's JSON input format."""
    if not isinstance(data, dict):
        raise InputFileError(f"{source}: top-level JSON value must be an object")

    unexpected_top_level = sorted(set(data) - _ALLOWED_TOP_LEVEL_KEYS)
    if unexpected_top_level:
        raise InputFileError(
            f"{source}: unexpected top-level key(s): {', '.join(unexpected_top_level)}"
        )

    if data.get("schema_version") != 1:
        raise InputFileError(f"{source}: schema_version must be 1")

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

    supported_feature_types = set(list_feature_types())
    feature_ids: set[str] = set()

    feature_types_by_id: dict[str, str] = {}

    for index, feature in enumerate(features):
        _validate_feature(feature, index, source, supported_feature_types)
        gml_id = feature["attributes"]["gml_id"].strip()
        if gml_id in feature_ids:
            raise InputFileError(
                f"{source}: features[{index}].attributes.gml_id duplicates {gml_id!r}"
            )
        feature_ids.add(gml_id)
        feature_types_by_id[gml_id] = feature["feature_type"]

    for index, feature in enumerate(features):
        parent_id = feature["attributes"].get("gml_parent_id")
        if parent_id is None:
            continue
        if not isinstance(parent_id, str) or not parent_id.strip():
            raise InputFileError(
                f"{source}: features[{index}].attributes.gml_parent_id must be a non-empty string when provided"
            )
        if parent_id not in feature_ids:
            raise InputFileError(
                f"{source}: features[{index}].attributes.gml_parent_id references missing gml_id {parent_id!r}"
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

    city_model = data["city_model"]
    factory = FeatureFactory(
        description=city_model.get("description"),
        name=city_model.get("name"),
    )

    for feature in data["features"]:
        factory.add(
            feature["feature_type"],
            normalize_feature_attributes(
                feature["feature_type"],
                dict(feature["attributes"]),
            ),
        )

    model = factory.build()

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


def _validate_feature(
    feature: Any,
    index: int,
    source: str,
    supported_feature_types: set[str],
) -> None:
    if not isinstance(feature, dict):
        raise InputFileError(f"{source}: features[{index}] must be an object")

    unexpected_feature_keys = sorted(set(feature) - {"feature_type", "attributes"})
    if unexpected_feature_keys:
        raise InputFileError(
            f"{source}: features[{index}] has unexpected key(s): {', '.join(unexpected_feature_keys)}"
        )

    feature_type = feature.get("feature_type")
    if not isinstance(feature_type, str) or feature_type not in supported_feature_types:
        valid_types = ", ".join(sorted(supported_feature_types))
        raise InputFileError(
            f"{source}: features[{index}].feature_type must be one of: {valid_types}"
        )

    attributes = feature.get("attributes")
    if not isinstance(attributes, dict):
        raise InputFileError(f"{source}: features[{index}].attributes must be an object")

    unexpected_attribute_keys = sorted(set(attributes) - get_allowed_attribute_names(feature_type))
    if unexpected_attribute_keys:
        raise InputFileError(
            f"{source}: features[{index}].attributes contains unsupported key(s) for "
            f"{feature_type}: {', '.join(unexpected_attribute_keys)}"
        )

    gml_id = attributes.get("gml_id")
    if not isinstance(gml_id, str) or not gml_id.strip():
        raise InputFileError(
            f"{source}: features[{index}].attributes.gml_id must be a non-empty string"
        )

    try:
        normalize_feature_attributes(feature_type, attributes)
    except ValueError as exc:
        raise InputFileError(f"{source}: features[{index}].attributes {exc}") from exc

    for key, value in attributes.items():
        if not isinstance(key, str):
            raise InputFileError(f"{source}: features[{index}].attributes keys must be strings")
        if isinstance(value, dict):
            # Nested object for CodeValue/MeasureValue/ScaleValue
            _validate_nested_value(value, key, index, source)
        elif not isinstance(value, _ALLOWED_SCALAR_TYPES):
            raise InputFileError(
                f"{source}: features[{index}].attributes.{key} must be a scalar or nested object"
            )

    # Check XSD-required fields
    required = FEATURE_REQUIRED_FIELDS.get(feature_type, ())
    normalized = normalize_feature_attributes(feature_type, attributes)
    for req_key in required:
        val = normalized.get(req_key)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise InputFileError(
                f"{source}: features[{index}].attributes.{req_key} is required "
                f"for {feature_type} (XSD minOccurs=1)"
            )


_ALLOWED_NESTED_KEYS = {"value", "uom", "codeSpace"}


def _validate_nested_value(
    obj: dict[str, Any],
    attr_key: str,
    index: int,
    source: str,
) -> None:
    """Validate a nested CodeValue/MeasureValue/ScaleValue object."""
    unexpected = sorted(set(obj) - _ALLOWED_NESTED_KEYS)
    if unexpected:
        raise InputFileError(
            f"{source}: features[{index}].attributes.{attr_key} "
            f"has unexpected key(s): {', '.join(unexpected)}"
        )
    if "value" not in obj:
        raise InputFileError(
            f"{source}: features[{index}].attributes.{attr_key} "
            f"nested object must contain a 'value' key"
        )
    for k, v in obj.items():
        if not isinstance(v, _ALLOWED_SCALAR_TYPES):
            raise InputFileError(
                f"{source}: features[{index}].attributes.{attr_key}.{k} "
                f"must be a scalar JSON value"
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
                f"{source}: geometry_sources[{index}].target_zone_part_id references missing gml_id {target_zone_part_id!r}"
            )
        if feature_types_by_id.get(target_zone_part_id) not in {
            "nrg3_Zone",
            "nrg3_ZonePart",
        }:
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_zone_part_id must reference a Zone or ZonePart"
            )
    else:
        target_building_id = geometry_source.get("target_building_id")
        if not isinstance(target_building_id, str) or not target_building_id.strip():
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_building_id must be a non-empty string"
            )
        if target_building_id not in feature_ids:
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_building_id references missing gml_id {target_building_id!r}"
            )
        if feature_types_by_id.get(target_building_id) not in {
            "bldg_Building",
            "bldg_BuildingPart",
        }:
            raise InputFileError(
                f"{source}: geometry_sources[{index}].target_building_id must reference a building or building part"
            )

        target_pv_id = geometry_source.get("target_pv_id")
        if target_pv_id is not None:
            if not isinstance(target_pv_id, str) or not target_pv_id.strip():
                raise InputFileError(
                    f"{source}: geometry_sources[{index}].target_pv_id must be a non-empty string when provided"
                )
            if target_pv_id not in feature_ids:
                raise InputFileError(
                    f"{source}: geometry_sources[{index}].target_pv_id references missing gml_id {target_pv_id!r}"
                )
            if feature_types_by_id.get(target_pv_id) != "nrg3_PhotovoltaicCollector":
                raise InputFileError(
                    f"{source}: geometry_sources[{index}].target_pv_id must reference an nrg3_PhotovoltaicCollector"
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

