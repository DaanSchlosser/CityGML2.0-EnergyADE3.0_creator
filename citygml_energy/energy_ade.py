"""Energy ADE 3.0 feature classes: devices, schedules, occupants, and more.

This module covers all 25 target classes from the Excel specification that
belong to the Energy ADE namespace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .base import BaseBuilder
from .building import (
    _BUILDING_SPACE_FIELD_MAP,
    _BUILDING_SPACE_ORDER,
    _CITY_OBJECT_ADE_FIELD_MAP,
    _CITY_OBJECT_ADE_ORDER,
    _AbstractBuildingSpace,
)
from .namespaces import NS_CORE, NS_GML, NS_NRG3
from .types import CodeValue, MeasureValue, ScaleValue, XlinkRef

# ===================================================================
# CityObjectRelation
# ===================================================================


@dataclass
class CityObjectRelation(BaseBuilder):
    """``nrg3:CityObjectRelation`` -- relation between city objects.

    The ``relatedTo`` child is an ``xlink:href`` reference to the related
    object, represented using :class:`XlinkRef`.
    """

    ELEMENT_TAG: ClassVar = (NS_NRG3, "CityObjectRelation")
    ELEMENT_ORDER: ClassVar = (
        (NS_NRG3, "relationType"),
        (NS_NRG3, "relatedTo"),
    )
    FIELD_MAP: ClassVar = {
        "relation_type": (NS_NRG3, "relationType"),
        "related_to": (NS_NRG3, "relatedTo"),
    }

    relation_type: CodeValue | None = None
    related_to: XlinkRef | None = None

    @property
    def related_to_href(self) -> str | None:
        """Backwards-compatible accessor for the href string."""
        return self.related_to.href if self.related_to is not None else None

    @related_to_href.setter
    def related_to_href(self, value: str | None) -> None:
        self.related_to = XlinkRef(value) if value is not None else None


# ===================================================================
# FeatureRelation (XSD: FeatureRelationType)
# ===================================================================


@dataclass
class FeatureRelation(BaseBuilder):
    """``nrg3:FeatureRelation`` -- relation between ADE features.

    Used by ``AbstractFeatureWithLifeSpan.relatedTo`` (as opposed to
    :class:`CityObjectRelation` which is used by CityObject.relatedTo).

    XSD: FeatureRelationType -- relationType (CodeType) + relatedTo
    (gml:FeaturePropertyType, i.e. xlink:href to another feature).
    """

    ELEMENT_TAG: ClassVar = (NS_NRG3, "FeatureRelation")
    ELEMENT_ORDER: ClassVar = (
        (NS_NRG3, "relationType"),
        (NS_NRG3, "relatedTo"),
    )
    FIELD_MAP: ClassVar = {
        "relation_type": (NS_NRG3, "relationType"),
        "related_to": (NS_NRG3, "relatedTo"),
    }

    relation_type: CodeValue | None = None
    related_to: XlinkRef | None = None


# ===================================================================
# Data types / qualified attributes
# ===================================================================


_QUALIFIED_ATTR_ORDER: tuple[tuple[str, str], ...] = (
    (NS_NRG3, "description"),
    (NS_NRG3, "source"),
    (NS_NRG3, "value"),
    (NS_NRG3, "type"),
)

_QUALIFIED_ATTR_FIELD_MAP: dict[str, tuple[str, str]] = {
    "description": (NS_NRG3, "description"),
    "source": (NS_NRG3, "source"),
    "value": (NS_NRG3, "value"),
    "type": (NS_NRG3, "type"),
}


@dataclass
class _AbstractQualifiedAttribute(BaseBuilder):
    """Shared base for QualifiedVolume / QualifiedArea / QualifiedHeight."""

    ELEMENT_ORDER: ClassVar = _QUALIFIED_ATTR_ORDER
    FIELD_MAP: ClassVar = _QUALIFIED_ATTR_FIELD_MAP

    description: str | None = None
    source: str | None = None
    value: MeasureValue | None = None
    type: CodeValue | None = None


@dataclass
class QualifiedVolume(_AbstractQualifiedAttribute):
    ELEMENT_TAG: ClassVar = (NS_NRG3, "QualifiedVolume")


@dataclass
class QualifiedArea(_AbstractQualifiedAttribute):
    ELEMENT_TAG: ClassVar = (NS_NRG3, "QualifiedArea")


@dataclass
class QualifiedHeight(_AbstractQualifiedAttribute):
    ELEMENT_TAG: ClassVar = (NS_NRG3, "QualifiedHeight")


# ===================================================================
# Metadata
# ===================================================================


@dataclass
class Metadata(BaseBuilder):
    """``nrg3:Metadata`` -- extends gml:MetaDataPropertyType."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "Metadata")
    ELEMENT_ORDER: ClassVar = (
        (NS_NRG3, "author"),
        (NS_NRG3, "acquisitionMethod"),
        (NS_NRG3, "owner"),
        (NS_NRG3, "qualityDescription"),
        (NS_NRG3, "source"),
    )
    FIELD_MAP: ClassVar = {
        "author": (NS_NRG3, "author"),
        "acquisition_method": (NS_NRG3, "acquisitionMethod"),
        "owner": (NS_NRG3, "owner"),
        "quality_description": (NS_NRG3, "qualityDescription"),
        "source": (NS_NRG3, "source"),
    }

    author: str | None = None
    acquisition_method: CodeValue | None = None
    owner: str | None = None
    quality_description: str | None = None
    source: str | None = None


