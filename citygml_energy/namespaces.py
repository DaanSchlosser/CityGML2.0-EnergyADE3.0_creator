"""Namespace URIs, prefix mappings, QName helpers, and codespace URL constants.

All namespace prefixes and URIs match exactly what appears in the reference
CityGML 2.0 + Energy ADE 3.0 files (Alderaan, RenoDAT).
"""

from collections import OrderedDict

# ---------------------------------------------------------------------------
# Namespace URIs
# ---------------------------------------------------------------------------
NS_APP = "http://www.opengis.net/citygml/appearance/2.0"
NS_BLDG = "http://www.opengis.net/citygml/building/2.0"
NS_BRID = "http://www.opengis.net/citygml/bridge/2.0"
NS_CORE = "http://www.opengis.net/citygml/2.0"
NS_DEM = "http://www.opengis.net/citygml/relief/2.0"
NS_FRN = "http://www.opengis.net/citygml/cityfurniture/2.0"
NS_GEN = "http://www.opengis.net/citygml/generics/2.0"
NS_GML = "http://www.opengis.net/gml"
NS_GRP = "http://www.opengis.net/citygml/cityobjectgroup/2.0"
NS_LUSE = "http://www.opengis.net/citygml/landuse/2.0"
NS_NRG3 = "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0"
NS_PBASE = "http://www.opengis.net/citygml/profiles/base/2.0"
NS_SCH = "http://www.ascc.net/xml/schematron"
NS_SMIL20 = "http://www.w3.org/2001/SMIL20/"
NS_SMIL20LANG = "http://www.w3.org/2001/SMIL20/Language"
NS_TEX = "http://www.opengis.net/citygml/texturedsurface/2.0"
NS_TRAN = "http://www.opengis.net/citygml/transportation/2.0"
NS_TUN = "http://www.opengis.net/citygml/tunnel/2.0"
NS_VEG = "http://www.opengis.net/citygml/vegetation/2.0"
NS_WTR = "http://www.opengis.net/citygml/waterbody/2.0"
NS_XAL = "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"
NS_XLINK = "http://www.w3.org/1999/xlink"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# ---------------------------------------------------------------------------
# Ordered namespace map -- xmlns declarations on the root element.
# Order matches the reference files exactly (alphabetical by prefix).
# ---------------------------------------------------------------------------
NSMAP: OrderedDict[str, str] = OrderedDict(
    [
        ("app", NS_APP),
        ("bldg", NS_BLDG),
        ("brid", NS_BRID),
        ("core", NS_CORE),
        ("dem", NS_DEM),
        ("frn", NS_FRN),
        ("gen", NS_GEN),
        ("gml", NS_GML),
        ("grp", NS_GRP),
        ("luse", NS_LUSE),
        ("nrg3", NS_NRG3),
        ("pbase", NS_PBASE),
        ("sch", NS_SCH),
        ("smil20", NS_SMIL20),
        ("smil20lang", NS_SMIL20LANG),
        ("tex", NS_TEX),
        ("tran", NS_TRAN),
        ("tun", NS_TUN),
        ("veg", NS_VEG),
        ("wtr", NS_WTR),
        ("xAL", NS_XAL),
        ("xlink", NS_XLINK),
        ("xsi", NS_XSI),
    ]
)


# Reverse lookup: namespace URI → prefix  (used by auto_from_dict)
NS_PREFIX_MAP: dict[str, str] = {uri: prefix for prefix, uri in NSMAP.items()}


def qn(prefix: str, local: str) -> str:
    """Build Clark-notation tag ``{uri}local`` from a namespace prefix."""
    uri = NSMAP[prefix]
    return f"{{{uri}}}{local}"


# ---------------------------------------------------------------------------
# Codespace URL constants
# ---------------------------------------------------------------------------
# CityGML 2.0 building codelists
CS_BUILDING_CLASS = (
    "http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_class.xml"
)
CS_BUILDING_FUNCTION = (
    "http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_function.xml"
)
CS_BUILDING_USAGE = (
    "http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_usage.xml"
)
CS_BUILDING_ROOFTYPE = (
    "https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_roofType.xml"
)

# Energy ADE 3.0 codespace base
_NRG3_CS = "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0"

CS_NRG3_OWNERSHIP_TYPE = f"{_NRG3_CS}/OwnershipTypeValue.xml"
CS_NRG3_BUILDING_TYPE = f"{_NRG3_CS}/BuildingTypeValue.xml"
CS_NRG3_VOLUME_TYPE = f"{_NRG3_CS}/VolumeTypeValue.xml"
CS_NRG3_AREA_TYPE = f"{_NRG3_CS}/AreaTypeValue.xml"
CS_NRG3_HEIGHT_TYPE = f"{_NRG3_CS}/HeightTypeValue.xml"
CS_NRG3_CURRENT_USE = f"{_NRG3_CS}/CurrentUseValue.xml"
CS_NRG3_CELL_TYPE = f"{_NRG3_CS}/CellTypeValue.xml"
CS_NRG3_DEVICE_OPERATION_TYPE = f"{_NRG3_CS}/DeviceOperationTypeValue.xml"
CS_NRG3_HEAT_SOURCE = f"{_NRG3_CS}/HeatSourceValue.xml"
CS_NRG3_EV_TYPE = f"{_NRG3_CS}/EVChargingStationTypeValue.xml"
CS_NRG3_CONSTRUCTION_WEIGHT = f"{_NRG3_CS}/ConstructionWeightValue.xml"
CS_NRG3_OCCUPANT_TYPE = f"{_NRG3_CS}/OccupantTypeValue.xml"
CS_NRG3_EPC_TYPE = f"{_NRG3_CS}/EPCTypeValue.xml"
CS_NRG3_BU_TYPE = f"{_NRG3_CS}/BuildingUnitTypeValue.xml"
CS_NRG3_SCHEDULE_TYPE = f"{_NRG3_CS}/ScheduleTypeValue.xml"
CS_NRG3_RELATION_TYPE = f"{_NRG3_CS}/RelationTypeValue.xml"
