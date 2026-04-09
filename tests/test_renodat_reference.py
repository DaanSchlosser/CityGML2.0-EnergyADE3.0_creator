"""Tests for the JSON-driven RenoDAT example."""

import os
import sys
from copy import deepcopy
from typing import Any, cast

import lxml.etree as etree
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    InputFileError,
    build_city_model_from_feature_collection,
    generate_city_model,
    load_feature_collection,
    validate_xml_against_energy_ade_schema,
)
from examples.create_renodat import INPUT


def test_renodat_imports_obj_geometry():
    """The RenoDAT example imports LOD3 surfaces, openings, and PV geometry."""
    model = generate_city_model(INPUT)

    assert len(model.city_object_members) == 1

    building = model.city_object_members[0]
    assert len(building.bounded_by_surfaces) == 11

    wall_surfaces = {
        surface.gml_id: surface
        for surface in building.bounded_by_surfaces
        if surface.__class__.__name__ == "WallSurface"
    }
    assert sorted(wall_surfaces) == [
        "WallSurface_01",
        "WallSurface_02",
        "WallSurface_03",
        "WallSurface_04",
        "WallSurface_05",
        "WallSurface_06",
        "WallSurface_07",
        "WallSurface_08",
    ]
    assert len(wall_surfaces["WallSurface_01"].openings) == 1
    assert len(wall_surfaces["WallSurface_02"].openings) == 4
    assert len(wall_surfaces["WallSurface_03"].openings) == 2
    assert len(wall_surfaces["WallSurface_04"].openings) == 6

    assert len(building.devices) == 1
    pv_collector = building.devices[0]
    pv_geometry = pv_collector.lod3_multi_surface.element
    assert len(pv_geometry.findall("./{http://www.opengis.net/gml}surfaceMember")) == 43


def test_generated_is_well_formed_xml():
    """The generated GML is well-formed XML."""
    doc = generate_city_model(INPUT)
    generated = doc.to_string()
    # This will raise if not well-formed
    etree.fromstring(generated.encode("utf-8"))


def test_renodat_is_schema_valid():
    """The canonical RenoDAT JSON workflow is valid against the beta8 schema."""
    doc = generate_city_model(INPUT)
    result = cast(
        dict[str, Any], validate_xml_against_energy_ade_schema(doc.to_string())
    )

    assert result["valid"], "Schema validation failed:\n" + "\n".join(
        f"  - line {error['line']}: {error['message']}"
        for error in result["errors"][:20]
    )


def test_renodat_input_supports_multiple_buildings():
    data = load_feature_collection(INPUT)
    second_building = deepcopy(data["features"][0])
    second_building["attributes"]["gml_id"] = "id_building_2"
    second_building["attributes"]["gml_name"] = "Leia's house"
    second_building["attributes"]["nrg3_identifier"] = "0503100000032915"
    second_building["attributes"]["nrg3_identifier_codeSpace"] = (
        "https://bagviewer.kadaster.nl/?objectId=0503100000032915"
    )

    extended_data = deepcopy(data)
    extended_data["features"].append(second_building)

    model = build_city_model_from_feature_collection(extended_data)

    assert len(model.city_object_members) == 2
    assert len(model.city_object_members[0].bounded_by_surfaces) == 11


def test_renodat_input_rejects_unknown_feature_type():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["features"][0]["feature_type"] = "nrg3_NotSupported"

    with pytest.raises(InputFileError, match="feature_type"):
        build_city_model_from_feature_collection(invalid_data)


def test_renodat_input_accepts_supported_fme_aliases():
    data = {
        "schema_version": 1,
        "city_model": {"name": "Alias test"},
        "features": [
            {
                "feature_type": "bldg_Building",
                "attributes": {
                    "gml_id": "building_alias_1",
                    "gml_name": "Alias House",
                    "citygml_creationDate": "2026-04-09",
                    "citygml_class": "1000",
                    "citygml_class_codeSpace": "class-space",
                    "citygml_function{}": "1000",
                    "citygml_function{}.codeSpace": "function-space",
                    "citygml_usage{}": "1000",
                    "citygml_usage{}.codeSpace": "usage-space",
                    "citygml_year_of_construction": 2020,
                },
            },
            {
                "feature_type": "nrg3_PhotovoltaicCollector",
                "attributes": {
                    "gml_id": "pv_alias_1",
                    "gml_parent_id": "building_alias_1",
                    "gml_name": "Alias PV",
                    "citygml_creationDate": "2026-04-09",
                    "nrg3_year_of_installation": 2020,
                    "nrg3_number_of_devices": 4,
                    "nrg3_installed_power": 1000,
                    "nrg3_installed_power_units": "W",
                },
            },
        ],
    }

    model = build_city_model_from_feature_collection(data)

    assert len(model.city_object_members) == 1
    building = model.city_object_members[0]
    assert building.year_of_construction == 2020
    assert len(building.devices) == 1
    assert building.devices[0].number_of_devices == 4
    assert building.devices[0].installed_power.text == "1000"


def test_renodat_input_rejects_unsupported_attribute_name():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["features"][0]["attributes"]["citygml_not_a_real_field"] = "x"

    with pytest.raises(InputFileError, match="unsupported key"):
        build_city_model_from_feature_collection(invalid_data)


def test_renodat_input_rejects_missing_geometry_source_target():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["geometry_sources"][0]["target_building_id"] = "missing_building"

    with pytest.raises(InputFileError, match="target_building_id"):
        build_city_model_from_feature_collection(invalid_data)


def test_renodat_input_rejects_missing_geometry_source_file():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["geometry_sources"][0]["path"] = "../does_not_exist.obj"

    with pytest.raises(InputFileError, match="does not exist"):
        build_city_model_from_feature_collection(
            invalid_data,
            base_path=os.path.dirname(INPUT),
        )


if __name__ == "__main__":
    test_renodat_imports_obj_geometry()
    print("All tests passed!")
