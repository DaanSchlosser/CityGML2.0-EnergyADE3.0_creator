"""Tests for the JSON-driven RenoDAT example."""

from copy import deepcopy
from pathlib import Path

import pytest
from lxml import etree

from citygml_energy import (
    Building,
    InputFileError,
    PhotovoltaicCollector,
    build_city_model_from_feature_collection,
    generate_city_model,
    load_feature_collection,
)
from examples.create_renodat import INPUT


def test_renodat_imports_step_brep_geometry():
    """The RenoDAT example imports multi-LOD STEP-backed geometry."""
    model = generate_city_model(INPUT)

    assert len(model.city_object_members) == 1

    building = model.city_object_members[0]
    assert isinstance(building, Building)
    assert len(building.devices) == 2
    assert len(building.occupied_by) == 1

    # LOD0: aggregate footprint on the Building
    assert building.lod0_foot_print is not None

    # LOD1: aggregate solid on the Building
    assert building.lod1_solid is not None

    # Surfaces shared between LOD2 and LOD3 are merged into a single entry
    # carrying both lod2MultiSurface and lod3MultiSurface (per the XSD).
    # LOD2: 7 surfaces (1 ground + 4 walls + 2 roofs) — all also in LOD3
    # LOD3: 11 surfaces (1 ground + 8 walls + 2 roofs) — 4 walls are LOD3-only
    # Total unique boundary surfaces: 11
    assert len(building.bounded_by_surfaces) == 11

    lod2_surfaces = [
        s for s in building.bounded_by_surfaces if s.lod2_multi_surface is not None
    ]
    assert len(lod2_surfaces) == 7

    lod3_surfaces = [
        s for s in building.bounded_by_surfaces if s.lod3_multi_surface is not None
    ]
    assert len(lod3_surfaces) == 11

    # The 7 shared surfaces carry both LOD2 and LOD3 geometry.
    both_lod = [
        s
        for s in building.bounded_by_surfaces
        if s.lod2_multi_surface is not None and s.lod3_multi_surface is not None
    ]
    assert len(both_lod) == 7

    # LOD3 wall surfaces with auto-generated IDs
    wall_surfaces = [
        s for s in lod3_surfaces if s.__class__.__name__ == "WallSurface"
    ]
    assert len(wall_surfaces) == 8
    for ws in wall_surfaces:
        assert ws.gml_id.startswith("id_building_1_WallSurface_")

    opening_counts = sorted(len(ws.openings) for ws in wall_surfaces)
    assert opening_counts == [0, 0, 0, 0, 1, 2, 4, 6]

    wall_with_6_openings = next(ws for ws in wall_surfaces if len(ws.openings) == 6)
    wall_surface_geometry = wall_with_6_openings.lod3_multi_surface.element
    wall_polygons = wall_surface_geometry.findall(
        "./{http://www.opengis.net/gml}surfaceMember/{http://www.opengis.net/gml}Polygon"
    )
    assert len(wall_polygons) == 1
    assert len(wall_polygons[0].findall("./{http://www.opengis.net/gml}interior")) == 6

    pv_collector = building.devices[0]
    assert isinstance(pv_collector, PhotovoltaicCollector)
    pv_geometry = pv_collector.lod3_multi_surface.element
    assert len(pv_geometry.findall("./{http://www.opengis.net/gml}surfaceMember")) == 36

    # ZonePart geometry: each zone part has lod3Solid
    assert len(building.zones) == 1
    zone = building.zones[0]
    assert len(zone.zone_parts) == 3
    for zone_part in zone.zone_parts:
        assert zone_part.lod3_solid is not None


def test_renodat_serializes_pv_as_nested_building_device():
    model = generate_city_model(INPUT)
    generated = model.to_string()
    root = etree.fromstring(generated.encode("utf-8"))
    ns = {
        "core": "http://www.opengis.net/citygml/2.0",
        "bldg": "http://www.opengis.net/citygml/building/2.0",
        "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
    }

    assert len(root.findall("./core:cityObjectMember/bldg:Building", ns)) == 1
    assert len(root.findall("./core:cityObjectMember/nrg3:PhotovoltaicCollector", ns)) == 0
    assert len(root.findall(".//bldg:Building/nrg3:device", ns)) == 2
    assert len(root.findall(".//bldg:Building/nrg3:device/nrg3:PhotovoltaicCollector", ns)) == 1
    assert len(root.findall(".//bldg:Building/nrg3:device/nrg3:EVChargingStation", ns)) == 1
    assert len(root.findall(".//bldg:Building/nrg3:occupiedBy", ns)) == 1
    assert len(root.findall(".//bldg:Building/nrg3:occupiedBy/nrg3:Occupants", ns)) == 1


