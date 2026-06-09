"""Load data-only feature collections into CityGML models.

Each feature in the input JSON is a flat dict with ``type``, ``id``,
``parent``, ``parent_field``, and xsdata field names as keys. All object
construction is delegated to the generic ``mapping`` module: no
feature-type-specific code lives here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import boundary_attributes, construction_mapping
from .core import CityModel
from .derived_attributes import apply_derived_attributes
from .errors import InputFileError
from .geometry import (
    GEOMETRY_SOURCE_SPECS,
    SUPPORTED_GEOMETRY_SOURCE_TYPES,
    apply_device_relations,
    apply_geometry_sources,
)
from .mapping import attach_child, build_from_dict, resolve_class
from .namespaces import DEFAULT_SRS_DIMENSION, DEFAULT_SRS_NAME

__all__ = [
    "InputFileError",
    "build_city_model_from_feature_collection",
    "load_feature_collection",
    "validate_feature_collection",
]

PathLike = str | Path

# XML 1.0 NCName: must start with a letter or '_' and contain only NCNameChar.
# We use a conservative ASCII subset; the XSD permits Unicode letters/digits,
# but tooling interoperability is far better with ASCII-only IDs.
_NCNAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")

# Keys that live at the feature level, not passed to build_from_dict.
_FEATURE_META_KEYS = frozenset({"type", "parent", "parent_field", "related_to"})

_ALLOWED_TOP_LEVEL_KEYS = {
    "$schema",
    "city_model",
    "features",
    "geometry_sources",
    "coordinate_origin",
    "construction_mapping",
    "srs_name",
    "srs_dimension",
    "file_header",
}
_ALLOWED_CITY_MODEL_KEYS = {"description", "name"}

# Union of ``target_*`` fields across every registered geometry-source spec,
# so adding a new spec that references a new target field is automatically
# accepted by the validator. The spec is the single source of truth.
_ALLOWED_GEOMETRY_SOURCE_KEYS: frozenset[str] = frozenset(
    {"type", "path"}
    | {field_name for spec in GEOMETRY_SOURCE_SPECS.values() for field_name in spec.target_fields}
)

# Parent-type constraints. Keys are child feature type strings; values are
# the set of feature type strings allowed as their ``parent``. Children not
# listed here accept any parent type the attachment machinery finds a slot
# for. Only add entries when the XSD's permissive ``issubclass`` match
# diverges from EnergyADE's intended containment hierarchy -- otherwise we
# duplicate schema knowledge that should live in the bindings.
#
# ``ZonePart`` is the canonical case: the XSD allows a ZonePart to slot
# directly under ``bldg:Building`` via ``ZonePropertyType``, but the
# Energy ADE 3.0 model specifies ``Building -> Zone -> ZonePart``. Silently
# accepting a ZonePart with a Building parent produces output that passes
# XSD validation but corrupts the thermal-zone hierarchy.
_ALLOWED_PARENT_TYPES: dict[str, frozenset[str]] = {
    "nrg3:ZonePart": frozenset({"nrg3:Zone"}),
}


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
    """Validate the repository's JSON input format."""
    if not isinstance(data, dict):
        raise InputFileError(f"{source}: top-level JSON value must be an object")

    unexpected_top_level = sorted(set(data) - _ALLOWED_TOP_LEVEL_KEYS)
    if unexpected_top_level:
        raise InputFileError(
            f"{source}: unexpected top-level key(s): {', '.join(unexpected_top_level)}"
        )

    if "$schema" in data and not isinstance(data["$schema"], str):
        raise InputFileError(f"{source}: $schema must be a string when provided")

    if "file_header" in data:
        file_header = data["file_header"]
        if not isinstance(file_header, str) or not file_header.strip():
            raise InputFileError(f"{source}: file_header must be a non-empty string when provided")
        # The header is emitted as an XML comment; XML 1.0 forbids '--'
        # inside a comment, so reject it here rather than produce a file
        # that no XML parser can read.
        if "--" in file_header:
            raise InputFileError(
                f"{source}: file_header may not contain the sequence '--' "
                f"(forbidden inside an XML comment)"
            )

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

    parent_edges: dict[str, str] = {}
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
        gml_id = feature["id"].strip()
        if parent_id == gml_id:
            raise InputFileError(
                f"{source}: features[{index}].parent {parent_id!r} points at itself"
            )
        child_type = feature["type"]
        allowed_parents = _ALLOWED_PARENT_TYPES.get(child_type)
        if allowed_parents is not None:
            parent_type = feature_types_by_id[parent_id]
            if parent_type not in allowed_parents:
                raise InputFileError(
                    f"{source}: features[{index}] ({child_type}) cannot have a "
                    f"parent of type {parent_type!r}; allowed parent type(s): "
                    f"{', '.join(sorted(allowed_parents))}"
                )
        parent_edges[gml_id] = parent_id

    # Detect parent-chain cycles. Silent acceptance would let the builder
    # recurse forever (or produce nonsense hierarchies); better to reject
    # at the validator with a message naming the cycle.
    _check_parent_cycles(parent_edges, source=source)

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
        _validate_construction_mapping(
            data["construction_mapping"],
            features=features,
            source=source,
        )

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
    # Optional file-banner comment, emitted on write between the XML
    # declaration and the root element. Validated above.
    model.file_header = data.get("file_header")

    # Two-phase build: first construct every object and index by id, then
    # attach children / promote roots. The split is required because a
    # parent may appear after its child in the features list.
    id_index: dict[str, Any] = {}
    built: list[tuple[str | None, str | None, Any]] = []
    # ``related_to`` entries declared on feature dicts. Each entry is
    # ``{"relation": str, "target": str | {"name": str, "lod": int}}`` —
    # ``relation`` names a member of the EnergyADE 3.0 RelationTypeValue
    # codelist family (currently OtherRelationTypeValue: ``installedOn`` /
    # ``serving`` / ``connectedTo``), and ``target`` is a STEP layer name,
    # an LoD-pinned ``{name, lod}`` object (only for surface-targeted
    # relations), or a plain gml:id (for feature-targeted relations).
    # The validator dispatches on the relation's registered target_kind
    # (see citygml_energy.device_relations.RELATION_KINDS). Deferred until
    # after geometry apply because referenced surface gml:ids don't exist
    # until then. Each device's parsed list is a sequence of
    # ``(relation_name, target_ref)`` tuples in author order; output
    # ``<nrg3:relatedTo>`` siblings preserve that order.
    related_to_by_device: dict[str, list[tuple[str, Any]]] = {}

    for index, feature in enumerate(data["features"]):
        cls = resolve_class(feature["type"])
        attrs = {k: v for k, v in feature.items() if k not in _FEATURE_META_KEYS}
        try:
            obj = build_from_dict(cls, attrs)
        except (TypeError, ValueError) as exc:
            raise InputFileError(
                f"features[{index}] (id={feature.get('id')!r}, type={feature.get('type')!r}): {exc}"
            ) from exc
        built.append((feature.get("parent"), feature.get("parent_field"), obj))
        gml_id = feature.get("id")
        if gml_id:
            id_index[gml_id] = obj
            related_to = feature.get("related_to")
            if related_to:
                related_to_by_device[gml_id] = _parse_related_to(
                    related_to, feature_index=index, feature_id=gml_id
                )

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

    # ``related_to`` entries resolve against the surface_name_index
    # (populated during apply_geometry_sources) and the feature index,
    # so they must run *after* geometry attachment. The dispatcher in
    # apply_device_relations picks the resolver path per relation via
    # RELATION_KINDS — ``installedOn`` resolves through STEP-name lookup
    # with LoD collapse (ADR-0001); ``serving`` and other feature-typed
    # relations resolve through the feature index only.
    try:
        apply_device_relations(model, related_to_by_device)
    except ValueError as exc:
        raise InputFileError(str(exc)) from exc

    # Energy ADE 3.0 derived properties in one model walk. The seam owns
    # iteration, list-field discovery, idempotence, and verification;
    # the per-ADE compute functions live in ``construction_mapping``
    # and ``boundary_attributes``. Registration order matters: the
    # construction emitter writes ``layered_construction``; the
    # boundary thickness + heat-capacity emitters read it. Adding a
    # new ADE (Scenario, Noise, …) means dropping a sibling module and
    # appending its ``EMITTERS`` here. No edit to the seam itself.
    apply_derived_attributes(
        model,
        emitters=(*construction_mapping.EMITTERS, *boundary_attributes.EMITTERS),
        setups=boundary_attributes.SETUPS,
        construction_mapping=data.get("construction_mapping") or {},
    )

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