# ===================================================================
# Abstract ADE Feature (XSD: AbstractFeatureWithLifeSpanType)
# ===================================================================

# Shared element order for all features extending AbstractFeatureWithLifeSpanType.
# This covers: gml:AbstractFeatureType → AbstractADEFeatureType →
# AbstractFeatureWithLifeSpanType.
_ADE_FEATURE_BASE_ORDER: tuple[tuple[str, str], ...] = (
    (NS_GML, "description"),
    (NS_GML, "name"),
    (NS_NRG3, "creationDate"),
    (NS_NRG3, "terminationDate"),
    (NS_NRG3, "externalReference"),  # AbstractADEFeatureType (0..*)
    (NS_NRG3, "metadata"),  # AbstractADEFeatureType
    (NS_NRG3, "identifier"),  # AbstractFeatureWithLifeSpanType
    (NS_NRG3, "validFrom"),
    (NS_NRG3, "validTo"),
    (NS_NRG3, "status"),
    (NS_NRG3, "relatedTo"),  # (0..*)
)

_ADE_FEATURE_BASE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    "creation_date": (NS_NRG3, "creationDate"),
    "termination_date": (NS_NRG3, "terminationDate"),
    "external_references": (NS_NRG3, "externalReference"),
    "metadata": (NS_NRG3, "metadata"),
    "identifier": (NS_NRG3, "identifier"),
    "valid_from": (NS_NRG3, "validFrom"),
    "valid_to": (NS_NRG3, "validTo"),
    "status": (NS_NRG3, "status"),
    "related_to": (NS_NRG3, "relatedTo"),
}


@dataclass
class _AbstractADEFeature(BaseBuilder):
    """Base for all Energy ADE features extending AbstractFeatureWithLifeSpanType.

    Covers: Occupants, EPC, Energy, all Schedules, all TimeSeries,
    DeviceOperation, ScheduleComponent.
    """

    gml_description: str | None = None
    gml_name: str | None = None
    creation_date: str | None = None
    termination_date: str | None = None
    external_references: list[Any] = field(default_factory=list)
    metadata: Metadata | None = None
    identifier: CodeValue | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    status: CodeValue | None = None
    related_to: list[FeatureRelation] = field(default_factory=list)


# ===================================================================
# Device Operation
# ===================================================================