def test_pv_collector_has_installed_on_relation():
    """The PV collector has an 'installedOn' relation to the roof surface it sits on."""
    model = generate_city_model(INPUT)
    building = model.city_object_members[0]
    pv_collector = building.devices[0]

    assert len(pv_collector.nrg3_related_to) >= 1
    relation = pv_collector.nrg3_related_to[0]
    assert relation.relation_type.value == "installedOn"
    assert "_RoofSurface_" in relation.related_to_href

    # Verify it serializes correctly in the XML
    generated = model.to_string()
    root = etree.fromstring(generated.encode("utf-8"))
    ns = {
        "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
        "xlink": "http://www.w3.org/1999/xlink",
    }
    relations = root.findall(".//nrg3:CityObjectRelation", ns)
    assert len(relations) >= 1
    rel_type = relations[0].find("nrg3:relationType", ns)
    assert rel_type is not None
    assert rel_type.text == "installedOn"
    inner_ref = relations[0].find("nrg3:relatedTo", ns)
    assert inner_ref is not None
    href = inner_ref.get(f"{{{ns['xlink']}}}href")
    assert href is not None
    assert "_RoofSurface_" in href


def test_generated_is_well_formed_xml():
    """The generated GML is well-formed XML."""
    doc = generate_city_model(INPUT)
    generated = doc.to_string()
    # This will raise if not well-formed
    etree.fromstring(generated.encode("utf-8"))


def test_generated_has_envelope_with_crs():
    """The generated GML has a gml:boundedBy envelope with srsName."""
    doc = generate_city_model(INPUT)
    generated = doc.to_string()
    root = etree.fromstring(generated.encode("utf-8"))
    ns = {"gml": "http://www.opengis.net/gml"}
    envelope = root.find(".//gml:Envelope", ns)
    assert envelope is not None, "Missing gml:Envelope"
    assert "srsName" in envelope.attrib
    assert envelope.attrib["srsDimension"] == "3"


def test_geometry_elements_have_srs():
    """All gml:MultiSurface elements carry srsName and srsDimension."""
    doc = generate_city_model(INPUT)
    generated = doc.to_string()
    root = etree.fromstring(generated.encode("utf-8"))
    ns = {"gml": "http://www.opengis.net/gml"}
    multi_surfaces = root.findall(".//gml:MultiSurface", ns)
    assert len(multi_surfaces) > 0
    for ms in multi_surfaces:
        assert "srsName" in ms.attrib, f"Missing srsName on {ms.attrib}"
        assert "srsDimension" in ms.attrib, f"Missing srsDimension on {ms.attrib}"


def test_no_scientific_notation_in_coordinates():
    """Coordinate values must not contain scientific notation."""
    doc = generate_city_model(INPUT)
    generated = doc.to_string()
    root = etree.fromstring(generated.encode("utf-8"))
    ns = {"gml": "http://www.opengis.net/gml"}
    for pos_list in root.findall(".//gml:posList", ns):
        text = pos_list.text or ""
        for token in text.split():
            assert "e" not in token.lower(), f"Scientific notation found in coordinates: {token}"


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

    buildings = [member for member in model.city_object_members if isinstance(member, Building)]

    assert len(model.city_object_members) == 2
    assert len(buildings) == 2
    assert len(buildings[0].bounded_by_surfaces) == 11


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
    invalid_data["geometry_sources"][0]["path"] = "../does_not_exist.stp"

    with pytest.raises(InputFileError, match="does not exist"):
        build_city_model_from_feature_collection(
            invalid_data,
            base_path=Path(INPUT).parent,
        )


if __name__ == "__main__":
    test_renodat_imports_step_brep_geometry()
    print("All tests passed!")
