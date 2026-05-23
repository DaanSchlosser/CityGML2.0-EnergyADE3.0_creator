"""Regenerate ``schemas/citygml_energy_input.schema.json`` from the bindings.

The JSON schema is a thin convenience for IDEs (VS Code autocomplete,
inline validation); the loader does not read it at runtime. Rather than
hand-maintain it, we derive:

* the allowed geometry-source ``type`` values from
  :data:`citygml_energy.geometry.GEOMETRY_SOURCE_SPECS`;
* the ``target_*`` keys and their required/optional status from the same
  specs;
* the feature ``type`` enum from the xsdata class registry, so every
  ``prefix:ElementName`` the bindings expose is suggested as a valid
  feature type.

Run ``python tools/generate_input_schema.py`` after regenerating bindings
or changing any geometry-source spec; a CI test
(``tests/test_input_schema.py``) refuses to let the committed schema drift
out of sync.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "citygml_energy_input.schema.json"

# Make the package importable when this script is run as ``python tools/...``.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from citygml_energy.device_relations import RELATION_KINDS
from citygml_energy.geometry import (
    GEOMETRY_SOURCE_SPECS,
    GeometrySourceSpec,
)
from citygml_energy.mapping import list_available_types
from citygml_energy.namespaces import DEFAULT_SRS_NAME


def _build_geometry_source_branches() -> list[dict[str, Any]]:
    """One ``oneOf`` branch per geometry-source type, required fields front-and-centre."""
    return [
        _branch_for_spec(spec)
        for spec in sorted(GEOMETRY_SOURCE_SPECS.values(), key=lambda s: s.source_type)
    ]


def _build_related_to_branches() -> list[dict[str, Any]]:
    """One ``oneOf`` branch per registered :class:`RelationKind`.

    The branches share the ``{"relation": str, "target": ...}`` shape but
    differ on the ``target`` schema by ``target_kind``:

    * ``surface`` accepts a bare string OR the LoD-pinned object form
      ``{"name": str, "lod": int}`` (per ADR-0001).
    * ``feature`` accepts a bare gml:id string only; the object form is
      intentionally rejected because LoD has no meaning for a feature
      reference and a typo against a STEP surface name would otherwise
      silently resolve as ``feature``-shaped.

    Sorting by codelist_value gives a deterministic schema output so
    repeated regenerations diff cleanly.
    """
    branches: list[dict[str, Any]] = []
    for relation_name in sorted(RELATION_KINDS):
        kind = RELATION_KINDS[relation_name]
        if kind.target_kind == "surface":
            target_schema: dict[str, Any] = {
                "oneOf": [
                    {
                        "type": "string",
                        "minLength": 1,
                        "description": (
                            "Bare STEP layer name (e.g. 'RoofSurface_02') or a "
                            "gml:id present in the model. Resolves to the "
                            "highest LoD that carries the name; falls back to "
                            "the gml:id index when no STEP-name match is found."
                        ),
                    },
                    {
                        "type": "object",
                        "required": ["name", "lod"],
                        "additionalProperties": False,
                        "properties": {
                            "name": {
                                "type": "string",
                                "minLength": 1,
                                "description": (
                                    "STEP layer name as it appears in the "
                                    "LoD-specific STEP file."
                                ),
                            },
                            "lod": {
                                "type": "integer",
                                "minimum": 0,
                                "description": (
                                    "Pin the relation to this specific LoD's "
                                    "representation of the named face. Use "
                                    "when bare-name resolution "
                                    "(highest-LoD-wins) is not what you want."
                                ),
                            },
                        },
                        "description": (
                            "Explicit (name, LoD) pair for unambiguous "
                            "surface targeting."
                        ),
                    },
                ],
            }
        else:  # target_kind == "feature"
            target_schema = {
                "type": "string",
                "minLength": 1,
                "description": (
                    "gml:id of the target feature. Resolved against the "
                    "feature index only; STEP-name lookup is intentionally "
                    "skipped so a typo against a surface name raises rather "
                    "than emitting a nonsense xlink to a surface gml:id."
                ),
            }
        branches.append({
            "type": "object",
            "required": ["relation", "target"],
            "additionalProperties": False,
            "properties": {
                "relation": {
                    "const": kind.codelist_value,
                    "description": (
                        f"{kind.codelist_value!r} from the EnergyADE 3.0 "
                        f"RelationTypeValue codelist family. "
                        f"Codespace: {kind.codespace}."
                    ),
                },
                "target": target_schema,
            },
        })
    return branches


def _branch_for_spec(spec: GeometrySourceSpec) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "type": {"const": spec.source_type},
        "path": {
            "type": "string",
            "minLength": 1,
            "description": (
                "Path to the STEP file (relative to this JSON file, or absolute)."
            ),
        },
    }
    for field_name, target_spec in spec.target_fields.items():
        properties[field_name] = {
            "type": "string",
            "minLength": 1,
            "description": (
                f"gml:id of the target {target_spec.xsd_type} feature."
                + ("" if target_spec.required else " Optional.")
            ),
        }

    required_fields = ["type", "path"] + list(spec.required_fields())
    return {
        "type": "object",
        "required": required_fields,
        "additionalProperties": False,
        "properties": properties,
    }


def _feature_type_enum() -> list[str]:
    """All ``prefix:ElementName`` strings exposed by the bindings, sorted."""
    return list_available_types()


def build_schema() -> dict[str, Any]:
    """Return the full JSON Schema document as a dict."""
    branches = _build_geometry_source_branches()
    feature_type_enum = _feature_type_enum()
    source_types = sorted(GEOMETRY_SOURCE_SPECS)

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.invalid/schemas/citygml_energy_input.schema.json",
        "title": "CityGML Energy Input",
        "description": (
            "JSON input format for the XSD-driven CityGML + Energy ADE generation "
            "pipeline. Generated by tools/generate_input_schema.py; do not edit by "
            "hand. Feature property keys beyond 'type', 'id', 'parent', and "
            "'parent_field' mirror the xsdata field names from "
            "citygml_energy.bindings and are validated at runtime, not by this schema."
        ),
        "type": "object",
        "required": ["city_model", "features"],
        "additionalProperties": False,
        "properties": {
            "$schema": {"type": "string"},
            "city_model": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "name": {"type": "string"},
                },
            },
            "coordinate_origin": {
                "type": "array",
                "description": (
                    "Optional XYZ offset added to every imported STEP coordinate."
                ),
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "number"},
            },
            "srs_name": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "CRS URN written onto gml:Envelope, gml:MultiSurface and "
                    f"gml:Solid. Defaults to {DEFAULT_SRS_NAME} (RD + NAP)."
                ),
            },
            "srs_dimension": {
                "type": "integer",
                "enum": [2, 3],
                "description": (
                    "Coordinate dimension written onto gml:Envelope and every "
                    "gml:MultiSurface / gml:Solid. Defaults to 3."
                ),
            },
            "construction_mapping": {
                "type": "object",
                "description": (
                    "Maps surface/opening types (and optionally specific gml:ids) "
                    "to construction feature IDs from a LayeredConstructionLibrary."
                ),
                "additionalProperties": False,
                "properties": {
                    "by_type": {
                        "type": "object",
                        "description": (
                            "Default construction ID per surface/opening type name "
                            "(e.g. WallSurface, RoofSurface, Door, Window)."
                        ),
                        "additionalProperties": {"type": "string", "minLength": 1},
                    },
                    "by_id": {
                        "type": "object",
                        "description": (
                            "Per-surface/opening overrides keyed by gml:id. Takes "
                            "precedence over by_type."
                        ),
                        "additionalProperties": {"type": "string", "minLength": 1},
                    },
                },
            },
            "features": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["type", "id"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": (
                                "Qualified element name such as 'bldg:Building' "
                                "or 'nrg3:Energy'. Must resolve to an xsdata class "
                                "in citygml_energy.bindings."
                            ),
                            "enum": feature_type_enum,
                        },
                        "id": {
                            "type": "string",
                            "minLength": 1,
                            "description": (
                                "gml:id for this feature; unique across all features. "
                                "Must be a valid XML NCName (letters, digits, '.', "
                                "'-', '_'; starting with a letter or '_')."
                            ),
                            "pattern": r"^[A-Za-z_][A-Za-z0-9_.\-]*$",
                        },
                        "parent": {
                            "type": "string",
                            "minLength": 1,
                            "description": "gml:id of the parent feature.",
                        },
                        "parent_field": {
                            "type": "string",
                            "minLength": 1,
                            "description": (
                                "Explicit field name on the parent to attach to. "
                                "Only needed when auto-discovery is ambiguous."
                            ),
                        },
                        "related_to": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"oneOf": _build_related_to_branches()},
                            "description": (
                                "CityObjectRelation entries declared on this "
                                "feature. Mirrors the EnergyADE 3.0 UML 1:1: "
                                "each entry is one nrg3:CityObjectRelation "
                                "with one relationType (the 'relation' field) "
                                "and one xlink target (the 'target' field). "
                                "The 'relation' value names a member of the "
                                "RelationTypeValue codelist family (currently "
                                "'installedOn' / 'serving' from "
                                "OtherRelationTypeValue.xml). Per-relation "
                                "target shape varies by target_kind: "
                                "'installedOn' (surface) accepts a bare STEP "
                                "layer name (resolves to highest-LoD match, "
                                "then gml:id fallback) or an explicit "
                                "{name, lod} object (LoD-pinned per ADR-0001); "
                                "'serving' and other feature-targeted "
                                "relations accept only a gml:id string. Author "
                                "order is preserved in the emitted "
                                "<nrg3:relatedTo> siblings."
                            ),
                        },
                    },
                },
            },
            "geometry_sources": {
                "type": "array",
                "description": (
                    "STEP geometry imports. Each entry's 'type' picks a handler; "
                    f"supported types: {', '.join(source_types)}."
                ),
                "items": {"oneOf": branches},
            },
        },
    }


def main() -> int:
    schema = build_schema()
    SCHEMA_PATH.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {SCHEMA_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
