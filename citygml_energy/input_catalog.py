"""Supported JSON input keys for the data-driven RenoDAT workflow.

The repository accepts a curated subset of FME attribute names.
Each supported field has one canonical input key and can optionally define
one or more raw FME aliases. Users may provide either form in JSON input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class InputField:
    canonical: str
    aliases: tuple[str, ...] = ()


def _field(canonical: str, *aliases: str) -> InputField:
    return InputField(canonical=canonical, aliases=aliases)


def _qualified_fields(canonical_prefix: str, raw_prefix: str) -> tuple[InputField, ...]:
    return (
        _field(f"{canonical_prefix}_description", f"{raw_prefix}_description"),
        _field(f"{canonical_prefix}_source", f"{raw_prefix}_source"),
        _field(f"{canonical_prefix}_value", f"{raw_prefix}_value"),
        _field(f"{canonical_prefix}_uom", f"{raw_prefix}_value_units"),
        _field(f"{canonical_prefix}_type", f"{raw_prefix}_type"),
        _field(f"{canonical_prefix}_type_codeSpace", f"{raw_prefix}_type_codeSpace"),
    )


_COMMON_FIELDS = (
    _field("gml_id"),
    _field("gml_parent_id"),
    _field("gml_description"),
    _field("gml_name"),
)

_CITY_OBJECT_FIELDS = _COMMON_FIELDS + (
    _field("core_creationDate", "citygml_creationDate"),
    _field("core_terminationDate", "citygml_terminationDate"),
    _field("nrg3_identifier", "nrg3_identifier{}"),
    _field("nrg3_identifier_codeSpace", "nrg3_identifier{}.codeSpace"),
)

_CITY_OBJECT_METADATA_FIELDS = (
    _field("nrg3_metadata_author", "nrg3_metadata{}.nrg3_metadata_nrg3_author"),
    _field(
        "nrg3_metadata_acquisitionMethod",
        "nrg3_metadata{}.nrg3_metadata_nrg3_acquisition_method",
    ),
    _field("nrg3_metadata_owner", "nrg3_metadata{}.nrg3_metadata_nrg3_owner"),
    _field(
        "nrg3_metadata_qualityDescription",
        "nrg3_metadata{}.nrg3_metadata_nrg3_quality_description",
    ),
    _field("nrg3_metadata_source", "nrg3_metadata{}.nrg3_metadata_nrg3_source"),
)

_NRG_FEATURE_FIELDS = _COMMON_FIELDS + (
    _field("nrg3_creationDate", "nrg3_creation_date"),
    _field("nrg3_terminationDate", "nrg3_termination_date"),
    _field("nrg3_identifier"),
    _field("nrg3_identifier_codeSpace"),
    _field("nrg3_validFrom", "nrg3_valid_from"),
    _field("nrg3_validTo", "nrg3_valid_to"),
    _field("nrg3_status"),
    _field("nrg3_status_codeSpace"),
)

_NRG_FEATURE_METADATA_FIELDS = (
    _field("nrg3_metadata_author", "nrg3_metadata_nrg3_metadata_nrg3_author"),
    _field(
        "nrg3_metadata_acquisitionMethod",
        "nrg3_metadata_nrg3_metadata_nrg3_acquisition_method",
    ),
    _field("nrg3_metadata_owner", "nrg3_metadata_nrg3_metadata_nrg3_owner"),
    _field(
        "nrg3_metadata_qualityDescription",
        "nrg3_metadata_nrg3_metadata_nrg3_quality_description",
    ),
    _field("nrg3_metadata_source", "nrg3_metadata_nrg3_metadata_nrg3_source"),
)

_BUILDING_FIELDS = (
    (
        _field("nrg3_validFrom", "nrg3_valid_from{}"),
        _field("nrg3_validTo", "nrg3_valid_to{}"),
        _field("nrg3_status", "nrg3_status{}"),
        _field("nrg3_status_codeSpace", "nrg3_status{}.codeSpace"),
        _field("bldg_class", "citygml_class"),
        _field("bldg_class_codeSpace", "citygml_class_codeSpace"),
        _field("bldg_function", "citygml_function{}"),
        _field("bldg_function_codeSpace", "citygml_function{}.codeSpace"),
        _field("bldg_usage", "citygml_usage{}"),
        _field("bldg_usage_codeSpace", "citygml_usage{}.codeSpace"),
        _field("bldg_yearOfConstruction", "citygml_year_of_construction"),
        _field("bldg_yearOfDemolition", "citygml_year_of_demolition"),
        _field("bldg_roofType", "citygml_roof_type"),
        _field("bldg_roofType_codeSpace", "citygml_roof_type_codeSpace"),
        _field("bldg_measuredHeight", "citygml_measured_height"),
        _field("bldg_measuredHeight_uom", "citygml_measured_height_units"),
        _field("bldg_storeysAboveGround", "citygml_storeys_above_ground"),
        _field("bldg_storeysBelowGround", "citygml_storeys_below_ground"),
        _field("bldg_storeyHeightsAboveGround", "citygml_storey_heights_above_ground"),
        _field("bldg_storeyHeightsBelowGround", "citygml_storey_heights_below_ground"),
        _field("nrg3_bdgIsProtected", "nrg3_bdg_is_protected{}"),
        _field(
            "nrg3_bdgNumberOfBuildingUnits",
            "nrg3_bdg_number_of_building_units{}",
        ),
        _field("nrg3_bdgOwnerName", "nrg3_bdg_owner_name{}"),
        _field("nrg3_bdgOwnershipType", "nrg3_bdg_ownership_type{}"),
        _field(
            "nrg3_bdgOwnershipType_codeSpace",
            "nrg3_bdg_ownership_type{}.codeSpace",
        ),
        _field("nrg3_bdgType", "nrg3_bdg_type{}"),
        _field("nrg3_bdgType_codeSpace", "nrg3_bdg_type{}.codeSpace"),
        _field("nrg3_bdgAtticThermalStatus", "nrg3_bdg_attic_thermal_status{}"),
        _field(
            "nrg3_bdgBasementThermalStatus",
            "nrg3_bdg_basement_thermal_status{}",
        ),
        _field("nrg3_bdgConstructionWeight", "nrg3_bdg_construction_weight{}"),
        _field(
            "nrg3_bdgConstructionWeight_codeSpace",
            "nrg3_bdg_construction_weight{}.codeSpace",
        ),
    )
    + _qualified_fields(
        "nrg3_bdgArea",
        "nrg3_bdg_area{}.nrg3_qualified_area_nrg3",
    )
    + _qualified_fields(
        "nrg3_bdgHeight",
        "nrg3_bdg_height{}.nrg3_qualified_height_nrg3",
    )
    + _qualified_fields(
        "nrg3_bdgVolume",
        "nrg3_bdg_volume{}.nrg3_qualified_volume_nrg3",
    )
)

_DEVICE_FIELDS = (
    _field("nrg3_validFrom", "nrg3_valid_from{}"),
    _field("nrg3_validTo", "nrg3_valid_to{}"),
    _field("nrg3_model"),
    _field("nrg3_yearOfInstallation", "nrg3_year_of_installation"),
    _field("nrg3_yearOfManufacture", "nrg3_year_of_manufacture"),
    _field("nrg3_numberOfDevices", "nrg3_number_of_devices"),
    _field("nrg3_installedPower", "nrg3_installed_power"),
    _field("nrg3_installedPower_uom", "nrg3_installed_power_units"),
    _field("nrg3_nominalEfficiency", "nrg3_nominal_efficiency"),
    _field("nrg3_nominalEfficiency_uom", "nrg3_nominal_efficiency_units"),
    _field("nrg3_efficiencyIndicator", "nrg3_efficiency_indicator"),
    _field("nrg3_heatDissipation", "nrg3_heat_dissipation"),
    _field("nrg3_heatDissipation_uom", "nrg3_heat_dissipation_units"),
    _field(
        "nrg3_heatDissipationConvectiveFraction",
        "nrg3_heat_dissipation_convective_fraction",
    ),
    _field(
        "nrg3_heatDissipationLatentFraction",
        "nrg3_heat_dissipation_latent_fraction",
    ),
    _field(
        "nrg3_heatDissipationRadiantFraction",
        "nrg3_heat_dissipation_radiant_fraction",
    ),
)

_SOLAR_FIELDS = (
    _field("nrg3_moduleArea", "nrg3_module_area"),
    _field("nrg3_moduleArea_uom", "nrg3_module_area_units"),
    _field("nrg3_apertureArea", "nrg3_aperture_area"),
    _field("nrg3_apertureArea_uom", "nrg3_aperture_area_units"),
    _field("nrg3_azimuth", "nrg3_azimuth"),
    _field("nrg3_azimuth_uom", "nrg3_azimuth_units"),
    _field("nrg3_inclination", "nrg3_inclination"),
    _field("nrg3_inclination_uom", "nrg3_inclination_units"),
)

_SURFACE_FIELDS = (
    _field(
        "nrg3_bdgBdrySurfAdditionalThermalBridgeUValue",
        "nrg3_bdg_bdry_surf_additional_thermal_bridge_uvalue{}",
    ),
    _field(
        "nrg3_bdgBdrySurfAdditionalThermalBridgeUValue_uom",
        "nrg3_bdg_bdry_surf_additional_thermal_bridge_uvalue{}.units",
    ),
    _field("nrg3_bdgBdrySurfAzimuth", "nrg3_bdg_bdry_surf_azimuth{}"),
    _field(
        "nrg3_bdgBdrySurfAzimuth_uom",
        "nrg3_bdg_bdry_surf_azimuth{}.units",
    ),
    _field(
        "nrg3_bdgBdrySurfGroundViewFactor",
        "nrg3_bdg_bdry_surf_ground_view_factor{}",
    ),
    _field(
        "nrg3_bdgBdrySurfHeatCapacity",
        "nrg3_bdg_bdry_surf_heat_capacity{}",
    ),
    _field(
        "nrg3_bdgBdrySurfHeatCapacity_uom",
        "nrg3_bdg_bdry_surf_heat_capacity{}.units",
    ),
    _field(
        "nrg3_bdgBdrySurfInclination",
        "nrg3_bdg_bdry_surf_inclination{}",
    ),
    _field(
        "nrg3_bdgBdrySurfInclination_uom",
        "nrg3_bdg_bdry_surf_inclination{}.units",
    ),
    _field("nrg3_bdgBdrySurfIsShared", "nrg3_bdg_bdry_surf_is_shared{}"),
    _field(
        "nrg3_bdgBdrySurfOpaqueSurfaceArea",
        "nrg3_bdg_bdry_surf_opaque_surface_area{}",
    ),
    _field(
        "nrg3_bdgBdrySurfOpaqueSurfaceArea_uom",
        "nrg3_bdg_bdry_surf_opaque_surface_area{}.units",
    ),
    _field(
        "nrg3_bdgBdrySurfSkyViewFactor",
        "nrg3_bdg_bdry_surf_sky_view_factor{}",
    ),
    _field(
        "nrg3_bdgBdrySurfThickness",
        "nrg3_bdg_bdry_surf_thickness{}",
    ),
    _field(
        "nrg3_bdgBdrySurfThickness_uom",
        "nrg3_bdg_bdry_surf_thickness{}.units",
    ),
    _field(
        "nrg3_bdgBdrySurfTotalSurfaceArea",
        "nrg3_bdg_bdry_surf_total_surface_area{}",
    ),
    _field(
        "nrg3_bdgBdrySurfTotalSurfaceArea_uom",
        "nrg3_bdg_bdry_surf_total_surface_area{}.units",
    ),
)

_OPENING_FIELDS = (
    _field("nrg3_bdgOpnArea", "nrg3_bdg_opn_area{}"),
    _field("nrg3_bdgOpnArea_uom", "nrg3_bdg_opn_area{}.units"),
    _field("nrg3_bdgOpnAzimuth", "nrg3_bdg_opn_azimuth{}"),
    _field("nrg3_bdgOpnAzimuth_uom", "nrg3_bdg_opn_azimuth{}.units"),
    _field(
        "nrg3_bdgOpnGroundViewFactor",
        "nrg3_bdg_opn_ground_view_factor{}",
    ),
    _field("nrg3_bdgOpnInclination", "nrg3_bdg_opn_inclination{}"),
    _field(
        "nrg3_bdgOpnInclination_uom",
        "nrg3_bdg_opn_inclination{}.units",
    ),
    _field("nrg3_bdgOpnSkyViewFactor", "nrg3_bdg_opn_sky_view_factor{}"),
)

_ROOM_AND_INSTALLATION_FIELDS = (
    _field("bldg_class", "citygml_class"),
    _field("bldg_class_codeSpace", "citygml_class_codeSpace"),
    _field("bldg_function", "citygml_function{}"),
    _field("bldg_function_codeSpace", "citygml_function{}.codeSpace"),
    _field("bldg_usage", "citygml_usage{}"),
    _field("bldg_usage_codeSpace", "citygml_usage{}.codeSpace"),
)

_BUILDING_UNIT_FIELDS = (
    (
        _field("nrg3_buType", "nrg3_type"),
        _field("nrg3_buType_codeSpace", "nrg3_type_codeSpace"),
        _field("nrg3_floorNumberFrom", "nrg3_floor_number_from"),
        _field("nrg3_floorNumberTo", "nrg3_floor_number_to"),
        _field("nrg3_numberOfRooms", "nrg3_number_of_rooms"),
        _field("nrg3_ownerName", "nrg3_owner_name"),
        _field("nrg3_ownershipType", "nrg3_ownership_type"),
        _field("nrg3_ownershipType_codeSpace", "nrg3_ownership_type_codeSpace"),
    )
    + _qualified_fields(
        "nrg3_area",
        "nrg3_area{}.nrg3_qualified_area_nrg3",
    )
    + _qualified_fields(
        "nrg3_volume",
        "nrg3_volume{}.nrg3_qualified_volume_nrg3",
    )
)

_OCCUPANTS_FIELDS = (
    _field("nrg3_occupantType", "nrg3_type"),
    _field("nrg3_occupantType_codeSpace", "nrg3_type_codeSpace"),
    _field("nrg3_numberOfOccupants", "nrg3_number_of_occupants"),
    _field("nrg3_averageDietType", "nrg3_average_diet_type"),
    _field(
        "nrg3_averageDietType_codeSpace",
        "nrg3_average_diet_type_codeSpace",
    ),
    _field("nrg3_averageIncomeLevel", "nrg3_average_income_level"),
    _field(
        "nrg3_averageIncomeLevel_codeSpace",
        "nrg3_average_income_level_codeSpace",
    ),
    _field(
        "nrg3_averageInstructionLevel",
        "nrg3_average_instruction_level",
    ),
    _field(
        "nrg3_averageInstructionLevel_codeSpace",
        "nrg3_average_instruction_level_codeSpace",
    ),
    _field("nrg3_heatDissipation", "nrg3_heat_dissipation"),
    _field("nrg3_heatDissipation_uom", "nrg3_heat_dissipation_units"),
    _field(
        "nrg3_heatDissipationConvectiveFraction",
        "nrg3_heat_dissipation_convective_fraction",
    ),
    _field(
        "nrg3_heatDissipationLatentFraction",
        "nrg3_heat_dissipation_latent_fraction",
    ),
    _field(
        "nrg3_heatDissipationRadiantFraction",
        "nrg3_heat_dissipation_radiant_fraction",
    ),
)

_EPC_FIELDS = (
    _field("nrg3_epcType", "nrg3_type"),
    _field("nrg3_epcType_codeSpace", "nrg3_type_codeSpace"),
    _field("nrg3_epcLabel", "nrg3_label"),
    _field("nrg3_epcValue", "nrg3_value"),
    _field("nrg3_epcValue_uom", "nrg3_value_units"),
    _field("nrg3_epcCertificationMethod", "nrg3_certification_method"),
)

_CONSTANT_SCHEDULE_FIELDS = (
    _field("nrg3_scheduleType", "nrg3_type"),
    _field("nrg3_scheduleType_codeSpace", "nrg3_type_codeSpace"),
    _field("nrg3_startTime", "nrg3_start_time"),
    _field("nrg3_startDay", "nrg3_start_day"),
    _field("nrg3_startMonth", "nrg3_start_month"),
    _field("nrg3_startYear", "nrg3_start_year"),
    _field("nrg3_scheduleValue", "nrg3_value"),
    _field("nrg3_scheduleValue_uom", "nrg3_value_units"),
)

_COMPOSITE_SCHEDULE_FIELDS = (
    _field("nrg3_scheduleType", "nrg3_type"),
    _field("nrg3_scheduleType_codeSpace", "nrg3_type_codeSpace"),
    _field("nrg3_startTime", "nrg3_start_time"),
    _field("nrg3_startDay", "nrg3_start_day"),
    _field("nrg3_startMonth", "nrg3_start_month"),
    _field("nrg3_startYear", "nrg3_start_year"),
)

FEATURE_INPUT_FIELDS: dict[str, tuple[InputField, ...]] = {
    "bldg_Building": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _BUILDING_FIELDS,
    "bldg_BuildingPart": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _BUILDING_FIELDS,
    "bldg_WallSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_RoofSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_GroundSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_CeilingSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_ClosureSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_FloorSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_OuterCeilingSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_OuterFloorSurface": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _SURFACE_FIELDS,
    "bldg_Door": _CITY_OBJECT_FIELDS + _CITY_OBJECT_METADATA_FIELDS + _OPENING_FIELDS,
    "bldg_Window": _CITY_OBJECT_FIELDS + _CITY_OBJECT_METADATA_FIELDS + _OPENING_FIELDS,
    "bldg_Room": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _ROOM_AND_INSTALLATION_FIELDS,
    "bldg_BuildingInstallation": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _ROOM_AND_INSTALLATION_FIELDS,
    "bldg_IntBuildingInstallation": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _ROOM_AND_INSTALLATION_FIELDS,
    "nrg3_PhotovoltaicCollector": _CITY_OBJECT_FIELDS
    + _DEVICE_FIELDS
    + _SOLAR_FIELDS
    + (
        _field("nrg3_cellType", "nrg3_cell_type"),
        _field("nrg3_cellType_codeSpace", "nrg3_cell_type_codeSpace"),
    ),
    "nrg3_HeatPump": _CITY_OBJECT_FIELDS
    + _DEVICE_FIELDS
    + (
        _field("nrg3_heatSource", "nrg3_heat_source"),
        _field("nrg3_heatSource_codeSpace", "nrg3_heat_source_codeSpace"),
        _field("nrg3_copSourceTemperature", "nrg3_cop_source_temperature"),
        _field(
            "nrg3_copSourceTemperature_uom",
            "nrg3_cop_source_temperature_units",
        ),
        _field(
            "nrg3_copOperationTemperature",
            "nrg3_cop_operation_temperature",
        ),
        _field(
            "nrg3_copOperationTemperature_uom",
            "nrg3_cop_operation_temperature_units",
        ),
    ),
    "nrg3_EVChargingStation": _CITY_OBJECT_FIELDS
    + _DEVICE_FIELDS
    + (
        _field("nrg3_evType", "nrg3_type"),
        _field("nrg3_evType_codeSpace", "nrg3_type_codeSpace"),
        _field("nrg3_chargingSpeedLevel", "nrg3_charging_speed_level"),
        _field(
            "nrg3_chargingSpeedLevel_codeSpace",
            "nrg3_charging_speed_level_codeSpace",
        ),
        _field("nrg3_connectorType", "nrg3_connector_type"),
        _field("nrg3_connectorType_codeSpace", "nrg3_connector_type_codeSpace"),
        _field("nrg3_hasLoadManagement", "nrg3_has_load_management"),
        _field("nrg3_access", "nrg3_access"),
        _field("nrg3_access_codeSpace", "nrg3_access_codeSpace"),
    ),
    "nrg3_Occupants": _NRG_FEATURE_FIELDS
    + _NRG_FEATURE_METADATA_FIELDS
    + _OCCUPANTS_FIELDS,
    "nrg3_EnergyPerformanceCertificate": _NRG_FEATURE_FIELDS
    + _NRG_FEATURE_METADATA_FIELDS
    + _EPC_FIELDS,
    "nrg3_BuildingUnit": _CITY_OBJECT_FIELDS
    + _CITY_OBJECT_METADATA_FIELDS
    + _BUILDING_UNIT_FIELDS,
    "nrg3_ConstantValueSchedule": _NRG_FEATURE_FIELDS
    + _NRG_FEATURE_METADATA_FIELDS
    + _CONSTANT_SCHEDULE_FIELDS,
    "nrg3_CompositeSchedule": _NRG_FEATURE_FIELDS
    + _NRG_FEATURE_METADATA_FIELDS
    + _COMPOSITE_SCHEDULE_FIELDS,
    "core_Address": _COMMON_FIELDS
    + (
        _field("xal_country"),
        _field("xal_locality"),
        _field("xal_thoroughfare"),
        _field("xal_thoroughfareNumber"),
        _field("xal_postalCode"),
    ),
}


def list_supported_feature_types() -> list[str]:
    return sorted(FEATURE_INPUT_FIELDS)


def get_allowed_attribute_names(feature_type: str) -> set[str]:
    fields = FEATURE_INPUT_FIELDS.get(feature_type)
    if fields is None:
        return set()
    names: set[str] = set()
    for field in fields:
        names.add(field.canonical)
        names.update(field.aliases)
    return names


def list_supported_attribute_names() -> list[str]:
    names: set[str] = set()
    for feature_type in FEATURE_INPUT_FIELDS:
        names.update(get_allowed_attribute_names(feature_type))
    return sorted(names)


def normalize_feature_attributes(
    feature_type: str,
    attributes: Mapping[str, Any],
) -> dict[str, Any]:
    fields = FEATURE_INPUT_FIELDS.get(feature_type)
    if fields is None:
        return dict(attributes)

    alias_map: dict[str, str] = {}
    for field in fields:
        alias_map[field.canonical] = field.canonical
        for alias in field.aliases:
            alias_map[alias] = field.canonical

    normalized: dict[str, Any] = {}
    for key, value in attributes.items():
        canonical = alias_map.get(key, key)
        if canonical in normalized:
            normalized[canonical] = _merge_values(
                canonical,
                normalized[canonical],
                value,
            )
        else:
            normalized[canonical] = value

    return normalized


def _merge_values(canonical: str, existing: Any, new_value: Any) -> Any:
    if _is_blank(existing):
        return new_value
    if _is_blank(new_value):
        return existing
    if existing == new_value:
        return existing
    raise ValueError(
        f"maps multiple input keys to {canonical!r} with conflicting values"
    )


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")
