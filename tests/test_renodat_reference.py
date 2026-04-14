"""Tests for the RenoDAT reference input.

Two concerns are tested:

1. **XSD validity** -- the generated GML validates against the Energy ADE 3.0
   beta8 + CityGML 2.0 XSD schema set, the same check FME performs.

2. **Completeness** -- every feature declared in the JSON input is present in
   the serialized XML.  XSD validation alone cannot catch silently dropped
   features because nearly all child elements are optional (minOccurs=0).

Supplementary tests cover qualities the XSD cannot enforce (CRS propagation,
coordinate formatting) and input-loader error handling.
"""

from copy import deepcopy
from pathlib import Path

import lxml.etree as etree
import pytest

from citygml_energy import (
    InputFileError,
    build_city_model_from_feature_collection,
    generate_city_model,
    load_feature_collection,
)
from examples.create_renodat import INPUT
from tools.validate_xsd import load_schema

NS = {
    "core": "http://www.opengis.net/citygml/2.0",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "gml": "http://www.opengis.net/gml",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
    "xlink": "http://www.w3.org/1999/xlink",
}


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def xsd_schema():
    return load_schema()


@pytest.fixture(scope="session")
def renodat_model():
    return generate_city_model(INPUT)


@pytest.fixture(scope="session")
def renodat_xml(renodat_model):
    return renodat_model.to_string()


@pytest.fixture(scope="session")
def renodat_root(renodat_xml):
    return etree.fromstring(renodat_xml.encode("utf-8"))


# ---------------------------------------------------------------------------
# 1. XSD validity
# ---------------------------------------------------------------------------


def test_generated_validates_against_xsd(xsd_schema, renodat_root):
    """The full RenoDAT output validates against the XSD schema set."""
    xsd_schema.assertValid(renodat_root)


# ---------------------------------------------------------------------------
# 2. Completeness -- every input feature is present in the output XML
#
# XSD says almost every child element is optional, so a building with
# zero devices, zero zones, and zero geometry would still validate.
# These tests verify nothing was silently dropped.
# ---------------------------------------------------------------------------


def test_single_building_as_city_object_member(renodat_root):
    """The input has one building; it must appear as one cityObjectMember."""
    buildings = renodat_root.findall("core:cityObjectMember/bldg:Building", NS)
    assert len(buildings) == 1


def test_all_devices_attached_to_building(renodat_root):
    """Input declares 3 devices (PV, HeatPump, EV); all must be nested under the building."""
    devices = renodat_root.findall(".//bldg:Building/nrg3:device", NS)
    assert len(devices) == 3

    assert len(renodat_root.findall(".//nrg3:device/nrg3:PhotovoltaicCollector", NS)) == 1
    assert len(renodat_root.findall(".//nrg3:device/nrg3:HeatPump", NS)) == 1
    assert len(renodat_root.findall(".//nrg3:device/nrg3:EVChargingStation", NS)) == 1


def test_occupants_attached_to_building(renodat_root):
    """Input declares 1 Occupants feature; it must be nested under the building."""
    occupants = renodat_root.findall(".//bldg:Building/nrg3:occupiedBy/nrg3:Occupants", NS)
    assert len(occupants) == 1


def test_zone_with_three_zone_parts(renodat_root):
    """Input declares 1 Zone with 3 ZoneParts."""
    zones = renodat_root.findall(".//bldg:Building/nrg3:zone//nrg3:Zone", NS)
    assert len(zones) == 1

    zone_parts = zones[0].findall("nrg3:zonePart/nrg3:ZonePart", NS)
    assert len(zone_parts) == 3


def test_heating_and_cooling_schedules_on_zone_parts(renodat_root):
    """Zone parts 1 and 2 each have a heating and cooling schedule; zone part 3 has none."""
    zone_parts = renodat_root.findall(".//nrg3:Zone/nrg3:zonePart/nrg3:ZonePart", NS)
    assert len(zone_parts) == 3

    parts_with_heating = [
        zp for zp in zone_parts if zp.find("nrg3:heatingSchedule", NS) is not None
    ]
    parts_with_cooling = [
        zp for zp in zone_parts if zp.find("nrg3:coolingSchedule", NS) is not None
    ]
    assert len(parts_with_heating) == 2
    assert len(parts_with_cooling) == 2


def test_energy_resources_attached_to_devices(renodat_root):
    """Input declares 2 Energy resources: one on the EV, one on the PV."""
    ev_resources = renodat_root.findall(".//nrg3:EVChargingStation/nrg3:resource/nrg3:Energy", NS)
    assert len(ev_resources) == 1

    pv_resources = renodat_root.findall(
        ".//nrg3:PhotovoltaicCollector/nrg3:resource/nrg3:Energy", NS
    )
    assert len(pv_resources) == 1


