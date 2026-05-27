"""Namespace URIs, prefix mappings, QName helpers, and codespace URL constants.

The XML namespace prefix map (:data:`NSMAP`) is built at import time by
combining namespaces discovered from the xsdata :mod:`bindings` module with
wire-only URIs (``xsi``, schematron, ``pbase``, ``tex``) listed in
``schemas/namespace_prefixes.json``.

Adding a new ADE (``ScenarioADE``, updated ``EnergyADE`` version, …):

1. Drop its XSD tree on disk and regenerate bindings
   (``python tools/generate_bindings.py``).
2. If bindings introduce a new namespace URI, add a line under ``prefixes``
   in ``schemas/namespace_prefixes.json``. The module emits a warning at
   import time listing any URI it could not resolve to a prefix, so drift
   is visible, never silent.

Prefixes are a human convention and cannot be recovered from XSD alone;
the JSON file is therefore the single source of truth for them.
"""

from __future__ import annotations

import dataclasses
import json
import warnings
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from functools import lru_cache
from pathlib import Path

from . import bindings

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PREFIX_CONFIG = _REPO_ROOT / "schemas" / "namespace_prefixes.json"


# ---------------------------------------------------------------------------
# Prefix config
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class PrefixConfig:
    """Prefix / wire-namespace / codespace metadata loaded from the JSON config.

    A single frozen record keeps the three concerns visibly distinct at the
    call site: callers access ``cfg.prefixes`` etc. instead of unpacking a
    positional tuple whose shape has to be remembered.
    """

    prefixes: Mapping[str, str]
    extra_uris: tuple[str, ...]
    codespace_bases: Mapping[str, str]


@lru_cache(maxsize=1)
def _load_prefix_config() -> PrefixConfig:
    """Return the parsed prefix config, cached for the process lifetime."""
    data = json.loads(_PREFIX_CONFIG.read_text(encoding="utf-8"))
    return PrefixConfig(
        prefixes=dict(data["prefixes"]),
        extra_uris=tuple(data.get("extra_uris", [])),
        codespace_bases=dict(data.get("codespace_bases", {})),
    )


# ---------------------------------------------------------------------------
# Binding introspection: single source of truth for "what's in the bindings"
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class BindingClassInfo:
    """Structured view over an xsdata-generated dataclass' ``Meta``.

    Both the NSMAP builder (which wants URIs) and the class registry
    (which wants ``prefix:ElementName`` keys) consume this, so the
    ~thousand-strong ``dir(bindings)`` walk happens exactly once per
    process.
    """

    cls: type
    namespace: str
    is_element: bool  # True iff Meta.namespace (wire-visible); False for target_namespace only
    xml_name: str


@lru_cache(maxsize=1)
def iter_binding_classes() -> tuple[BindingClassInfo, ...]:
    """Every xsdata dataclass in :mod:`bindings` that declares a namespace.

    Cached: the bindings module is immutable once imported.

    Used by this module (for :data:`NSMAP` discovery) and by
    :func:`citygml_energy.mapping._build_class_registry`. Any other
    consumer that needs to reflect over the bindings should route through
    here rather than rewalking ``dir(bindings)``.
    """
    out: list[BindingClassInfo] = []
    for name in dir(bindings):
        cls = getattr(bindings, name)
        if not (isinstance(cls, type) and dataclasses.is_dataclass(cls)):
            continue
        meta = getattr(cls, "Meta", None)
        if meta is None:
            continue
        element_ns = getattr(meta, "namespace", None)
        type_ns = getattr(meta, "target_namespace", None)
        namespace = element_ns or type_ns
        if namespace is None:
            continue
        xml_name = getattr(meta, "name", None) or name
        out.append(
            BindingClassInfo(
                cls=cls,
                namespace=namespace,
                is_element=element_ns is not None,
                xml_name=xml_name,
            )
        )
    return tuple(out)


