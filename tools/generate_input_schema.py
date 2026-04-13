"""Generate the JSON schema for the RenoDAT input file.

This keeps the static schema aligned with the supported input catalog.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from citygml_energy.input_catalog import (
    FEATURE_INPUT_FIELDS,
    list_supported_feature_types,
)

SCHEMA_PATH = REPO_ROOT / "schemas" / "citygml_energy_input.schema.json"


def main() -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.invalid/schemas/citygml_energy_input.schema.json",
        "title": "CityGML Energy Input",
        "type": "object",
        "required": ["schema_version", "city_model", "features"],
        "additionalProperties": False,
        "properties": {
            "$schema": {"type": "string"},
            "schema_version": {"const": 1},
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
                "description": "Optional XYZ offset added to all imported STEP coordinates.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "number"},
            },
            "features": {
                "type": "array",
                "items": _build_feature_item_schema(),
            },
            "geometry_sources": {
                "type": "array",
                "items": _build_geometry_source_schema(),
            },
        },
    }

    SCHEMA_PATH.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def _build_feature_item_schema() -> dict:
    conditions = [
        {
            "if": {"properties": {"feature_type": {"const": feature_type}}},
            "then": {
                "properties": {
                    "attributes": _build_attributes_schema(FEATURE_INPUT_FIELDS[feature_type])
                }
            },
        }
        for feature_type in list_supported_feature_types()
    ]

    return {
        "type": "object",
        "required": ["feature_type", "attributes"],
        "additionalProperties": False,
        "properties": {
            "feature_type": {
                "type": "string",
                "enum": list_supported_feature_types(),
                "description": (
                    "Supported feature types that can currently be created from JSON input."
                ),
            },
            "attributes": {
                "type": "object",
                "required": ["gml_id"],
            },
        },
        "allOf": conditions,
    }


def _build_attributes_schema(fields) -> dict:
    properties = {
        "gml_id": {
            "type": "string",
            "minLength": 1,
        },
        "gml_parent_id": {
            "type": "string",
            "minLength": 1,
        },
    }

    for field in fields:
        properties.setdefault(field.canonical, _scalar_property_schema())
        for alias in field.aliases:
            properties.setdefault(alias, _scalar_property_schema())

    return {
        "type": "object",
        "required": ["gml_id"],
        "additionalProperties": False,
        "properties": dict(sorted(properties.items())),
    }


def _scalar_property_schema() -> dict:
    return {"type": ["string", "number", "boolean", "null"]}


def _build_geometry_source_schema() -> dict:
    return {
        "oneOf": [
            {
                "type": "object",
                "description": (
                    "Import semantic boundary surfaces (wall/roof/ground/opening) "
                    "and optional PV geometry from a RenoDAT-style STEP file onto "
                    "a Building or BuildingPart."
                ),
                "required": ["type", "path", "target_building_id"],
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [f"step-renodat-lod{n}" for n in range(5)],
                    },
                    "path": {"type": "string", "minLength": 1},
                    "target_building_id": {"type": "string", "minLength": 1},
                    "target_pv_id": {"type": "string", "minLength": 1},
                },
            },
            {
                "type": "object",
                "description": (
                    "Import volume geometry from a STEP file onto a Zone or "
                    "ZonePart. All shells are collected into a single "
                    "lod0MultiSurface or lod1-3Solid."
                ),
                "required": ["type", "path", "target_zone_part_id"],
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [f"step-zonepart-lod{n}" for n in range(4)],
                    },
                    "path": {"type": "string", "minLength": 1},
                    "target_zone_part_id": {"type": "string", "minLength": 1},
                },
            },
        ],
    }


if __name__ == "__main__":
    main()
