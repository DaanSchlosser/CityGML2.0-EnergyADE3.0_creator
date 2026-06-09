"""Per-building CLI entry point: JSON + STEP -> CityGML 2.0 + EnergyADE 3.0.

Default inputs point at the owner-occupier reference building
(``inputs/buildings/NL-single-family-house.json``). Use ``--input`` to
pass a different feature-collection JSON. See the README for the
RenoDAT research context this script is a test case for.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from citygml_energy import (
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    CityModel,
    generate_city_model,
    generate_gml_file,
)

INPUT = DEFAULT_INPUT_PATH
OUTPUT = DEFAULT_OUTPUT_PATH


def create_building(input_path: Path | str = INPUT) -> CityModel:
    """Load *input_path* and return a :class:`CityModel` without writing.

    Thin wrapper around :func:`citygml_energy.generate_city_model` with
    the default input set to the owner-occupier reference building.
    """
    return generate_city_model(input_path=input_path)


def write_building_gml_file(
    input_path: Path | str = INPUT,
    output_path: Path | str = OUTPUT,
) -> CityModel:
    """Load *input_path*, build a :class:`CityModel`, write GML to *output_path*.

    Thin wrapper around :func:`citygml_energy.generate_gml_file`.
    """
    return generate_gml_file(
        input_path=input_path,
        output_path=output_path,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT,
        help="Feature-collection JSON input.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Destination path for the generated GML file.",
    )
    return parser


if __name__ == "__main__":
    parser = _build_argument_parser()
    args = parser.parse_args()

    model = write_building_gml_file(
        input_path=args.input,
        output_path=args.output,
    )

    print(f"Written to {args.output}")
    print(f"Top-level city objects: {len(model.xsd.city_object_member)}")