def _parse_related_to(
    raw: Any,
    *,
    feature_index: int,
    feature_id: str,
) -> list[tuple[str, Any]]:
    """Validate and unpack a feature's ``related_to`` field.

    Returns a list of ``(relation_name, target_ref)`` tuples in author
    order, ready for :func:`device_relations.apply_device_relations`.

    Shape validation happens here; semantic resolution (does the target
    name exist in the model at the requested LoD?) happens later in the
    resolver, after geometry attachment. The split keeps shape errors
    pre-geometry and resolution errors post-geometry, so error sources
    are unambiguous to the author.

    Per-relation target-shape rules come from
    :data:`device_relations.RELATION_KINDS`: ``target_kind="surface"``
    accepts a bare string (highest-LoD-wins) or an
    ``{"name": str, "lod": int}`` object (LoD-pinned per ADR-0001);
    ``target_kind="feature"`` accepts only a bare gml:id string.
    """
    # Local import to keep input_loader's static dependency surface flat
    # and avoid a circular import: device_relations imports nothing from
    # this module, but the registry is owned there.
    from .device_relations import RELATION_KINDS

    if not isinstance(raw, list) or not raw:
        raise InputFileError(
            f"features[{feature_index}] (id={feature_id!r}): 'related_to' must "
            f"be a non-empty list of {{'relation': str, 'target': ...}} entries, "
            f"got {raw!r}"
        )

    parsed: list[tuple[str, Any]] = []
    for entry_index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise InputFileError(
                f"features[{feature_index}] (id={feature_id!r}): "
                f"'related_to'[{entry_index}] must be an object "
                f"{{'relation': str, 'target': ...}}; got {type(entry).__name__}"
            )
        extra = set(entry) - {"relation", "target"}
        if extra:
            raise InputFileError(
                f"features[{feature_index}] (id={feature_id!r}): "
                f"'related_to'[{entry_index}] has unexpected keys "
                f"{sorted(extra)!r}; only 'relation' and 'target' are allowed"
            )
        relation = entry.get("relation")
        target = entry.get("target")
        if not isinstance(relation, str) or not relation:
            raise InputFileError(
                f"features[{feature_index}] (id={feature_id!r}): "
                f"'related_to'[{entry_index}].relation must be a non-empty "
                f"string naming a member of the EnergyADE 3.0 RelationTypeValue "
                f"codelist family (e.g. 'installedOn', 'serving')"
            )
        if relation not in RELATION_KINDS:
            known = ", ".join(sorted(RELATION_KINDS)) or "(no relations registered)"
            raise InputFileError(
                f"features[{feature_index}] (id={feature_id!r}): "
                f"'related_to'[{entry_index}].relation = {relation!r} is not "
                f"registered. Known relations: {known}"
            )
        _validate_related_to_target(
            target,
            target_kind=RELATION_KINDS[relation].target_kind,
            relation=relation,
            entry_index=entry_index,
            feature_index=feature_index,
            feature_id=feature_id,
        )
        parsed.append((relation, target))
    return parsed


