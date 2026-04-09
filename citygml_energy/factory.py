"""FME-style flat attribute → builder factory.

Key ideas
---------
* Every class accepts a flat ``dict`` of attributes (same style as FME writer
  attributes).
* Attribute names follow ``{ns_prefix}_{elementName}`` conventions.
* ``MeasureValue`` fields split into ``attr`` (value) + ``attr_uom`` (unit).
* ``CodeValue`` fields split into ``attr`` (value) + ``attr_codeSpace`` (opt).
* Nested sub-objects use an extra segment, e.g. ``nrg3_bdgVolume_value``.
* ``gml_parent_id`` links a child feature to its parent's ``gml_id``.

Quick usage
-----------
::

    from citygml_energy.factory import create_feature, FeatureFactory

    # Single feature
    bldg = create_feature("bldg_Building", {
        "gml_id":                           "id_building_1",
        "gml_name":                         "Han Solo's house",
        "core_creationDate":                "2026-04-04",
        "bldg_class":                       "1000",
        "bldg_class_codeSpace":             CS_BUILDING_CLASS,
        "bldg_yearOfConstruction":          "2020",
        "nrg3_bdgOwnerName":                "Han Solo",
        "nrg3_bdgIsProtected":              "false",
        "nrg3_bdgVolume_value":             "823.30",
        "nrg3_bdgVolume_uom":               "m3",
        "nrg3_bdgVolume_type":              "grossVolume",
        "nrg3_bdgVolume_type_codeSpace":    CS_NRG3_VOLUME_TYPE,
    })

    # Batch: use gml_parent_id to link PV → Building
    factory = FeatureFactory()
    factory.add("bldg_Building", {"gml_id": "bldg_1", ...})
    factory.add("nrg3_PhotovoltaicCollector", {
        "gml_id": "pv_1",
        "gml_parent_id": "bldg_1",   # ← link to parent
        ...
    })
    city_model = factory.build()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from .core import Address, CityModel
from .energy_ade import (
    BuildingUnit,
    CompositeSchedule,
    ConstantValueSchedule,
    EnergyPerformanceCertificate,
    EVChargingStation,
    HeatPump,
    Metadata,
    Occupants,
    PhotovoltaicCollector,
    QualifiedArea,
    QualifiedHeight,
    QualifiedVolume,
)
from .types import CodeValue, MeasureValue, ScaleValue

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _str(v: Any) -> Optional[str]:
    return str(v).strip() if v is not None and str(v).strip() != "" else None


def _int(v: Any) -> Optional[int]:
    s = _str(v)
    return int(s) if s is not None else None


def _float(v: Any) -> Optional[float]:
    s = _str(v)
    return float(s) if s is not None else None


def _bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def _code(attrs: Dict, key: str, cs_key: Optional[str] = None) -> Optional[CodeValue]:
    val = _str(attrs.get(key))
    if val is None:
        return None
    cs_lookup = cs_key or f"{key}_codeSpace"
    cs = _str(attrs.get(cs_lookup))
    return CodeValue(val, cs)


def _measure(
    attrs: Dict, key: str, uom_key: Optional[str] = None
) -> Optional[MeasureValue]:
    val = _str(attrs.get(key))
    if val is None:
        return None
    uom_lookup = uom_key or f"{key}_uom"
    uom = _str(attrs.get(uom_lookup)) or ""
    return MeasureValue(val, uom)


def _scale(attrs: Dict, key: str) -> Optional[ScaleValue]:
    val = _str(attrs.get(key))
    if val is None:
        return None
    return ScaleValue(val, "unit interval")


# ---------------------------------------------------------------------------
# Per-class constructors
# ---------------------------------------------------------------------------


def _make_metadata(attrs: Dict, prefix: str = "nrg3_metadata") -> Optional[Metadata]:
    """Build a Metadata from flat attrs with a given prefix."""
    found = any(
        _str(attrs.get(f"{prefix}_{k}")) is not None
        for k in (
            "author",
            "acquisitionMethod",
            "owner",
            "qualityDescription",
            "source",
        )
    )
    if not found:
        return None
    return Metadata(
        author=_str(attrs.get(f"{prefix}_author")),
        acquisition_method=_str(attrs.get(f"{prefix}_acquisitionMethod")),
        owner=_str(attrs.get(f"{prefix}_owner")),
        quality_description=_str(attrs.get(f"{prefix}_qualityDescription")),
        source=_str(attrs.get(f"{prefix}_source")),
    )


def _make_qualified_volume(
    attrs: Dict, prefix: str = "nrg3_bdgVolume"
) -> Optional[QualifiedVolume]:
    if _str(attrs.get(f"{prefix}_value")) is None:
        return None
    return QualifiedVolume(
        description=_str(attrs.get(f"{prefix}_description")),
        source=_str(attrs.get(f"{prefix}_source")),
        value=_measure(attrs, f"{prefix}_value", f"{prefix}_uom"),
        type=_code(attrs, f"{prefix}_type", f"{prefix}_type_codeSpace"),
    )


def _make_qualified_area(
    attrs: Dict, prefix: str = "nrg3_bdgArea"
) -> Optional[QualifiedArea]:
    if _str(attrs.get(f"{prefix}_value")) is None:
        return None
    return QualifiedArea(
        description=_str(attrs.get(f"{prefix}_description")),
        source=_str(attrs.get(f"{prefix}_source")),
        value=_measure(attrs, f"{prefix}_value", f"{prefix}_uom"),
        type=_code(attrs, f"{prefix}_type", f"{prefix}_type_codeSpace"),
    )


def _make_qualified_height(
    attrs: Dict, prefix: str = "nrg3_bdgHeight"
) -> Optional[QualifiedHeight]:
    if _str(attrs.get(f"{prefix}_value")) is None:
        return None
    return QualifiedHeight(
        description=_str(attrs.get(f"{prefix}_description")),
        source=_str(attrs.get(f"{prefix}_source")),
        value=_measure(attrs, f"{prefix}_value", f"{prefix}_uom"),
        type=_code(attrs, f"{prefix}_type", f"{prefix}_type_codeSpace"),
    )


def building_from_dict(attrs: Dict) -> Building:
    """Create a :class:`Building` from a flat attribute dictionary.

    Attribute reference
    -------------------
    **GML / Core**

    =================================  ================================
    Attribute key                      Meaning
    =================================  ================================
    ``gml_id``                         Feature ID (gml:id)
    ``gml_description``                gml:description text
    ``gml_name``                       gml:name text
    ``core_creationDate``              ISO date, e.g. ``2026-04-04``
    ``core_terminationDate``           ISO date
    =================================  ================================

    **CityGML building properties**

    =================================  ================================
    ``bldg_class``                     Code value
    ``bldg_class_codeSpace``           Optional codeSpace URL
    ``bldg_function``                  Code value
    ``bldg_function_codeSpace``
    ``bldg_usage``                     Code value
    ``bldg_usage_codeSpace``
    ``bldg_yearOfConstruction``        Integer year
    ``bldg_yearOfDemolition``          Integer year
    ``bldg_roofType``                  Code value
    ``bldg_roofType_codeSpace``
    ``bldg_measuredHeight``            Numeric value
    ``bldg_measuredHeight_uom``        Unit of measure (e.g. ``m``)
    ``bldg_storeysAboveGround``        Integer
    ``bldg_storeysBelowGround``        Integer
    =================================  ================================

    **Energy ADE CityObject extensions**

    ==========================================  ========================
    ``nrg3_identifier``                         Identifier string
    ``nrg3_identifier_codeSpace``               Optional codeSpace URL
    ``nrg3_metadata_author``                    Metadata author
    ``nrg3_metadata_acquisitionMethod``         e.g. ``measurement``
    ``nrg3_metadata_owner``                     Owner name
    ``nrg3_metadata_qualityDescription``        Quality description
    ``nrg3_metadata_source``                    Source description
    ==========================================  ========================

    **Energy ADE building extensions**

    ==========================================  ========================
    ``nrg3_bdgIsProtected``                     ``true`` / ``false``
    ``nrg3_bdgNumberOfBuildingUnits``           Integer
    ``nrg3_bdgOwnerName``                       String
    ``nrg3_bdgOwnershipType``                   Code value
    ``nrg3_bdgOwnershipType_codeSpace``
    ``nrg3_bdgType``                            Code value
    ``nrg3_bdgType_codeSpace``
    ``nrg3_bdgAtticThermalStatus``              Enum value
    ``nrg3_bdgBasementThermalStatus``           Enum value
    ``nrg3_bdgConstructionWeight``              Code value
    ``nrg3_bdgConstructionWeight_codeSpace``
    ``nrg3_bdgVolume_description``              QualifiedVolume desc
    ``nrg3_bdgVolume_source``                   QualifiedVolume source
    ``nrg3_bdgVolume_value``                    Numeric value
    ``nrg3_bdgVolume_uom``                      Unit (e.g. ``m3``)
    ``nrg3_bdgVolume_type``                     Code value
    ``nrg3_bdgVolume_type_codeSpace``
    ``nrg3_bdgArea_value``                      Numeric value
    ``nrg3_bdgArea_uom``                        Unit (e.g. ``m2``)
    ``nrg3_bdgArea_type``                       Code value
    ``nrg3_bdgArea_type_codeSpace``
    ``nrg3_bdgHeight_value``                    Numeric value
    ``nrg3_bdgHeight_uom``                      Unit (e.g. ``m``)
    ``nrg3_bdgHeight_type``                     Code value
    ``nrg3_bdgHeight_type_codeSpace``
    ==========================================  ========================
    """
    vol = _make_qualified_volume(attrs)
    area = _make_qualified_area(attrs)
    height = _make_qualified_height(attrs)

    return Building(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        # Energy ADE CityObject extensions
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        nrg3_status=_code(attrs, "nrg3_status"),
        nrg3_valid_from=_str(attrs.get("nrg3_validFrom")),
        nrg3_valid_to=_str(attrs.get("nrg3_validTo")),
        # bldg properties
        bldg_class=_code(attrs, "bldg_class"),
        bldg_function=_code(attrs, "bldg_function"),
        bldg_usage=_code(attrs, "bldg_usage"),
        year_of_construction=_int(attrs.get("bldg_yearOfConstruction")),
        year_of_demolition=_int(attrs.get("bldg_yearOfDemolition")),
        roof_type=_code(attrs, "bldg_roofType"),
        measured_height=_measure(attrs, "bldg_measuredHeight"),
        storeys_above_ground=_int(attrs.get("bldg_storeysAboveGround")),
        storeys_below_ground=_int(attrs.get("bldg_storeysBelowGround")),
        storey_heights_above_ground=_str(attrs.get("bldg_storeyHeightsAboveGround")),
        storey_heights_below_ground=_str(attrs.get("bldg_storeyHeightsBelowGround")),
        # Energy ADE building extensions
        bdg_is_protected=_bool(attrs.get("nrg3_bdgIsProtected")),
        bdg_number_of_building_units=_int(attrs.get("nrg3_bdgNumberOfBuildingUnits")),
        bdg_owner_name=_str(attrs.get("nrg3_bdgOwnerName")),
        bdg_ownership_type=_code(attrs, "nrg3_bdgOwnershipType"),
        bdg_type=_code(attrs, "nrg3_bdgType"),
        bdg_attic_thermal_status=_str(attrs.get("nrg3_bdgAtticThermalStatus")),
        bdg_basement_thermal_status=_str(attrs.get("nrg3_bdgBasementThermalStatus")),
        bdg_construction_weight=_code(attrs, "nrg3_bdgConstructionWeight"),
        bdg_volumes=[vol] if vol else [],
        bdg_areas=[area] if area else [],
        bdg_heights=[height] if height else [],
    )


def building_part_from_dict(attrs: Dict) -> BuildingPart:
    building = building_from_dict(attrs)
    return BuildingPart(**building.__dict__)


def pv_collector_from_dict(attrs: Dict) -> PhotovoltaicCollector:
    """Create a :class:`PhotovoltaicCollector` from flat attributes.

    Attribute reference
    -------------------
    **GML / Core**

    ===========================  ===================================
    ``gml_id``                   Feature ID (gml:id)
    ``gml_parent_id``            Parent Building gml:id (for linking)
    ``gml_description``          gml:description
    ``gml_name``                 gml:name
    ``core_creationDate``        ISO date
    ===========================  ===================================

    **CityObject ADE extensions (from AbstractFeatureWithLifeSpan)**

    ===========================  ===================================
    ``nrg3_identifier``          Identifier string
    ``nrg3_identifier_codeSpace``
    ``nrg3_validFrom``           DateTime string
    ``nrg3_validTo``             DateTime string
    ===========================  ===================================

    **AbstractDevice fields**

    ================================  ===============================
    ``nrg3_model``                    Model string
    ``nrg3_yearOfInstallation``       Integer year
    ``nrg3_yearOfManufacture``        Integer year
    ``nrg3_numberOfDevices``          Integer count
    ``nrg3_installedPower``           Numeric value
    ``nrg3_installedPower_uom``       e.g. ``W`` or ``kWp``
    ``nrg3_nominalEfficiency``        Numeric value
    ``nrg3_nominalEfficiency_uom``    e.g. ``unit interval``
    ``nrg3_efficiencyIndicator``      String
    ``nrg3_heatDissipation``          Numeric value
    ``nrg3_heatDissipation_uom``      e.g. ``W/m^2``
    ``nrg3_heatDissipationConvectiveFraction``
    ``nrg3_heatDissipationLatentFraction``
    ``nrg3_heatDissipationRadiantFraction``
    ================================  ===============================

    **AbstractSolarCollector fields**

    ================================  ===============================
    ``nrg3_moduleArea``               Numeric value
    ``nrg3_moduleArea_uom``           e.g. ``m^2``
    ``nrg3_apertureArea``             Numeric value
    ``nrg3_apertureArea_uom``         e.g. ``m^2``
    ``nrg3_azimuth``                  Numeric value
    ``nrg3_azimuth_uom``              e.g. ``deg`` / ``decimal degrees``
    ``nrg3_inclination``              Numeric value
    ``nrg3_inclination_uom``
    ================================  ===============================

    **PhotovoltaicCollector-specific**

    ================================  ===============================
    ``nrg3_cellType``                 e.g. ``monocrystalline``
    ``nrg3_cellType_codeSpace``       Optional codeSpace URL
    ================================  ===============================
    """
    return PhotovoltaicCollector(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        valid_from=_str(attrs.get("nrg3_validFrom")),
        valid_to=_str(attrs.get("nrg3_validTo")),
        model=_str(attrs.get("nrg3_model")),
        year_of_installation=_int(attrs.get("nrg3_yearOfInstallation")),
        year_of_manufacture=_int(attrs.get("nrg3_yearOfManufacture")),
        number_of_devices=_int(attrs.get("nrg3_numberOfDevices")),
        installed_power=_measure(attrs, "nrg3_installedPower"),
        nominal_efficiency=_measure(attrs, "nrg3_nominalEfficiency"),
        efficiency_indicator=_str(attrs.get("nrg3_efficiencyIndicator")),
        heat_dissipation=_measure(attrs, "nrg3_heatDissipation"),
        heat_dissipation_convective_fraction=_scale(
            attrs, "nrg3_heatDissipationConvectiveFraction"
        ),
        heat_dissipation_latent_fraction=_scale(
            attrs, "nrg3_heatDissipationLatentFraction"
        ),
        heat_dissipation_radiant_fraction=_scale(
            attrs, "nrg3_heatDissipationRadiantFraction"
        ),
        module_area=_measure(attrs, "nrg3_moduleArea"),
        aperture_area=_measure(attrs, "nrg3_apertureArea"),
        azimuth=_measure(attrs, "nrg3_azimuth"),
        inclination=_measure(attrs, "nrg3_inclination"),
        cell_type=_code(attrs, "nrg3_cellType"),
    )


def heat_pump_from_dict(attrs: Dict) -> HeatPump:
    """Create a :class:`HeatPump` from flat attributes.

    Attribute reference
    -------------------
    All **AbstractDevice** fields (same as PV, see above) plus:

    =====================================  ============================
    ``nrg3_heatSource``                    Code value
    ``nrg3_heatSource_codeSpace``
    ``nrg3_copSourceTemperature``          Numeric value
    ``nrg3_copSourceTemperature_uom``      e.g. ``degC``
    ``nrg3_copOperationTemperature``       Numeric value
    ``nrg3_copOperationTemperature_uom``
    =====================================  ============================
    """
    return HeatPump(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        valid_from=_str(attrs.get("nrg3_validFrom")),
        valid_to=_str(attrs.get("nrg3_validTo")),
        model=_str(attrs.get("nrg3_model")),
        year_of_installation=_int(attrs.get("nrg3_yearOfInstallation")),
        year_of_manufacture=_int(attrs.get("nrg3_yearOfManufacture")),
        number_of_devices=_int(attrs.get("nrg3_numberOfDevices")),
        installed_power=_measure(attrs, "nrg3_installedPower"),
        nominal_efficiency=_measure(attrs, "nrg3_nominalEfficiency"),
        efficiency_indicator=_str(attrs.get("nrg3_efficiencyIndicator")),
        heat_dissipation=_measure(attrs, "nrg3_heatDissipation"),
        heat_source=_code(attrs, "nrg3_heatSource"),
        cop_source_temperature=_measure(attrs, "nrg3_copSourceTemperature"),
        cop_operation_temperature=_measure(attrs, "nrg3_copOperationTemperature"),
    )


def ev_charging_station_from_dict(attrs: Dict) -> EVChargingStation:
    """Create an :class:`EVChargingStation` from flat attributes.

    Attribute reference
    -------------------
    All **AbstractDevice** fields plus:

    ========================================  ==========================
    ``nrg3_evType``                           Code value (type of EV charger)
    ``nrg3_evType_codeSpace``
    ``nrg3_chargingSpeedLevel``               Code value
    ``nrg3_chargingSpeedLevel_codeSpace``
    ``nrg3_connectorType``                    Code value
    ``nrg3_connectorType_codeSpace``
    ``nrg3_hasLoadManagement``                ``true`` / ``false``
    ``nrg3_access``                           Code value
    ``nrg3_access_codeSpace``
    ========================================  ==========================
    """
    return EVChargingStation(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        valid_from=_str(attrs.get("nrg3_validFrom")),
        valid_to=_str(attrs.get("nrg3_validTo")),
        model=_str(attrs.get("nrg3_model")),
        year_of_installation=_int(attrs.get("nrg3_yearOfInstallation")),
        year_of_manufacture=_int(attrs.get("nrg3_yearOfManufacture")),
        number_of_devices=_int(attrs.get("nrg3_numberOfDevices")),
        installed_power=_measure(attrs, "nrg3_installedPower"),
        ev_type=_code(attrs, "nrg3_evType"),
        charging_speed_level=_code(attrs, "nrg3_chargingSpeedLevel"),
        connector_type=_code(attrs, "nrg3_connectorType"),
        has_load_management=_bool(attrs.get("nrg3_hasLoadManagement")),
        access=_code(attrs, "nrg3_access"),
    )


def occupants_from_dict(attrs: Dict) -> Occupants:
    """Create :class:`Occupants` from flat attributes.

    Attribute reference
    -------------------
    ============================================  ======================
    ``gml_id``                                    Feature ID
    ``gml_name``                                  gml:name
    ``nrg3_occupantType``                         Code value
    ``nrg3_occupantType_codeSpace``
    ``nrg3_numberOfOccupants``                    Integer
    ``nrg3_averageDietType``                      Code value
    ``nrg3_averageDietType_codeSpace``
    ``nrg3_averageIncomeLevel``                   Code value
    ``nrg3_averageInstructionLevel``              Code value
    ``nrg3_heatDissipation``                      Numeric value
    ``nrg3_heatDissipation_uom``
    ============================================  ======================
    """
    return Occupants(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("nrg3_creationDate")),
        termination_date=_str(attrs.get("nrg3_terminationDate")),
        occ_metadata=_make_metadata(attrs),
        identifier=_code(attrs, "nrg3_identifier"),
        valid_from=_str(attrs.get("nrg3_validFrom")),
        valid_to=_str(attrs.get("nrg3_validTo")),
        status=_code(attrs, "nrg3_status"),
        occupant_type=_code(attrs, "nrg3_occupantType"),
        number_of_occupants=_int(attrs.get("nrg3_numberOfOccupants")),
        average_diet_type=_code(attrs, "nrg3_averageDietType"),
        average_income_level=_code(attrs, "nrg3_averageIncomeLevel"),
        average_instruction_level=_code(attrs, "nrg3_averageInstructionLevel"),
        heat_dissipation=_measure(attrs, "nrg3_heatDissipation"),
        heat_dissipation_convective_fraction=_scale(
            attrs, "nrg3_heatDissipationConvectiveFraction"
        ),
        heat_dissipation_latent_fraction=_scale(
            attrs, "nrg3_heatDissipationLatentFraction"
        ),
        heat_dissipation_radiant_fraction=_scale(
            attrs, "nrg3_heatDissipationRadiantFraction"
        ),
    )


def epc_from_dict(attrs: Dict) -> EnergyPerformanceCertificate:
    """Create an :class:`EnergyPerformanceCertificate` from flat attributes.

    Attribute reference
    -------------------
    ============================================  ======================
    ``gml_id``                                    Feature ID
    ``gml_parent_id``                             Parent Building gml:id
    ``nrg3_epcType``                              Code value
    ``nrg3_epcType_codeSpace``
    ``nrg3_epcLabel``                             Label string (e.g. ``A+``)
    ``nrg3_epcValue``                             Numeric value
    ``nrg3_epcValue_uom``                         e.g. ``kWh/(m^2*a)``
    ``nrg3_epcCertificationMethod``               String
    ============================================  ======================
    """
    return EnergyPerformanceCertificate(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("nrg3_creationDate")),
        termination_date=_str(attrs.get("nrg3_terminationDate")),
        epc_metadata=_make_metadata(attrs),
        identifier=_code(attrs, "nrg3_identifier"),
        valid_from=_str(attrs.get("nrg3_validFrom")),
        valid_to=_str(attrs.get("nrg3_validTo")),
        status=_code(attrs, "nrg3_status"),
        epc_type=_code(attrs, "nrg3_epcType"),
        label=_str(attrs.get("nrg3_epcLabel")),
        value=_measure(attrs, "nrg3_epcValue"),
        certification_method=_str(attrs.get("nrg3_epcCertificationMethod")),
    )


def building_unit_from_dict(attrs: Dict) -> BuildingUnit:
    """Create a :class:`BuildingUnit` from flat attributes.

    Attribute reference
    -------------------
    ============================================  ======================
    ``gml_id``                                    Feature ID
    ``gml_parent_id``                             Parent Building gml:id
    ``gml_name``                                  gml:name
    ``core_creationDate``                         ISO date
    ``nrg3_buType``                               Code value
    ``nrg3_buType_codeSpace``
    ``nrg3_floorNumberFrom``                      Float
    ``nrg3_floorNumberTo``                        Float
    ``nrg3_numberOfRooms``                        Integer
    ``nrg3_ownerName``                            String
    ``nrg3_ownershipType``                        Code value
    ``nrg3_ownershipType_codeSpace``
    ============================================  ======================
    """
    return BuildingUnit(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        areas=[_make_qualified_area(attrs, prefix="nrg3_area")]
        if _make_qualified_area(attrs, prefix="nrg3_area")
        else [],
        volumes=[_make_qualified_volume(attrs, prefix="nrg3_volume")]
        if _make_qualified_volume(attrs, prefix="nrg3_volume")
        else [],
        bu_type=_code(attrs, "nrg3_buType"),
        floor_number_from=_float(attrs.get("nrg3_floorNumberFrom")),
        floor_number_to=_float(attrs.get("nrg3_floorNumberTo")),
        number_of_rooms=_int(attrs.get("nrg3_numberOfRooms")),
        owner_name=_str(attrs.get("nrg3_ownerName")),
        ownership_type=_code(attrs, "nrg3_ownershipType"),
    )


def constant_value_schedule_from_dict(attrs: Dict) -> ConstantValueSchedule:
    """Create a :class:`ConstantValueSchedule` from flat attributes.

    Attribute reference
    -------------------
    ============================================  ======================
    ``gml_id``                                    Feature ID
    ``gml_name``                                  gml:name
    ``nrg3_scheduleType``                         Code value
    ``nrg3_scheduleType_codeSpace``
    ``nrg3_scheduleValue``                        Numeric value
    ``nrg3_scheduleValue_uom``                    Unit of measure
    ============================================  ======================
    """
    return ConstantValueSchedule(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("nrg3_creationDate")),
        termination_date=_str(attrs.get("nrg3_terminationDate")),
        schedule_metadata=_make_metadata(attrs),
        identifier=_code(attrs, "nrg3_identifier"),
        valid_from=_str(attrs.get("nrg3_validFrom")),
        valid_to=_str(attrs.get("nrg3_validTo")),
        status=_code(attrs, "nrg3_status"),
        schedule_type=_code(attrs, "nrg3_scheduleType"),
        start_time=_str(attrs.get("nrg3_startTime")),
        start_day=_int(attrs.get("nrg3_startDay")),
        start_month=_int(attrs.get("nrg3_startMonth")),
        start_year=_int(attrs.get("nrg3_startYear")),
        value=_measure(attrs, "nrg3_scheduleValue"),
    )


def address_from_dict(attrs: Dict) -> "Address":
    """Create a :class:`Address` from flat attributes.

    Attribute reference
    -------------------
    ============================================  ======================
    ``gml_id``                                    Feature ID
    ``gml_parent_id``                             Parent Building gml:id
    ``xal_country``                               Country name
    ``xal_locality``                              Town / city name
    ``xal_thoroughfare``                          Street name
    ``xal_thoroughfareNumber``                    House number
    ``xal_postalCode``                            Postal code
    ============================================  ======================
    """
    return Address(
        gml_id=_str(attrs.get("gml_id")),
        country=_str(attrs.get("xal_country")),
        locality=_str(attrs.get("xal_locality")),
        thoroughfare=_str(attrs.get("xal_thoroughfare")),
        thoroughfare_number=_str(attrs.get("xal_thoroughfareNumber")),
        postal_code=_str(attrs.get("xal_postalCode")),
    )


def composite_schedule_from_dict(attrs: Dict) -> "CompositeSchedule":
    """Create a :class:`CompositeSchedule` from flat attributes.

    Attribute reference
    -------------------
    ============================================  ======================
    ``gml_id``                                    Feature ID
    ``gml_parent_id``                             Parent gml:id
    ``gml_name``                                  gml:name
    ``core_creationDate``                         ISO date
    ``nrg3_scheduleType``                         Code value
    ``nrg3_scheduleType_codeSpace``
    ``nrg3_startTime``                            Start time string
    ``nrg3_startDay``                             Integer
    ``nrg3_startMonth``                           Integer
    ``nrg3_startYear``                            Integer
    ============================================  ======================

    Note: ``scheduleComponent`` children are assembled via ``gml_parent_id``
    in :class:`FeatureFactory`.
    """
    return CompositeSchedule(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("nrg3_creationDate")),
        termination_date=_str(attrs.get("nrg3_terminationDate")),
        schedule_metadata=_make_metadata(attrs),
        identifier=_code(attrs, "nrg3_identifier"),
        valid_from=_str(attrs.get("nrg3_validFrom")),
        valid_to=_str(attrs.get("nrg3_validTo")),
        status=_code(attrs, "nrg3_status"),
        schedule_type=_code(attrs, "nrg3_scheduleType"),
        start_time=_str(attrs.get("nrg3_startTime")),
        start_day=_int(attrs.get("nrg3_startDay")),
        start_month=_int(attrs.get("nrg3_startMonth")),
        start_year=_int(attrs.get("nrg3_startYear")),
    )


def room_from_dict(attrs: Dict) -> Room:
    return Room(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        bldg_class=_code(attrs, "bldg_class"),
        bldg_function=_code(attrs, "bldg_function"),
        bldg_usage=_code(attrs, "bldg_usage"),
    )


def building_installation_from_dict(attrs: Dict) -> BuildingInstallation:
    return BuildingInstallation(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        bldg_class=_code(attrs, "bldg_class"),
        bldg_function=_code(attrs, "bldg_function"),
        bldg_usage=_code(attrs, "bldg_usage"),
    )


def int_building_installation_from_dict(attrs: Dict) -> IntBuildingInstallation:
    return IntBuildingInstallation(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        bldg_class=_code(attrs, "bldg_class"),
        bldg_function=_code(attrs, "bldg_function"),
        bldg_usage=_code(attrs, "bldg_usage"),
    )


def _surface_from_dict(cls, attrs: Dict):
    """Generic boundary surface constructor."""
    return cls(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        bdg_bdry_surf_azimuth=_measure(attrs, "nrg3_bdgBdrySurfAzimuth"),
        bdg_bdry_surf_inclination=_measure(attrs, "nrg3_bdgBdrySurfInclination"),
        bdg_bdry_surf_total_surface_area=_measure(
            attrs, "nrg3_bdgBdrySurfTotalSurfaceArea"
        ),
        bdg_bdry_surf_opaque_surface_area=_measure(
            attrs, "nrg3_bdgBdrySurfOpaqueSurfaceArea"
        ),
        bdg_bdry_surf_heat_capacity=_measure(attrs, "nrg3_bdgBdrySurfHeatCapacity"),
        bdg_bdry_surf_thickness=_measure(attrs, "nrg3_bdgBdrySurfThickness"),
        bdg_bdry_surf_is_shared=_bool(attrs.get("nrg3_bdgBdrySurfIsShared")),
        bdg_bdry_surf_additional_thermal_bridge_u_value=_measure(
            attrs, "nrg3_bdgBdrySurfAdditionalThermalBridgeUValue"
        ),
        bdg_bdry_surf_ground_view_factor=_scale(
            attrs, "nrg3_bdgBdrySurfGroundViewFactor"
        ),
        bdg_bdry_surf_sky_view_factor=_scale(attrs, "nrg3_bdgBdrySurfSkyViewFactor"),
    )


def _opening_from_dict(cls, attrs: Dict):
    """Generic opening (Door / Window) constructor."""
    return cls(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        bdg_opn_area=_measure(attrs, "nrg3_bdgOpnArea"),
        bdg_opn_azimuth=_measure(attrs, "nrg3_bdgOpnAzimuth"),
        bdg_opn_inclination=_measure(attrs, "nrg3_bdgOpnInclination"),
        bdg_opn_ground_view_factor=_scale(attrs, "nrg3_bdgOpnGroundViewFactor"),
        bdg_opn_sky_view_factor=_scale(attrs, "nrg3_bdgOpnSkyViewFactor"),
    )


# ---------------------------------------------------------------------------
# Boundary surface attribute reference docstring (shared across surfaces)
# ---------------------------------------------------------------------------
_SURFACE_ATTR_DOC = """
    Attribute reference (shared by all thematic surfaces)
    -----------------------------------------------------
    ==============================================  ====================
    ``gml_id``                                      Feature ID
    ``gml_parent_id``                               Parent gml:id
    ``gml_description``                             gml:description
    ``gml_name``                                    gml:name
    ``core_creationDate``                           ISO date
    ``nrg3_bdgBdrySurfAzimuth``                     Numeric value
    ``nrg3_bdgBdrySurfAzimuth_uom``                 e.g. ``deg``
    ``nrg3_bdgBdrySurfInclination``                 Numeric value
    ``nrg3_bdgBdrySurfInclination_uom``
    ``nrg3_bdgBdrySurfTotalSurfaceArea``            Numeric value
    ``nrg3_bdgBdrySurfTotalSurfaceArea_uom``        e.g. ``m^2``
    ``nrg3_bdgBdrySurfOpaqueSurfaceArea``           Numeric value
    ``nrg3_bdgBdrySurfOpaqueSurfaceArea_uom``
    ``nrg3_bdgBdrySurfHeatCapacity``                Numeric value
    ``nrg3_bdgBdrySurfHeatCapacity_uom``
    ``nrg3_bdgBdrySurfThickness``                   Numeric value
    ``nrg3_bdgBdrySurfThickness_uom``               e.g. ``m``
    ``nrg3_bdgBdrySurfIsShared``                    ``true`` / ``false``
    ``nrg3_bdgBdrySurfGroundViewFactor``            Float 0..1
    ``nrg3_bdgBdrySurfSkyViewFactor``               Float 0..1
    ``nrg3_bdgBdrySurfAdditionalThermalBridgeUValue``
    ``nrg3_bdgBdrySurfAdditionalThermalBridgeUValue_uom``
    ==============================================  ====================
