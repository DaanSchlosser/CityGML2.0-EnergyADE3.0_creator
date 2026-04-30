"""Canonical CityGML generation workflow from JSON feature input."""

from __future__ import annotations

from pathlib import Path

from .core import CityModel
from .input_loader import load_city_model_from_feature_collection

PathLike = str | Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = REPO_ROOT / "inputs" / "buildings" / "owner_occupier_building.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "generated" / "owner_occupier_building.gml"


def generate_city_model(input_path: PathLike = DEFAULT_INPUT_PATH) -> CityModel:
    """Generate a CityModel from a JSON feature input file."""
    return load_city_model_from_feature_collection(Path(input_path))


def generate_gml_file(
    input_path: PathLike = DEFAULT_INPUT_PATH,
    output_path: PathLike = DEFAULT_OUTPUT_PATH,
) -> CityModel:
    """Generate and write a GML file from the canonical JSON input."""
    model = generate_city_model(input_path=input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(output_path))
    return model