def _iter_binding_namespaces() -> Iterator[str]:
    """Every distinct namespace URI referenced by the bindings."""
    seen: set[str] = set()
    for info in iter_binding_classes():
        if info.namespace not in seen:
            seen.add(info.namespace)
            yield info.namespace


def _discover_binding_namespaces() -> set[str]:
    """Materialised set of every binding-referenced namespace URI."""
    return set(_iter_binding_namespaces())


def _build_nsmap() -> OrderedDict[str, str]:
    """Compose the alphabetical prefix→URI map from bindings + config.

    Warns when the bindings reference a URI the config does not cover;
    those URIs are left out of the xmlns declaration set until a prefix
    is registered for them.
    """
    cfg = _load_prefix_config()
    uris = _discover_binding_namespaces() | set(cfg.extra_uris)

    unknown = uris - cfg.prefixes.keys()
    if unknown:
        warnings.warn(
            "Namespace URIs present in the bindings have no registered "
            "prefix in schemas/namespace_prefixes.json and will not appear "
            "in xmlns declarations. Add a prefix for each URI under "
            "'prefixes':\n  - " + "\n  - ".join(sorted(unknown)),
            stacklevel=2,
        )

    pairs = sorted(
        ((cfg.prefixes[uri], uri) for uri in uris if uri in cfg.prefixes),
        key=lambda pu: pu[0],
    )
    return OrderedDict(pairs)


# ---------------------------------------------------------------------------
# Public API: NSMAP + reverse lookup + QName helper
# ---------------------------------------------------------------------------

NSMAP: OrderedDict[str, str] = _build_nsmap()

# Reverse lookup: namespace URI → prefix. Used by :mod:`mapping` to build the
# ``"prefix:ElementName"`` registry from xsdata ``Meta.namespace`` values.
NS_PREFIX_MAP: dict[str, str] = {uri: prefix for prefix, uri in NSMAP.items()}


def qn(prefix: str, local: str) -> str:
    """Build Clark-notation tag ``{uri}local`` from a registered prefix."""
    return f"{{{NSMAP[prefix]}}}{local}"


# ---------------------------------------------------------------------------
# CRS defaults, written onto gml:Envelope, gml:MultiSurface, gml:Solid.
# ---------------------------------------------------------------------------
# Compound CRS: RD New (EPSG:28992) horizontal + NAP (EPSG:5109) vertical.
DEFAULT_SRS_NAME = "urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109"
DEFAULT_SRS_DIMENSION = 3


# ---------------------------------------------------------------------------
# Codespace URL constants
# ---------------------------------------------------------------------------
# These URLs appear as ``@codeSpace`` on ``gml:CodeType`` values. They are
# semantically distinct from the XML namespace URIs above (even when a
# codespace happens to share a host+path with a namespace URI, as the
# Energy-ADE 3.0 codespaces do).

# CityGML 2.0 building codelists (SIG3D). All four use ``https://`` for
# consistency: SIG3D serves the codelists at both schemes (``http`` 301-
# redirects to ``https``); pinning all of them to ``https://`` keeps a
# single normal form across the document so a consumer doing a plain
# string compare on the codeSpace URL doesn't have to special-case
# ``roofType`` against the other three.
CS_BUILDING_CLASS = (
    "https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_class.xml"
)
CS_BUILDING_FUNCTION = (
    "https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_function.xml"
)
CS_BUILDING_USAGE = (
    "https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_usage.xml"
)
CS_BUILDING_ROOFTYPE = (
    "https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_roofType.xml"
)

# BAG (Basisregistratie Adressen en Gebouwen) linked-data identifier URL
# bases. These are the ``rdf_seealso`` prefixes published by the Dutch
# Kadaster for Pand and Verblijfsobject resources respectively. Attached
# as ``@codeSpace`` on ``nrg3:identifier`` so any consumer can
# reconstruct the full dereferenceable BAG URL by concatenating the
# codespace + the identificatie value.
#
# The scheme is intentionally ``http://`` and must stay that way: only
# the http-scheme URLs actually dereference (HEAD on a Pand id returns
# 200 OK), while the https-scheme equivalents return 404 on the same
# host. Other codespaces in this file (sig3d.org, the 3DBAG docs) are
# documented under https; BAG is the asymmetric one.
CS_BAG_PAND = "http://bag.basisregistraties.overheid.nl/bag/id/pand/"
CS_BAG_VERBLIJFSOBJECT = "http://bag.basisregistraties.overheid.nl/bag/id/verblijfsobject/"

