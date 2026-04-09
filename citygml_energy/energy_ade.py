"""Energy ADE 3.0 feature classes: devices, schedules, occupants, and more.

This module covers all 25 target classes from the Excel specification that
belong to the Energy ADE namespace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from lxml import etree

from .base import BaseBuilder
from .namespaces import NS_CORE, NS_GML, NS_NRG3, NS_XLINK
from .types import CodeValue, MeasureValue, ScaleValue

# ===================================================================
# CityObjectRelation
# ===================================================================


@dataclass
class CityObjectRelation(BaseBuilder):
    """``nrg3:CityObjectRelation`` -- relation between city objects.

    The inner ``nrg3:relatedTo`` child carries an ``xlink:href`` pointing
    to the related object rather than nesting a full element, so we
    override ``to_xml`` for this special case.
    """

    ELEMENT_TAG: ClassVar = (NS_NRG3, "CityObjectRelation")
    ELEMENT_ORDER: ClassVar = (
        (NS_NRG3, "relationType"),
        (NS_NRG3, "relatedTo"),
    )
    FIELD_MAP: ClassVar = {
        "relation_type": (NS_NRG3, "relationType"),
    }

    relation_type: Optional[CodeValue] = None
    related_to_href: Optional[str] = None

    def to_xml(self, parent: Optional[etree._Element] = None) -> etree._Element:
        elem = super().to_xml(parent)
        if self.related_to_href is not None:
            inner = etree.SubElement(elem, f"{{{NS_NRG3}}}relatedTo")
            inner.set(f"{{{NS_XLINK}}}href", self.related_to_href)
        return elem


# ===================================================================
# Data types / qualified attributes
# ===================================================================


@dataclass
class QualifiedVolume(BaseBuilder):
    """``nrg3:QualifiedVolume`` -- a volume with type qualifier."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "QualifiedVolume")
    ELEMENT_ORDER: ClassVar = (
        (NS_NRG3, "description"),
        (NS_NRG3, "source"),
        (NS_NRG3, "value"),
        (NS_NRG3, "type"),
    )
    FIELD_MAP: ClassVar = {
        "description": (NS_NRG3, "description"),
        "source": (NS_NRG3, "source"),
        "value": (NS_NRG3, "value"),
        "type": (NS_NRG3, "type"),
    }

    description: Optional[str] = None
    source: Optional[str] = None
    value: Optional[MeasureValue] = None
    type: Optional[CodeValue] = None


@dataclass
class QualifiedArea(BaseBuilder):
    """``nrg3:QualifiedArea`` -- an area with type qualifier."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "QualifiedArea")
    ELEMENT_ORDER: ClassVar = (
        (NS_NRG3, "description"),
        (NS_NRG3, "source"),
        (NS_NRG3, "value"),
        (NS_NRG3, "type"),
    )
    FIELD_MAP: ClassVar = {
        "description": (NS_NRG3, "description"),
        "source": (NS_NRG3, "source"),
        "value": (NS_NRG3, "value"),
        "type": (NS_NRG3, "type"),
    }

    description: Optional[str] = None
    source: Optional[str] = None
    value: Optional[MeasureValue] = None
    type: Optional[CodeValue] = None


@dataclass
class QualifiedHeight(BaseBuilder):
    """``nrg3:QualifiedHeight`` -- a height with type qualifier."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "QualifiedHeight")
    ELEMENT_ORDER: ClassVar = (
        (NS_NRG3, "description"),
        (NS_NRG3, "source"),
        (NS_NRG3, "value"),
        (NS_NRG3, "type"),
    )
    FIELD_MAP: ClassVar = {
        "description": (NS_NRG3, "description"),
        "source": (NS_NRG3, "source"),
        "value": (NS_NRG3, "value"),
        "type": (NS_NRG3, "type"),
    }

    description: Optional[str] = None
    source: Optional[str] = None
    value: Optional[MeasureValue] = None
    type: Optional[CodeValue] = None


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

    author: Optional[str] = None
    acquisition_method: Optional[str] = None
    owner: Optional[str] = None
    quality_description: Optional[str] = None
    source: Optional[str] = None


