"""Backward-compatible RenoDAT factory entry point using JSON input."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import CityModel, load_city_model_from_feature_collection
from examples.create_renodat import INPUT, write_renodat_file

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "generated" / "renodat_factory.gml"


def create_renodat_via_factory(input_path: Path | str = INPUT) -> CityModel:
    """Build the RenoDAT example city model using the FeatureFactory path."""
    return load_city_model_from_feature_collection(input_path)


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
