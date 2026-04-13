"""Tests for the FME-style flat-attribute factory (citygml_energy/factory.py)."""

import pytest
from lxml import etree

from citygml_energy import (
    CS_BUILDING_CLASS,
    CS_BUILDING_FUNCTION,
    CS_BUILDING_ROOFTYPE,
    CS_BUILDING_USAGE,
    CS_NRG3_BUILDING_TYPE,
    CS_NRG3_OWNERSHIP_TYPE,
    CS_NRG3_VOLUME_TYPE,
    Building,
    FeatureFactory,
    PhotovoltaicCollector,
    WallSurface,
    building_from_dict,
    building_unit_from_dict,
    create_feature,
    list_feature_types,
)

# ---------------------------------------------------------------------------
# Helpers: reusable attribute dicts
# ---------------------------------------------------------------------------

_BUILDING_ATTRS = {
    "gml_id": "id_building_1",
    "gml_name": "Han solo's house",
    "core_creationDate": "2026-04-04",
    "nrg3_identifier": "0503100000032914",
    "nrg3_identifier_codeSpace": "https://bagviewer.kadaster.nl/?objectId=0503100000032914",
    "nrg3_metadata_author": "Daan Schlosser",
    "nrg3_metadata_acquisitionMethod": "measurement",
    "nrg3_metadata_owner": "Han Solo",
    "bldg_class": "1000",
    "bldg_class_codeSpace": CS_BUILDING_CLASS,
    "bldg_function": "1000",
    "bldg_function_codeSpace": CS_BUILDING_FUNCTION,
    "bldg_usage": "1000",
    "bldg_usage_codeSpace": CS_BUILDING_USAGE,
    "bldg_yearOfConstruction": "2020",
    "bldg_roofType": "1030",
    "bldg_roofType_codeSpace": CS_BUILDING_ROOFTYPE,
    "bldg_storeysAboveGround": "3",
    "bldg_storeysBelowGround": "0",
    "nrg3_bdgIsProtected": "false",
    "nrg3_bdgNumberOfBuildingUnits": "1",
    "nrg3_bdgOwnerName": "Han Solo",
    "nrg3_bdgOwnershipType": "occupantPrivateOwner",
    "nrg3_bdgOwnershipType_codeSpace": CS_NRG3_OWNERSHIP_TYPE,
    "nrg3_bdgType": "singleFamilyHouse",
    "nrg3_bdgType_codeSpace": CS_NRG3_BUILDING_TYPE,
    "nrg3_bdgVolume_description": "Building's gross volume of 3D model",
    "nrg3_bdgVolume_source": "3D model",
    "nrg3_bdgVolume_value": "823.30",
    "nrg3_bdgVolume_uom": "m3",
    "nrg3_bdgVolume_type": "grossVolume",
    "nrg3_bdgVolume_type_codeSpace": CS_NRG3_VOLUME_TYPE,
}

_PV_ATTRS = {
    "gml_id": "pv_panel_1",
    "gml_parent_id": "id_building_1",
    "gml_name": "PV collector (36x270 Wp)",
    "core_creationDate": "2026-04-04",
    "nrg3_model": "PV-16-270 PW",
    "nrg3_yearOfInstallation": "2020",
    "nrg3_numberOfDevices": "36",
    "nrg3_installedPower": "9720",
    "nrg3_installedPower_uom": "W",
    "nrg3_azimuth": "235.65",
    "nrg3_azimuth_uom": "deg",
    "nrg3_inclination": "44.51",
    "nrg3_inclination_uom": "deg",
    "nrg3_cellType": "unknown",
}


# ---------------------------------------------------------------------------
# list_feature_types
# ---------------------------------------------------------------------------


def test_list_feature_types_contains_expected():
    types = list_feature_types()
    assert "bldg_Building" in types
    assert "nrg3_PhotovoltaicCollector" in types
    assert "nrg3_HeatPump" in types
    assert "nrg3_EVChargingStation" in types
    assert "nrg3_Occupants" in types
    assert "nrg3_EnergyPerformanceCertificate" in types
    assert "nrg3_BuildingUnit" in types
    assert "nrg3_ConstantValueSchedule" in types
    assert "bldg_WallSurface" in types
    assert "bldg_RoofSurface" in types
    assert "bldg_GroundSurface" in types
    assert "bldg_Window" in types
    assert "bldg_Door" in types


def test_list_feature_types_is_sorted():
    types = list_feature_types()
    assert types == sorted(types)


def test_list_feature_types_excludes_unimplemented_by_default():
    types = list_feature_types()
    assert "nrg3_WeatherStation" not in types


# ---------------------------------------------------------------------------
# create_feature dispatch
# ---------------------------------------------------------------------------


def test_create_feature_building():
    obj = create_feature("bldg_Building", {"gml_id": "b1"})
    assert isinstance(obj, Building)
    assert obj.gml_id == "b1"