@dataclass
class DeviceOperation(_AbstractADEFeature):
    """``nrg3:DeviceOperation``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "DeviceOperation")
    ELEMENT_ORDER: ClassVar = (
        *_ADE_FEATURE_BASE_ORDER,
        (NS_NRG3, "type"),
        (NS_NRG3, "yearlyGlobalEfficiency"),
        (NS_NRG3, "schedule"),
    )
    FIELD_MAP: ClassVar = {
        **_ADE_FEATURE_BASE_FIELD_MAP,
        "type": (NS_NRG3, "type"),
        "yearly_global_efficiency": (NS_NRG3, "yearlyGlobalEfficiency"),
        "schedule": (NS_NRG3, "schedule"),
    }

    type: CodeValue | None = None
    yearly_global_efficiency: float | None = None
    schedule: Any | None = None  # AbstractSchedule or xlink ref


# ===================================================================
# Abstract Device (shared fields)
# ===================================================================

# Element order for CityObject extensions + AbstractDevice fields.
# AbstractDevice substitutes core:_CityObject, so it inherits ALL 14
# CityObject ADE hooks via _GenericApplicationPropertyOfCityObject.
_DEVICE_BASE_ORDER: tuple[tuple[str, str], ...] = (
    # -- gml:AbstractFeatureType --
    (NS_GML, "description"),
    (NS_GML, "name"),
    # -- core:AbstractCityObjectType --
    (NS_CORE, "creationDate"),
    (NS_CORE, "terminationDate"),
    (NS_CORE, "externalReference"),
    # -- Energy ADE CityObject extensions (all 14) --
    *_CITY_OBJECT_ADE_ORDER,
    # -- nrg3:AbstractDeviceType --
    (NS_NRG3, "model"),
    (NS_NRG3, "yearOfInstallation"),
    (NS_NRG3, "yearOfManufacture"),
    (NS_NRG3, "numberOfDevices"),
    (NS_NRG3, "installedPower"),
    (NS_NRG3, "nominalEfficiency"),
    (NS_NRG3, "efficiencyIndicator"),
    (NS_NRG3, "heatDissipation"),
    (NS_NRG3, "heatDissipationConvectiveFraction"),
    (NS_NRG3, "heatDissipationLatentFraction"),
    (NS_NRG3, "heatDissipationRadiantFraction"),
    (NS_NRG3, "deviceOperation"),
)

_DEVICE_BASE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    "creation_date": (NS_CORE, "creationDate"),
    "termination_date": (NS_CORE, "terminationDate"),
    "external_references": (NS_CORE, "externalReference"),
    # All 14 CityObject ADE hooks
    **_CITY_OBJECT_ADE_FIELD_MAP,
    # AbstractDeviceType
    "model": (NS_NRG3, "model"),
    "year_of_installation": (NS_NRG3, "yearOfInstallation"),
    "year_of_manufacture": (NS_NRG3, "yearOfManufacture"),
    "number_of_devices": (NS_NRG3, "numberOfDevices"),
    "installed_power": (NS_NRG3, "installedPower"),
    "nominal_efficiency": (NS_NRG3, "nominalEfficiency"),
    "efficiency_indicator": (NS_NRG3, "efficiencyIndicator"),
    "heat_dissipation": (NS_NRG3, "heatDissipation"),
    "heat_dissipation_convective_fraction": (
        NS_NRG3,
        "heatDissipationConvectiveFraction",
    ),
    "heat_dissipation_latent_fraction": (NS_NRG3, "heatDissipationLatentFraction"),
    "heat_dissipation_radiant_fraction": (NS_NRG3, "heatDissipationRadiantFraction"),
    "device_operations": (NS_NRG3, "deviceOperation"),
}


@dataclass
class _AbstractDevice(BaseBuilder):
    """Base for all device types (not instantiated directly).

    XSD: AbstractDeviceType extends core:AbstractCityObjectType,
    so it inherits all 14 CityObject ADE extension hooks.
    """

    # -- gml:AbstractFeatureType --
    gml_description: str | None = None
    gml_name: str | None = None
    # -- core:AbstractCityObjectType --
    creation_date: str | None = None
    termination_date: str | None = None
    external_references: list[Any] = field(default_factory=list)
    # -- CityObject ADE hooks (all 14) --
    nrg3_devices: list[Any] = field(default_factory=list)
    nrg3_identifier: CodeValue | None = None
    nrg3_indicators: list[Any] = field(default_factory=list)
    nrg3_interventions: list[Any] = field(default_factory=list)
    nrg3_layered_construction: Any | None = None
    nrg3_metadata: Metadata | None = None
    nrg3_related_to: list[Any] = field(default_factory=list)
    nrg3_resources: list[Any] = field(default_factory=list)
    nrg3_sensor_data: list[Any] = field(default_factory=list)
    nrg3_status: CodeValue | None = None
    nrg3_utility_network_connections: list[Any] = field(default_factory=list)
    nrg3_valid_from: str | None = None
    nrg3_valid_to: str | None = None
    nrg3_reference_point: Any | None = None
    # -- nrg3:AbstractDeviceType --
    model: str | None = None
    year_of_installation: int | None = None
    year_of_manufacture: int | None = None
    number_of_devices: int | None = None
    installed_power: MeasureValue | None = None
    nominal_efficiency: MeasureValue | None = None
    efficiency_indicator: str | None = None
    heat_dissipation: MeasureValue | None = None
    heat_dissipation_convective_fraction: ScaleValue | None = None
    heat_dissipation_latent_fraction: ScaleValue | None = None
    heat_dissipation_radiant_fraction: ScaleValue | None = None
    device_operations: list[DeviceOperation] = field(default_factory=list)


# ===================================================================
# Solar Collectors (XSD: AbstractSolarCollectorType → AbstractDeviceType)
# ===================================================================

_SOLAR_COLLECTOR_ORDER: tuple[tuple[str, str], ...] = (
    *_DEVICE_BASE_ORDER,
    (NS_NRG3, "moduleArea"),
    (NS_NRG3, "apertureArea"),
    (NS_NRG3, "azimuth"),
    (NS_NRG3, "inclination"),
    (NS_NRG3, "lod2MultiSurface"),
    (NS_NRG3, "lod3MultiSurface"),
)

_SOLAR_COLLECTOR_FIELD_MAP: dict[str, tuple[str, str]] = {
    **_DEVICE_BASE_FIELD_MAP,
    "module_area": (NS_NRG3, "moduleArea"),
    "aperture_area": (NS_NRG3, "apertureArea"),
    "azimuth": (NS_NRG3, "azimuth"),
    "inclination": (NS_NRG3, "inclination"),
    "lod2_multi_surface": (NS_NRG3, "lod2MultiSurface"),
    "lod3_multi_surface": (NS_NRG3, "lod3MultiSurface"),
}


@dataclass
class _AbstractSolarCollector(_AbstractDevice):
    """XSD: AbstractSolarCollectorType → AbstractDeviceType.

    Shared base for PhotovoltaicCollector, SolarThermalCollector.
    """

    module_area: MeasureValue | None = None
    aperture_area: MeasureValue | None = None
    azimuth: MeasureValue | None = None
    inclination: MeasureValue | None = None
    lod2_multi_surface: Any | None = None
    lod3_multi_surface: Any | None = None


@dataclass
class PhotovoltaicCollector(_AbstractSolarCollector):
    """``nrg3:PhotovoltaicCollector`` -- PV panel/array.

    XSD: PhotovoltaicCollectorType → AbstractSolarCollectorType.
    """

    ELEMENT_TAG: ClassVar = (NS_NRG3, "PhotovoltaicCollector")
    FEATURE_TYPE: ClassVar = "nrg3_PhotovoltaicCollector"
    PARENT_FIELD: ClassVar = "nrg3_devices"
    ELEMENT_ORDER: ClassVar = (
        *_SOLAR_COLLECTOR_ORDER,
        (NS_NRG3, "cellType"),
    )
    FIELD_MAP: ClassVar = {
        **_SOLAR_COLLECTOR_FIELD_MAP,
        "cell_type": (NS_NRG3, "cellType"),
    }

    cell_type: CodeValue | None = None


# ===================================================================
# Heat Pump
# ===================================================================


@dataclass
class HeatPump(_AbstractDevice):
    """``nrg3:HeatPump``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "HeatPump")
    FEATURE_TYPE: ClassVar = "nrg3_HeatPump"
    PARENT_FIELD: ClassVar = "nrg3_devices"
    ELEMENT_ORDER: ClassVar = (
        *_DEVICE_BASE_ORDER,
        (NS_NRG3, "heatSource"),
        (NS_NRG3, "copSourceTemperature"),
        (NS_NRG3, "copOperationTemperature"),
    )
    FIELD_MAP: ClassVar = {
        **_DEVICE_BASE_FIELD_MAP,
        "heat_source": (NS_NRG3, "heatSource"),
        "cop_source_temperature": (NS_NRG3, "copSourceTemperature"),
        "cop_operation_temperature": (NS_NRG3, "copOperationTemperature"),
    }

    heat_source: CodeValue | None = None
    cop_source_temperature: MeasureValue | None = None
    cop_operation_temperature: MeasureValue | None = None


