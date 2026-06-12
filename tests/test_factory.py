"""XSD validation tests for each supported feature type using xsdata bindings.

Every test constructs xsdata-generated objects directly, wraps them in a
CityModel, serializes to XML, and validates against the full Energy ADE 3.0
beta8 + CityGML 2.0 XSD schema set.
"""

import lxml.etree as etree
import pytest
from xsdata.models.datatype import XmlDate, XmlPeriod

from citygml_energy.bindings import (
    AbstractSchedulePropertyType,
    AbstractTimeSeriesPropertyType,
    AngleType,
    BoundarySurfacePropertyType2,
    Building,
    BuildingUnit1,
    BuildingUnit2,
    CityModel,
    CityObjectMember,
    CodeType,
    ConstantValueSchedule,
    Device,
    Energy,
    EnergyPerformanceCertificate1,
    EnergyPerformanceCertificate2,
    EvchargingStation,
    HeatPump,
    MeasureListType,
    MeasureType,
    MonthlyTimeSeries,
    Name,
    Occupants,
    OccupantsPropertyType,
    OpeningPropertyType2,
    PhotovoltaicCollector,
    Resource,
    WallSurface2,
    Window2,
    Zone1,
    Zone2,
    ZonePart,
    ZonePartPropertyType,
)
from citygml_energy.namespaces import (
    CS_BUILDING_CLASS,
    CS_BUILDING_FUNCTION,
    CS_BUILDING_ROOFTYPE,
    CS_NRG3_BUILDING_TYPE,
    CS_NRG3_CELL_TYPE,
    CS_NRG3_CURRENT_USE,
    CS_NRG3_ENERGY_END_USE,
    CS_NRG3_ENERGY_TYPE,
    CS_NRG3_EPC_TYPE,
    CS_NRG3_EV_SPEED_LEVEL,
    CS_NRG3_EV_STATION_TYPE,
    CS_NRG3_HEAT_SOURCE,
    CS_NRG3_OCCUPANTS_TYPE,
    CS_NRG3_RESOURCE_OPERATION_TYPE,
    CS_NRG3_SCHEDULE_TYPE,
)
from citygml_energy.serialization import serialize_to_string
from tools.validate_xsd import load_schema

# ---------------------------------------------------------------------------
# Shared XSD schema (loaded once per session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def xsd_schema():
    return load_schema()


def _validate(city_model: CityModel, xsd_schema) -> None:
    """Serialize and validate a CityModel against the XSD.

    Also cross-checks that every ``CityObjectMember`` constructed in
    Python actually appears as a ``gml:id``-bearing element in the
    serialized XML. XSD validation alone permits an empty document
    (``minOccurs=0`` on every child), so a future refactor that forgets
    to attach a feature to the model would still pass. This routine
    catches that by diffing the input-side id set against the output.
    """
    xml = serialize_to_string(city_model)
    doc = etree.fromstring(xml.encode("utf-8"))
    xsd_schema.validate(doc)
    errors = [str(e) for e in xsd_schema.error_log]
    assert not errors, "XSD validation errors:\n" + "\n".join(errors)

    # Collect every gml:id attached to a top-level feature in the model.
    # xsdata dataclasses use ``__slots__``, so iterate declared fields.
    import dataclasses as _dc

    expected_ids: set[str] = set()
    for member in city_model.city_object_member:
        for field in _dc.fields(member):
            candidate = getattr(member, field.name, None)
            if candidate is None or isinstance(candidate, (str, int, float, bool, list)):
                continue
            fid = getattr(candidate, "id", None)
            if isinstance(fid, str) and fid:
                expected_ids.add(fid)
                break

    actual_ids = {
        el.get("{http://www.opengis.net/gml}id")
        for el in doc.iter()
        if el.get("{http://www.opengis.net/gml}id")
    }
    missing = expected_ids - actual_ids
    assert not missing, (
        "feature(s) declared in the CityModel never made it into the "
        f"serialized XML: {sorted(missing)}"
    )
    assert expected_ids, "test fixture built an empty CityModel; _validate would pass vacuously"


# ---------------------------------------------------------------------------
# XSD validation: individual feature types
# ---------------------------------------------------------------------------