def _validate_related_to_target(
    target: Any,
    *,
    target_kind: str,
    relation: str,
    entry_index: int,
    feature_index: int,
    feature_id: str,
) -> None:
    """Validate a ``related_to`` entry's ``target`` against its target_kind."""
    if target_kind == "surface":
        if isinstance(target, str):
            if not target:
                raise InputFileError(
                    f"features[{feature_index}] (id={feature_id!r}): "
                    f"'related_to'[{entry_index}].target must be a non-empty "
                    f"string (bare STEP layer name or gml:id) or "
                    f"{{'name': str, 'lod': int}}"
                )
            return
        if isinstance(target, dict):
            extra = set(target) - {"name", "lod"}
            if extra:
                raise InputFileError(
                    f"features[{feature_index}] (id={feature_id!r}): "
                    f"'related_to'[{entry_index}].target has unexpected keys "
                    f"{sorted(extra)!r}; only 'name' and 'lod' are allowed in "
                    f"the LoD-pinned object form"
                )
            name = target.get("name")
            lod = target.get("lod")
            if not isinstance(name, str) or not name:
                raise InputFileError(
                    f"features[{feature_index}] (id={feature_id!r}): "
                    f"'related_to'[{entry_index}].target.name must be a "
                    f"non-empty string"
                )
            if not isinstance(lod, int) or isinstance(lod, bool) or lod < 0:
                raise InputFileError(
                    f"features[{feature_index}] (id={feature_id!r}): "
                    f"'related_to'[{entry_index}].target.lod must be a "
                    f"non-negative integer"
                )
            return
        raise InputFileError(
            f"features[{feature_index}] (id={feature_id!r}): "
            f"'related_to'[{entry_index}].target for relation {relation!r} "
            f"must be a string or {{'name': str, 'lod': int}}; got "
            f"{type(target).__name__}"
        )

    # target_kind == "feature"
    if not isinstance(target, str) or not target:
        raise InputFileError(
            f"features[{feature_index}] (id={feature_id!r}): "
            f"'related_to'[{entry_index}].target for relation {relation!r} "
            f"must be a non-empty gml:id string; the {{'name', 'lod'}} object "
            f"form is only valid for surface-targeted relations"
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
        raise InputFileError(f"{source}: geometry_sources[{index}].path must be a non-empty string")

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
            f"{source}: geometry_sources[{index}].{field_name} references missing id {target_id!r}"
        )
    actual_type = feature_types_by_id.get(target_id)
    if actual_type != expected_type:
        raise InputFileError(
            f"{source}: geometry_sources[{index}].{field_name} expects a feature of type "
            f"{expected_type!r} but {target_id!r} is {actual_type!r}"
        )