# ===================================================================
# EV Charging Station
# ===================================================================


@dataclass
class EVChargingStation(_AbstractDevice):
    """``nrg3:EVChargingStation``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "EVChargingStation")
    FEATURE_TYPE: ClassVar = "nrg3_EVChargingStation"
    PARENT_FIELD: ClassVar = "nrg3_devices"

    ELEMENT_ORDER: ClassVar = (
        *_DEVICE_BASE_ORDER,
        (NS_NRG3, "type"),
        (NS_NRG3, "chargingSpeedLevel"),
        (NS_NRG3, "connectorType"),
        (NS_NRG3, "hasLoadManagement"),
        (NS_NRG3, "access"),
    )
    FIELD_MAP: ClassVar = {
        **_DEVICE_BASE_FIELD_MAP,
        "ev_type": (NS_NRG3, "type"),
        "charging_speed_level": (NS_NRG3, "chargingSpeedLevel"),
        "connector_type": (NS_NRG3, "connectorType"),
        "has_load_management": (NS_NRG3, "hasLoadManagement"),
        "access": (NS_NRG3, "access"),
    }

    ev_type: CodeValue | None = None
    charging_speed_level: CodeValue | None = None
    connector_type: CodeValue | None = None
    has_load_management: bool | None = None
    access: CodeValue | None = None


# ===================================================================
# Schedules
# ===================================================================

# Shared schedule base order (AbstractScheduleType extends AbstractFeatureWithLifeSpanType)
_SCHEDULE_BASE_ORDER: tuple[tuple[str, str], ...] = (
    *_ADE_FEATURE_BASE_ORDER,
    (NS_NRG3, "type"),
    (NS_NRG3, "startTime"),
    (NS_NRG3, "startDay"),
    (NS_NRG3, "startMonth"),
    (NS_NRG3, "startYear"),
    (NS_NRG3, "temporalExtent"),
)

_SCHEDULE_BASE_FIELD_MAP: dict[str, tuple[str, str]] = {
    **_ADE_FEATURE_BASE_FIELD_MAP,
    "schedule_type": (NS_NRG3, "type"),
    "start_time": (NS_NRG3, "startTime"),
    "start_day": (NS_NRG3, "startDay"),
    "start_month": (NS_NRG3, "startMonth"),
    "start_year": (NS_NRG3, "startYear"),
    "temporal_extent": (NS_NRG3, "temporalExtent"),
}


@dataclass
class _AbstractSchedule(_AbstractADEFeature):
    """Shared fields for all schedule types (XSD: AbstractScheduleType)."""

    schedule_type: CodeValue | None = None
    start_time: str | None = None
    start_day: int | None = None
    start_month: int | None = None
    start_year: int | None = None
    temporal_extent: Any | None = None


@dataclass
class ConstantValueSchedule(_AbstractSchedule):
    """``nrg3:ConstantValueSchedule``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "ConstantValueSchedule")
    FEATURE_TYPE: ClassVar = "nrg3_ConstantValueSchedule"
    ELEMENT_ORDER: ClassVar = (
        *_SCHEDULE_BASE_ORDER,
        (NS_NRG3, "value"),
    )
    FIELD_MAP: ClassVar = {
        **_SCHEDULE_BASE_FIELD_MAP,
        "value": (NS_NRG3, "value"),
    }

    value: MeasureValue | None = None