def test_create_feature_pv():
    obj = create_feature("nrg3_PhotovoltaicCollector", {"gml_id": "pv1"})
    assert isinstance(obj, PhotovoltaicCollector)
    assert obj.gml_id == "pv1"


def test_create_feature_unknown_raises():
    with pytest.raises(ValueError, match="Unknown feature type"):
        create_feature("not_a_feature", {})


# ---------------------------------------------------------------------------
# building_from_dict
# ---------------------------------------------------------------------------


def test_building_from_dict_basic_fields():
    b = building_from_dict(_BUILDING_ATTRS)
    assert b.gml_id == "id_building_1"
    assert b.gml_name == "Han solo's house"
    assert b.creation_date == "2026-04-04"
    assert b.year_of_construction == 2020
    assert b.storeys_above_ground == 3
    assert b.storeys_below_ground == 0
    assert b.bdg_is_protected is False
    assert b.bdg_number_of_building_units == 1
    assert b.bdg_owner_name == "Han Solo"


def test_building_from_dict_code_values():
    b = building_from_dict(_BUILDING_ATTRS)
    assert b.bldg_class.value == "1000"
    assert b.bldg_class.code_space == CS_BUILDING_CLASS
    assert b.bdg_ownership_type.value == "occupantPrivateOwner"
    assert b.bdg_type.value == "singleFamilyHouse"


def test_building_from_dict_identifier():
    b = building_from_dict(_BUILDING_ATTRS)
    assert b.nrg3_identifier.value == "0503100000032914"
    assert "bagviewer" in b.nrg3_identifier.code_space


def test_building_from_dict_metadata():
    b = building_from_dict(_BUILDING_ATTRS)
    assert b.nrg3_metadata.author == "Daan Schlosser"
    assert b.nrg3_metadata.acquisition_method.value == "measurement"
    assert b.nrg3_metadata.owner == "Han Solo"


def test_building_from_dict_qualified_volume():
    b = building_from_dict(_BUILDING_ATTRS)
    assert len(b.bdg_volumes) == 1
    vol = b.bdg_volumes[0]
    assert vol.value.text == "823.30"
    assert vol.value.uom == "m3"
    assert vol.type.value == "grossVolume"


def test_building_from_dict_empty():
    """Empty attrs should not raise, all optional fields stay None."""
    b = building_from_dict({})
    assert b.gml_id is None
    assert b.bldg_class is None
    assert b.bdg_volumes == []


# ---------------------------------------------------------------------------
# pv_collector_from_dict
# ---------------------------------------------------------------------------


def test_pv_from_dict_fields():
    pv = create_feature("nrg3_PhotovoltaicCollector", _PV_ATTRS)
    assert pv.gml_id == "pv_panel_1"
    assert pv.gml_name == "PV collector (36x270 Wp)"
    assert pv.model == "PV-16-270 PW"
    assert pv.year_of_installation == 2020
    assert pv.number_of_devices == 36
    assert pv.installed_power.text == "9720"
    assert pv.installed_power.uom == "W"
    assert pv.azimuth.text == "235.65"
    assert pv.inclination.text == "44.51"
    assert pv.cell_type.value == "unknown"


# ---------------------------------------------------------------------------
# heat_pump_from_dict
# ---------------------------------------------------------------------------


def test_heat_pump_from_dict():
    hp = create_feature(
        "nrg3_HeatPump",
        {
            "gml_id": "hp_1",
            "nrg3_model": "Daikin X",
            "nrg3_installedPower": "5000",
            "nrg3_installedPower_uom": "W",
            "nrg3_heatSource": "airSource",
            "nrg3_copSourceTemperature": "7",
            "nrg3_copSourceTemperature_uom": "degC",
        },
    )
    assert hp.gml_id == "hp_1"
    assert hp.model == "Daikin X"
    assert hp.heat_source.value == "airSource"
    assert hp.cop_source_temperature.text == "7"


# ---------------------------------------------------------------------------
# ev_charging_station_from_dict
# ---------------------------------------------------------------------------


def test_ev_from_dict():
    ev = create_feature(
        "nrg3_EVChargingStation",
        {
            "gml_id": "ev_1",
            "nrg3_evType": "normalCharger",
            "nrg3_chargingSpeedLevel": "slow",
            "nrg3_hasLoadManagement": "true",
        },
    )
    assert ev.gml_id == "ev_1"
    assert ev.ev_type.value == "normalCharger"
    assert ev.has_load_management is True


# ---------------------------------------------------------------------------
# Occupants via create_feature (auto_from_dict)
# ---------------------------------------------------------------------------


def test_occupants_from_dict():
    occ = create_feature(
        "nrg3_Occupants",
        {
            "gml_id": "occ_1",
            "nrg3_occupantType": "residents",
            "nrg3_numberOfOccupants": "4",
        },
    )
    assert occ.gml_id == "occ_1"
    assert occ.occupant_type.value == "residents"
    assert occ.number_of_occupants == 4


