"""Canonical CityGML generation workflow from JSON feature input."""

from __future__ import annotations

from pathlib import Path

from .core import CityModel
from .input_loader import load_city_model_from_feature_collection
from .validation import validate_file_against_energy_ade_schema

PathLike = str | Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = REPO_ROOT / "inputs" / "renodat_input.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "generated" / "renodat.gml"


def generate_city_model(input_path: PathLike = DEFAULT_INPUT_PATH) -> CityModel:
    """Generate a CityModel from the repository's canonical JSON input workflow."""
    return load_city_model_from_feature_collection(input_path)


def generate_gml_file(
    input_path: PathLike = DEFAULT_INPUT_PATH,
    output_path: PathLike = DEFAULT_OUTPUT_PATH,
    *,
    validate_against_schema: bool = True,
) -> tuple[CityModel, dict[str, object] | None]:
    """Generate, write, and optionally schema-validate a GML file."""
    model = generate_city_model(input_path=input_path)
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