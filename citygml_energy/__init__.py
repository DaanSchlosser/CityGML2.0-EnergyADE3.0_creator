"""CityGML 2.0 + Energy ADE 3.0 Creator -- public API.

Usage::

    from citygml_energy import (
        GMLDocument, Building, PhotovoltaicCollector, HeatPump,
        EVChargingStation, Metadata, QualifiedVolume, Occupants,
        CodeValue, MeasureValue,
    )
"""

# Value types
# Building module
from .building import (
    Building,
    BuildingInstallation,
    BuildingPart,
    CeilingSurface,
    ClosureSurface,
    Door,
    FloorSurface,
    GroundSurface,
    IntBuildingInstallation,
    OuterCeilingSurface,
    OuterFloorSurface,
    RoofSurface,
    Room,
    WallSurface,
    Window,
    Zone,
    ZonePart,
)

# Core
from .core import Address, CityModel, Envelope

# Energy ADE module
from .energy_ade import (
    BuildingUnit,
    CityObjectRelation,
    CompositeSchedule,
    ConstantValueSchedule,
    DeviceOperation,
    Energy,
    EnergyPerformanceCertificate,
    EVChargingStation,
    HeatPump,
    Metadata,
    Occupants,
    PhotovoltaicCollector,
    QualifiedArea,
    QualifiedHeight,
    QualifiedVolume,
    ScheduleComponent,
)

# Excel loader
from .excel_loader import (
    load_city_model_from_excel,
    load_excel_feature_collection,
)

# Factory
from .factory import (
    FeatureFactory,
    auto_from_dict,
    building_from_dict,
    building_unit_from_dict,
    constant_value_schedule_from_dict,
    create_feature,
    energy_from_dict,
    epc_from_dict,
    ev_charging_station_from_dict,
    heat_pump_from_dict,
    list_feature_types,
    occupants_from_dict,
    pv_collector_from_dict,
    zone_from_dict,
    zone_part_from_dict,
)

# Canonical generation workflow
from .generation import (
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    generate_city_model,
    generate_gml_file,
)

# Input loader
from .input_loader import (
    InputFileError,
    build_city_model_from_feature_collection,
    load_city_model_from_feature_collection,
    load_feature_collection,
)

# Codespace constants
from .namespaces import (
    CS_BUILDING_CLASS,
    CS_BUILDING_FUNCTION,
    CS_BUILDING_ROOFTYPE,
    CS_BUILDING_USAGE,
    CS_NRG3_AREA_TYPE,
    CS_NRG3_BU_TYPE,
    CS_NRG3_BUILDING_TYPE,
    CS_NRG3_CELL_TYPE,
    CS_NRG3_CURRENT_USE,
    CS_NRG3_CONSTRUCTION_WEIGHT,
    CS_NRG3_DEVICE_OPERATION_TYPE,
    CS_NRG3_EPC_TYPE,
    CS_NRG3_EV_TYPE,
    CS_NRG3_HEAT_SOURCE,
    CS_NRG3_HEIGHT_TYPE,
    CS_NRG3_OCCUPANT_TYPE,
    CS_NRG3_OWNERSHIP_TYPE,
    CS_NRG3_RELATION_TYPE,
    CS_NRG3_SCHEDULE_TYPE,
    CS_NRG3_VOLUME_TYPE,
)

# XML-backed helpers
from .template import (
    find_city_object_by_gml_id,
    load_city_model_template,
    normalize_city_model_for_beta8,
)
from .types import CodeValue, MeasureValue, ScaleValue
from .xml_support import RawXmlElement

__all__ = [
    # Codespace constants
    "CS_BUILDING_CLASS",
    "CS_BUILDING_FUNCTION",
    "CS_BUILDING_ROOFTYPE",
    "CS_BUILDING_USAGE",
    "CS_NRG3_AREA_TYPE",
    "CS_NRG3_BUILDING_TYPE",
    "CS_NRG3_BU_TYPE",
    "CS_NRG3_CELL_TYPE",
    "CS_NRG3_CURRENT_USE",
    "CS_NRG3_CONSTRUCTION_WEIGHT",
    "CS_NRG3_DEVICE_OPERATION_TYPE",
    "CS_NRG3_EPC_TYPE",
    "CS_NRG3_EV_TYPE",
    "CS_NRG3_HEAT_SOURCE",
    "CS_NRG3_HEIGHT_TYPE",
    "CS_NRG3_OCCUPANT_TYPE",
    "CS_NRG3_OWNERSHIP_TYPE",
    "CS_NRG3_RELATION_TYPE",
    "CS_NRG3_SCHEDULE_TYPE",
    "CS_NRG3_VOLUME_TYPE",
    "DEFAULT_INPUT_PATH",
    "DEFAULT_OUTPUT_PATH",
    # Core
    "Address",
    # Building
    "Building",
    "BuildingInstallation",
    "BuildingPart",
    # Energy ADE
    "BuildingUnit",
    "CeilingSurface",
    "CityModel",
    "CityObjectRelation",
    "ClosureSurface",
    # Value types
    "CodeValue",
    "CompositeSchedule",
    "ConstantValueSchedule",
    "DeviceOperation",
    "Door",
    "EVChargingStation",
    "Energy",
    "EnergyPerformanceCertificate",
    "Envelope",
    # Factory
    "FeatureFactory",
    "auto_from_dict",
    "FloorSurface",
    "GroundSurface",
    "HeatPump",
    # Input loader
    "InputFileError",
    "IntBuildingInstallation",
    "MeasureValue",
    "Metadata",
    "Occupants",
    "OuterCeilingSurface",
    "OuterFloorSurface",
    "PhotovoltaicCollector",
    "QualifiedArea",
    "QualifiedHeight",
    "QualifiedVolume",
    "RawXmlElement",
    "RoofSurface",
    "Room",
    "ScaleValue",
    "ScheduleComponent",
    "WallSurface",
    "Window",
    "build_city_model_from_feature_collection",
    "building_from_dict",
    "building_unit_from_dict",
    "constant_value_schedule_from_dict",
    "create_feature",
    "energy_from_dict",
    "epc_from_dict",
    "ev_charging_station_from_dict",
    # XML-backed helpers
    "find_city_object_by_gml_id",
    "generate_city_model",
    "generate_gml_file",
    "heat_pump_from_dict",
    "list_feature_types",
    "load_city_model_from_excel",
    "load_city_model_from_feature_collection",
    "load_city_model_template",
    "load_excel_feature_collection",
    "load_feature_collection",
    "normalize_city_model_for_beta8",
    "occupants_from_dict",
    "pv_collector_from_dict",
    "Zone",
    "ZonePart",
    "zone_from_dict",
    "zone_part_from_dict",
]
