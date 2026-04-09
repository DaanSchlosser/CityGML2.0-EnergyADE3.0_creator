"""Build RenoDAT output from a data-only JSON feature input file."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    CityModel,
    load_city_model_from_feature_collection,
    validate_file_against_energy_ade_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT = REPO_ROOT / "inputs" / "renodat_input.json"
OUTPUT = REPO_ROOT / "generated" / "renodat.gml"


def create_renodat(input_path: Path | str = INPUT) -> CityModel:
    """Build the RenoDAT example CityModel from JSON input only."""
    return load_city_model_from_feature_collection(input_path)


def write_renodat_file(
    input_path: Path | str = INPUT,
    output_path: Path | str = OUTPUT,
    *,
    validate_against_schema: bool = True,
) -> tuple[CityModel, dict[str, object] | None]:
    """Build RenoDAT from JSON input, write it, and optionally validate it."""
    model = create_renodat(input_path=input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(output_path))

    validation = None
    if validate_against_schema:
        validation = validate_file_against_energy_ade_schema(output_path)
        if not validation["valid"]:
            messages = "\n".join(
                f"line {entry['line']}: {entry['message']}"
                for entry in validation["errors"][:20]
            )
            raise ValueError(f"Generated file is not schema-valid:\n{messages}")

    return model, validation


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT,
        help="JSON feature input file to convert into CityGML.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Destination path for the generated GML file.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip schema validation after writing the output file.",
    )
    return parser


if __name__ == "__main__":
    parser = _build_argument_parser()
    args = parser.parse_args()

    model, validation = write_renodat_file(
        input_path=args.input,
        output_path=args.output,
        validate_against_schema=not args.no_validate,
    )

    print(f"Written to {args.output}")
    print(f"Top-level city objects: {len(model.city_object_members)}")
    if validation is None:
        print("Schema validation skipped")
    else:
        print("Schema validation: OK")