# ===================================================================
# Device Operation
# ===================================================================


@dataclass
class DeviceOperation(BaseBuilder):
    """``nrg3:DeviceOperation``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "DeviceOperation")
    ELEMENT_ORDER: ClassVar = (
        (NS_GML, "description"),
        (NS_GML, "name"),
        (NS_NRG3, "creationDate"),
        (NS_NRG3, "terminationDate"),
        (NS_NRG3, "externalReference"),  # AbstractADEFeatureType
        (NS_NRG3, "metadata"),  # AbstractADEFeatureType
        (NS_NRG3, "identifier"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "validFrom"),
        (NS_NRG3, "validTo"),
        (NS_NRG3, "status"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "relatedTo"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "type"),
        (NS_NRG3, "yearlyGlobalEfficiency"),
        (NS_NRG3, "schedule"),
    )
    FIELD_MAP: ClassVar = {
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
        "type": (NS_NRG3, "type"),
        "yearly_global_efficiency": (NS_NRG3, "yearlyGlobalEfficiency"),
        "schedule": (NS_NRG3, "schedule"),
    }

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    creation_date: Optional[str] = None
    termination_date: Optional[str] = None
    external_references: List[Any] = field(default_factory=list)
    metadata: Optional[Any] = None
    identifier: Optional[CodeValue] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: Optional[CodeValue] = None
    related_to: List[Any] = field(default_factory=list)
    type: Optional[CodeValue] = None
    yearly_global_efficiency: Optional[float] = None
    schedule: Optional[Any] = None  # AbstractSchedule or xlink ref


# ===================================================================
# Abstract Device (shared fields)
# ===================================================================

# Element order for CityObject extensions + AbstractDevice fields
_DEVICE_BASE_ORDER: Tuple[Tuple[str, str], ...] = (
    (NS_GML, "description"),
    (NS_GML, "name"),
    (NS_CORE, "creationDate"),
    (NS_CORE, "terminationDate"),
    # CityObject ADE extensions used by devices (XSD declaration order)
    (NS_NRG3, "identifier"),
    (NS_NRG3, "relatedTo"),
    (NS_NRG3, "validFrom"),
    (NS_NRG3, "validTo"),
    (
        NS_NRG3,
        "referencePoint",
    ),  # declared last in _GenericApplicationPropertyOfCityObject
    # AbstractDevice fields
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

_DEVICE_BASE_FIELD_MAP: Dict[str, Tuple[str, str]] = {
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    "creation_date": (NS_CORE, "creationDate"),
    "termination_date": (NS_CORE, "terminationDate"),
    "nrg3_identifier": (NS_NRG3, "identifier"),
    "nrg3_related_to": (NS_NRG3, "relatedTo"),
    "valid_from": (NS_NRG3, "validFrom"),
    "valid_to": (NS_NRG3, "validTo"),
    "reference_point": (NS_NRG3, "referencePoint"),
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
    """Base for all device types (not instantiated directly)."""

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    creation_date: Optional[str] = None
    termination_date: Optional[str] = None
    nrg3_identifier: Optional[CodeValue] = None
    reference_point: Optional[Any] = None
    nrg3_related_to: List[Any] = field(default_factory=list)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    model: Optional[str] = None
    year_of_installation: Optional[int] = None
    year_of_manufacture: Optional[int] = None
    number_of_devices: Optional[int] = None
    installed_power: Optional[MeasureValue] = None
    nominal_efficiency: Optional[MeasureValue] = None
    efficiency_indicator: Optional[str] = None
    heat_dissipation: Optional[MeasureValue] = None
    heat_dissipation_convective_fraction: Optional[ScaleValue] = None
    heat_dissipation_latent_fraction: Optional[ScaleValue] = None
    heat_dissipation_radiant_fraction: Optional[ScaleValue] = None
    device_operations: List[DeviceOperation] = field(default_factory=list)


# ===================================================================
# Solar collector base + PV
# ===================================================================

_SOLAR_EXTRA_ORDER: Tuple[Tuple[str, str], ...] = (
    (NS_NRG3, "moduleArea"),
    (NS_NRG3, "apertureArea"),
    (NS_NRG3, "azimuth"),
    (NS_NRG3, "inclination"),
    (NS_NRG3, "lod2MultiSurface"),
    (NS_NRG3, "lod3MultiSurface"),
)

_SOLAR_EXTRA_FIELD_MAP: Dict[str, Tuple[str, str]] = {
    "module_area": (NS_NRG3, "moduleArea"),
    "aperture_area": (NS_NRG3, "apertureArea"),
    "azimuth": (NS_NRG3, "azimuth"),
    "inclination": (NS_NRG3, "inclination"),
    "lod2_multi_surface": (NS_NRG3, "lod2MultiSurface"),
    "lod3_multi_surface": (NS_NRG3, "lod3MultiSurface"),
}


@dataclass
class PhotovoltaicCollector(_AbstractDevice):
    """``nrg3:PhotovoltaicCollector`` -- PV panel/array."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "PhotovoltaicCollector")
    ELEMENT_ORDER: ClassVar = (
        *_DEVICE_BASE_ORDER,
        *_SOLAR_EXTRA_ORDER,
        (NS_NRG3, "cellType"),
    )
    FIELD_MAP: ClassVar = {
        **_DEVICE_BASE_FIELD_MAP,
        **_SOLAR_EXTRA_FIELD_MAP,
        "cell_type": (NS_NRG3, "cellType"),
    }

    # Solar collector fields
    module_area: Optional[MeasureValue] = None
    aperture_area: Optional[MeasureValue] = None
    azimuth: Optional[MeasureValue] = None
    inclination: Optional[MeasureValue] = None
    lod2_multi_surface: Optional[Any] = None
    lod3_multi_surface: Optional[Any] = None
    # PV-specific
    cell_type: Optional[CodeValue] = None