@dataclass
class ScheduleComponent(_AbstractADEFeature):
    """``nrg3:ScheduleComponent`` -- part of a CompositeSchedule."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "ScheduleComponent")
    ELEMENT_ORDER: ClassVar = (
        *_ADE_FEATURE_BASE_ORDER,
        (NS_NRG3, "type"),
        (NS_NRG3, "repetitions"),
        (NS_NRG3, "additionalGap"),
        (NS_NRG3, "scheduleComponentMember"),
    )
    FIELD_MAP: ClassVar = {
        **_ADE_FEATURE_BASE_FIELD_MAP,
        "component_type": (NS_NRG3, "type"),
        "repetitions": (NS_NRG3, "repetitions"),
        "additional_gap": (NS_NRG3, "additionalGap"),
        "schedule_member": (NS_NRG3, "scheduleComponentMember"),
    }

    component_type: CodeValue | None = None
    repetitions: int | None = None
    additional_gap: Any | None = None
    schedule_member: Any | None = None  # AbstractSchedule


@dataclass
class CompositeSchedule(_AbstractSchedule):
    """``nrg3:CompositeSchedule``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "CompositeSchedule")
    FEATURE_TYPE: ClassVar = "nrg3_CompositeSchedule"
    ELEMENT_ORDER: ClassVar = (
        *_SCHEDULE_BASE_ORDER,
        (NS_NRG3, "scheduleComponent"),
    )
    FIELD_MAP: ClassVar = {
        **_SCHEDULE_BASE_FIELD_MAP,
        "schedule_components": (NS_NRG3, "scheduleComponent"),
    }

    schedule_components: list[ScheduleComponent] = field(default_factory=list)