# BAG ``gebruiksdoel`` (VBO usage purpose) vocabulary. The 11 categories
# (woonfunctie, bijeenkomstfunctie, celfunctie, gezondheidszorgfunctie,
# industriefunctie, kantoorfunctie, logiesfunctie, onderwijsfunctie,
# sportfunctie, winkelfunctie, overige gebruiksfunctie) come from the
# Dutch Bouwbesluit 2012 and are intentionally kept verbatim rather
# than mapped to the EnergyADE 3.0 ``CurrentUseValue.xml`` /
# ``BuildingTypeValue.xml`` codelists, which lose the BAG distinctions
# (e.g. ``logiesfunctie`` collapses to ``residential``). The codespace
# is the official linked-data IRI for the Gebruiksdoel concept in the
# BAG vocabulary, which dereferences to the catalog page at
# ``catalogus.kadaster.nl/bag/nl/page/Gebruiksdoel`` and identifies the
# vocabulary as a whole.
CS_BAG_GEBRUIKSDOEL = "http://bag.basisregistraties.overheid.nl/id/concept/Gebruiksdoel"

# 3DBAG roof-type vocabulary. 3DBAG's ``b3_dak_type`` string values
# (``horizontal``, ``slanted``, ``multiple horizontal``) are NOT
# elements of SIG3D's numeric roof-type codelist; emitting them with
# the SIG3D codespace would mis-label the vocabulary. A 3DBAG-owned
# codespace documents the source enumeration correctly.
CS_3DBAG_DAK_TYPE = "https://docs.3dbag.nl/en/schema/attributes/#b3_dak_type"

# RVO NTA-8800 Gebouwtype vocabulary. The CSV column ``Gebouwtype`` in
# the EP-online Mutatiebestand carries Dutch RVO terms such as "Rijwoning
# hoek", "Vrijstaande woning", "Kantoorgebouw"; we surface them verbatim
# on ``nrg3:bdgType`` rather than translating into the Energy-ADE 3.0
# ``BuildingTypeValue.xml`` codelist (which is too coarse for the
# NTA-8800 typology and would silently merge "Hoekwoning" /
# "Tussenwoning" / "2-onder-1-kap" under one ``singleFamilyHouse``
# member).
#
# The codeSpace points at the canonical NTA-8800 generic upload XSD
# published by Dictu (the Dutch government IT service that operates
# EP-online for RVO) on GitHub. That XSD declares the closed
# ``TypeBuilding`` simpleType used by the EP-online element
# ``BuildingCategory`` (Dutch column name: ``Gebouwtype``) and
# enumerates the values RVO recognises (``Vrijstaande woning``,
# ``Rijwoning hoek``, ``Rijwoning tussen``, ``Appartement``,
# ``Twee-onder-één-kap``, ``Logieswoning``, …). It is dereferenceable,
# machine-readable, and authoritative in a way the previous landing-page
# URL (``rvo.nl/onderwerpen/...``) was not. The mutatiebestand v4
# totaalbestand exports the human-readable Dutch label rather than the
# integer code, but the vocabulary it draws from is exactly this file's
# enumeration.
#
# Caveat: the URL is pinned to the ``master`` branch of the Dictu repo,
# so a future v4.5 schema bump may extend the enumeration. The closed
# enumeration of basic terms (Vrijstaande woning etc.) is stable across
# v4.0–v4.4, so a value emitted today will remain valid; new values
# would be additive. If absolute URL stability becomes important the
# ``targetNamespace`` IRI ``http://schemas.ep-online.nl/monitoringbestand``
# is an acceptable alternative codeSpace per gml:CodeType semantics
# (anyURI, no dereference contract), but it is not a live document.
CS_RVO_GEBOUWTYPE = (
    "https://raw.githubusercontent.com/Dictu/EP-online-API/master/"
    "XSD/Energielabel/generieke%20xml%20v4.4/monitoringsbestand.xsd"
)

