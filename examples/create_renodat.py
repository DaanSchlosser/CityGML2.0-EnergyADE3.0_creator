"""Canonical RenoDAT GML generation entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    CityModel,
    generate_city_model,
    generate_gml_file,
)

INPUT = DEFAULT_INPUT_PATH
OUTPUT = DEFAULT_OUTPUT_PATH


def create_renodat(input_path: Path | str = INPUT) -> CityModel:
    """Backward-compatible wrapper for the canonical generation API."""
    return generate_city_model(input_path=input_path)


def write_renodat_file(
    input_path: Path | str = INPUT,
    output_path: Path | str = OUTPUT,
    *,
    validate_against_schema: bool = True,
) -> tuple[CityModel, dict[str, object] | None]:
    """Backward-compatible wrapper for the canonical generation API."""
    return generate_gml_file(
        input_path=input_path,
        output_path=output_path,
        validate_against_schema=validate_against_schema,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT,
        help="Canonical JSON feature input file to convert into CityGML.",
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
