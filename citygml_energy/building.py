"""CityGML 2.0 Building module classes with Energy ADE 3.0 extensions.

Covers: Building, BuildingPart, BuildingInstallation,
IntBuildingInstallation, Room, all thematic surfaces, and openings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .base import BaseBuilder
from .namespaces import NS_BLDG, NS_CORE, NS_GML, NS_NRG3
from .types import CodeValue, MeasureValue, ScaleValue

# ===================================================================
# Thematic surfaces
# ===================================================================

_BOUNDARY_SURFACE_ORDER: tuple[tuple[str, str], ...] = (
    (NS_GML, "description"),
    (NS_GML, "name"),
    (NS_CORE, "creationDate"),
    (NS_CORE, "terminationDate"),
    # Energy ADE CityObject extensions on boundary surfaces
    (NS_NRG3, "identifier"),
    (NS_NRG3, "layeredConstruction"),  # CityObject ADE slot: before metadata
    (NS_NRG3, "metadata"),
    # bldg:AbstractBoundarySurfaceType
    (NS_BLDG, "lod2MultiSurface"),
    (NS_BLDG, "lod3MultiSurface"),
    (NS_BLDG, "lod4MultiSurface"),
    (NS_BLDG, "opening"),
    # Energy ADE boundary surface extensions
    (NS_NRG3, "bdgBdrySurfAdditionalThermalBridgeUValue"),
    (NS_NRG3, "bdgBdrySurfIsShared"),
    (NS_NRG3, "bdgBdrySurfThickness"),
    (NS_NRG3, "bdgBdrySurfTotalSurfaceArea"),
    (NS_NRG3, "bdgBdrySurfOpaqueSurfaceArea"),
    (NS_NRG3, "bdgBdrySurfHeatCapacity"),
    (NS_NRG3, "bdgBdrySurfAzimuth"),
    (NS_NRG3, "bdgBdrySurfInclination"),
    (NS_NRG3, "bdgBdrySurfGroundViewFactor"),
    (NS_NRG3, "bdgBdrySurfSkyViewFactor"),
)

_BOUNDARY_SURFACE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    "creation_date": (NS_CORE, "creationDate"),
    "termination_date": (NS_CORE, "terminationDate"),
    "nrg3_identifier": (NS_NRG3, "identifier"),
    "nrg3_metadata": (NS_NRG3, "metadata"),
    "lod2_multi_surface": (NS_BLDG, "lod2MultiSurface"),
    "lod3_multi_surface": (NS_BLDG, "lod3MultiSurface"),
    "lod4_multi_surface": (NS_BLDG, "lod4MultiSurface"),
    "openings": (NS_BLDG, "opening"),
    "bdg_bdry_surf_additional_thermal_bridge_u_value": (
        NS_NRG3,
        "bdgBdrySurfAdditionalThermalBridgeUValue",
    ),
    "bdg_bdry_surf_is_shared": (NS_NRG3, "bdgBdrySurfIsShared"),
    "bdg_bdry_surf_thickness": (NS_NRG3, "bdgBdrySurfThickness"),
    "bdg_bdry_surf_total_surface_area": (NS_NRG3, "bdgBdrySurfTotalSurfaceArea"),
    "bdg_bdry_surf_opaque_surface_area": (NS_NRG3, "bdgBdrySurfOpaqueSurfaceArea"),
    "bdg_bdry_surf_heat_capacity": (NS_NRG3, "bdgBdrySurfHeatCapacity"),
    "bdg_bdry_surf_azimuth": (NS_NRG3, "bdgBdrySurfAzimuth"),
    "bdg_bdry_surf_inclination": (NS_NRG3, "bdgBdrySurfInclination"),
    "bdg_bdry_surf_ground_view_factor": (NS_NRG3, "bdgBdrySurfGroundViewFactor"),
    "bdg_bdry_surf_sky_view_factor": (NS_NRG3, "bdgBdrySurfSkyViewFactor"),
    "layered_construction": (NS_NRG3, "layeredConstruction"),
}


@dataclass
class _BoundarySurface(BaseBuilder):
    """Base for all thematic boundary surfaces."""

    ELEMENT_ORDER: ClassVar = _BOUNDARY_SURFACE_ORDER
    FIELD_MAP: ClassVar = _BOUNDARY_SURFACE_FIELD_MAP

    gml_description: str | None = None
    gml_name: str | None = None
    creation_date: str | None = None
    termination_date: str | None = None
    nrg3_identifier: CodeValue | None = None
    nrg3_metadata: Any | None = None  # Metadata builder
    lod2_multi_surface: Any | None = None  # raw lxml or builder
    lod3_multi_surface: Any | None = None
    lod4_multi_surface: Any | None = None
    openings: list[Any] = field(default_factory=list)
    bdg_bdry_surf_additional_thermal_bridge_u_value: MeasureValue | None = None
    bdg_bdry_surf_is_shared: bool | None = None
    bdg_bdry_surf_thickness: MeasureValue | None = None
    bdg_bdry_surf_total_surface_area: MeasureValue | None = None
    bdg_bdry_surf_opaque_surface_area: MeasureValue | None = None
    bdg_bdry_surf_heat_capacity: MeasureValue | None = None
    bdg_bdry_surf_azimuth: MeasureValue | None = None
    bdg_bdry_surf_inclination: MeasureValue | None = None
    bdg_bdry_surf_ground_view_factor: ScaleValue | None = None
    bdg_bdry_surf_sky_view_factor: ScaleValue | None = None
    layered_construction: Any | None = None


@dataclass
class WallSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "WallSurface")
    FEATURE_TYPE: ClassVar = "bldg_WallSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


@dataclass
class RoofSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "RoofSurface")
    FEATURE_TYPE: ClassVar = "bldg_RoofSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


@dataclass
class GroundSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "GroundSurface")
    FEATURE_TYPE: ClassVar = "bldg_GroundSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


@dataclass
class CeilingSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "CeilingSurface")
    FEATURE_TYPE: ClassVar = "bldg_CeilingSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


@dataclass
class ClosureSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "ClosureSurface")
    FEATURE_TYPE: ClassVar = "bldg_ClosureSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


@dataclass
class FloorSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "FloorSurface")
    FEATURE_TYPE: ClassVar = "bldg_FloorSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


@dataclass
class OuterCeilingSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "OuterCeilingSurface")
    FEATURE_TYPE: ClassVar = "bldg_OuterCeilingSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


@dataclass
class OuterFloorSurface(_BoundarySurface):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "OuterFloorSurface")
    FEATURE_TYPE: ClassVar = "bldg_OuterFloorSurface"
    PARENT_FIELD: ClassVar = "bounded_by_surfaces"


# ===================================================================
# Openings
# ===================================================================

_OPENING_ORDER: tuple[tuple[str, str], ...] = (
    (NS_GML, "description"),
    (NS_GML, "name"),
    (NS_CORE, "creationDate"),
    (NS_CORE, "terminationDate"),
    (NS_NRG3, "identifier"),
    (NS_NRG3, "layeredConstruction"),  # CityObject ADE slot: before metadata
    (NS_NRG3, "metadata"),
    (NS_BLDG, "lod3MultiSurface"),
    (NS_BLDG, "lod4MultiSurface"),
    # Energy ADE opening extensions
    (NS_NRG3, "bdgOpnArea"),
    (NS_NRG3, "bdgOpnInclination"),
    (NS_NRG3, "bdgOpnAzimuth"),
    (NS_NRG3, "bdgOpnGroundViewFactor"),
    (NS_NRG3, "bdgOpnSkyViewFactor"),
)

_OPENING_FIELD_MAP: dict[str, tuple[str, str]] = {
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    "creation_date": (NS_CORE, "creationDate"),
    "termination_date": (NS_CORE, "terminationDate"),
    "nrg3_identifier": (NS_NRG3, "identifier"),
    "nrg3_metadata": (NS_NRG3, "metadata"),
    "lod3_multi_surface": (NS_BLDG, "lod3MultiSurface"),
    "lod4_multi_surface": (NS_BLDG, "lod4MultiSurface"),
    "bdg_opn_area": (NS_NRG3, "bdgOpnArea"),
    "bdg_opn_inclination": (NS_NRG3, "bdgOpnInclination"),
    "bdg_opn_azimuth": (NS_NRG3, "bdgOpnAzimuth"),
    "bdg_opn_ground_view_factor": (NS_NRG3, "bdgOpnGroundViewFactor"),
    "bdg_opn_sky_view_factor": (NS_NRG3, "bdgOpnSkyViewFactor"),
    "layered_construction": (NS_NRG3, "layeredConstruction"),
}


@dataclass
class _Opening(BaseBuilder):
    """Base for Door and Window openings."""

    ELEMENT_ORDER: ClassVar = _OPENING_ORDER
    FIELD_MAP: ClassVar = _OPENING_FIELD_MAP

    gml_description: str | None = None
    gml_name: str | None = None
    creation_date: str | None = None
    termination_date: str | None = None
    nrg3_identifier: CodeValue | None = None
    nrg3_metadata: Any | None = None
    lod3_multi_surface: Any | None = None
    lod4_multi_surface: Any | None = None
    bdg_opn_area: MeasureValue | None = None
    bdg_opn_inclination: MeasureValue | None = None
    bdg_opn_azimuth: MeasureValue | None = None
    bdg_opn_ground_view_factor: ScaleValue | None = None
    bdg_opn_sky_view_factor: ScaleValue | None = None
    layered_construction: Any | None = None


@dataclass
class Door(_Opening):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "Door")
    FEATURE_TYPE: ClassVar = "bldg_Door"
    PARENT_FIELD: ClassVar = "openings"


@dataclass
class Window(_Opening):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "Window")
    FEATURE_TYPE: ClassVar = "bldg_Window"
    PARENT_FIELD: ClassVar = "openings"


# ===================================================================
# Room
# ===================================================================


@dataclass
class Room(BaseBuilder):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "Room")
    FEATURE_TYPE: ClassVar = "bldg_Room"
    PARENT_FIELD: ClassVar = "interior_rooms"
    ELEMENT_ORDER: ClassVar = (
        (NS_GML, "description"),
        (NS_GML, "name"),
        (NS_CORE, "creationDate"),
        (NS_CORE, "terminationDate"),
        (NS_NRG3, "identifier"),
        (NS_NRG3, "metadata"),
        (NS_BLDG, "class"),
        (NS_BLDG, "function"),
        (NS_BLDG, "usage"),
        (NS_BLDG, "lod4Solid"),
        (NS_BLDG, "lod4MultiSurface"),
        (NS_BLDG, "boundedBy"),
        (NS_BLDG, "interiorFurniture"),
        (NS_BLDG, "roomInstallation"),
    )
    FIELD_MAP: ClassVar = {
        "gml_description": (NS_GML, "description"),
        "gml_name": (NS_GML, "name"),
        "creation_date": (NS_CORE, "creationDate"),
        "termination_date": (NS_CORE, "terminationDate"),
        "nrg3_identifier": (NS_NRG3, "identifier"),
        "nrg3_metadata": (NS_NRG3, "metadata"),
        "bldg_class": (NS_BLDG, "class"),
        "bldg_function": (NS_BLDG, "function"),
        "bldg_usage": (NS_BLDG, "usage"),
        "lod4_solid": (NS_BLDG, "lod4Solid"),
        "lod4_multi_surface": (NS_BLDG, "lod4MultiSurface"),
        "bounded_by_surfaces": (NS_BLDG, "boundedBy"),
        "interior_furniture": (NS_BLDG, "interiorFurniture"),
        "room_installations": (NS_BLDG, "roomInstallation"),
    }

    gml_description: str | None = None
    gml_name: str | None = None
    creation_date: str | None = None
    termination_date: str | None = None
    nrg3_identifier: CodeValue | None = None
    nrg3_metadata: Any | None = None
    bldg_class: CodeValue | None = None
    bldg_function: CodeValue | None = None
    bldg_usage: CodeValue | None = None
    lod4_solid: Any | None = None
    lod4_multi_surface: Any | None = None
    bounded_by_surfaces: list[_BoundarySurface] = field(default_factory=list)
    interior_furniture: list[Any] = field(default_factory=list)
    room_installations: list[Any] = field(default_factory=list)


# ===================================================================
# BuildingInstallation / IntBuildingInstallation
# ===================================================================

_INSTALLATION_ORDER: tuple[tuple[str, str], ...] = (
    (NS_GML, "description"),
    (NS_GML, "name"),
    (NS_CORE, "creationDate"),
    (NS_CORE, "terminationDate"),
    (NS_NRG3, "identifier"),
    (NS_NRG3, "metadata"),
    (NS_BLDG, "class"),
    (NS_BLDG, "function"),
    (NS_BLDG, "usage"),
    (NS_BLDG, "lod2Geometry"),
    (NS_BLDG, "lod3Geometry"),
    (NS_BLDG, "lod4Geometry"),
    (NS_BLDG, "lod2ImplicitRepresentation"),
    (NS_BLDG, "lod3ImplicitRepresentation"),
    (NS_BLDG, "lod4ImplicitRepresentation"),
    (NS_BLDG, "boundedBy"),
)

_INSTALLATION_FIELD_MAP: dict[str, tuple[str, str]] = {
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    "creation_date": (NS_CORE, "creationDate"),
    "termination_date": (NS_CORE, "terminationDate"),
    "nrg3_identifier": (NS_NRG3, "identifier"),
    "nrg3_metadata": (NS_NRG3, "metadata"),
    "bldg_class": (NS_BLDG, "class"),
    "bldg_function": (NS_BLDG, "function"),
    "bldg_usage": (NS_BLDG, "usage"),
    "lod2_geometry": (NS_BLDG, "lod2Geometry"),
    "lod3_geometry": (NS_BLDG, "lod3Geometry"),
    "lod4_geometry": (NS_BLDG, "lod4Geometry"),
    "lod2_implicit_representation": (NS_BLDG, "lod2ImplicitRepresentation"),
    "lod3_implicit_representation": (NS_BLDG, "lod3ImplicitRepresentation"),
    "lod4_implicit_representation": (NS_BLDG, "lod4ImplicitRepresentation"),
    "bounded_by_surfaces": (NS_BLDG, "boundedBy"),
}


@dataclass
class BuildingInstallation(BaseBuilder):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "BuildingInstallation")
    FEATURE_TYPE: ClassVar = "bldg_BuildingInstallation"
    PARENT_FIELD: ClassVar = "outer_building_installations"
    ELEMENT_ORDER: ClassVar = _INSTALLATION_ORDER
    FIELD_MAP: ClassVar = _INSTALLATION_FIELD_MAP

    gml_description: str | None = None
    gml_name: str | None = None
    creation_date: str | None = None
    termination_date: str | None = None
    nrg3_identifier: CodeValue | None = None
    nrg3_metadata: Any | None = None
    bldg_class: CodeValue | None = None
    bldg_function: CodeValue | None = None
    bldg_usage: CodeValue | None = None
    lod2_geometry: Any | None = None
    lod3_geometry: Any | None = None
    lod4_geometry: Any | None = None
    lod2_implicit_representation: Any | None = None
    lod3_implicit_representation: Any | None = None
    lod4_implicit_representation: Any | None = None
    bounded_by_surfaces: list[_BoundarySurface] = field(default_factory=list)


@dataclass
class IntBuildingInstallation(BaseBuilder):
    ELEMENT_TAG: ClassVar = (NS_BLDG, "IntBuildingInstallation")
    FEATURE_TYPE: ClassVar = "bldg_IntBuildingInstallation"
    PARENT_FIELD: ClassVar = "interior_building_installations"
    ELEMENT_ORDER: ClassVar = (
        (NS_GML, "description"),
        (NS_GML, "name"),
        (NS_CORE, "creationDate"),
        (NS_CORE, "terminationDate"),
        (NS_NRG3, "identifier"),
        (NS_NRG3, "metadata"),
        (NS_BLDG, "class"),
        (NS_BLDG, "function"),
        (NS_BLDG, "usage"),
        (NS_BLDG, "lod4Geometry"),
        (NS_BLDG, "lod4ImplicitRepresentation"),
    )
    FIELD_MAP: ClassVar = {
        "gml_description": (NS_GML, "description"),
        "gml_name": (NS_GML, "name"),
        "creation_date": (NS_CORE, "creationDate"),
        "termination_date": (NS_CORE, "terminationDate"),
        "nrg3_identifier": (NS_NRG3, "identifier"),
        "nrg3_metadata": (NS_NRG3, "metadata"),
        "bldg_class": (NS_BLDG, "class"),
        "bldg_function": (NS_BLDG, "function"),
        "bldg_usage": (NS_BLDG, "usage"),
        "lod4_geometry": (NS_BLDG, "lod4Geometry"),
        "lod4_implicit_representation": (NS_BLDG, "lod4ImplicitRepresentation"),
    }

    gml_description: str | None = None
    gml_name: str | None = None
    creation_date: str | None = None
    termination_date: str | None = None
    nrg3_identifier: CodeValue | None = None
    nrg3_metadata: Any | None = None
    bldg_class: CodeValue | None = None
    bldg_function: CodeValue | None = None
    bldg_usage: CodeValue | None = None
    lod4_geometry: Any | None = None
    lod4_implicit_representation: Any | None = None


# ===================================================================
# Building / BuildingPart
# ===================================================================

# Full element order for bldg:Building, derived from the XSD type hierarchy:
#   gml:AbstractFeatureType
#   -> core:AbstractCityObjectType  (+ADE CityObject hooks)
#   -> bldg:AbstractBuildingType    (+ADE Building hooks)
#   -> bldg:BuildingType

_BUILDING_ELEMENT_ORDER: tuple[tuple[str, str], ...] = (
    # -- gml:AbstractFeatureType --
    (NS_GML, "description"),
    (NS_GML, "name"),
    # -- core:AbstractCityObjectType --
    (NS_CORE, "creationDate"),
    (NS_CORE, "terminationDate"),
    (NS_CORE, "externalReference"),
    # -- Energy ADE CityObject extensions --
    (NS_NRG3, "device"),
    (NS_NRG3, "identifier"),
    (NS_NRG3, "indicator"),
    (NS_NRG3, "intervention"),
    (NS_NRG3, "layeredConstruction"),
    (NS_NRG3, "metadata"),
    (NS_NRG3, "relatedTo"),
    (NS_NRG3, "resource"),
    (NS_NRG3, "sensorData"),
    (NS_NRG3, "status"),
    (NS_NRG3, "utilityNetworkConnection"),
    (NS_NRG3, "validFrom"),
    (NS_NRG3, "validTo"),
    (NS_NRG3, "referencePoint"),
    # -- bldg:AbstractBuildingType --
    (NS_BLDG, "class"),
    (NS_BLDG, "function"),
    (NS_BLDG, "usage"),
    (NS_BLDG, "yearOfConstruction"),
    (NS_BLDG, "yearOfDemolition"),
    (NS_BLDG, "roofType"),
    (NS_BLDG, "measuredHeight"),
    (NS_BLDG, "storeysAboveGround"),
    (NS_BLDG, "storeysBelowGround"),
    (NS_BLDG, "storeyHeightsAboveGround"),
    (NS_BLDG, "storeyHeightsBelowGround"),
    (NS_BLDG, "lod0FootPrint"),
    (NS_BLDG, "lod0RoofEdge"),
    (NS_BLDG, "lod1Solid"),
    (NS_BLDG, "lod1MultiSurface"),
    (NS_BLDG, "lod1TerrainIntersection"),
    (NS_BLDG, "lod2Solid"),
    (NS_BLDG, "lod2MultiSurface"),
    (NS_BLDG, "lod2MultiCurve"),
    (NS_BLDG, "lod2TerrainIntersection"),
    (NS_BLDG, "lod3Solid"),
    (NS_BLDG, "lod3MultiSurface"),
    (NS_BLDG, "lod3MultiCurve"),
    (NS_BLDG, "lod3TerrainIntersection"),
    (NS_BLDG, "lod4Solid"),
    (NS_BLDG, "lod4MultiSurface"),
    (NS_BLDG, "lod4MultiCurve"),
    (NS_BLDG, "lod4TerrainIntersection"),
    (NS_BLDG, "boundedBy"),
    (NS_BLDG, "outerBuildingInstallation"),
    (NS_BLDG, "interiorBuildingInstallation"),
    (NS_BLDG, "interiorRoom"),
    # -- Energy ADE AbstractBuildingType extensions (XSD declaration order) --
    (NS_NRG3, "bdgHeight"),
    (NS_NRG3, "bdgArea"),
    (NS_NRG3, "bdgVolume"),
    (NS_NRG3, "bdgOwnerName"),
    (NS_NRG3, "bdgOwnershipType"),
    (NS_NRG3, "bdgNumberOfBuildingUnits"),
    (NS_NRG3, "bdgAtticThermalStatus"),
    (NS_NRG3, "bdgBasementThermalStatus"),
    (NS_NRG3, "bdgConstructionWeight"),
    (NS_NRG3, "bdgIsProtected"),
    (NS_NRG3, "bdgType"),
    (NS_NRG3, "occupiedBy"),
    (NS_NRG3, "buildingUnit"),
    (NS_NRG3, "zone"),
    (NS_NRG3, "energyPerformanceCertificate"),
    # -- bldg:BuildingType extensions (extends AbstractBuildingType) --
    (NS_BLDG, "consistsOfBuildingPart"),
    (NS_BLDG, "address"),
)

_BUILDING_FIELD_MAP: dict[str, tuple[str, str]] = {
    # gml
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    # core
    "creation_date": (NS_CORE, "creationDate"),
    "termination_date": (NS_CORE, "terminationDate"),
    "external_references": (NS_CORE, "externalReference"),
    # Energy ADE CityObject extensions
    "devices": (NS_NRG3, "device"),
    "nrg3_identifier": (NS_NRG3, "identifier"),
    "nrg3_indicators": (NS_NRG3, "indicator"),
    "nrg3_interventions": (NS_NRG3, "intervention"),
    "nrg3_layered_construction": (NS_NRG3, "layeredConstruction"),
    "nrg3_metadata": (NS_NRG3, "metadata"),
    "nrg3_related_to": (NS_NRG3, "relatedTo"),
    "nrg3_resources": (NS_NRG3, "resource"),
    "nrg3_sensor_data": (NS_NRG3, "sensorData"),
    "nrg3_status": (NS_NRG3, "status"),
    "nrg3_utility_network_connections": (NS_NRG3, "utilityNetworkConnection"),
    "nrg3_valid_from": (NS_NRG3, "validFrom"),
    "nrg3_valid_to": (NS_NRG3, "validTo"),
    "nrg3_reference_point": (NS_NRG3, "referencePoint"),
    # bldg
    "bldg_class": (NS_BLDG, "class"),
    "bldg_function": (NS_BLDG, "function"),
    "bldg_usage": (NS_BLDG, "usage"),
    "year_of_construction": (NS_BLDG, "yearOfConstruction"),
    "year_of_demolition": (NS_BLDG, "yearOfDemolition"),
    "roof_type": (NS_BLDG, "roofType"),
    "measured_height": (NS_BLDG, "measuredHeight"),
    "storeys_above_ground": (NS_BLDG, "storeysAboveGround"),
    "storeys_below_ground": (NS_BLDG, "storeysBelowGround"),
    "storey_heights_above_ground": (NS_BLDG, "storeyHeightsAboveGround"),
    "storey_heights_below_ground": (NS_BLDG, "storeyHeightsBelowGround"),
    "lod0_foot_print": (NS_BLDG, "lod0FootPrint"),
    "lod0_roof_edge": (NS_BLDG, "lod0RoofEdge"),
    "lod1_solid": (NS_BLDG, "lod1Solid"),
    "lod1_multi_surface": (NS_BLDG, "lod1MultiSurface"),
    "lod1_terrain_intersection": (NS_BLDG, "lod1TerrainIntersection"),
    "lod2_solid": (NS_BLDG, "lod2Solid"),
    "lod2_multi_surface": (NS_BLDG, "lod2MultiSurface"),
    "lod2_multi_curve": (NS_BLDG, "lod2MultiCurve"),
    "lod2_terrain_intersection": (NS_BLDG, "lod2TerrainIntersection"),
    "lod3_solid": (NS_BLDG, "lod3Solid"),
    "lod3_multi_surface": (NS_BLDG, "lod3MultiSurface"),
    "lod3_multi_curve": (NS_BLDG, "lod3MultiCurve"),
    "lod3_terrain_intersection": (NS_BLDG, "lod3TerrainIntersection"),
    "lod4_solid": (NS_BLDG, "lod4Solid"),
    "lod4_multi_surface": (NS_BLDG, "lod4MultiSurface"),
    "lod4_multi_curve": (NS_BLDG, "lod4MultiCurve"),
    "lod4_terrain_intersection": (NS_BLDG, "lod4TerrainIntersection"),
    "bounded_by_surfaces": (NS_BLDG, "boundedBy"),
    "outer_building_installations": (NS_BLDG, "outerBuildingInstallation"),
    "interior_building_installations": (NS_BLDG, "interiorBuildingInstallation"),
    "interior_rooms": (NS_BLDG, "interiorRoom"),
    "building_parts": (NS_BLDG, "consistsOfBuildingPart"),
    "addresses": (NS_BLDG, "address"),
    # Energy ADE Building extensions (order matches reference files)
    "bdg_heights": (NS_NRG3, "bdgHeight"),
    "bdg_areas": (NS_NRG3, "bdgArea"),
    "bdg_attic_thermal_status": (NS_NRG3, "bdgAtticThermalStatus"),
    "bdg_basement_thermal_status": (NS_NRG3, "bdgBasementThermalStatus"),
    "bdg_construction_weight": (NS_NRG3, "bdgConstructionWeight"),
    "bdg_is_protected": (NS_NRG3, "bdgIsProtected"),
    "bdg_number_of_building_units": (NS_NRG3, "bdgNumberOfBuildingUnits"),
    "bdg_owner_name": (NS_NRG3, "bdgOwnerName"),
    "bdg_ownership_type": (NS_NRG3, "bdgOwnershipType"),
    "bdg_type": (NS_NRG3, "bdgType"),
    "bdg_volumes": (NS_NRG3, "bdgVolume"),
    "occupied_by": (NS_NRG3, "occupiedBy"),
    "building_units": (NS_NRG3, "buildingUnit"),
    "zones": (NS_NRG3, "zone"),
    "energy_performance_certificates": (NS_NRG3, "energyPerformanceCertificate"),
}


@dataclass
class Building(BaseBuilder):
    """CityGML 2.0 ``bldg:Building`` with Energy ADE 3.0 extensions."""

    ELEMENT_TAG: ClassVar = (NS_BLDG, "Building")
    FEATURE_TYPE: ClassVar = "bldg_Building"
    ELEMENT_ORDER: ClassVar = _BUILDING_ELEMENT_ORDER
    FIELD_MAP: ClassVar = _BUILDING_FIELD_MAP

    # -- gml --
    gml_description: str | None = None
    gml_name: str | None = None
    # -- core --
    creation_date: str | None = None
    termination_date: str | None = None
    external_references: list[Any] = field(default_factory=list)
    # -- Energy ADE CityObject extensions --
    devices: list[Any] = field(default_factory=list)
    nrg3_identifier: CodeValue | None = None
    nrg3_indicators: list[Any] = field(default_factory=list)
    nrg3_interventions: list[Any] = field(default_factory=list)
    nrg3_layered_construction: Any | None = None
    nrg3_metadata: Any | None = None
    nrg3_related_to: list[Any] = field(default_factory=list)
    nrg3_resources: list[Any] = field(default_factory=list)
    nrg3_sensor_data: list[Any] = field(default_factory=list)
    nrg3_status: CodeValue | None = None
    nrg3_utility_network_connections: list[Any] = field(default_factory=list)
    nrg3_valid_from: str | None = None
    nrg3_valid_to: str | None = None
    nrg3_reference_point: Any | None = None
    # -- bldg:AbstractBuildingType --
    bldg_class: CodeValue | None = None
    bldg_function: CodeValue | None = None
    bldg_usage: CodeValue | None = None
    year_of_construction: int | None = None
    year_of_demolition: int | None = None
    roof_type: CodeValue | None = None
    measured_height: MeasureValue | None = None
    storeys_above_ground: int | None = None
    storeys_below_ground: int | None = None
    storey_heights_above_ground: str | None = None
    storey_heights_below_ground: str | None = None
    # Geometry (raw lxml elements or builders)
    lod0_foot_print: Any | None = None
    lod0_roof_edge: Any | None = None
    lod1_solid: Any | None = None
    lod1_multi_surface: Any | None = None
    lod1_terrain_intersection: Any | None = None
    lod2_solid: Any | None = None
    lod2_multi_surface: Any | None = None
    lod2_multi_curve: Any | None = None
    lod2_terrain_intersection: Any | None = None
    lod3_solid: Any | None = None
    lod3_multi_surface: Any | None = None
    lod3_multi_curve: Any | None = None
    lod3_terrain_intersection: Any | None = None
    lod4_solid: Any | None = None
    lod4_multi_surface: Any | None = None
    lod4_multi_curve: Any | None = None
    lod4_terrain_intersection: Any | None = None
    # Sub-features
    bounded_by_surfaces: list[_BoundarySurface] = field(default_factory=list)
    outer_building_installations: list[BuildingInstallation] = field(default_factory=list)
    interior_building_installations: list[IntBuildingInstallation] = field(default_factory=list)
    interior_rooms: list[Room] = field(default_factory=list)
    building_parts: list[Any] = field(default_factory=list)  # BuildingPart
    addresses: list[Any] = field(default_factory=list)  # Address
    # -- Energy ADE Building extensions --
    bdg_heights: list[Any] = field(default_factory=list)
    bdg_areas: list[Any] = field(default_factory=list)
    bdg_volumes: list[Any] = field(default_factory=list)
    bdg_owner_name: str | None = None
    bdg_ownership_type: CodeValue | None = None
    bdg_number_of_building_units: int | None = None
    bdg_attic_thermal_status: str | None = None
    bdg_basement_thermal_status: str | None = None
    bdg_construction_weight: CodeValue | None = None
    bdg_is_protected: bool | None = None
    bdg_type: CodeValue | None = None
    occupied_by: list[Any] = field(default_factory=list)
    building_units: list[Any] = field(default_factory=list)
    zones: list[Any] = field(default_factory=list)
    energy_performance_certificates: list[Any] = field(default_factory=list)


@dataclass
class BuildingPart(Building):
    """``bldg:BuildingPart`` -- structurally identical to Building."""

    ELEMENT_TAG: ClassVar = (NS_BLDG, "BuildingPart")
    FEATURE_TYPE: ClassVar = "bldg_BuildingPart"
    PARENT_FIELD: ClassVar = "building_parts"


# ===================================================================
# Zone
# ===================================================================

_ZONE_ELEMENT_ORDER: tuple[tuple[str, str], ...] = (
    # -- gml:AbstractFeatureType --
    (NS_GML, "description"),
    (NS_GML, "name"),
    # -- core:AbstractCityObjectType --
    (NS_CORE, "creationDate"),
    (NS_CORE, "terminationDate"),
    (NS_CORE, "externalReference"),
    # -- Energy ADE CityObject extensions (substitutionGroup) --
    (NS_NRG3, "identifier"),
    (NS_NRG3, "metadata"),
    (NS_NRG3, "relatedTo"),
    (NS_NRG3, "status"),
    (NS_NRG3, "validFrom"),
    (NS_NRG3, "validTo"),
    (NS_NRG3, "referencePoint"),
    # -- nrg3:AbstractCityObjectSpaceType --
    (NS_NRG3, "area"),
    (NS_NRG3, "volume"),
    (NS_NRG3, "lod0MultiSurface"),
    (NS_NRG3, "lod1Solid"),
    (NS_NRG3, "lod2Solid"),
    (NS_NRG3, "lod3Solid"),
    # -- nrg3:AbstractBuildingSpaceType --
    (NS_NRG3, "occupiedBy"),
    # -- nrg3:AbstractZoneType --
    (NS_NRG3, "type"),
    (NS_NRG3, "isCooled"),
    (NS_NRG3, "isHeated"),
    (NS_NRG3, "isMechanicallyVentilated"),
    (NS_NRG3, "infiltrationRate"),
    (NS_NRG3, "heatCapacity"),
    (NS_NRG3, "internalHeatGains"),
    (NS_NRG3, "internalHeatGainsConvectiveFraction"),
    (NS_NRG3, "internalHeatGainsLatentFraction"),
    (NS_NRG3, "internalHeatGainsRadiantFraction"),
    (NS_NRG3, "numberOfBuildingUnits"),
    (NS_NRG3, "coincidesWithLod2Hull"),
    (NS_NRG3, "coincidesWithLod3Hull"),
    (NS_NRG3, "buildingUnit"),
    (NS_NRG3, "heatingSchedule"),
    (NS_NRG3, "coolingSchedule"),
    (NS_NRG3, "mechanicalVentilationSchedule"),
    (NS_NRG3, "zoneBoundary"),
    # -- nrg3:ZoneType --
    (NS_NRG3, "zonePart"),
)

_ZONE_FIELD_MAP: dict[str, tuple[str, str]] = {
    # gml
    "gml_description": (NS_GML, "description"),
    "gml_name": (NS_GML, "name"),
    # core
    "creation_date": (NS_CORE, "creationDate"),
    "termination_date": (NS_CORE, "terminationDate"),
    "external_references": (NS_CORE, "externalReference"),
    # Energy ADE CityObject extensions
    "nrg3_identifier": (NS_NRG3, "identifier"),
    "nrg3_metadata": (NS_NRG3, "metadata"),
    "nrg3_related_to": (NS_NRG3, "relatedTo"),
    "nrg3_status": (NS_NRG3, "status"),
    "nrg3_valid_from": (NS_NRG3, "validFrom"),
    "nrg3_valid_to": (NS_NRG3, "validTo"),
    "nrg3_reference_point": (NS_NRG3, "referencePoint"),
    # AbstractCityObjectSpaceType
    "areas": (NS_NRG3, "area"),
    "volumes": (NS_NRG3, "volume"),
    "lod0_multi_surface": (NS_NRG3, "lod0MultiSurface"),
    "lod1_solid": (NS_NRG3, "lod1Solid"),
    "lod2_solid": (NS_NRG3, "lod2Solid"),
    "lod3_solid": (NS_NRG3, "lod3Solid"),
    # AbstractBuildingSpaceType
    "occupied_by": (NS_NRG3, "occupiedBy"),
    # AbstractZoneType
    "zone_type": (NS_NRG3, "type"),
    "is_cooled": (NS_NRG3, "isCooled"),
    "is_heated": (NS_NRG3, "isHeated"),
    "is_mechanically_ventilated": (NS_NRG3, "isMechanicallyVentilated"),
    "infiltration_rate": (NS_NRG3, "infiltrationRate"),
    "heat_capacity": (NS_NRG3, "heatCapacity"),
    "internal_heat_gains": (NS_NRG3, "internalHeatGains"),
    "internal_heat_gains_convective_fraction": (
        NS_NRG3,
        "internalHeatGainsConvectiveFraction",
    ),
    "internal_heat_gains_latent_fraction": (NS_NRG3, "internalHeatGainsLatentFraction"),
    "internal_heat_gains_radiant_fraction": (NS_NRG3, "internalHeatGainsRadiantFraction"),
    "number_of_building_units": (NS_NRG3, "numberOfBuildingUnits"),
    "coincides_with_lod2_hull": (NS_NRG3, "coincidesWithLod2Hull"),
    "coincides_with_lod3_hull": (NS_NRG3, "coincidesWithLod3Hull"),
    "building_units": (NS_NRG3, "buildingUnit"),
    "heating_schedule": (NS_NRG3, "heatingSchedule"),
    "cooling_schedule": (NS_NRG3, "coolingSchedule"),
    "mechanical_ventilation_schedule": (NS_NRG3, "mechanicalVentilationSchedule"),
    "zone_boundaries": (NS_NRG3, "zoneBoundary"),
    # ZoneType
    "zone_parts": (NS_NRG3, "zonePart"),
}


@dataclass
class Zone(BaseBuilder):
    """``nrg3:Zone`` -- a thermal zone within a building."""

    ELEMENT_TAG: ClassVar = (NS_NRG3, "Zone")
    FEATURE_TYPE: ClassVar = "nrg3_Zone"
    PARENT_FIELD: ClassVar = "zones"
    ELEMENT_ORDER: ClassVar = _ZONE_ELEMENT_ORDER
    FIELD_MAP: ClassVar = _ZONE_FIELD_MAP

    # -- gml --
    gml_description: str | None = None
    gml_name: str | None = None
    # -- core --
    creation_date: str | None = None
    termination_date: str | None = None
    external_references: list[Any] = field(default_factory=list)
    # -- Energy ADE CityObject extensions --
    nrg3_identifier: CodeValue | None = None
    nrg3_metadata: Any | None = None
    nrg3_related_to: list[Any] = field(default_factory=list)
    nrg3_status: CodeValue | None = None
    nrg3_valid_from: str | None = None
    nrg3_valid_to: str | None = None
    nrg3_reference_point: Any | None = None
    # -- AbstractCityObjectSpaceType --
    areas: list[Any] = field(default_factory=list)
    volumes: list[Any] = field(default_factory=list)
    lod0_multi_surface: Any | None = None
    lod1_solid: Any | None = None
    lod2_solid: Any | None = None
    lod3_solid: Any | None = None
    # -- AbstractBuildingSpaceType --
    occupied_by: list[Any] = field(default_factory=list)
    # -- AbstractZoneType --
    zone_type: CodeValue | None = None
    is_cooled: bool | None = None
    is_heated: bool | None = None
    is_mechanically_ventilated: bool | None = None
    infiltration_rate: MeasureValue | None = None
    heat_capacity: MeasureValue | None = None
    internal_heat_gains: MeasureValue | None = None
    internal_heat_gains_convective_fraction: ScaleValue | None = None
    internal_heat_gains_latent_fraction: ScaleValue | None = None
    internal_heat_gains_radiant_fraction: ScaleValue | None = None
    number_of_building_units: int | None = None
    coincides_with_lod2_hull: bool | None = None
    coincides_with_lod3_hull: bool | None = None
    building_units: list[Any] = field(default_factory=list)
    heating_schedule: Any | None = None
    cooling_schedule: Any | None = None
    mechanical_ventilation_schedule: Any | None = None
    zone_boundaries: list[Any] = field(default_factory=list)
    # -- ZoneType --
    zone_parts: list[Any] = field(default_factory=list)


@dataclass
class ZonePart(Zone):
    """``nrg3:ZonePart`` -- a subdivision of a Zone.

    Structurally identical to Zone's AbstractZone fields but without
    the ``zonePart`` child element.
    """

    ELEMENT_TAG: ClassVar = (NS_NRG3, "ZonePart")
    FEATURE_TYPE: ClassVar = "nrg3_ZonePart"
    PARENT_FIELD: ClassVar = "zone_parts"
    # ZonePart extends AbstractZoneType directly (no zonePart children).
    ELEMENT_ORDER: ClassVar = _ZONE_ELEMENT_ORDER[:-1]