# ---------------------------------------------------------------------------
# EPC via create_feature (auto_from_dict)
# ---------------------------------------------------------------------------


def test_epc_from_dict():
    epc = create_feature(
        "nrg3_EnergyPerformanceCertificate",
        {
            "gml_id": "epc_1",
            "nrg3_epcLabel": "A",
            "nrg3_epcValue": "50",
            "nrg3_epcValue_uom": "kWh/(m^2*a)",
        },
    )
    assert epc.label == "A"
    assert epc.value.text == "50"
    assert epc.value.uom == "kWh/(m^2*a)"


# ---------------------------------------------------------------------------
# building_unit_from_dict
# ---------------------------------------------------------------------------


def test_building_unit_from_dict():
    bu = building_unit_from_dict(
        {
            "gml_id": "bu_1",
            "nrg3_buType": "apartment",
            "nrg3_numberOfRooms": "3",
            "nrg3_ownerName": "Jane Doe",
        }
    )
    assert bu.gml_id == "bu_1"
    assert bu.bu_type.value == "apartment"
    assert bu.number_of_rooms == 3
    assert bu.owner_name == "Jane Doe"


# ---------------------------------------------------------------------------
# ConstantValueSchedule via create_feature (auto_from_dict)
# ---------------------------------------------------------------------------


def test_constant_value_schedule_from_dict():
    sched = create_feature(
        "nrg3_ConstantValueSchedule",
        {
            "gml_id": "sched_1",
            "nrg3_scheduleValue": "1.0",
            "nrg3_scheduleValue_uom": "unit interval",
        },
    )
    assert sched.gml_id == "sched_1"
    assert sched.value.text == "1.0"
    assert sched.value.uom == "unit interval"


# ---------------------------------------------------------------------------
# FeatureFactory: parent-child assembly
# ---------------------------------------------------------------------------


def test_factory_pv_attached_to_building():
    factory = FeatureFactory()
    factory.add("bldg_Building", {"gml_id": "bldg_1"})
    factory.add("nrg3_PhotovoltaicCollector", {"gml_id": "pv_1", "gml_parent_id": "bldg_1"})
    model = factory.build()
    # Should have exactly one member (the building)
    assert len(model.city_object_members) == 1
    bldg = model.city_object_members[0]
    assert len(bldg.devices) == 1
    assert isinstance(bldg.devices[0], PhotovoltaicCollector)


def test_factory_surface_attached_to_building():
    factory = FeatureFactory()
    factory.add("bldg_Building", {"gml_id": "bldg_1"})
    factory.add("bldg_WallSurface", {"gml_id": "wall_1", "gml_parent_id": "bldg_1"})
    model = factory.build()
    bldg = model.city_object_members[0]
    assert len(bldg.bounded_by_surfaces) == 1
    assert isinstance(bldg.bounded_by_surfaces[0], WallSurface)


def test_factory_missing_parent_raises():
    factory = FeatureFactory()
    factory.add(
        "nrg3_PhotovoltaicCollector",
        {
            "gml_id": "pv_1",
            "gml_parent_id": "nonexistent_building",
        },
    )
    with pytest.raises(ValueError, match="gml_parent_id"):
        factory.build()


def test_factory_no_parent_id_is_top_level():
    factory = FeatureFactory()
    factory.add("bldg_Building", {"gml_id": "bldg_1"})
    factory.add("bldg_Building", {"gml_id": "bldg_2"})
    model = factory.build()
    assert len(model.city_object_members) == 2


def test_factory_multiple_devices():
    factory = FeatureFactory()
    factory.add("bldg_Building", {"gml_id": "bldg_1"})
    factory.add("nrg3_PhotovoltaicCollector", {"gml_id": "pv_1", "gml_parent_id": "bldg_1"})
    factory.add("nrg3_HeatPump", {"gml_id": "hp_1", "gml_parent_id": "bldg_1"})
    factory.add("nrg3_EVChargingStation", {"gml_id": "ev_1", "gml_parent_id": "bldg_1"})
    model = factory.build()
    bldg = model.city_object_members[0]
    assert len(bldg.devices) == 3


def test_factory_output_is_well_formed_xml():
    """FeatureFactory produces well-formed XML for assembled models."""
    factory = FeatureFactory()
    factory.add("bldg_Building", {"gml_id": "bldg_1"})
    factory.add("nrg3_PhotovoltaicCollector", {"gml_id": "pv_1", "gml_parent_id": "bldg_1"})
    generated = factory.build().to_string()
    etree.fromstring(generated.encode("utf-8"))


if __name__ == "__main__":
    test_factory_output_is_well_formed_xml()
    print("All factory tests passed!")
