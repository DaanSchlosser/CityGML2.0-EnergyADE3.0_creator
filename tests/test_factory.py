"""XSD validation tests for each supported feature type.

Every test creates a feature from a flat attribute dict, wraps it in a
CityModel, serializes to XML, and validates against the full Energy ADE 3.0
beta8 + CityGML 2.0 XSD schema set.  This is the same validation that FME
performs when writing CityGML.
"""

import lxml.etree as etree
import pytest

from citygml_energy import (
    FeatureFactory,
    create_feature,
    list_feature_types,
)
from tools.validate_xsd import load_schema

# ---------------------------------------------------------------------------
# Shared XSD schema (loaded once per session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def xsd_schema():
    return load_schema()


def _validate_features(features: list[tuple[str, dict]], xsd_schema):
    """Build a CityModel from *features*, serialize, and assert XSD validity.

    Each entry is ``(feature_type, attributes_dict)``.  Features with a
    ``gml_parent_id`` are attached as children automatically.
    """
    factory = FeatureFactory()
    for ftype, attrs in features:
        factory.add(ftype, attrs)
    model = factory.build()
    xml = model.to_string()
    doc = etree.fromstring(xml.encode("utf-8"))
    xsd_schema.assertValid(doc)


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


def test_create_feature_unknown_raises():
    with pytest.raises(ValueError, match="Unknown feature type"):
        create_feature("not_a_feature", {})


# ---------------------------------------------------------------------------
# XSD validation: individual feature types
# ---------------------------------------------------------------------------


def test_building_validates(xsd_schema):
    _validate_features(
        [
            (
                "bldg_Building",
                {
                    "gml_id": "bldg_1",
                    "gml_name": "Test house",
                    "core_creationDate": "2026-04-13",
                    "bldg_class": {
                        "value": "1000",
                        "codeSpace": "http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_class.xml",
                    },
                    "bldg_function": {
                        "value": "1000",
                        "codeSpace": "http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_function.xml",
                    },
                    "bldg_yearOfConstruction": 2020,
                    "bldg_storeysAboveGround": 2,
                    "bldg_storeysBelowGround": 0,
                    "bldg_roofType": {
                        "value": "1030",
                        "codeSpace": "https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_roofType.xml",
                    },
                },
            )
        ],
        xsd_schema,
    )


def test_pv_collector_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_PhotovoltaicCollector",
                {
                    "gml_id": "pv_1",
                    "gml_parent_id": "bldg_1",
                    "gml_name": "Test PV",
                    "core_creationDate": "2026-04-13",
                    "nrg3_model": "PV-16-270 PW",
                    "nrg3_yearOfInstallation": 2020,
                    "nrg3_numberOfDevices": 36,
                    "nrg3_installedPower": {"value": "9720", "uom": "W"},
                    "nrg3_azimuth": {"value": "235.65", "uom": "deg"},
                    "nrg3_inclination": {"value": "44.51", "uom": "deg"},
                    "nrg3_cellType": {
                        "value": "monocrystalline",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CellTypeValue.xml",
                    },
                },
            ),
        ],
        xsd_schema,
    )


def test_heat_pump_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_HeatPump",
                {
                    "gml_id": "hp_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_model": "NIBE F1255 PC",
                    "nrg3_installedPower": {"value": "6000", "uom": "W"},
                    "nrg3_heatSource": {
                        "value": "waterSource",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/HeatSourceTypeValue.xml",
                    },
                    "nrg3_copSourceTemperature": {"value": "24", "uom": "degC"},
                    "nrg3_copOperationTemperature": {"value": "31", "uom": "degC"},
                },
            ),
        ],
        xsd_schema,
    )


def test_ev_charging_station_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_EVChargingStation",
                {
                    "gml_id": "ev_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_type": {
                        "value": "AC",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingStationTypeValue.xml",
                    },
                    "nrg3_chargingSpeedLevel": {
                        "value": "Level 2",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingSpeedLevelValue.xml",
                    },
                    "nrg3_hasLoadManagement": True,
                },
            ),
        ],
        xsd_schema,
    )


def test_occupants_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_Occupants",
                {
                    "gml_id": "occ_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_type": {
                        "value": "residents",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OccupantsTypeValue.xml",
                    },
                    "nrg3_numberOfOccupants": 4,
                    "nrg3_heatDissipation": {"value": "80", "uom": "W"},
                },
            ),
        ],
        xsd_schema,
    )


def test_epc_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_EnergyPerformanceCertificate",
                {
                    "gml_id": "epc_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_type": {
                        "value": "EPC-NL",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EPCTypeValue.xml",
                    },
                    "nrg3_label": "A",
                    "nrg3_value": {"value": "50", "uom": "kWh/(m^2*a)"},
                },
            ),
        ],
        xsd_schema,
    )