def test_building_validates(xsd_schema):
    building = Building(
        id="bldg_1",
        name=[Name(value="Test house")],
        class_value=CodeType(value="1000", code_space=CS_BUILDING_CLASS),
        function=[CodeType(value="1000", code_space=CS_BUILDING_FUNCTION)],
        year_of_construction=XmlPeriod("2020"),
        storeys_above_ground=2,
        storeys_below_ground=0,
        roof_type=CodeType(value="1030", code_space=CS_BUILDING_ROOFTYPE),
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_pv_collector_validates(xsd_schema):
    pv = PhotovoltaicCollector(
        id="pv_1",
        name=[Name(value="Test PV")],
        model="PV-16-270 PW",
        year_of_installation=2020,
        number_of_devices=36,
        installed_power=MeasureType(value=9720, uom="W"),
        azimuth=AngleType(value=235.65, uom="deg"),
        inclination=AngleType(value=45.0, uom="deg"),
        cell_type=CodeType(value="monocrystalline", code_space=CS_NRG3_CELL_TYPE),
    )
    building = Building(
        id="bldg_1",
        device=[Device(photovoltaic_collector=pv)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_heat_pump_validates(xsd_schema):
    hp = HeatPump(
        id="hp_1",
        model="NIBE F1255 PC",
        installed_power=MeasureType(value=6000, uom="W"),
        heat_source=CodeType(value="waterSource", code_space=CS_NRG3_HEAT_SOURCE),
        cop_source_temperature=MeasureType(value=24, uom="Cel"),
        cop_operation_temperature=MeasureType(value=31, uom="Cel"),
    )
    building = Building(
        id="bldg_1",
        device=[Device(heat_pump=hp)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_ev_charging_station_validates(xsd_schema):
    ev = EvchargingStation(
        id="ev_1",
        type_value=CodeType(value="AC", code_space=CS_NRG3_EV_STATION_TYPE),
        charging_speed_level=CodeType(value="Level 2", code_space=CS_NRG3_EV_SPEED_LEVEL),
        has_load_management=True,
    )
    building = Building(
        id="bldg_1",
        device=[Device(evcharging_station=ev)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_occupants_validates(xsd_schema):
    occ = Occupants(
        id="occ_1",
        type_value=CodeType(value="residents", code_space=CS_NRG3_OCCUPANTS_TYPE),
        number_of_occupants=4,
        heat_dissipation=MeasureType(value=80, uom="W"),
    )
    unit = BuildingUnit1(
        id="bu_1",
        type_value=CodeType(value="apartment", code_space=CS_NRG3_BUILDING_TYPE),
        occupied_by=[OccupantsPropertyType(occupants=occ)],
    )
    building = Building(
        id="bldg_1",
        building_unit=[BuildingUnit2(building_unit=unit)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_epc_validates(xsd_schema):
    epc = EnergyPerformanceCertificate1(
        id="epc_1",
        type_value=CodeType(value="EPC-NL", code_space=CS_NRG3_EPC_TYPE),
        label="A",
        value=MeasureType(value=50, uom="kWh/m2/a"),
    )
    building = Building(
        id="bldg_1",
        energy_performance_certificate=[
            EnergyPerformanceCertificate2(energy_performance_certificate=epc)
        ],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_building_unit_validates(xsd_schema):
    bu = BuildingUnit1(
        id="bu_1",
        type_value=CodeType(value="apartment", code_space=CS_NRG3_BUILDING_TYPE),
        number_of_rooms=3,
        owner_name="Jane Doe",
    )
    building = Building(
        id="bldg_1",
        building_unit=[BuildingUnit2(building_unit=bu)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_constant_value_schedule_validates(xsd_schema):
    schedule = ConstantValueSchedule(
        id="sched_1",
        type_value=CodeType(value="typicalYear", code_space=CS_NRG3_SCHEDULE_TYPE),
        value=MeasureType(value=22, uom="Cel"),
    )
    zone_part = ZonePart(
        id="zp_1",
        type_value=CodeType(value="residential", code_space=CS_NRG3_CURRENT_USE),
        is_heated=True,
        is_cooled=False,
        heating_schedule=AbstractSchedulePropertyType(
            constant_value_schedule=schedule,
        ),
    )
    zone = Zone1(
        id="zone_1",
        type_value=CodeType(value="residential", code_space=CS_NRG3_CURRENT_USE),
        zone_part=[ZonePartPropertyType(zone_part=zone_part)],
    )
    building = Building(
        id="bldg_1",
        zone=[Zone2(zone=zone)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_energy_resource_validates(xsd_schema):
    energy = Energy(
        id="energy_1",
        operation_type=CodeType(value="demands", code_space=CS_NRG3_RESOURCE_OPERATION_TYPE),
        is_amount_normalized=False,
        type_value=CodeType(value="final", code_space=CS_NRG3_ENERGY_TYPE),
        end_use=CodeType(value="mobility", code_space=CS_NRG3_ENERGY_END_USE),
        amount=MeasureType(value=1.125, uom="MWh/a"),
    )
    ev = EvchargingStation(
        id="ev_1",
        type_value=CodeType(value="AC", code_space=CS_NRG3_EV_STATION_TYPE),
        resource=[Resource(energy=energy)],
    )
    building = Building(
        id="bldg_1",
        device=[Device(evcharging_station=ev)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_wall_surface_validates(xsd_schema):
    wall = WallSurface2(id="wall_1")
    building = Building(
        id="bldg_1",
        bounded_by=[BoundarySurfacePropertyType2(wall_surface=wall)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_window_on_wall_validates(xsd_schema):
    window = Window2(id="win_1")
    wall = WallSurface2(
        id="wall_1",
        opening=[OpeningPropertyType2(window=window)],
    )
    building = Building(
        id="bldg_1",
        bounded_by=[BoundarySurfacePropertyType2(wall_surface=wall)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_multiple_devices_validate(xsd_schema):
    pv = PhotovoltaicCollector(
        id="pv_1",
        cell_type=CodeType(value="monocrystalline", code_space=CS_NRG3_CELL_TYPE),
    )
    hp = HeatPump(
        id="hp_1",
        heat_source=CodeType(value="airSource", code_space=CS_NRG3_HEAT_SOURCE),
    )
    ev = EvchargingStation(
        id="ev_1",
        type_value=CodeType(value="AC", code_space=CS_NRG3_EV_STATION_TYPE),
    )
    building = Building(
        id="bldg_1",
        device=[
            Device(photovoltaic_collector=pv),
            Device(heat_pump=hp),
            Device(evcharging_station=ev),
        ],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)


def test_multiple_buildings_validate(xsd_schema):
    b1 = Building(id="bldg_1", name=[Name(value="House 1")])
    b2 = Building(id="bldg_2", name=[Name(value="House 2")])
    model = CityModel(
        city_object_member=[
            CityObjectMember(building=b1),
            CityObjectMember(building=b2),
        ]
    )
    _validate(model, xsd_schema)


def test_monthly_time_series_validates(xsd_schema):
    ts = MonthlyTimeSeries(
        id="ts_1",
        interpolation_type="averageInSucceedingInterval",
        start_date=XmlDate(2024, 1, 1),
        end_date=XmlDate(2024, 12, 1),
        values_list=MeasureListType(
            value=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
            uom="kWh",
        ),
    )
    energy = Energy(
        id="energy_1",
        operation_type=CodeType(value="produces", code_space=CS_NRG3_RESOURCE_OPERATION_TYPE),
        is_amount_normalized=False,
        type_value=CodeType(value="final", code_space=CS_NRG3_ENERGY_TYPE),
        end_use=CodeType(value="electricalAppliances", code_space=CS_NRG3_ENERGY_END_USE),
        time_dependent_amount=AbstractTimeSeriesPropertyType(
            monthly_time_series=ts,
        ),
    )
    pv = PhotovoltaicCollector(
        id="pv_1",
        cell_type=CodeType(value="monocrystalline", code_space=CS_NRG3_CELL_TYPE),
        resource=[Resource(energy=energy)],
    )
    building = Building(
        id="bldg_1",
        device=[Device(photovoltaic_collector=pv)],
    )
    model = CityModel(city_object_member=[CityObjectMember(building=building)])
    _validate(model, xsd_schema)