_ALLOWED_CONSTRUCTION_MAPPING_KEYS = {"by_type", "by_id"}


def _collect_library_member_ids(features: list[Any]) -> set[str]:
    """Return the set of ``id`` values inside every ``library_member`` entry.

    LayeredConstruction / SolidMaterial / Gas ids live one level below the
    library feature, so they do not appear in the top-level ``features`` id
    set. We scan the nested ``library_member`` dicts to recover them and
    cross-check every ``construction_mapping.by_id`` value against this
    set, making a typo impossible to miss.
    """
    ids: set[str] = set()
    for feature in features:
        if not isinstance(feature, dict):
            continue
        members = feature.get("library_member")
        if not isinstance(members, list):
            continue
        for member in members:
            if not isinstance(member, dict):
                continue
            for nested in member.values():
                if isinstance(nested, dict):
                    member_id = nested.get("id")
                    if isinstance(member_id, str) and member_id.strip():
                        ids.add(member_id.strip())
    return ids


def _check_parent_cycles(edges: Mapping[str, str], *, source: str) -> None:
    """Detect cycles in the parent-of relation.

    Walks each start node along ``edges`` until it either terminates at a
    root (no parent) or revisits a node already seen on the walk. The latter
    is a cycle; since self-references are rejected upstream, any cycle here
    is length >= 2.
    """
    for start in edges:
        seen: list[str] = []
        node: str | None = start
        while node is not None:
            if node in seen:
                cycle = " -> ".join(seen[seen.index(node) :] + [node])
                raise InputFileError(f"{source}: cyclic parent relation detected: {cycle}")
            seen.append(node)
            node = edges.get(node)


def _validate_construction_mapping(
    mapping: Any,
    *,
    features: list[Any],
    source: str,
) -> None:
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
            raise InputFileError(f"{source}: construction_mapping.{sub_key} must be an object")
        for k, v in sub.items():
            if not isinstance(k, str) or not k.strip():
                raise InputFileError(
                    f"{source}: construction_mapping.{sub_key} keys must be non-empty strings"
                )
            if not isinstance(v, str) or not v.strip():
                raise InputFileError(
                    f"{source}: construction_mapping.{sub_key}[{k!r}] must be a non-empty string"
                )

    # Cross-check every referenced construction id against the library.
    # A typo on the value side used to land silently: the mapping applier
    # just skips surfaces whose resolved id isn't there, producing GML
    # without a construction reference and no warning.
    library_ids = _collect_library_member_ids(features)
    if library_ids:
        referenced = set(mapping.get("by_type", {}).values()) | set(
            mapping.get("by_id", {}).values()
        )
        dangling = sorted(v for v in referenced if v not in library_ids)
        if dangling:
            raise InputFileError(
                f"{source}: construction_mapping references unknown construction "
                f"id(s) (no library_member declares these): {', '.join(dangling)}"
            )


def _resolve_geometry_source_paths(data: dict[str, Any], base_path: Path) -> dict[str, Any]:
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
                source_copy["path"] = str(_resolve_geometry_source_path(path_value, base_path))
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