def test_building_unit_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_BuildingUnit",
                {
                    "gml_id": "bu_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_buType": {
                        "value": "apartment",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/BuildingUnitTypeValue.xml",
                    },
                    "nrg3_numberOfRooms": 3,
                    "nrg3_ownerName": "Jane Doe",
                },
            ),
        ],
        xsd_schema,
    )


def test_constant_value_schedule_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_Zone",
                {
                    "gml_id": "zone_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_zoneType": {
                        "value": "residential",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CurrentUseValue.xml",
                    },
                },
            ),
            (
                "nrg3_ZonePart",
                {
                    "gml_id": "zp_1",
                    "gml_parent_id": "zone_1",
                    "nrg3_zoneType": {
                        "value": "residential",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CurrentUseValue.xml",
                    },
                    "nrg3_isHeated": True,
                    "nrg3_isCooled": False,
                },
            ),
            (
                "nrg3_ConstantValueSchedule",
                {
                    "gml_id": "sched_1",
                    "gml_parent_id": "zp_1",
                    "gml_parent_field": "heating_schedule",
                    "nrg3_type": {
                        "value": "typicalYear",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml",
                    },
                    "nrg3_value": {"value": "22", "uom": "degC"},
                },
            ),
        ],
        xsd_schema,
    )


def test_energy_resource_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_EVChargingStation",
                {
                    "gml_id": "ev_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_type": {
                        "value": "AC",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingStationTypeValue.xml",
                    },
                },
            ),
            (
                "nrg3_Energy",
                {
                    "gml_id": "energy_1",
                    "gml_parent_id": "ev_1",
                    "nrg3_operationType": {
                        "value": "demands",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ResourceOperationTypeValue.xml",
                    },
                    "nrg3_isAmountNormalized": False,
                    "nrg3_type": {
                        "value": "finalEnergy",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyTypeValue.xml",
                    },
                    "nrg3_endUse": {
                        "value": "mobility",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyEndUseValue.xml",
                    },
                    "nrg3_amount": {"value": "1.125", "uom": "MWh/a"},
                },
            ),
        ],
        xsd_schema,
    )


def test_wall_surface_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "bldg_WallSurface",
                {
                    "gml_id": "wall_1",
                    "gml_parent_id": "bldg_1",
                },
            ),
        ],
        xsd_schema,
    )


def test_window_on_wall_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            ("bldg_WallSurface", {"gml_id": "wall_1", "gml_parent_id": "bldg_1"}),
            ("bldg_Window", {"gml_id": "win_1", "gml_parent_id": "wall_1"}),
        ],
        xsd_schema,
    )


def test_multiple_devices_validate(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_PhotovoltaicCollector",
                {
                    "gml_id": "pv_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_cellType": {
                        "value": "monocrystalline",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CellTypeValue.xml",
                    },
                },
            ),
            (
                "nrg3_HeatPump",
                {
                    "gml_id": "hp_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_heatSource": {
                        "value": "airSource",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/HeatSourceTypeValue.xml",
                    },
                },
            ),
            (
                "nrg3_EVChargingStation",
                {
                    "gml_id": "ev_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_type": {
                        "value": "AC",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingStationTypeValue.xml",
                    },
                },
            ),
        ],
        xsd_schema,
    )


def test_multiple_buildings_validate(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1", "gml_name": "House 1"}),
            ("bldg_Building", {"gml_id": "bldg_2", "gml_name": "House 2"}),
        ],
        xsd_schema,
    )


def test_monthly_time_series_validates(xsd_schema):
    _validate_features(
        [
            ("bldg_Building", {"gml_id": "bldg_1"}),
            (
                "nrg3_PhotovoltaicCollector",
                {
                    "gml_id": "pv_1",
                    "gml_parent_id": "bldg_1",
                    "nrg3_cellType": {
                        "value": "monocrystalline",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CellTypeValue.xml",
                    },
                },
            ),
            (
                "nrg3_Energy",
                {
                    "gml_id": "energy_1",
                    "gml_parent_id": "pv_1",
                    "nrg3_operationType": {
                        "value": "produces",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ResourceOperationTypeValue.xml",
                    },
                    "nrg3_isAmountNormalized": False,
                    "nrg3_type": {
                        "value": "finalEnergy",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyTypeValue.xml",
                    },
                    "nrg3_endUse": {
                        "value": "electricalAppliances",
                        "codeSpace": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyEndUseValue.xml",
                    },
                },
            ),
            (
                "nrg3_MonthlyTimeSeries",
                {
                    "gml_id": "ts_1",
                    "gml_parent_id": "energy_1",
                    "nrg3_interpolationType": "averageInSucceedingInterval",
                    "nrg3_startDate": "2024-01-01",
                    "nrg3_endDate": "2024-12-01",
                    "nrg3_valuesList": {
                        "value": "100 200 300 400 500 600 700 800 900 1000 1100 1200",
                        "uom": "kWh",
                    },
                },
            ),
        ],
        xsd_schema,
    )