# ===================================================================
# Occupants
# ===================================================================


@dataclass
class Occupants(_AbstractADEFeature):
    """``nrg3:Occupants``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "Occupants")
    FEATURE_TYPE: ClassVar = "nrg3_Occupants"
    PARENT_FIELD: ClassVar = "occupied_by"
    ELEMENT_ORDER: ClassVar = (
        *_ADE_FEATURE_BASE_ORDER,
        (NS_NRG3, "type"),
        (NS_NRG3, "numberOfOccupants"),
        (NS_NRG3, "averageDietType"),
        (NS_NRG3, "averageIncomeLevel"),
        (NS_NRG3, "averageInstructionLevel"),
        (NS_NRG3, "heatDissipation"),
        (NS_NRG3, "heatDissipationConvectiveFraction"),
        (NS_NRG3, "heatDissipationLatentFraction"),
        (NS_NRG3, "heatDissipationRadiantFraction"),
        (NS_NRG3, "occupancySchedule"),
    )
    FIELD_MAP: ClassVar = {
        **_ADE_FEATURE_BASE_FIELD_MAP,
        "occupant_type": (NS_NRG3, "type"),
        "number_of_occupants": (NS_NRG3, "numberOfOccupants"),
        "average_diet_type": (NS_NRG3, "averageDietType"),
        "average_income_level": (NS_NRG3, "averageIncomeLevel"),
        "average_instruction_level": (NS_NRG3, "averageInstructionLevel"),
        "heat_dissipation": (NS_NRG3, "heatDissipation"),
        "heat_dissipation_convective_fraction": (
            NS_NRG3,
            "heatDissipationConvectiveFraction",
        ),
        "heat_dissipation_latent_fraction": (NS_NRG3, "heatDissipationLatentFraction"),
        "heat_dissipation_radiant_fraction": (
            NS_NRG3,
            "heatDissipationRadiantFraction",
        ),
        "occupancy_schedule": (NS_NRG3, "occupancySchedule"),
    }

    occupant_type: CodeValue | None = None
    number_of_occupants: int | None = None
    average_diet_type: CodeValue | None = None
    average_income_level: CodeValue | None = None
    average_instruction_level: CodeValue | None = None
    heat_dissipation: MeasureValue | None = None
    heat_dissipation_convective_fraction: ScaleValue | None = None
    heat_dissipation_latent_fraction: ScaleValue | None = None
    heat_dissipation_radiant_fraction: ScaleValue | None = None
    occupancy_schedule: Any | None = None


# ===================================================================
# Energy Performance Certificate
# ===================================================================


@dataclass
class EnergyPerformanceCertificate(_AbstractADEFeature):
    """``nrg3:EnergyPerformanceCertificate``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "EnergyPerformanceCertificate")
    FEATURE_TYPE: ClassVar = "nrg3_EnergyPerformanceCertificate"
    PARENT_FIELD: ClassVar = "energy_performance_certificates"
    ELEMENT_ORDER: ClassVar = (
        *_ADE_FEATURE_BASE_ORDER,
        (NS_NRG3, "type"),
        (NS_NRG3, "label"),
        (NS_NRG3, "value"),
        (NS_NRG3, "certificationMethod"),
    )
    FIELD_MAP: ClassVar = {
        **_ADE_FEATURE_BASE_FIELD_MAP,
        "epc_type": (NS_NRG3, "type"),
        "label": (NS_NRG3, "label"),
        "value": (NS_NRG3, "value"),
        "certification_method": (NS_NRG3, "certificationMethod"),
    }

    epc_type: CodeValue | None = None
    label: str | None = None
    value: MeasureValue | None = None
    certification_method: str | None = None


# ===================================================================
# Resources (XSD: AbstractResourceType → AbstractFeatureWithLifeSpanType)
# ===================================================================

