"""CityGML 2.0 + Energy ADE 3.0 generation from JSON/Excel input."""

from .core import CityModel
from .generation import (
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    generate_city_model,
    generate_gml_file,
)
from .input_loader import (
    InputFileError,
    build_city_model_from_feature_collection,
    load_feature_collection,
)
__all__ = [
    "CityModel",
    "DEFAULT_INPUT_PATH",
    "DEFAULT_OUTPUT_PATH",
    "InputFileError",
    "build_city_model_from_feature_collection",
    "generate_city_model",
    "generate_gml_file",
    "load_feature_collection",
]