"""  # noqa: E501


# ---------------------------------------------------------------------------
# Dispatch registry: FME writer name → (class, from_dict_function)
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Any] = {}


def _is_stub(fn: Any) -> bool:
    return bool(getattr(fn, "_is_stub", False))


def _reg(fme_name: str, fn):
    _REGISTRY[fme_name] = fn


_reg("bldg_Building", building_from_dict)
_reg("bldg_BuildingPart", building_part_from_dict)
_reg("bldg_WallSurface", lambda a: _surface_from_dict(WallSurface, a))
_reg("bldg_RoofSurface", lambda a: _surface_from_dict(RoofSurface, a))
_reg("bldg_GroundSurface", lambda a: _surface_from_dict(GroundSurface, a))
_reg("bldg_CeilingSurface", lambda a: _surface_from_dict(CeilingSurface, a))
_reg("bldg_ClosureSurface", lambda a: _surface_from_dict(ClosureSurface, a))
_reg("bldg_FloorSurface", lambda a: _surface_from_dict(FloorSurface, a))
_reg("bldg_OuterCeilingSurface", lambda a: _surface_from_dict(OuterCeilingSurface, a))
_reg("bldg_OuterFloorSurface", lambda a: _surface_from_dict(OuterFloorSurface, a))
_reg("bldg_Door", lambda a: _opening_from_dict(Door, a))
_reg("bldg_Window", lambda a: _opening_from_dict(Window, a))
_reg("bldg_Room", room_from_dict)
_reg("bldg_BuildingInstallation", building_installation_from_dict)
_reg("bldg_IntBuildingInstallation", int_building_installation_from_dict)
_reg("nrg3_PhotovoltaicCollector", pv_collector_from_dict)
_reg("nrg3_HeatPump", heat_pump_from_dict)
_reg("nrg3_EVChargingStation", ev_charging_station_from_dict)
_reg("nrg3_Occupants", occupants_from_dict)
_reg("nrg3_EnergyPerformanceCertificate", epc_from_dict)
_reg("nrg3_BuildingUnit", building_unit_from_dict)
_reg("nrg3_ConstantValueSchedule", constant_value_schedule_from_dict)
_reg("nrg3_CompositeSchedule", composite_schedule_from_dict)
_reg("core_Address", address_from_dict)


# ---------------------------------------------------------------------------
# Stub registry: all Blank rows from FME division.xlsx
# Feature types listed here are not yet implemented. Each raises
# NotImplementedError so you can find and implement them one by one.
# To implement: build a Python builder class, write a from_dict function
# with the attribute mapping, and replace the stub registration below.
# ---------------------------------------------------------------------------


def _stub(feature_type: str):
    """Return a stub callable that raises NotImplementedError for *feature_type*."""

    def _fn(attrs: Dict) -> None:
        raise NotImplementedError(
            f"'{feature_type}' is not yet implemented.\n"
            f"Steps to implement:\n"
            f"  1. Build a Python builder class in citygml_energy/\n"
            f"  2. Write a {feature_type}_from_dict(attrs) function in factory.py\n"
            f"  3. Replace the stub _reg() call with the real function."
        )

    _fn.__name__ = feature_type + "_stub"
    _fn._is_stub = True
    return _fn


# --- CityGML standard modules (Blank rows) ---
_reg("frn_CityFurniture", _stub("frn_CityFurniture"))
_reg("gen_GenericCityObject", _stub("gen_GenericCityObject"))
_reg("grp_CityObjectGroup", _stub("grp_CityObjectGroup"))
_reg("luse_LandUse", _stub("luse_LandUse"))

# --- Energy ADE: resources / materials (Blank rows) ---
_reg("nrg3_ConstructionMaterial", _stub("nrg3_ConstructionMaterial"))
_reg("nrg3_LayeredConstruction", _stub("nrg3_LayeredConstruction"))
_reg("nrg3_LayeredConstructionLibrary", _stub("nrg3_LayeredConstructionLibrary"))
_reg("nrg3_MaterialLibrary", _stub("nrg3_MaterialLibrary"))
_reg("nrg3_ReverseLayeredConstruction", _stub("nrg3_ReverseLayeredConstruction"))
_reg("nrg3_SolidMaterial", _stub("nrg3_SolidMaterial"))

# --- Energy ADE: energy carriers / commodities (Blank rows) ---
_reg("nrg3_Energy", _stub("nrg3_Energy"))
_reg("nrg3_Liquid", _stub("nrg3_Liquid"))
_reg("nrg3_OtherResource", _stub("nrg3_OtherResource"))
_reg("nrg3_Waste", _stub("nrg3_Waste"))
_reg("nrg3_Water", _stub("nrg3_Water"))

# --- Energy ADE: devices (Blank rows) ---
_reg("nrg3_Boiler", _stub("nrg3_Boiler"))
_reg("nrg3_DeviceOperation", _stub("nrg3_DeviceOperation"))
_reg("nrg3_ElectricalStorageDevice", _stub("nrg3_ElectricalStorageDevice"))
_reg("nrg3_GenericDevice", _stub("nrg3_GenericDevice"))
_reg("nrg3_GenericElectricalDevice", _stub("nrg3_GenericElectricalDevice"))
_reg("nrg3_GenericStorageDevice", _stub("nrg3_GenericStorageDevice"))
_reg("nrg3_LightingDevice", _stub("nrg3_LightingDevice"))
_reg("nrg3_MovableShadingDevice", _stub("nrg3_MovableShadingDevice"))
_reg("nrg3_SolarThermalCollector", _stub("nrg3_SolarThermalCollector"))
_reg("nrg3_ThermalStorageDevice", _stub("nrg3_ThermalStorageDevice"))

# --- Energy ADE: energy networks / distribution (Blank rows) ---
_reg("nrg3_PowerDistribution", _stub("nrg3_PowerDistribution"))
_reg("nrg3_ThermalDistribution", _stub("nrg3_ThermalDistribution"))
_reg("nrg3_UtilityNetworkConnection", _stub("nrg3_UtilityNetworkConnection"))

# --- Energy ADE: schedules (Blank rows) ---
_reg("nrg3_DualValueSchedule", _stub("nrg3_DualValueSchedule"))
_reg("nrg3_IrregularTimeSeries", _stub("nrg3_IrregularTimeSeries"))
_reg("nrg3_IrregularTimeSeriesFile", _stub("nrg3_IrregularTimeSeriesFile"))
_reg("nrg3_MonthlyTimeSeries", _stub("nrg3_MonthlyTimeSeries"))
_reg("nrg3_MonthlyTimeSeriesFile", _stub("nrg3_MonthlyTimeSeriesFile"))
_reg("nrg3_RegularTimeSeries", _stub("nrg3_RegularTimeSeries"))
_reg("nrg3_RegularTimeSeriesFile", _stub("nrg3_RegularTimeSeriesFile"))
_reg("nrg3_ScheduleComponent", _stub("nrg3_ScheduleComponent"))
_reg("nrg3_ScheduleLibrary", _stub("nrg3_ScheduleLibrary"))
_reg("nrg3_TimeSeriesSchedule", _stub("nrg3_TimeSeriesSchedule"))
_reg(
    "nrg3_TypicalValuesIrregularTimeSeries",
    _stub("nrg3_TypicalValuesIrregularTimeSeries"),
)
_reg(
    "nrg3_TypicalValuesIrregularTimeSeriesFile",
    _stub("nrg3_TypicalValuesIrregularTimeSeriesFile"),
)
_reg(
    "nrg3_TypicalValuesMonthlyTimeSeries", _stub("nrg3_TypicalValuesMonthlyTimeSeries")
)
_reg(
    "nrg3_TypicalValuesMonthlyTimeSeriesFile",
    _stub("nrg3_TypicalValuesMonthlyTimeSeriesFile"),
)
_reg(
    "nrg3_TypicalValuesRegularTimeSeries", _stub("nrg3_TypicalValuesRegularTimeSeries")
)
_reg(
    "nrg3_TypicalValuesRegularTimeSeriesFile",
    _stub("nrg3_TypicalValuesRegularTimeSeriesFile"),
)

# --- Energy ADE: sensors (Blank rows) ---
_reg("nrg3_SensorConnection", _stub("nrg3_SensorConnection"))
_reg("nrg3_SensorData", _stub("nrg3_SensorData"))
_reg("nrg3_WeatherData", _stub("nrg3_WeatherData"))
_reg("nrg3_WeatherStation", _stub("nrg3_WeatherStation"))

# --- Energy ADE: urban / zone objects (Blank rows) ---
_reg("nrg3_Intervention", _stub("nrg3_Intervention"))
_reg("nrg3_UrbanFunctionArea", _stub("nrg3_UrbanFunctionArea"))
_reg("nrg3_UrbanSpace", _stub("nrg3_UrbanSpace"))
_reg("nrg3_Zone", _stub("nrg3_Zone"))
_reg("nrg3_ZonePart", _stub("nrg3_ZonePart"))

# --- Energy ADE: zone surfaces (Blank rows) ---
_reg("nrg3_ZoneAtticFloorSurface", _stub("nrg3_ZoneAtticFloorSurface"))
_reg("nrg3_ZoneClosureSurface", _stub("nrg3_ZoneClosureSurface"))
_reg("nrg3_ZoneDoor", _stub("nrg3_ZoneDoor"))
_reg("nrg3_ZoneGroundSurface", _stub("nrg3_ZoneGroundSurface"))
_reg("nrg3_ZoneIntermediateFloorSurface", _stub("nrg3_ZoneIntermediateFloorSurface"))
_reg("nrg3_ZoneOuterCeilingSurface", _stub("nrg3_ZoneOuterCeilingSurface"))
_reg("nrg3_ZoneOuterFloorSurface", _stub("nrg3_ZoneOuterFloorSurface"))
_reg("nrg3_ZoneRoofSurface", _stub("nrg3_ZoneRoofSurface"))
_reg("nrg3_ZoneWallSurface", _stub("nrg3_ZoneWallSurface"))
_reg("nrg3_ZoneWindow", _stub("nrg3_ZoneWindow"))


def create_feature(feature_type: str, attrs: Dict) -> Any:
    """Create a builder object from an FME-style feature type name and attributes.

    Parameters
    ----------
    feature_type:
        FME writer name (e.g. ``"bldg_Building"``,
        ``"nrg3_PhotovoltaicCollector"``).
    attrs:
        Flat attribute dictionary.

    Returns
    -------
    A builder instance (e.g. :class:`Building`, :class:`PhotovoltaicCollector`).

    Raises
    ------
    ValueError
        If *feature_type* is not registered.
    """
    fn = _REGISTRY.get(feature_type)
    if fn is None:
        registered = sorted(_REGISTRY.keys())
        raise ValueError(
            f"Unknown feature type {feature_type!r}. Registered types: {registered}"
        )
    return fn(attrs)


def list_feature_types(*, include_unimplemented: bool = False) -> List[str]:
    """Return registered FME-style feature types.

    By default this returns only feature types that can currently be created
    from input data. Set ``include_unimplemented=True`` to include stubbed
    feature types that are registered for future work.
    """
    if include_unimplemented:
        return sorted(_REGISTRY.keys())
    return sorted(name for name, fn in _REGISTRY.items() if not _is_stub(fn))


# ---------------------------------------------------------------------------
# FeatureFactory: batch builder with parent-child relationship management
# ---------------------------------------------------------------------------


class FeatureFactory:
    """Stateful batch builder that assembles a city model from flat feature rows.

    Usage::

        factory = FeatureFactory(description="My city", name="City 1")

        factory.add("bldg_Building", {
            "gml_id":                  "bldg_1",
            "gml_name":                "House 1",
            "bldg_yearOfConstruction": "2020",
            "nrg3_bdgOwnerName":       "Jane Doe",
        })

        factory.add("nrg3_PhotovoltaicCollector", {
            "gml_id":            "pv_1",
            "gml_parent_id":     "bldg_1",    # ← links to bldg_1
            "nrg3_model":        "SunPower X",
            "nrg3_installedPower":     "5000",
            "nrg3_installedPower_uom": "W",
            "nrg3_azimuth":            "180",
            "nrg3_azimuth_uom":        "deg",
            "nrg3_inclination":        "30",
            "nrg3_inclination_uom":    "deg",
            "nrg3_cellType":           "monocrystalline",
        })

        city_model = factory.build()
        city_model.write("output.gml")

    Supported parent-child relationships
    -------------------------------------
    * ``nrg3_*`` devices (PV, HeatPump, EV) → Building (via ``devices``)
    * ``bldg_*Surface``                      → Building (via ``bounded_by_surfaces``)
    * ``bldg_BuildingPart``                  → Building (via ``building_parts``)
    * ``nrg3_BuildingUnit``                  → Building
    * ``nrg3_EnergyPerformanceCertificate``  → Building
    * ``bldg_Room``                          → Building (via ``interior_rooms``)
    * ``bldg_Window`` / ``bldg_Door``        → any BoundarySurface (via ``openings``)
    * ``bldg_BuildingInstallation``          → Building (outer)
    * ``bldg_IntBuildingInstallation``       → Building (interior)
    """

    # Feature types that are "devices" attached to a building
    _DEVICE_TYPES = {
        "nrg3_PhotovoltaicCollector",
        "nrg3_HeatPump",
        "nrg3_EVChargingStation",
    }

    # Feature types that are boundary surfaces attached to a building
    _SURFACE_TYPES = {
        "bldg_WallSurface",
        "bldg_RoofSurface",
        "bldg_GroundSurface",
        "bldg_CeilingSurface",
        "bldg_ClosureSurface",
        "bldg_FloorSurface",
        "bldg_OuterCeilingSurface",
        "bldg_OuterFloorSurface",
    }

    # Feature types that are openings attached to a surface
    _OPENING_TYPES = {"bldg_Door", "bldg_Window"}

    def __init__(
        self,
        description: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        self._description = description
        self._name = name
        # Ordered list of (feature_type, attrs, built_object)
        self._rows: List[tuple] = []

    def add(self, feature_type: str, attrs: Dict) -> "FeatureFactory":
        """Queue a feature row for assembly."""
        obj = create_feature(feature_type, attrs)
        parent_id = _str(attrs.get("gml_parent_id"))
        self._rows.append((feature_type, parent_id, obj))
        return self

    def build(self) -> CityModel:
        """Assemble and return a :class:`CityModel`.

        All features with a ``gml_parent_id`` are attached to their parent.
        Top-level features (no ``gml_parent_id``) become ``cityObjectMember``s.
        """
        # Index by gml_id for quick lookup
        id_index: Dict[str, Any] = {}
        for ftype, parent_id, obj in self._rows:
            if obj.gml_id:
                id_index[obj.gml_id] = (ftype, obj)

        # Attach children to parents
        for ftype, parent_id, obj in self._rows:
            if parent_id is None:
                continue
            parent_entry = id_index.get(parent_id)
            if parent_entry is None:
                raise ValueError(
                    f"gml_parent_id {parent_id!r} not found "
                    f"(referenced by {obj.gml_id!r})"
                )
            parent_ftype, parent_obj = parent_entry
            self._attach(ftype, obj, parent_ftype, parent_obj)

        # Collect top-level features
        model = CityModel(
            gml_description=self._description,
            gml_name=self._name,
        )
        for ftype, parent_id, obj in self._rows:
            if parent_id is None:
                model.add(obj)

        return model

    # ------------------------------------------------------------------
    def _attach(
        self, child_type: str, child: Any, parent_type: str, parent: Any
    ) -> None:
        """Attach a child feature to its parent."""
        if child_type in self._DEVICE_TYPES:
            parent.devices.append(child)

        elif child_type in self._SURFACE_TYPES:
            parent.bounded_by_surfaces.append(child)

        elif child_type in self._OPENING_TYPES:
            parent.openings.append(child)

        elif child_type == "bldg_BuildingPart":
            parent.building_parts.append(child)

        elif child_type == "bldg_Room":
            parent.interior_rooms.append(child)

        elif child_type == "bldg_BuildingInstallation":
            parent.outer_building_installations.append(child)

        elif child_type == "bldg_IntBuildingInstallation":
            parent.interior_building_installations.append(child)

        elif child_type == "nrg3_BuildingUnit":
            parent.building_units.append(child)

        elif child_type == "nrg3_EnergyPerformanceCertificate":
            if hasattr(parent, "energy_performance_certificates"):
                parent.energy_performance_certificates.append(child)

        elif child_type == "nrg3_Occupants":
            parent.occupied_by.append(child)

        else:
            raise ValueError(
                f"Don't know how to attach {child_type!r} to {parent_type!r}"
            )