# ===================================================================
# Heat Pump
# ===================================================================


@dataclass
class HeatPump(_AbstractDevice):
    """``nrg3:HeatPump``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "HeatPump")
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

    heat_source: Optional[CodeValue] = None
    cop_source_temperature: Optional[MeasureValue] = None
    cop_operation_temperature: Optional[MeasureValue] = None


# ===================================================================
# EV Charging Station
# ===================================================================


@dataclass
class EVChargingStation(_AbstractDevice):
    """``nrg3:EVChargingStation``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "EVChargingStation")
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

    ev_type: Optional[CodeValue] = None
    charging_speed_level: Optional[CodeValue] = None
    connector_type: Optional[CodeValue] = None
    has_load_management: Optional[bool] = None
    access: Optional[CodeValue] = None


# ===================================================================
# Schedules
# ===================================================================

# Shared schedule base order (AbstractScheduleType extends AbstractFeatureWithLifeSpanType)
_SCHEDULE_BASE_ORDER: Tuple[Tuple[str, str], ...] = (
    (NS_GML, "description"),
    (NS_GML, "name"),
    (NS_NRG3, "creationDate"),
    (NS_NRG3, "terminationDate"),
    (NS_NRG3, "externalReference"),  # AbstractADEFeatureType
    (NS_NRG3, "metadata"),  # AbstractADEFeatureType
    (NS_NRG3, "identifier"),  # AbstractFeatureWithLifeSpanType
    (NS_NRG3, "validFrom"),
    (NS_NRG3, "validTo"),
    (NS_NRG3, "status"),  # AbstractFeatureWithLifeSpanType
    (NS_NRG3, "relatedTo"),  # AbstractFeatureWithLifeSpanType
    (NS_NRG3, "type"),
    (NS_NRG3, "startTime"),
    (NS_NRG3, "startDay"),
    (NS_NRG3, "startMonth"),
    (NS_NRG3, "startYear"),
    (NS_NRG3, "temporalExtent"),
)