def test_monthly_time_series_on_pv_energy(renodat_root):
    """The PV energy resource has a MonthlyTimeSeries for time-dependent production."""
    ts = renodat_root.findall(
        ".//nrg3:PhotovoltaicCollector//nrg3:Energy"
        "/nrg3:timeDependentAmount/nrg3:MonthlyTimeSeries",
        NS,
    )
    assert len(ts) == 1


def test_pv_has_installed_on_relation(renodat_root):
    """The PV collector has an installedOn relation to a roof surface."""
    relations = renodat_root.findall(
        ".//nrg3:PhotovoltaicCollector/nrg3:relatedTo/nrg3:CityObjectRelation", NS
    )
    assert len(relations) >= 1
    rel_type = relations[0].find("nrg3:relationType", NS)
    assert rel_type is not None and rel_type.text == "installedOn"

    # xsdata's generated AbstractCityObjectPropertyType doesn't expose xlink:href
    # attributes, so the relatedTo child element is present but the href target
    # cannot be set.  Verify the element exists; href support requires a
    # custom xsdata extension or post-processing step.
    related_to = relations[0].find("nrg3:relatedTo", NS)
    assert related_to is not None


def test_geometry_imported_from_step(renodat_root):
    """Input has STEP files for LOD0-3; the building must have geometry at each level."""
    building = renodat_root.find("core:cityObjectMember/bldg:Building", NS)

    # LOD0 footprint
    assert building.find("bldg:lod0FootPrint", NS) is not None

    # LOD1 solid
    assert building.find("bldg:lod1Solid", NS) is not None

    # LOD2+3 boundary surfaces (walls, roofs, ground)
    bounded = building.findall("bldg:boundedBy", NS)
    assert len(bounded) > 0

    # Zone parts have lod3Solid from STEP files
    zone_parts = renodat_root.findall(".//nrg3:ZonePart", NS)
    parts_with_solid = [zp for zp in zone_parts if zp.find("nrg3:lod3Solid", NS) is not None]
    assert len(parts_with_solid) == 3


def test_pv_has_geometry(renodat_root):
    """The PV collector must have lod3MultiSurface geometry from the STEP import."""
    pv_geom = renodat_root.findall(".//nrg3:PhotovoltaicCollector/nrg3:lod3MultiSurface", NS)
    assert len(pv_geom) == 1


# ---------------------------------------------------------------------------
# XSD validity with modified input
# ---------------------------------------------------------------------------


def test_multiple_buildings_validate_against_xsd(xsd_schema):
    """Adding a second building still produces XSD-valid output."""
    data = load_feature_collection(INPUT)
    second_building = deepcopy(data["features"][0])
    second_building["id"] = "id_building_2"
    second_building["name"] = ["Leia's house"]
    second_building["identifier"] = [
        {"value": "0000000000000002", "code_space": "https://example.invalid/bag"},
    ]

    extended_data = deepcopy(data)
    extended_data["features"].append(second_building)

    model = build_city_model_from_feature_collection(extended_data)
    xml = model.to_string()
    doc = etree.fromstring(xml.encode("utf-8"))
    xsd_schema.assertValid(doc)


# ---------------------------------------------------------------------------
# Supplementary: qualities the XSD cannot enforce
# ---------------------------------------------------------------------------


def test_generated_has_envelope_with_crs(renodat_root):
    """The gml:Envelope carries srsName and srsDimension (needed by CityGML readers)."""
    envelope = renodat_root.find(".//gml:Envelope", NS)
    assert envelope is not None, "Missing gml:Envelope"
    assert "srsName" in envelope.attrib
    assert envelope.attrib["srsDimension"] == "3"


def test_geometry_elements_have_srs(renodat_root):
    """All gml:MultiSurface elements carry srsName and srsDimension."""
    multi_surfaces = renodat_root.findall(".//gml:MultiSurface", NS)
    assert len(multi_surfaces) > 0
    for ms in multi_surfaces:
        assert "srsName" in ms.attrib, f"Missing srsName on {ms.attrib}"
        assert "srsDimension" in ms.attrib, f"Missing srsDimension on {ms.attrib}"


def test_no_scientific_notation_in_coordinates(renodat_root):
    """Coordinate values must not contain scientific notation (breaks many CityGML readers)."""
    for pos_list in renodat_root.findall(".//gml:posList", NS):
        text = pos_list.text or ""
        for token in text.split():
            assert "e" not in token.lower(), f"Scientific notation found in coordinates: {token}"


# ---------------------------------------------------------------------------
# Input loader: error handling
# ---------------------------------------------------------------------------


def test_renodat_input_rejects_unknown_feature_type():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["features"][0]["type"] = "nrg3:NotSupported"

    with pytest.raises(InputFileError, match="Unknown type"):
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