# Gemeente Emmen ``bor_groen_bomen_beschermd`` FeatureServer. Used as
# the ``codeSpace`` on ``veg:species`` for trees enriched from this
# register; pointing at the ArcGIS REST endpoint is more honest than a
# generic botanical authority (GBIF, ITIS) because the exact Latin
# names land here as Emmen's BOR has them, not as a taxonomy authority
# would canonicalise them. Other BOR fields (protection status, growth
# form, height/diameter classes, …) do not reach typed CityGML slots
# (see docs/mapping_city.md), so this codespace is currently
# only consumed by the species write.
CS_EMMEN_BOR_TREES = (
    "https://services3.arcgis.com/YaBq8GMTp0Kh437n/arcgis/rest/services/"
    "bor_groen_bomen_beschermd/FeatureServer/0"
)

# Vocabulary that classifies what kind of ``nrg3:UrbanFunctionArea`` we
# are emitting. EnergyADE 3.0 declares ``UrbanFunctionArea/type`` as an
# open ``gml:CodeType`` (no upstream codelist file): the schema delegates
# the typology to the publishing application. We pin the project's own
# vocabulary URL so the codeSpace identifies the closed set of values
# this pipeline emits (currently only ``"postalCode6"``); future area
# types (e.g. CBS buurt / wijk / vierkant) would be additive members of
# the same vocabulary. The URL points at the mapping-doc anchor that
# documents the values, mirroring the SIG3D / RVO pattern of attaching a
# codeSpace to a dereferenceable definition.
CS_NRG3_URBAN_FUNCTION_AREA_TYPE = (
    "https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator/"
    "blob/main/docs/mapping_city.md#urban-function-area-types"
)

# Dutch postcode register vocabulary. PostNL is the authoritative
# publisher of the 6-position postcode (PC6). The codeSpace dereferences
# to the catalog page describing the format; concatenation with the
# value reconstructs neither a record URL nor a Linked-Data IRI (PostNL
# does not expose one), but it cleanly identifies the vocabulary the
# value belongs to per ``gml:CodeType`` semantics (codeSpace = vocabulary
# identifier, not record locator). Used on
# ``nrg3:UrbanFunctionArea/code`` for postcode-keyed areas.
CS_NL_POSTCODE_PC6 = "https://www.postnl.nl/zakelijk/business-tools/postcodecheck/"

# CBS Postcode6 dataset on PDOK. Used as
# ``core:externalReference/informationSystem`` on each emitted
# ``nrg3:UrbanFunctionArea`` so a downstream reader can identify the
# authoritative source of the per-postcode dwelling statistics. Pinned
# to the dataset metadata page rather than the WFS endpoint because the
# metadata page describes the dataset semantics (variable definitions,
# vintage, suppression rules) even when the WFS URL eventually moves.
CBS_POSTCODE6_INFORMATION_SYSTEM_URL = (
    "https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search"
    "#/metadata/ed2f2381-873b-4d88-9c55-616e3a78d711"
)


def _nrg3_cs_base() -> str:
    """Codespace base URL for Energy-ADE 3.0 codelists.

    Sourced from ``codespace_bases.nrg3`` in the prefix config so that a
    vendor change (e.g. adopting an official OGC codespace for a future
    EnergyADE release) is a one-line config edit.
    """
    try:
        return _load_prefix_config().codespace_bases["nrg3"]
    except KeyError as err:
        raise RuntimeError(
            "schemas/namespace_prefixes.json is missing "
            "codespace_bases.nrg3, cannot build Energy-ADE codespace URLs"
        ) from err