_SCHEDULE_BASE_FIELD_MAP: Dict[str, Tuple[str, str]] = {
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    "creation_date": (NS_NRG3, "creationDate"),
    "termination_date": (NS_NRG3, "terminationDate"),
    "external_references": (NS_NRG3, "externalReference"),
    "schedule_metadata": (NS_NRG3, "metadata"),
    "identifier": (NS_NRG3, "identifier"),
    "valid_from": (NS_NRG3, "validFrom"),
    "valid_to": (NS_NRG3, "validTo"),
    "status": (NS_NRG3, "status"),
    "related_to": (NS_NRG3, "relatedTo"),
    "schedule_type": (NS_NRG3, "type"),
    "start_time": (NS_NRG3, "startTime"),
    "start_day": (NS_NRG3, "startDay"),
    "start_month": (NS_NRG3, "startMonth"),
    "start_year": (NS_NRG3, "startYear"),
    "temporal_extent": (NS_NRG3, "temporalExtent"),
}


@dataclass
class _AbstractSchedule(BaseBuilder):
    """Shared fields for all schedule types."""

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    creation_date: Optional[str] = None
    termination_date: Optional[str] = None
    external_references: List[Any] = field(default_factory=list)
    schedule_metadata: Optional[Any] = None  # Metadata builder
    identifier: Optional[CodeValue] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: Optional[CodeValue] = None
    related_to: List[Any] = field(default_factory=list)
    schedule_type: Optional[CodeValue] = None
    start_time: Optional[str] = None
    start_day: Optional[int] = None
    start_month: Optional[int] = None
    start_year: Optional[int] = None
    temporal_extent: Optional[Any] = None


@dataclass
class ConstantValueSchedule(_AbstractSchedule):
    """``nrg3:ConstantValueSchedule``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "ConstantValueSchedule")
    ELEMENT_ORDER: ClassVar = (
        *_SCHEDULE_BASE_ORDER,
        (NS_NRG3, "value"),
    )
    FIELD_MAP: ClassVar = {
        **_SCHEDULE_BASE_FIELD_MAP,
        "value": (NS_NRG3, "value"),
    }

    value: Optional[MeasureValue] = None


@dataclass
class ScheduleComponent(BaseBuilder):
    """``nrg3:ScheduleComponent`` -- part of a CompositeSchedule."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "ScheduleComponent")
    ELEMENT_ORDER: ClassVar = (
        (NS_GML, "description"),
        (NS_GML, "name"),
        (NS_NRG3, "creationDate"),  # AbstractADEFeatureType
        (NS_NRG3, "terminationDate"),
        (NS_NRG3, "externalReference"),  # AbstractADEFeatureType (0..*)
        (NS_NRG3, "metadata"),  # AbstractADEFeatureType
        (NS_NRG3, "identifier"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "validFrom"),
        (NS_NRG3, "validTo"),
        (NS_NRG3, "status"),
        (NS_NRG3, "relatedTo"),  # (0..*)
        (NS_NRG3, "type"),
        (NS_NRG3, "repetitions"),
        (NS_NRG3, "additionalGap"),
        (NS_NRG3, "scheduleComponentMember"),
    )
    FIELD_MAP: ClassVar = {
        "gml_description": (NS_GML, "description"),
        "gml_name": (NS_GML, "name"),
        "creation_date": (NS_NRG3, "creationDate"),
        "termination_date": (NS_NRG3, "terminationDate"),
        "external_references": (NS_NRG3, "externalReference"),
        "component_metadata": (NS_NRG3, "metadata"),
        "identifier": (NS_NRG3, "identifier"),
        "valid_from": (NS_NRG3, "validFrom"),
        "valid_to": (NS_NRG3, "validTo"),
        "status": (NS_NRG3, "status"),
        "related_to": (NS_NRG3, "relatedTo"),
        "component_type": (NS_NRG3, "type"),
        "repetitions": (NS_NRG3, "repetitions"),
        "additional_gap": (NS_NRG3, "additionalGap"),
        "schedule_member": (NS_NRG3, "scheduleComponentMember"),
    }

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    creation_date: Optional[str] = None
    termination_date: Optional[str] = None
    external_references: List[Any] = field(default_factory=list)
    component_metadata: Optional[Any] = None
    identifier: Optional[CodeValue] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: Optional[CodeValue] = None
    related_to: List[Any] = field(default_factory=list)
    component_type: Optional[CodeValue] = None
    repetitions: Optional[int] = None
    additional_gap: Optional[Any] = None
    schedule_member: Optional[Any] = None  # AbstractSchedule


