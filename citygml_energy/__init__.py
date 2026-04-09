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
)

# Core
from .core import Address, CityModel, Envelope

# Document
from .document import GMLDocument

# Energy ADE module
from .energy_ade import (
    BuildingUnit,
    CompositeSchedule,
    ConstantValueSchedule,
    DeviceOperation,
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

# Factory
from .factory import (
    FeatureFactory,
    building_from_dict,
    building_unit_from_dict,
    constant_value_schedule_from_dict,
    create_feature,
    epc_from_dict,
    ev_charging_station_from_dict,
    heat_pump_from_dict,
    list_feature_types,
    occupants_from_dict,
    pv_collector_from_dict,
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
    CS_NRG3_CONSTRUCTION_WEIGHT,
    CS_NRG3_DEVICE_OPERATION_TYPE,
    CS_NRG3_EPC_TYPE,
    CS_NRG3_EV_TYPE,
    CS_NRG3_HEAT_SOURCE,
    CS_NRG3_HEIGHT_TYPE,
    CS_NRG3_OCCUPANT_TYPE,
    CS_NRG3_OWNERSHIP_TYPE,
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

# Validation
from .validation import (
    compare_with_reference,
    validate_file_against_energy_ade_schema,
    validate_xml_against_energy_ade_schema,
)
from .xml_support import RawXmlElement

__all__ = [
    # Value types
    "CodeValue",
    "MeasureValue",
    "ScaleValue",
    # Core
    "Address",
    "CityModel",
    "Envelope",
    "GMLDocument",
    "RawXmlElement",
    "DEFAULT_INPUT_PATH",
    "DEFAULT_OUTPUT_PATH",
    "generate_city_model",
    "generate_gml_file",
    # Input loader
    "InputFileError",
    "build_city_model_from_feature_collection",
    "load_city_model_from_feature_collection",
    "load_feature_collection",
    # Building
    "Building",
    "BuildingInstallation",
    "BuildingPart",
    "CeilingSurface",
    "ClosureSurface",
    "Door",
    "FloorSurface",
    "GroundSurface",
    "IntBuildingInstallation",
    "OuterCeilingSurface",
    "OuterFloorSurface",
    "RoofSurface",
    "Room",
    "WallSurface",
    "Window",
    # Energy ADE
    "BuildingUnit",
    "CompositeSchedule",
    "ConstantValueSchedule",
    "DeviceOperation",
    "EnergyPerformanceCertificate",
    "EVChargingStation",
    "HeatPump",
    "Metadata",
    "Occupants",
    "PhotovoltaicCollector",
    "QualifiedArea",
    "QualifiedHeight",
    "QualifiedVolume",
    "ScheduleComponent",
    # XML-backed helpers
    "find_city_object_by_gml_id",
    "load_city_model_template",
    "normalize_city_model_for_beta8",
    # Validation
    "compare_with_reference",
    "validate_file_against_energy_ade_schema",
    "validate_xml_against_energy_ade_schema",
    # Factory
    "FeatureFactory",
    "building_from_dict",
    "building_unit_from_dict",
    "constant_value_schedule_from_dict",
    "create_feature",
    "epc_from_dict",
    "ev_charging_station_from_dict",
    "heat_pump_from_dict",
    "list_feature_types",
    "occupants_from_dict",
    "pv_collector_from_dict",
    # Codespace constants
    "CS_BUILDING_CLASS",
    "CS_BUILDING_FUNCTION",
    "CS_BUILDING_ROOFTYPE",
    "CS_BUILDING_USAGE",
    "CS_NRG3_AREA_TYPE",
    "CS_NRG3_BU_TYPE",
    "CS_NRG3_BUILDING_TYPE",
    "CS_NRG3_CELL_TYPE",
    "CS_NRG3_CONSTRUCTION_WEIGHT",
    "CS_NRG3_DEVICE_OPERATION_TYPE",
    "CS_NRG3_EPC_TYPE",
    "CS_NRG3_EV_TYPE",
    "CS_NRG3_HEAT_SOURCE",
    "CS_NRG3_HEIGHT_TYPE",
    "CS_NRG3_OCCUPANT_TYPE",
    "CS_NRG3_OWNERSHIP_TYPE",
    "CS_NRG3_SCHEDULE_TYPE",
    "CS_NRG3_VOLUME_TYPE",
]
