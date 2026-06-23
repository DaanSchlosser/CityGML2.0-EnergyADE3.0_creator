"""XSD-qualified element names referenced directly by the Python source.

Regenerating bindings from updated XSD files is the primary mechanism for
schema change: xsdata re-derives every dataclass, and downstream modules
(:mod:`mapping`, :mod:`geometry`, :mod:`city_builder`) pick up the new
shapes through reflection. This module is the tiny remaining surface
where the source code has to *name* an element (geometry attachment,
city-scale builders, construction mapping). It only needs to be edited
when element names themselves change (new ADE version, different vendor,
different CityGML edition).

Each constant is an XSD-qualified name (``"prefix:LocalName"``) resolved
through :func:`citygml_energy.mapping.resolve_class` at call time, so no
xsdata class is imported at module scope and nothing here is bound to a
specific bindings revision.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CityGML 2.0: Core
# ---------------------------------------------------------------------------
ADDRESS = "core:Address"

# ---------------------------------------------------------------------------
# CityGML 2.0: Building
# ---------------------------------------------------------------------------
BUILDING = "bldg:Building"
GROUND_SURFACE = "bldg:GroundSurface"
WALL_SURFACE = "bldg:WallSurface"
ROOF_SURFACE = "bldg:RoofSurface"

# ---------------------------------------------------------------------------
# CityGML 2.0: Vegetation
# ---------------------------------------------------------------------------
SOLITARY_VEGETATION_OBJECT = "veg:SolitaryVegetationObject"
PLANT_COVER = "veg:PlantCover"

# ---------------------------------------------------------------------------
# CityGML 2.0: Semantic landcover (the 3D Basisvoorziening terrain surfaces)
# ---------------------------------------------------------------------------
# The terrain is carried as classified ground surfaces draped from the 3D
# Basisvoorziening, not a bare-earth relief: each BGT ground object maps onto
# its idiomatic CityGML 2.0 feature. ``veg:PlantCover`` is declared once in the
# vegetation section above and reused here for the 3DBV ``PlantCover`` objects.
LAND_USE = "luse:LandUse"
ROAD = "tran:Road"
WATER_BODY = "wtr:WaterBody"
BRIDGE = "brid:Bridge"
GENERIC_CITY_OBJECT = "gen:GenericCityObject"

# ---------------------------------------------------------------------------
# CityGML 2.0: Generics (used for attributes without a native schema field)
# ---------------------------------------------------------------------------
GEN_STRING_ATTRIBUTE = "gen:stringAttribute"
GEN_INT_ATTRIBUTE = "gen:intAttribute"
GEN_DOUBLE_ATTRIBUTE = "gen:doubleAttribute"
GEN_DATE_ATTRIBUTE = "gen:dateAttribute"
GEN_URI_ATTRIBUTE = "gen:uriAttribute"

# ---------------------------------------------------------------------------
# CityGML 2.0: Appearance
# ---------------------------------------------------------------------------
APPEARANCE = "app:Appearance"
X3D_MATERIAL = "app:X3DMaterial"

# ---------------------------------------------------------------------------
# GML 3.1.1: Point / MultiPoint
# ---------------------------------------------------------------------------
GML_POINT = "gml:Point"
GML_MULTI_POINT = "gml:MultiPoint"
GML_POINT_MEMBER = "gml:pointMember"

# ---------------------------------------------------------------------------
# xAL (address detail vocabulary embedded under core:Address)
# ---------------------------------------------------------------------------
XAL_ADDRESS_DETAILS = "xAL:AddressDetails"
XAL_LOCALITY = "xAL:Locality"
XAL_THOROUGHFARE = "xAL:Thoroughfare"
XAL_THOROUGHFARE_NUMBER = "xAL:ThoroughfareNumber"
XAL_POSTAL_CODE = "xAL:PostalCode"

# ---------------------------------------------------------------------------
# Energy ADE 3.0
# ---------------------------------------------------------------------------
PHOTOVOLTAIC_COLLECTOR = "nrg3:PhotovoltaicCollector"
ZONE_PART = "nrg3:ZonePart"
BUILDING_UNIT = "nrg3:BuildingUnit"
ENERGY_PERFORMANCE_CERTIFICATE = "nrg3:EnergyPerformanceCertificate"
LAYERED_CONSTRUCTION = "nrg3:layeredConstruction"
URBAN_FUNCTION_AREA = "nrg3:UrbanFunctionArea"

# ---------------------------------------------------------------------------
# CityGML surface-type map for semantic LoD 2+ attachment
# ---------------------------------------------------------------------------
# Maps the CityGML/CityJSON surface-type string to its XSD-qualified element
# name. The second member of each tuple is the Python field name on the
# ``bldg:boundedBy`` wrapper that carries this surface type. xsdata derives
# these from XSD element-ref names (e.g. ``<element ref="bldg:WallSurface"/>``
# becomes ``wall_surface``). If the wrapper field is ever renamed by xsdata,
# this constant is the single place to update.
CITYGML_SURFACE_TYPES: dict[str, tuple[str, str]] = {
    "GroundSurface": (GROUND_SURFACE, "ground_surface"),
    "WallSurface": (WALL_SURFACE, "wall_surface"),
    "RoofSurface": (ROOF_SURFACE, "roof_surface"),
}