@dataclass
class CompositeSchedule(_AbstractSchedule):
    """``nrg3:CompositeSchedule``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "CompositeSchedule")
    ELEMENT_ORDER: ClassVar = (
        *_SCHEDULE_BASE_ORDER,
        (NS_NRG3, "scheduleComponent"),
    )
    FIELD_MAP: ClassVar = {
        **_SCHEDULE_BASE_FIELD_MAP,
        "schedule_components": (NS_NRG3, "scheduleComponent"),
    }

    schedule_components: List[ScheduleComponent] = field(default_factory=list)


# ===================================================================
# Occupants
# ===================================================================


@dataclass
class Occupants(BaseBuilder):
    """``nrg3:Occupants``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "Occupants")
    ELEMENT_ORDER: ClassVar = (
        (NS_GML, "description"),
        (NS_GML, "name"),
        (NS_NRG3, "creationDate"),
        (NS_NRG3, "terminationDate"),
        (NS_NRG3, "externalReference"),  # AbstractADEFeatureType
        (NS_NRG3, "metadata"),  # AbstractADEFeatureType
        (NS_NRG3, "identifier"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "validFrom"),
        (NS_NRG3, "validTo"),
        (NS_NRG3, "status"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "relatedTo"),  # AbstractFeatureWithLifeSpanType
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
        "gml_description": (NS_GML, "description"),
        "gml_name": (NS_GML, "name"),
        "creation_date": (NS_NRG3, "creationDate"),
        "termination_date": (NS_NRG3, "terminationDate"),
        "external_references": (NS_NRG3, "externalReference"),
        "occ_metadata": (NS_NRG3, "metadata"),
        "identifier": (NS_NRG3, "identifier"),
        "valid_from": (NS_NRG3, "validFrom"),
        "valid_to": (NS_NRG3, "validTo"),
        "status": (NS_NRG3, "status"),
        "related_to": (NS_NRG3, "relatedTo"),
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

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    creation_date: Optional[str] = None
    termination_date: Optional[str] = None
    external_references: List[Any] = field(default_factory=list)
    occ_metadata: Optional[Any] = None
    identifier: Optional[CodeValue] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: Optional[CodeValue] = None
    related_to: List[Any] = field(default_factory=list)
    occupant_type: Optional[CodeValue] = None
    number_of_occupants: Optional[int] = None
    average_diet_type: Optional[CodeValue] = None
    average_income_level: Optional[CodeValue] = None
    average_instruction_level: Optional[CodeValue] = None
    heat_dissipation: Optional[MeasureValue] = None
    heat_dissipation_convective_fraction: Optional[ScaleValue] = None
    heat_dissipation_latent_fraction: Optional[ScaleValue] = None
    heat_dissipation_radiant_fraction: Optional[ScaleValue] = None
    occupancy_schedule: Optional[Any] = None


# ===================================================================
# Energy Performance Certificate
# ===================================================================


@dataclass
class EnergyPerformanceCertificate(BaseBuilder):
    """``nrg3:EnergyPerformanceCertificate``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "EnergyPerformanceCertificate")
    ELEMENT_ORDER: ClassVar = (
        (NS_GML, "description"),
        (NS_GML, "name"),
        (NS_NRG3, "creationDate"),
        (NS_NRG3, "terminationDate"),
        (NS_NRG3, "externalReference"),  # AbstractADEFeatureType (0..*)
        (NS_NRG3, "metadata"),  # AbstractADEFeatureType
        (NS_NRG3, "identifier"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "validFrom"),
        (NS_NRG3, "validTo"),
        (NS_NRG3, "status"),  # AbstractFeatureWithLifeSpanType
        (NS_NRG3, "relatedTo"),  # AbstractFeatureWithLifeSpanType (0..*)
        (NS_NRG3, "type"),
        (NS_NRG3, "label"),
        (NS_NRG3, "value"),
        (NS_NRG3, "certificationMethod"),
    )
    FIELD_MAP: ClassVar = {
        "gml_description": (NS_GML, "description"),
        "gml_name": (NS_GML, "name"),
        "creation_date": (NS_NRG3, "creationDate"),
        "termination_date": (NS_NRG3, "terminationDate"),
        "external_references": (NS_NRG3, "externalReference"),
        "epc_metadata": (NS_NRG3, "metadata"),
        "identifier": (NS_NRG3, "identifier"),
        "valid_from": (NS_NRG3, "validFrom"),
        "valid_to": (NS_NRG3, "validTo"),
        "status": (NS_NRG3, "status"),
        "related_to": (NS_NRG3, "relatedTo"),
        "epc_type": (NS_NRG3, "type"),
        "label": (NS_NRG3, "label"),
        "value": (NS_NRG3, "value"),
        "certification_method": (NS_NRG3, "certificationMethod"),
    }

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    creation_date: Optional[str] = None
    termination_date: Optional[str] = None
    external_references: List[Any] = field(default_factory=list)
    epc_metadata: Optional[Any] = None
    identifier: Optional[CodeValue] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: Optional[CodeValue] = None
    related_to: List[Any] = field(default_factory=list)
    epc_type: Optional[CodeValue] = None
    label: Optional[str] = None
    value: Optional[MeasureValue] = None
    certification_method: Optional[str] = None


# ===================================================================
# Building Unit
# ===================================================================


@dataclass
class BuildingUnit(BaseBuilder):
    """``nrg3:BuildingUnit``."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "BuildingUnit")
    ELEMENT_ORDER: ClassVar = (
        (NS_GML, "description"),
        (NS_GML, "name"),
        (NS_CORE, "creationDate"),
        (NS_CORE, "terminationDate"),
        (NS_NRG3, "identifier"),
        (NS_NRG3, "metadata"),
        # AbstractBuildingSpace -> AbstractCityObjectSpace
        (NS_NRG3, "area"),
        (NS_NRG3, "volume"),
        # AbstractBuildingSpace
        (NS_NRG3, "occupiedBy"),
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
        "gml_description": (NS_GML, "description"),
        "gml_name": (NS_GML, "name"),
        "creation_date": (NS_CORE, "creationDate"),
        "termination_date": (NS_CORE, "terminationDate"),
        "identifier": (NS_NRG3, "identifier"),
        "nrg3_metadata": (NS_NRG3, "metadata"),
        "areas": (NS_NRG3, "area"),
        "volumes": (NS_NRG3, "volume"),
        "occupied_by": (NS_NRG3, "occupiedBy"),
        "bu_type": (NS_NRG3, "type"),
        "floor_number_from": (NS_NRG3, "floorNumberFrom"),
        "floor_number_to": (NS_NRG3, "floorNumberTo"),
        "number_of_rooms": (NS_NRG3, "numberOfRooms"),
        "owner_name": (NS_NRG3, "ownerName"),
        "ownership_type": (NS_NRG3, "ownershipType"),
        "addresses": (NS_NRG3, "address"),
        "energy_performance_certificates": (NS_NRG3, "energyPerformanceCertificate"),
    }

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    creation_date: Optional[str] = None
    termination_date: Optional[str] = None
    identifier: Optional[CodeValue] = None
    nrg3_metadata: Optional[Metadata] = None
    areas: List[QualifiedArea] = field(default_factory=list)
    volumes: List[QualifiedVolume] = field(default_factory=list)
    occupied_by: List[Occupants] = field(default_factory=list)
    bu_type: Optional[CodeValue] = None
    floor_number_from: Optional[float] = None
    floor_number_to: Optional[float] = None
    number_of_rooms: Optional[int] = None
    owner_name: Optional[str] = None
    ownership_type: Optional[CodeValue] = None
    addresses: List[Any] = field(default_factory=list)
    energy_performance_certificates: List[EnergyPerformanceCertificate] = field(
        default_factory=list
    )