_RESOURCE_BASE_ORDER: tuple[tuple[str, str], ...] = (
    *_ADE_FEATURE_BASE_ORDER,
    (NS_NRG3, "operationType"),
    (NS_NRG3, "referencePeriod"),
    (NS_NRG3, "amount"),
    (NS_NRG3, "year"),
    (NS_NRG3, "isAmountNormalized"),
    (NS_NRG3, "normalizationValue"),
    (NS_NRG3, "normalizationParameter"),
    (NS_NRG3, "expense"),
    (NS_NRG3, "revenue"),
    (NS_NRG3, "co2Equivalent"),
    (NS_NRG3, "timeDependentAmount"),
    (NS_NRG3, "timeDependentExpense"),
    (NS_NRG3, "timeDependentRevenue"),
    (NS_NRG3, "amountBasedOn"),
)

_RESOURCE_BASE_FIELD_MAP: dict[str, tuple[str, str]] = {
    **_ADE_FEATURE_BASE_FIELD_MAP,
    "operation_type": (NS_NRG3, "operationType"),
    "reference_period": (NS_NRG3, "referencePeriod"),
    "amount": (NS_NRG3, "amount"),
    "year": (NS_NRG3, "year"),
    "is_amount_normalized": (NS_NRG3, "isAmountNormalized"),
    "normalization_value": (NS_NRG3, "normalizationValue"),
    "normalization_parameter": (NS_NRG3, "normalizationParameter"),
    "expense": (NS_NRG3, "expense"),
    "revenue": (NS_NRG3, "revenue"),
    "co2_equivalent": (NS_NRG3, "co2Equivalent"),
    "time_dependent_amount": (NS_NRG3, "timeDependentAmount"),
    "time_dependent_expense": (NS_NRG3, "timeDependentExpense"),
    "time_dependent_revenue": (NS_NRG3, "timeDependentRevenue"),
    "amount_based_on": (NS_NRG3, "amountBasedOn"),
}


@dataclass
class _AbstractResource(_AbstractADEFeature):
    """XSD: AbstractResourceType → AbstractFeatureWithLifeSpanType.

    Shared base for Energy, Waste, Liquid, Water, OtherResource.
    """

    PARENT_FIELD: ClassVar = "nrg3_resources"

    operation_type: CodeValue | None = None
    reference_period: CodeValue | None = None
    amount: MeasureValue | None = None
    year: int | None = None
    is_amount_normalized: bool | None = None
    normalization_value: MeasureValue | None = None
    normalization_parameter: str | None = None
    expense: MeasureValue | None = None
    revenue: MeasureValue | None = None
    co2_equivalent: MeasureValue | None = None
    time_dependent_amount: Any | None = None  # AbstractTimeSeries
    time_dependent_expense: Any | None = None  # AbstractTimeSeries
    time_dependent_revenue: Any | None = None  # AbstractTimeSeries
    amount_based_on: Any | None = None  # AbstractSchedule


@dataclass
class Energy(_AbstractResource):
    """``nrg3:Energy`` -- energy resource (consumption or production).

    XSD: EnergyType → AbstractResourceType → AbstractFeatureWithLifeSpanType.
    """

    ELEMENT_TAG: ClassVar = (NS_NRG3, "Energy")
    FEATURE_TYPE: ClassVar = "nrg3_Energy"
    ELEMENT_ORDER: ClassVar = (
        *_RESOURCE_BASE_ORDER,
        (NS_NRG3, "type"),
        (NS_NRG3, "endUse"),
        (NS_NRG3, "energyCarrier"),
        (NS_NRG3, "maximumLoad"),
        (NS_NRG3, "maximumLoadTime"),
        (NS_NRG3, "maximumLoadDay"),
        (NS_NRG3, "maximumLoadMonth"),
        (NS_NRG3, "source"),
    )
    FIELD_MAP: ClassVar = {
        **_RESOURCE_BASE_FIELD_MAP,
        "energy_type": (NS_NRG3, "type"),
        "end_use": (NS_NRG3, "endUse"),
        "energy_carrier": (NS_NRG3, "energyCarrier"),
        "maximum_load": (NS_NRG3, "maximumLoad"),
        "maximum_load_time": (NS_NRG3, "maximumLoadTime"),
        "maximum_load_day": (NS_NRG3, "maximumLoadDay"),
        "maximum_load_month": (NS_NRG3, "maximumLoadMonth"),
        "energy_source": (NS_NRG3, "source"),
    }

    energy_type: CodeValue | None = None
    end_use: CodeValue | None = None
    energy_carrier: CodeValue | None = None
    maximum_load: MeasureValue | None = None
    maximum_load_time: str | None = None
    maximum_load_day: int | None = None
    maximum_load_month: int | None = None
    energy_source: CodeValue | None = None


