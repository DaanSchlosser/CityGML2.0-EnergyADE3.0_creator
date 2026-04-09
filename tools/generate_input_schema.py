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
    conditions = []
    for feature_type in list_supported_feature_types():
        conditions.append(
            {
                "if": {"properties": {"feature_type": {"const": feature_type}}},
                "then": {
                    "properties": {
                        "attributes": _build_attributes_schema(
                            FEATURE_INPUT_FIELDS[feature_type]
                        )
                    }
                },
            }
        )

    return {
        "type": "object",
        "required": ["feature_type", "attributes"],
        "additionalProperties": False,
        "properties": {
            "feature_type": {
                "type": "string",
                "enum": list_supported_feature_types(),
                "description": (
                    "Supported feature types that can currently be created from "
                    "JSON input."
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
        "type": "object",
        "required": ["type", "path", "target_building_id"],
        "additionalProperties": False,
        "properties": {
            "type": {
                "type": "string",
                "enum": ["step-renodat-lod3"],
                "description": (
                    "Import LOD3 wall/roof/ground/opening geometry and optional PV "
                    "panel geometry from a RenoDAT-style STEP file."
                ),
            },
            "path": {
                "type": "string",
                "minLength": 1,
            },
            "target_building_id": {
                "type": "string",
                "minLength": 1,
            },
            "target_pv_id": {
                "type": "string",
                "minLength": 1,
            },
        },
    }


if __name__ == "__main__":
    main()
