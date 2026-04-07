"""FME attribute reference template for all Yes / Blank feature types.

Copy the relevant ``factory.add(...)`` blocks into your script,
fill in the values, and run ``factory.build()`` to get a CityModel.

Blank-row feature types currently raise ``NotImplementedError``.
To implement one:
  1. Build a Python builder class in ``citygml_energy/``
  2. Write a ``<FeatureType>_from_dict(attrs)`` function in ``factory.py``
  3. Replace the ``_stub(...)`` call with the real function in the registry.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    FeatureFactory,
    CS_BUILDING_CLASS, CS_BUILDING_FUNCTION, CS_BUILDING_ROOFTYPE, CS_BUILDING_USAGE,
    CS_NRG3_AREA_TYPE, CS_NRG3_BU_TYPE, CS_NRG3_BUILDING_TYPE, CS_NRG3_CELL_TYPE,
    CS_NRG3_CONSTRUCTION_WEIGHT, CS_NRG3_DEVICE_OPERATION_TYPE, CS_NRG3_EPC_TYPE,
    CS_NRG3_EV_TYPE, CS_NRG3_HEAT_SOURCE, CS_NRG3_HEIGHT_TYPE, CS_NRG3_OCCUPANT_TYPE,
    CS_NRG3_OWNERSHIP_TYPE, CS_NRG3_SCHEDULE_TYPE, CS_NRG3_VOLUME_TYPE,
)

# =============================================================================
# YES rows — fully implemented
# =============================================================================

factory = FeatureFactory(
    description="",   # gml:description for the CityModel root
    name="",          # gml:name for the CityModel root
)

# -----------------------------------------------------------------------------
# core_CityModel  (container — configured via FeatureFactory constructor above)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# core_Address
# -----------------------------------------------------------------------------
factory.add("core_Address", {
    "gml_id":               "",
    "gml_parent_id":        "",   # parent Building gml:id
    "xal_country":          "",
    "xal_locality":         "",   # town / city
    "xal_thoroughfare":     "",   # street name
    "xal_thoroughfareNumber": "",
    "xal_postalCode":       "",
})

# -----------------------------------------------------------------------------
# bldg_Building
# -----------------------------------------------------------------------------
factory.add("bldg_Building", {
    # GML / core
    "gml_id":                           "",
    "gml_description":                  "",
    "gml_name":                         "",
    "core_creationDate":                "",   # ISO date e.g. "2026-01-01"
    "core_terminationDate":             "",
    # Energy ADE CityObject extensions
    "nrg3_identifier":                  "",
    "nrg3_identifier_codeSpace":        "",
    "nrg3_metadata_author":             "",
    "nrg3_metadata_acquisitionMethod":  "",
    "nrg3_metadata_owner":              "",
    "nrg3_metadata_qualityDescription": "",
    "nrg3_metadata_source":             "",
    # CityGML building properties
    "bldg_class":                       "",
    "bldg_class_codeSpace":             CS_BUILDING_CLASS,
    "bldg_function":                    "",
    "bldg_function_codeSpace":          CS_BUILDING_FUNCTION,
    "bldg_usage":                       "",
    "bldg_usage_codeSpace":             CS_BUILDING_USAGE,
    "bldg_yearOfConstruction":          "",   # integer year
    "bldg_yearOfDemolition":            "",
    "bldg_roofType":                    "",
    "bldg_roofType_codeSpace":          CS_BUILDING_ROOFTYPE,
    "bldg_measuredHeight":              "",
    "bldg_measuredHeight_uom":          "m",
    "bldg_storeysAboveGround":          "",
    "bldg_storeysBelowGround":          "",
    # Energy ADE building extensions
    "nrg3_bdgAtticThermalStatus":       "",
    "nrg3_bdgBasementThermalStatus":    "",
    "nrg3_bdgConstructionWeight":       "",
    "nrg3_bdgConstructionWeight_codeSpace": CS_NRG3_CONSTRUCTION_WEIGHT,
    "nrg3_bdgIsProtected":              "",   # "true" / "false"
    "nrg3_bdgNumberOfBuildingUnits":    "",
    "nrg3_bdgOwnerName":                "",
    "nrg3_bdgOwnershipType":            "",
    "nrg3_bdgOwnershipType_codeSpace":  CS_NRG3_OWNERSHIP_TYPE,
    "nrg3_bdgType":                     "",
    "nrg3_bdgType_codeSpace":           CS_NRG3_BUILDING_TYPE,
    # QualifiedVolume
    "nrg3_bdgVolume_description":       "",
    "nrg3_bdgVolume_source":            "",
    "nrg3_bdgVolume_value":             "",
    "nrg3_bdgVolume_uom":               "m3",
    "nrg3_bdgVolume_type":              "",
    "nrg3_bdgVolume_type_codeSpace":    CS_NRG3_VOLUME_TYPE,
    # QualifiedArea
    "nrg3_bdgArea_description":         "",
    "nrg3_bdgArea_source":              "",
    "nrg3_bdgArea_value":               "",
    "nrg3_bdgArea_uom":                 "m2",
    "nrg3_bdgArea_type":                "",
    "nrg3_bdgArea_type_codeSpace":      CS_NRG3_AREA_TYPE,
    # QualifiedHeight
    "nrg3_bdgHeight_description":       "",
    "nrg3_bdgHeight_source":            "",
    "nrg3_bdgHeight_value":             "",
    "nrg3_bdgHeight_uom":               "m",
    "nrg3_bdgHeight_type":              "",
    "nrg3_bdgHeight_type_codeSpace":    CS_NRG3_HEIGHT_TYPE,
})

# -----------------------------------------------------------------------------
# bldg_BuildingPart  (same attributes as bldg_Building)
# -----------------------------------------------------------------------------
factory.add("bldg_BuildingPart", {
    "gml_id":           "",
    "gml_parent_id":    "",   # parent Building gml:id
    # ... same attribute keys as bldg_Building above
})

# -----------------------------------------------------------------------------
# bldg_WallSurface / bldg_RoofSurface / bldg_GroundSurface /
# bldg_CeilingSurface / bldg_ClosureSurface / bldg_FloorSurface /
# bldg_OuterCeilingSurface / bldg_OuterFloorSurface
# (all share the same attribute schema)
# -----------------------------------------------------------------------------
_SURFACE_ATTRS = {
    "gml_id":                                       "",
    "gml_parent_id":                                "",   # parent Building gml:id
    "gml_description":                              "",
    "gml_name":                                     "",
    "core_creationDate":                            "",
    "nrg3_bdgBdrySurfAzimuth":                      "",
    "nrg3_bdgBdrySurfAzimuth_uom":                  "deg",
    "nrg3_bdgBdrySurfInclination":                  "",
    "nrg3_bdgBdrySurfInclination_uom":              "deg",
    "nrg3_bdgBdrySurfTotalSurfaceArea":             "",
    "nrg3_bdgBdrySurfTotalSurfaceArea_uom":         "m2",
    "nrg3_bdgBdrySurfOpaqueSurfaceArea":            "",
    "nrg3_bdgBdrySurfOpaqueSurfaceArea_uom":        "m2",
    "nrg3_bdgBdrySurfHeatCapacity":                 "",
    "nrg3_bdgBdrySurfHeatCapacity_uom":             "J/(K*m2)",
    "nrg3_bdgBdrySurfThickness":                    "",
    "nrg3_bdgBdrySurfThickness_uom":                "m",
    "nrg3_bdgBdrySurfIsShared":                     "",   # "true" / "false"
    "nrg3_bdgBdrySurfGroundViewFactor":             "",   # 0..1
    "nrg3_bdgBdrySurfSkyViewFactor":                "",   # 0..1
    "nrg3_bdgBdrySurfAdditionalThermalBridgeUValue":    "",
    "nrg3_bdgBdrySurfAdditionalThermalBridgeUValue_uom":"W/(m2*K)",
}

factory.add("bldg_WallSurface",         {**_SURFACE_ATTRS})
factory.add("bldg_RoofSurface",         {**_SURFACE_ATTRS})
factory.add("bldg_GroundSurface",       {**_SURFACE_ATTRS})
factory.add("bldg_CeilingSurface",      {**_SURFACE_ATTRS})
factory.add("bldg_ClosureSurface",      {**_SURFACE_ATTRS})
factory.add("bldg_FloorSurface",        {**_SURFACE_ATTRS})
factory.add("bldg_OuterCeilingSurface", {**_SURFACE_ATTRS})
factory.add("bldg_OuterFloorSurface",   {**_SURFACE_ATTRS})

# -----------------------------------------------------------------------------
# bldg_Door / bldg_Window
# -----------------------------------------------------------------------------
_OPENING_ATTRS = {
    "gml_id":                           "",
    "gml_parent_id":                    "",   # parent surface gml:id
    "gml_description":                  "",
    "gml_name":                         "",
    "core_creationDate":                "",
    "nrg3_bdgOpnArea":                  "",
    "nrg3_bdgOpnArea_uom":              "m2",
    "nrg3_bdgOpnAzimuth":               "",
    "nrg3_bdgOpnAzimuth_uom":           "deg",
    "nrg3_bdgOpnInclination":           "",
    "nrg3_bdgOpnInclination_uom":       "deg",
    "nrg3_bdgOpnGroundViewFactor":      "",   # 0..1
    "nrg3_bdgOpnSkyViewFactor":         "",   # 0..1
}

factory.add("bldg_Door",   {**_OPENING_ATTRS})
factory.add("bldg_Window", {**_OPENING_ATTRS})

# -----------------------------------------------------------------------------
# bldg_Room
# -----------------------------------------------------------------------------
factory.add("bldg_Room", {
    "gml_id":           "",
    "gml_parent_id":    "",   # parent Building gml:id
    "gml_name":         "",
    "core_creationDate":"",
    "bldg_class":       "",
    "bldg_class_codeSpace": CS_BUILDING_CLASS,
    "bldg_function":    "",
    "bldg_function_codeSpace": CS_BUILDING_FUNCTION,
    "bldg_usage":       "",
    "bldg_usage_codeSpace": CS_BUILDING_USAGE,
})

# -----------------------------------------------------------------------------
# bldg_BuildingInstallation
# -----------------------------------------------------------------------------
factory.add("bldg_BuildingInstallation", {
    "gml_id":           "",
    "gml_parent_id":    "",   # parent Building gml:id
    "gml_name":         "",
    "core_creationDate":"",
    "bldg_class":       "",
    "bldg_class_codeSpace": CS_BUILDING_CLASS,
    "bldg_function":    "",
    "bldg_function_codeSpace": CS_BUILDING_FUNCTION,
    "bldg_usage":       "",
    "bldg_usage_codeSpace": CS_BUILDING_USAGE,
})

# -----------------------------------------------------------------------------
# bldg_IntBuildingInstallation
# -----------------------------------------------------------------------------
factory.add("bldg_IntBuildingInstallation", {
    "gml_id":           "",
    "gml_parent_id":    "",   # parent Building gml:id
    "gml_name":         "",
    "core_creationDate":"",
    "bldg_class":       "",
    "bldg_function":    "",
    "bldg_usage":       "",
})

# -----------------------------------------------------------------------------
# nrg3_PhotovoltaicCollector
# -----------------------------------------------------------------------------
factory.add("nrg3_PhotovoltaicCollector", {
    "gml_id":                   "",
    "gml_parent_id":            "",   # parent Building gml:id
    "gml_description":          "",
    "gml_name":                 "",
    "core_creationDate":        "",
    "nrg3_identifier":          "",
    "nrg3_identifier_codeSpace":"",
    "nrg3_validFrom":           "",
    "nrg3_validTo":             "",
    "nrg3_model":               "",
    "nrg3_yearOfInstallation":  "",
    "nrg3_yearOfManufacture":   "",
    "nrg3_numberOfDevices":     "",
    "nrg3_installedPower":      "",
    "nrg3_installedPower_uom":  "W",
    "nrg3_nominalEfficiency":   "",
    "nrg3_nominalEfficiency_uom": "unit interval",
    "nrg3_efficiencyIndicator": "",
    "nrg3_heatDissipation":     "",
    "nrg3_heatDissipation_uom": "W/m2",
    "nrg3_heatDissipationConvectiveFraction": "",
    "nrg3_heatDissipationLatentFraction":     "",
    "nrg3_heatDissipationRadiantFraction":    "",
    "nrg3_moduleArea":          "",
    "nrg3_moduleArea_uom":      "m2",
    "nrg3_apertureArea":        "",
    "nrg3_apertureArea_uom":    "m2",
    "nrg3_azimuth":             "",
    "nrg3_azimuth_uom":         "deg",
    "nrg3_inclination":         "",
    "nrg3_inclination_uom":     "deg",
    "nrg3_cellType":            "",
    "nrg3_cellType_codeSpace":  CS_NRG3_CELL_TYPE,
})

# -----------------------------------------------------------------------------
# nrg3_HeatPump
# -----------------------------------------------------------------------------
factory.add("nrg3_HeatPump", {
    "gml_id":                       "",
    "gml_parent_id":                "",   # parent Building gml:id
    "gml_name":                     "",
    "core_creationDate":            "",
    "nrg3_model":                   "",
    "nrg3_yearOfInstallation":      "",
    "nrg3_numberOfDevices":         "",
    "nrg3_installedPower":          "",
    "nrg3_installedPower_uom":      "W",
    "nrg3_nominalEfficiency":       "",
    "nrg3_nominalEfficiency_uom":   "unit interval",
    "nrg3_heatSource":              "",
    "nrg3_heatSource_codeSpace":    CS_NRG3_HEAT_SOURCE,
    "nrg3_copSourceTemperature":    "",
    "nrg3_copSourceTemperature_uom":"degC",
    "nrg3_copOperationTemperature": "",
    "nrg3_copOperationTemperature_uom": "degC",
})

# -----------------------------------------------------------------------------
# nrg3_EVChargingStation
# -----------------------------------------------------------------------------
factory.add("nrg3_EVChargingStation", {
    "gml_id":                       "",
    "gml_parent_id":                "",   # parent Building gml:id
    "gml_name":                     "",
    "core_creationDate":            "",
    "nrg3_model":                   "",
    "nrg3_yearOfInstallation":      "",
    "nrg3_numberOfDevices":         "",
    "nrg3_installedPower":          "",
    "nrg3_installedPower_uom":      "W",
    "nrg3_evType":                  "",
    "nrg3_evType_codeSpace":        CS_NRG3_EV_TYPE,
    "nrg3_chargingSpeedLevel":      "",
    "nrg3_chargingSpeedLevel_codeSpace": "",
    "nrg3_connectorType":           "",
    "nrg3_connectorType_codeSpace": "",
    "nrg3_hasLoadManagement":       "",   # "true" / "false"
    "nrg3_access":                  "",
    "nrg3_access_codeSpace":        "",
})

# -----------------------------------------------------------------------------
# nrg3_Occupants
# -----------------------------------------------------------------------------
factory.add("nrg3_Occupants", {
    "gml_id":                           "",
    "gml_parent_id":                    "",   # parent Building / BuildingUnit gml:id
    "gml_name":                         "",
    "nrg3_occupantType":                "",
    "nrg3_occupantType_codeSpace":      CS_NRG3_OCCUPANT_TYPE,
    "nrg3_numberOfOccupants":           "",
    "nrg3_averageDietType":             "",
    "nrg3_averageDietType_codeSpace":   "",
    "nrg3_averageIncomeLevel":          "",
    "nrg3_averageInstructionLevel":     "",
    "nrg3_heatDissipation":             "",
    "nrg3_heatDissipation_uom":         "W",
    "nrg3_heatDissipationConvectiveFraction": "",
    "nrg3_heatDissipationLatentFraction":     "",
    "nrg3_heatDissipationRadiantFraction":    "",
})

# -----------------------------------------------------------------------------
# nrg3_EnergyPerformanceCertificate
# -----------------------------------------------------------------------------
factory.add("nrg3_EnergyPerformanceCertificate", {
    "gml_id":                       "",
    "gml_parent_id":                "",   # parent Building gml:id
    "nrg3_epcType":                 "",
    "nrg3_epcType_codeSpace":       CS_NRG3_EPC_TYPE,
    "nrg3_epcLabel":                "",   # e.g. "A+"
    "nrg3_epcValue":                "",
    "nrg3_epcValue_uom":            "kWh/(m2*a)",
    "nrg3_epcCertificationMethod":  "",
})

# -----------------------------------------------------------------------------
# nrg3_BuildingUnit
# -----------------------------------------------------------------------------
factory.add("nrg3_BuildingUnit", {
    "gml_id":                       "",
    "gml_parent_id":                "",   # parent Building gml:id
    "gml_name":                     "",
    "core_creationDate":            "",
    "nrg3_buType":                  "",
    "nrg3_buType_codeSpace":        CS_NRG3_BU_TYPE,
    "nrg3_floorNumberFrom":         "",
    "nrg3_floorNumberTo":           "",
    "nrg3_numberOfRooms":           "",
    "nrg3_ownerName":               "",
    "nrg3_ownershipType":           "",
    "nrg3_ownershipType_codeSpace": CS_NRG3_OWNERSHIP_TYPE,
})

# -----------------------------------------------------------------------------
# nrg3_ConstantValueSchedule
# -----------------------------------------------------------------------------
factory.add("nrg3_ConstantValueSchedule", {
    "gml_id":                   "",
    "gml_parent_id":            "",   # parent who uses this schedule
    "gml_name":                 "",
    "core_creationDate":        "",
    "nrg3_scheduleType":        "",
    "nrg3_scheduleType_codeSpace": CS_NRG3_SCHEDULE_TYPE,
    "nrg3_scheduleValue":       "",
    "nrg3_scheduleValue_uom":   "",
})

# -----------------------------------------------------------------------------
# nrg3_CompositeSchedule
# -----------------------------------------------------------------------------
factory.add("nrg3_CompositeSchedule", {
    "gml_id":                   "",
    "gml_parent_id":            "",
    "gml_name":                 "",
    "core_creationDate":        "",
    "nrg3_scheduleType":        "",
    "nrg3_scheduleType_codeSpace": CS_NRG3_SCHEDULE_TYPE,
    "nrg3_startTime":           "",
    "nrg3_startDay":            "",
    "nrg3_startMonth":          "",
    "nrg3_startYear":           "",
})


# =============================================================================
# BLANK rows — stubs (raise NotImplementedError until implemented)
# Uncomment and fill in once the builder class exists.
# =============================================================================

# factory.add("frn_CityFurniture",              {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("gen_GenericCityObject",          {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("grp_CityObjectGroup",            {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("luse_LandUse",                   {"gml_id": "", "gml_parent_id": "", "gml_name": ""})

# --- resources / materials ---
# factory.add("nrg3_ConstructionMaterial",      {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_LayeredConstruction",       {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_LayeredConstructionLibrary",{"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_MaterialLibrary",           {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_ReverseLayeredConstruction",{"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_SolidMaterial",             {"gml_id": "", "gml_parent_id": "", "gml_name": ""})

# --- energy carriers ---
# factory.add("nrg3_Energy",                    {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_Liquid",                    {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_OtherResource",             {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_Waste",                     {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_Water",                     {"gml_id": "", "gml_parent_id": "", "gml_name": ""})

# --- devices ---
# factory.add("nrg3_Boiler",                    {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_DeviceOperation",           {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_ElectricalStorageDevice",   {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_GenericDevice",             {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_GenericElectricalDevice",   {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_GenericStorageDevice",      {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_LightingDevice",            {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_MovableShadingDevice",      {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_SolarThermalCollector",     {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_ThermalStorageDevice",      {"gml_id": "", "gml_parent_id": "", "gml_name": ""})

# --- energy networks ---
# factory.add("nrg3_PowerDistribution",         {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_ThermalDistribution",       {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_UtilityNetworkConnection",  {"gml_id": "", "gml_parent_id": "", "gml_name": ""})

# --- schedules ---
# factory.add("nrg3_DualValueSchedule",         {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_IrregularTimeSeries",       {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_IrregularTimeSeriesFile",   {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_MonthlyTimeSeries",         {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_MonthlyTimeSeriesFile",     {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_RegularTimeSeries",         {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_RegularTimeSeriesFile",     {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_ScheduleComponent",         {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_ScheduleLibrary",           {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_TimeSeriesSchedule",        {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_TypicalValuesIrregularTimeSeries",     {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_TypicalValuesIrregularTimeSeriesFile", {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_TypicalValuesMonthlyTimeSeries",       {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_TypicalValuesMonthlyTimeSeriesFile",   {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_TypicalValuesRegularTimeSeries",       {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_TypicalValuesRegularTimeSeriesFile",   {"gml_id": "", "gml_parent_id": ""})

# --- sensors ---
# factory.add("nrg3_SensorConnection",          {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_SensorData",                {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_WeatherData",               {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_WeatherStation",            {"gml_id": "", "gml_parent_id": "", "gml_name": ""})

# --- urban / zone objects ---
# factory.add("nrg3_Intervention",              {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_UrbanFunctionArea",         {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_UrbanSpace",                {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_Zone",                      {"gml_id": "", "gml_parent_id": "", "gml_name": ""})
# factory.add("nrg3_ZonePart",                  {"gml_id": "", "gml_parent_id": "", "gml_name": ""})

# --- zone surfaces ---
# factory.add("nrg3_ZoneAtticFloorSurface",         {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneClosureSurface",            {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneDoor",                      {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneGroundSurface",             {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneIntermediateFloorSurface",  {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneOuterCeilingSurface",       {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneOuterFloorSurface",         {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneRoofSurface",               {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneWallSurface",               {"gml_id": "", "gml_parent_id": ""})
# factory.add("nrg3_ZoneWindow",                    {"gml_id": "", "gml_parent_id": ""})