# ===================================================================
# Time Series (XSD: AbstractTimeSeriesType → AbstractFeatureWithLifeSpanType)
# ===================================================================

_TIME_SERIES_BASE_ORDER: tuple[tuple[str, str], ...] = (
    *_ADE_FEATURE_BASE_ORDER,
    (NS_NRG3, "interpolationType"),
)

_TIME_SERIES_BASE_FIELD_MAP: dict[str, tuple[str, str]] = {
    **_ADE_FEATURE_BASE_FIELD_MAP,
    "interpolation_type": (NS_NRG3, "interpolationType"),
}


@dataclass
class _AbstractTimeSeries(_AbstractADEFeature):
    """XSD: AbstractTimeSeriesType → AbstractFeatureWithLifeSpanType.

    Shared base for MonthlyTimeSeries, RegularTimeSeries,
    IrregularTimeSeries, and all TypicalValues* variants.
    """

    PARENT_FIELD: ClassVar = "time_dependent_amount"

    interpolation_type: str | None = None


@dataclass
class MonthlyTimeSeries(_AbstractTimeSeries):
    """``nrg3:MonthlyTimeSeries`` -- monthly time series with inline values.

    XSD: MonthlyTimeSeriesType → AbstractTimeSeriesType.
    """

    ELEMENT_TAG: ClassVar = (NS_NRG3, "MonthlyTimeSeries")
    FEATURE_TYPE: ClassVar = "nrg3_MonthlyTimeSeries"
    ELEMENT_ORDER: ClassVar = (
        *_TIME_SERIES_BASE_ORDER,
        (NS_NRG3, "startDate"),
        (NS_NRG3, "endDate"),
        (NS_NRG3, "valuesList"),
    )
    FIELD_MAP: ClassVar = {
        **_TIME_SERIES_BASE_FIELD_MAP,
        "start_date": (NS_NRG3, "startDate"),
        "end_date": (NS_NRG3, "endDate"),
        "values_list": (NS_NRG3, "valuesList"),
    }

    start_date: str | None = None
    end_date: str | None = None
    values_list: MeasureValue | None = None


# ===================================================================
# Building Unit
# ===================================================================


@dataclass
class BuildingUnit(_AbstractBuildingSpace):
    """``nrg3:BuildingUnit``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "BuildingUnit")
    FEATURE_TYPE: ClassVar = "nrg3_BuildingUnit"
    PARENT_FIELD: ClassVar = "building_units"
    ELEMENT_ORDER: ClassVar = (
        *_BUILDING_SPACE_ORDER,
        # BuildingUnit-specific
        (NS_NRG3, "type"),
        (NS_NRG3, "floorNumberFrom"),
        (NS_NRG3, "floorNumberTo"),
        (NS_NRG3, "numberOfRooms"),
        (NS_NRG3, "ownerName"),
        (NS_NRG3, "ownershipType"),
        (NS_NRG3, "address"),
        (NS_NRG3, "energyPerformanceCertificate"),
    )
    FIELD_MAP: ClassVar = {
        **_BUILDING_SPACE_FIELD_MAP,
        "bu_type": (NS_NRG3, "type"),
        "floor_number_from": (NS_NRG3, "floorNumberFrom"),
        "floor_number_to": (NS_NRG3, "floorNumberTo"),
        "number_of_rooms": (NS_NRG3, "numberOfRooms"),
        "owner_name": (NS_NRG3, "ownerName"),
        "ownership_type": (NS_NRG3, "ownershipType"),
        "addresses": (NS_NRG3, "address"),
        "energy_performance_certificates": (NS_NRG3, "energyPerformanceCertificate"),
    }

    # BuildingUnit-specific fields only (inherited fields come from _AbstractBuildingSpace)
    bu_type: CodeValue | None = None
    floor_number_from: float | None = None
    floor_number_to: float | None = None
    number_of_rooms: int | None = None
    owner_name: str | None = None
    ownership_type: CodeValue | None = None
    addresses: list[Any] = field(default_factory=list)
    energy_performance_certificates: list[EnergyPerformanceCertificate] = field(
        default_factory=list
    )
