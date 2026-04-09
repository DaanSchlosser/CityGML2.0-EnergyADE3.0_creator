"""Rebuild the Alderaan Energy ADE dataset from the checked-in reference template.

This example supports two distinct workflows:

- exact structural reproduction of ``Alderaan_Energy_ADE_All.gml``
- beta8-normalized output that validates against the bundled schema

Because the Alderaan reference uses more CityGML and Energy ADE classes than
the current typed Python builders expose, the example loads the template as raw
XML-backed members and then applies deterministic, schema-oriented cleanup when
requested.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    CityModel,
    find_city_object_by_gml_id,
    load_city_model_template,
    normalize_city_model_for_beta8,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CANDIDATES = (
    REPO_ROOT / "Alderaan_Energy_ADE_All.gml",
    REPO_ROOT / "Alderaan_Energy_ADE_All_beta8.gml",
    REPO_ROOT / "Energy_ADE-3.0beta8" / "test_data" / "Alderaan_Energy_ADE_All.gml",
)
OUTPUT = REPO_ROOT / "generated" / "alderaan.gml"


def resolve_alderaan_reference_path(path: Path | str | None = None) -> Path:
    """Return the canonical Alderaan template path available in this repository."""
    if path is not None:
        candidate = Path(path)
        if candidate.exists():
            return candidate
        repo_relative_candidate = REPO_ROOT / candidate
        if repo_relative_candidate.exists():
            return repo_relative_candidate
        raise FileNotFoundError(
            f"Alderaan template not found: {candidate}. Checked {repo_relative_candidate}."
        )

    for candidate in REFERENCE_CANDIDATES:
        if candidate.exists():
            return candidate

    searched = ", ".join(str(candidate) for candidate in REFERENCE_CANDIDATES)
    raise FileNotFoundError(f"Could not locate an Alderaan template. Checked: {searched}")


REFERENCE = resolve_alderaan_reference_path()


def write_alderaan_file(
    output_path: Path | str = OUTPUT,
    *,
    template_path: Path | str = REFERENCE,
    normalize_for_beta8: bool = True,
    city_name: str | None = None,
    city_description: str | None = None,
    building_name_updates: dict[str, str] | None = None,
) -> CityModel:
    """Write an Alderaan-derived file."""
    model = create_alderaan(
        template_path=template_path,
        normalize_for_beta8=normalize_for_beta8,
    )
    apply_basic_customizations(
        model,
        city_name=city_name,
        city_description=city_description,
        building_name_updates=building_name_updates,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(output_path))

    return model


def create_alderaan(
    template_path: Path | str = REFERENCE,
    *,
    normalize_for_beta8: bool = True,
) -> CityModel:
    """Load the Alderaan reference dataset into an editable CityModel."""
    model = load_city_model_template(resolve_alderaan_reference_path(template_path))
    if normalize_for_beta8:
        normalize_city_model_for_beta8(model)
    return model


def list_buildings(model: CityModel) -> list[tuple[str | None, str | None]]:
    """Return top-level Alderaan buildings as ``(gml:id, gml:name)`` pairs."""
    buildings: list[tuple[str | None, str | None]] = []
    for member in model.city_object_members:
        element = getattr(member, "element", None)
        if element is None:
            continue
        if etree.QName(element).localname != "Building":
            continue
        name = element.find("{http://www.opengis.net/gml}name")
        buildings.append(
            (
                element.get("{http://www.opengis.net/gml}id"),
                name.text if name is not None else None,
            )
        )
    return buildings


def rename_building(
    model: CityModel,
    building_id: str,
    new_name: str,
):
    """Rename a top-level building by its ``gml:id``."""
    building = find_city_object_by_gml_id(model, building_id)
    if building is None:
        raise KeyError(f"Building with gml:id {building_id!r} not found")
    building.set_child_text("gml", "name", new_name)
    return building


def apply_basic_customizations(
    model: CityModel,
    *,
    city_name: str | None = None,
    city_description: str | None = None,
    building_name_updates: dict[str, str] | None = None,
) -> CityModel:
    """Apply the most common user-facing customizations to the Alderaan model."""
    if city_name is not None:
        model.gml_name = city_name
    if city_description is not None:
        model.gml_description = city_description

    for building_id, new_name in (building_name_updates or {}).items():
        rename_building(model, building_id, new_name)

    return model


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--template",
        type=Path,
        default=REFERENCE,
        help="Template GML file to load before optional normalization and customization.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Destination path for the generated GML file.",
    )
    parser.add_argument(
        "--exact-reference",
        action="store_true",
        help="Write a structurally equivalent XML tree to the reference file instead of the beta8-normalized variant.",
    )
    parser.add_argument(
        "--list-buildings",
        action="store_true",
        help="Print available top-level building IDs and names before writing the output file.",
    )
    parser.add_argument(
        "--city-name",
        help="Override the top-level gml:name of the CityModel.",
    )
    parser.add_argument(
        "--city-description",
        help="Override the top-level gml:description of the CityModel.",
    )
    parser.add_argument(
        "--building-id",
        help="Target building gml:id for a simple rename operation.",
    )
    parser.add_argument(
        "--building-name",
        help="Replacement gml:name for the building selected by --building-id.",
    )
    return parser


if __name__ == "__main__":
    parser = _build_argument_parser()
    args = parser.parse_args()

    if bool(args.building_id) != bool(args.building_name):
        parser.error("--building-id and --building-name must be used together")

    if args.list_buildings:
        preview_model = create_alderaan(
            template_path=args.template,
            normalize_for_beta8=not args.exact_reference,
        )
        print("Available buildings:")
        for building_id, building_name in list_buildings(preview_model):
            print(f"  {building_id}: {building_name}")

    building_name_updates = None
    if args.building_id and args.building_name:
        building_name_updates = {args.building_id: args.building_name}

    model = write_alderaan_file(
        output_path=args.output,
        template_path=args.template,
        normalize_for_beta8=not args.exact_reference,
        city_name=args.city_name,
        city_description=args.city_description,
        building_name_updates=building_name_updates,
    )

    first_building = find_city_object_by_gml_id(model, "id_building_1")
    first_building_name = None
    if first_building is not None:
        name = first_building.find_child("gml", "name")
        first_building_name = name.text if name is not None else None

    print(f"Written to {args.output}")
    if first_building_name is not None:
        print(f"First building name: {first_building_name}")
