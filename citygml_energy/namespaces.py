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

# CityGML 2.0 building codelists (SIG3D).
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
CS_NRG3_RELATION_TYPE = f"{_NRG3_CS}/RelationTypeValue.xml"
CS_NRG3_RESOURCE_OPERATION_TYPE = f"{_NRG3_CS}/ResourceOperationTypeValue.xml"
CS_NRG3_SCHEDULE_TYPE = f"{_NRG3_CS}/ScheduleTypeValue.xml"
CS_NRG3_VOLUME_TYPE = f"{_NRG3_CS}/VolumeTypeValue.xml"