_NRG3_CS = _nrg3_cs_base()

CS_NRG3_AREA_TYPE = f"{_NRG3_CS}/AreaTypeValue.xml"
CS_NRG3_BUILDING_TYPE = f"{_NRG3_CS}/BuildingTypeValue.xml"
CS_NRG3_CELL_TYPE = f"{_NRG3_CS}/CellTypeValue.xml"
CS_NRG3_CONSTRUCTION_WEIGHT = f"{_NRG3_CS}/ConstructionWeightValue.xml"
CS_NRG3_CURRENT_USE = f"{_NRG3_CS}/CurrentUseValue.xml"
CS_NRG3_DEVICE_OPERATION_TYPE = f"{_NRG3_CS}/DeviceOperationTypeValue.xml"
CS_NRG3_ENERGY_CARRIER = f"{_NRG3_CS}/EnergyCarrierValue.xml"
CS_NRG3_ENERGY_END_USE = f"{_NRG3_CS}/EnergyEndUseValue.xml"
CS_NRG3_ENERGY_SOURCE = f"{_NRG3_CS}/EnergySourceValue.xml"
CS_NRG3_ENERGY_TYPE = f"{_NRG3_CS}/EnergyTypeValue.xml"
CS_NRG3_EPC_STATUS = f"{_NRG3_CS}/EPCStatusValue.xml"
CS_NRG3_EPC_TYPE = f"{_NRG3_CS}/EPCTypeValue.xml"
CS_NRG3_EV_ACCESS = f"{_NRG3_CS}/EVChargingAccessTypeValue.xml"
CS_NRG3_EV_CONNECTOR_TYPE = f"{_NRG3_CS}/EVChargingConnectorTypeValue.xml"
CS_NRG3_EV_SPEED_LEVEL = f"{_NRG3_CS}/EVChargingSpeedLevelValue.xml"
CS_NRG3_EV_STATION_TYPE = f"{_NRG3_CS}/EVChargingStationTypeValue.xml"
CS_NRG3_HEAT_SOURCE = f"{_NRG3_CS}/HeatSourceValue.xml"
CS_NRG3_HEIGHT_TYPE = f"{_NRG3_CS}/HeightTypeValue.xml"
CS_NRG3_OCCUPANTS_TYPE = f"{_NRG3_CS}/OccupantsTypeValue.xml"
CS_NRG3_OWNERSHIP_TYPE = f"{_NRG3_CS}/OwnershipTypeValue.xml"
CS_NRG3_REFERENCE_PERIOD = f"{_NRG3_CS}/ReferencePeriodValue.xml"
CS_NRG3_OTHER_RELATION_TYPE = f"{_NRG3_CS}/OtherRelationTypeValue.xml"
# CityObjectRelation's relationType is a gml:CodeType drawn from one of
# three sub-codelists (Other / Temporal / Topological) under the abstract
# parent RelationTypeValue per the UML class diagram. OtherRelationTypeValue
# (above) carries installedOn / connectedTo / serving in beta 8;
# TopologicalRelationTypeValue carries adjacentTo / sharedWith; Temporal is
# empty in beta 8. Pre-pin the topological URL so the relation registry can
# host topological kinds without a follow-up namespaces.py edit.
CS_NRG3_TOPOLOGICAL_RELATION_TYPE = f"{_NRG3_CS}/TopologicalRelationTypeValue.xml"
CS_NRG3_TEMPORAL_RELATION_TYPE = f"{_NRG3_CS}/TemporalRelationTypeValue.xml"
CS_NRG3_RESOURCE_OPERATION_TYPE = f"{_NRG3_CS}/ResourceOperationTypeValue.xml"
CS_NRG3_SCHEDULE_TYPE = f"{_NRG3_CS}/ScheduleTypeValue.xml"
CS_NRG3_VOLUME_TYPE = f"{_NRG3_CS}/VolumeTypeValue.xml"
