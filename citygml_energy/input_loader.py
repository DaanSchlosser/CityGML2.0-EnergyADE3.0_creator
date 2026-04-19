"""Load data-only feature collections into CityGML models.

Supports the schema_version 2 JSON format where each feature is a flat dict
with ``type``, ``id``, ``parent``, ``parent_field``, and xsdata field names
as keys.  All object construction is delegated to the generic ``mapping``
module: no feature-type-specific code lives here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .core import CityModel
from .geometry import (
    GEOMETRY_SOURCE_SPECS,
    SUPPORTED_GEOMETRY_SOURCE_TYPES,
    apply_construction_mapping,
    apply_device_relations,
    apply_geometry_sources,
)
from .mapping import attach_child, build_from_dict, resolve_class
from .namespaces import DEFAULT_SRS_DIMENSION, DEFAULT_SRS_NAME

PathLike = str | Path

# XML 1.0 NCName: must start with a letter or '_' and contain only NCNameChar.
# We use a conservative ASCII subset; the XSD permits Unicode letters/digits,
# but tooling interoperability is far better with ASCII-only IDs.
_NCNAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")

# Keys that live at the feature level, not passed to build_from_dict.
_FEATURE_META_KEYS = frozenset({"type", "parent", "parent_field", "installed_on"})

_ALLOWED_TOP_LEVEL_KEYS = {
    "$schema",
    "schema_version",
    "city_model",
    "features",
    "geometry_sources",
    "coordinate_origin",
    "construction_mapping",
    "srs_name",
    "srs_dimension",
}
_ALLOWED_CITY_MODEL_KEYS = {"description", "name"}

# Union of ``target_*`` fields across every registered geometry-source spec,
# so adding a new spec that references a new target field is automatically
# accepted by the validator. The spec is the single source of truth.
_ALLOWED_GEOMETRY_SOURCE_KEYS: frozenset[str] = frozenset(
    {"type", "path"}
    | {
        field_name
        for spec in GEOMETRY_SOURCE_SPECS.values()
        for field_name in spec.target_fields
    }
)


class InputFileError(ValueError):
    """Raised when a JSON feature input file is invalid."""


def load_feature_collection(path: PathLike) -> dict[str, Any]:
    """Load and validate a JSON feature collection from *path*.

    Returns a fully validated dict with geometry-source paths resolved
    relative to *path*'s parent directory.
    """
    input_path = Path(path)
    try:
        raw_text = input_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InputFileError(f"Input file not found: {input_path}") from exc
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise InputFileError(
            f"Invalid JSON in {input_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    validate_feature_collection(
        data,
        source=str(input_path),
        base_path=input_path.parent,
    )
    return _resolve_geometry_source_paths(data, input_path.parent)


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
            raise InputFileError(f"{source}: features[{index}].id duplicates {gml_id!r}")
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

    if "construction_mapping" in data:
        _validate_construction_mapping(data["construction_mapping"], source=source)

    if "srs_name" in data:
        srs_name = data["srs_name"]
        if not isinstance(srs_name, str) or not srs_name.strip():
            raise InputFileError(f"{source}: srs_name must be a non-empty string when provided")

    if "srs_dimension" in data:
        srs_dimension = data["srs_dimension"]
        if (
            isinstance(srs_dimension, bool)
            or not isinstance(srs_dimension, int)
            or srs_dimension not in (2, 3)
        ):
            raise InputFileError(
                f"{source}: srs_dimension must be 2 or 3 when provided (got {srs_dimension!r})"
            )


def build_city_model_from_feature_collection(
    data: dict[str, Any],
    *,
    base_path: PathLike | None = None,
    _already_validated: bool = False,
) -> CityModel:
    """Build a CityModel from feature collection data.

    Validates *data* unless ``_already_validated`` is set (used by
    :func:`load_city_model_from_feature_collection` to avoid re-validating
    the same dict twice). When *base_path* is given, geometry-source paths
    are resolved relative to it.
    """
    if not _already_validated:
        validate_feature_collection(
            data,
            source=str(base_path) if base_path is not None else "input",
            base_path=base_path,
        )
        if base_path is not None:
            data = _resolve_geometry_source_paths(data, Path(base_path))

    city_model_meta = data["city_model"]
    model = CityModel(
        gml_description=city_model_meta.get("description"),
        gml_name=city_model_meta.get("name"),
    )

    # Two-phase build: first construct every object and index by id, then
    # attach children / promote roots. The split is required because a
    # parent may appear after its child in the features list.
    id_index: dict[str, Any] = {}
    built: list[tuple[str | None, str | None, Any]] = []
    # Device-to-surface relations declared on feature dicts via the
    # pseudo-field ``installed_on``. Deferred until after geometry apply
    # because the referenced surface gml:ids don't exist yet.
    device_relations: dict[str, list[str]] = {}

    for index, feature in enumerate(data["features"]):
        cls = resolve_class(feature["type"])
        attrs = {k: v for k, v in feature.items() if k not in _FEATURE_META_KEYS}
        try:
            obj = build_from_dict(cls, attrs)
        except (TypeError, ValueError) as exc:
            raise InputFileError(
                f"features[{index}] (id={feature.get('id')!r}, "
                f"type={feature.get('type')!r}): {exc}"
            ) from exc
        built.append((feature.get("parent"), feature.get("parent_field"), obj))
        gml_id = feature.get("id")
        if gml_id:
            id_index[gml_id] = obj
            installed_on = feature.get("installed_on")
            if installed_on:
                if not (
                    isinstance(installed_on, list)
                    and all(isinstance(t, str) and t for t in installed_on)
                ):
                    raise InputFileError(
                        f"features[{index}] (id={gml_id!r}): 'installed_on' must be a "
                        f"non-empty list of strings, got {installed_on!r}"
                    )
                device_relations[gml_id] = list(installed_on)

    for parent_id, parent_field, obj in built:
        if parent_id is None:
            model.add(obj)
            continue
        parent_obj = id_index.get(parent_id)
        if parent_obj is None:
            raise InputFileError(
                f"parent {parent_id!r} not found (referenced by {getattr(obj, 'id', '?')!r})"
            )
        attach_child(parent_obj, obj, field_hint=parent_field)

    # Apply geometry
    raw_origin = data.get("coordinate_origin")
    if raw_origin is not None:
        if (
            not isinstance(raw_origin, list)
            or len(raw_origin) != 3
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in raw_origin)
        ):
            raise InputFileError(
                f"coordinate_origin must be an array of 3 numbers [x, y, z] (got {raw_origin!r})"
            )
        origin = (float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2]))
    else:
        origin = (0.0, 0.0, 0.0)

    srs_name = data.get("srs_name", DEFAULT_SRS_NAME)
    srs_dimension = data.get("srs_dimension", DEFAULT_SRS_DIMENSION)

    apply_geometry_sources(
        model,
        data.get("geometry_sources", []),
        origin=origin,
        srs_name=srs_name,
        srs_dimension=srs_dimension,
    )

    # Device-to-surface relations resolve against the surface_name_index
    # populated during apply_geometry_sources, so they must run *after*
    # geometry attachment.
    try:
        apply_device_relations(model, device_relations)
    except ValueError as exc:
        raise InputFileError(str(exc)) from exc

    construction_mapping = data.get("construction_mapping")
    if construction_mapping is not None:
        apply_construction_mapping(model, construction_mapping)

    return model


def load_city_model_from_feature_collection(path: PathLike) -> CityModel:
    """Load, validate, and build a CityModel from a JSON feature file."""
    input_path = Path(path)
    data = load_feature_collection(input_path)
    return build_city_model_from_feature_collection(
        data, base_path=input_path.parent, _already_validated=True
    )


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
        raise InputFileError(f"{source}: features[{index}].type: {exc}") from exc

    gml_id = feature.get("id")
    if not isinstance(gml_id, str) or not gml_id.strip():
        raise InputFileError(f"{source}: features[{index}].id must be a non-empty string")
    if not _NCNAME_RE.match(gml_id):
        raise InputFileError(
            f"{source}: features[{index}].id {gml_id!r} is not a valid XML NCName "
            f"(must start with a letter or '_' and contain only letters, digits, "
            f"'.', '-', or '_'; no spaces or colons)"
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
            f"{source}: geometry_sources[{index}] has unexpected key(s): "
            f"{', '.join(unexpected_keys)}"
        )

    source_type = geometry_source.get("type")
    if not isinstance(source_type, str) or source_type not in SUPPORTED_GEOMETRY_SOURCE_TYPES:
        raise InputFileError(
            f"{source}: geometry_sources[{index}].type must be one of: "
            + ", ".join(sorted(SUPPORTED_GEOMETRY_SOURCE_TYPES))
        )

    path_value = geometry_source.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise InputFileError(
            f"{source}: geometry_sources[{index}].path must be a non-empty string"
        )

    if base_path is None and not Path(path_value).is_absolute():
        raise InputFileError(
            f"{source}: geometry_sources[{index}].path is relative ({path_value!r}) "
            f"but no base_path was provided to resolve it against"
        )

    # Drive target validation from the spec so new source types (or new
    # target fields on existing ones) need no loader changes.
    spec = GEOMETRY_SOURCE_SPECS[source_type]
    for field_name, target_spec in spec.target_fields.items():
        _validate_geometry_target(
            geometry_source,
            field_name=field_name,
            expected_type=target_spec.xsd_type,
            index=index,
            source=source,
            feature_ids=feature_ids,
            feature_types_by_id=feature_types_by_id,
            required=target_spec.required,
        )

    # Reject target-like keys that this spec doesn't declare. Prevents
    # typos like `target_pv_id` on a zonepart source being silently ignored.
    target_like = {k for k in geometry_source if k.startswith("target_")}
    unknown_targets = sorted(target_like - set(spec.target_fields))
    if unknown_targets:
        raise InputFileError(
            f"{source}: geometry_sources[{index}] has target key(s) not valid for "
            f"type {source_type!r}: {', '.join(unknown_targets)}"
        )

    if base_path is not None:
        resolved_path = _resolve_geometry_source_path(path_value, base_path)
        if not resolved_path.is_file():
            raise InputFileError(
                f"{source}: geometry_sources[{index}].path does not exist: {resolved_path}"
            )


def _validate_geometry_target(
    geometry_source: dict[str, Any],
    *,
    field_name: str,
    expected_type: str,
    index: int,
    source: str,
    feature_ids: set[str],
    feature_types_by_id: Mapping[str, str],
    required: bool,
) -> None:
    """Check that ``field_name`` references a feature of ``expected_type``."""
    target_id = geometry_source.get(field_name)
    if target_id is None:
        if required:
            raise InputFileError(
                f"{source}: geometry_sources[{index}].{field_name} must be a non-empty string"
            )
        return
    if not isinstance(target_id, str) or not target_id.strip():
        raise InputFileError(
            f"{source}: geometry_sources[{index}].{field_name} must be a non-empty string"
            + ("" if required else " when provided")
        )
    if target_id not in feature_ids:
        raise InputFileError(
            f"{source}: geometry_sources[{index}].{field_name} references missing id "
            f"{target_id!r}"
        )
    actual_type = feature_types_by_id.get(target_id)
    if actual_type != expected_type:
        raise InputFileError(
            f"{source}: geometry_sources[{index}].{field_name} expects a feature of type "
            f"{expected_type!r} but {target_id!r} is {actual_type!r}"
        )


_ALLOWED_CONSTRUCTION_MAPPING_KEYS = {"by_type", "by_id"}


def _validate_construction_mapping(mapping: Any, *, source: str) -> None:
    if not isinstance(mapping, dict):
        raise InputFileError(f"{source}: construction_mapping must be an object")

    unexpected = sorted(set(mapping) - _ALLOWED_CONSTRUCTION_MAPPING_KEYS)
    if unexpected:
        raise InputFileError(
            f"{source}: construction_mapping has unexpected key(s): {', '.join(unexpected)}"
        )

    for sub_key in _ALLOWED_CONSTRUCTION_MAPPING_KEYS:
        if sub_key not in mapping:
            continue
        sub = mapping[sub_key]
        if not isinstance(sub, dict):
            raise InputFileError(
                f"{source}: construction_mapping.{sub_key} must be an object"
            )
        for k, v in sub.items():
            if not isinstance(k, str) or not k.strip():
                raise InputFileError(
                    f"{source}: construction_mapping.{sub_key} keys must be non-empty strings"
                )
            if not isinstance(v, str) or not v.strip():
                raise InputFileError(
                    f"{source}: construction_mapping.{sub_key}[{k!r}] must be a non-empty string"
                )


def _resolve_geometry_source_paths(
    data: dict[str, Any], base_path: Path
) -> dict[str, Any]:
    """Return a shallow copy of *data* with geometry-source paths resolved.

    The input dict is left unmodified: both ``geometry_sources`` and each
    individual source dict are copied before mutation.
    """
    geometry_sources = data.get("geometry_sources")
    if not isinstance(geometry_sources, list):
        return data

    resolved_sources: list[Any] = []
    for geometry_source in geometry_sources:
        if isinstance(geometry_source, dict):
            path_value = geometry_source.get("path")
            if isinstance(path_value, str) and path_value.strip():
                source_copy = dict(geometry_source)
                source_copy["path"] = str(
                    _resolve_geometry_source_path(path_value, base_path)
                )
                resolved_sources.append(source_copy)
                continue
        resolved_sources.append(geometry_source)

    new_data = dict(data)
    new_data["geometry_sources"] = resolved_sources
    return new_data


def _resolve_geometry_source_path(path_value: str, base_path: Path) -> Path:
    source_path = Path(path_value)
    if not source_path.is_absolute():
        source_path = base_path / source_path
    return source_path.resolve()
