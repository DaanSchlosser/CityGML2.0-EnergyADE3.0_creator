"""Golden-file and schema tests for the Alderaan reference generator."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    compare_with_reference,
    find_city_object_by_gml_id,
    validate_xml_against_energy_ade_schema,
)
from examples.create_alderaan import (
    REFERENCE,
    apply_basic_customizations,
    create_alderaan,
    list_buildings,
    resolve_alderaan_reference_path,
    write_alderaan_file,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE_PATH = str(resolve_alderaan_reference_path())


def test_alderaan_matches_reference():
    doc = create_alderaan(normalize_for_beta8=False)
    generated = doc.to_string()
    result = compare_with_reference(generated, REFERENCE_PATH)
    if not result["match"]:
        for difference in result["differences"][:50]:
            print(f"  DIFF: {difference}")
    assert result["match"], (
        f"Found {len(result['differences'])} difference(s):\n"
        + "\n".join(f"  - {difference}" for difference in result["differences"][:50])
    )


def test_alderaan_is_schema_valid():
    doc = create_alderaan(normalize_for_beta8=True)
    result = validate_xml_against_energy_ade_schema(doc.to_string())
    if not result["valid"]:
        for error in result["errors"][:20]:
            print(f"  SCHEMA: line {error['line']}: {error['message']}")
    assert result["valid"], "Schema validation failed:\n" + "\n".join(
        f"  - line {error['line']}: {error['message']}"
        for error in result["errors"][:20]
    )


def test_loaded_alderaan_members_are_editable():
    model = create_alderaan(normalize_for_beta8=False)
    building = find_city_object_by_gml_id(model, "id_building_1")
    assert building is not None

    building.set_child_text("gml", "name", "My custom building")
    updated_xml = model.to_string()

    assert "<gml:name>My custom building</gml:name>" in updated_xml


def test_alderaan_buildings_can_be_listed():
    model = create_alderaan(normalize_for_beta8=False)

    buildings = list_buildings(model)

    assert buildings
    assert buildings[0] == ("id_building_1", "Building 1 (Snoke's Palace)")


def test_alderaan_basic_customizations_apply_cleanly():
    model = create_alderaan(normalize_for_beta8=False)

    apply_basic_customizations(
        model,
        city_name="My Custom City",
        city_description="Custom description",
        building_name_updates={"id_building_1": "My custom building"},
    )
    updated_xml = model.to_string()

    assert model.gml_name == "My Custom City"
    assert model.gml_description == "Custom description"
    assert "<gml:name>My custom building</gml:name>" in updated_xml


def test_write_alderaan_file_skips_validation_for_exact_reference(tmp_path):
    output_path = tmp_path / "alderaan_exact.gml"

    model, validation = write_alderaan_file(
        output_path=output_path,
        normalize_for_beta8=False,
    )

    assert model is not None
    assert validation is None
    result = compare_with_reference(
        output_path.read_text(encoding="utf-8"), REFERENCE_PATH
    )
    assert result["match"]


def test_write_alderaan_file_validates_normalized_output(tmp_path):
    output_path = tmp_path / "alderaan_valid.gml"

    model, validation = write_alderaan_file(
        output_path=output_path,
        normalize_for_beta8=True,
    )

    assert model is not None
    assert validation is not None
    assert validation["valid"]

    output_text = output_path.read_text(encoding="utf-8")
    assert "<nrg3:accessType" not in output_text
    assert "EVChargingAccessTypeValue.xml" in output_text

    comparison = compare_with_reference(output_text, REFERENCE_PATH)
    assert len(comparison["differences"]) == 4


def test_reference_path_resolves_existing_template():
    assert os.path.exists(REFERENCE)
    assert os.path.exists(REFERENCE_PATH)
