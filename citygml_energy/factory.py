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

Extensibility
-------------
To add a new feature type, define a dataclass that inherits from
:class:`BaseBuilder` with ``FEATURE_TYPE`` and (optionally) ``PARENT_FIELD``::

    @dataclass
    class SolarThermalCollector(_AbstractSolarCollector):
        ELEMENT_TAG: ClassVar = (NS_NRG3, "SolarThermalCollector")
        FEATURE_TYPE: ClassVar = "nrg3_SolarThermalCollector"
        PARENT_FIELD: ClassVar = "devices"
        ELEMENT_ORDER: ClassVar = (*_SOLAR_COLLECTOR_ORDER, (NS_NRG3, "fluidType"))
        FIELD_MAP: ClassVar = {**_SOLAR_COLLECTOR_FIELD_MAP, "fluid_type": (NS_NRG3, "fluidType")}

        fluid_type: CodeValue | None = None

That's it — ``auto_from_dict`` + auto-registration handle the rest.
For classes that need custom construction logic (e.g. ``Building`` with
its ``QualifiedVolume`` lists), define a manual ``from_dict`` function and
register it in ``_CUSTOM_FROM_DICT``.

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

import dataclasses
import types as _types
from collections.abc import Callable
from typing import Any, ClassVar, get_type_hints

from .base import BaseBuilder

# These imports are needed even if not directly referenced in this file:
# importing the modules triggers __init_subclass__ which registers each
# builder class in BaseBuilder._all_subclasses for auto-registration.
from .building import (  # noqa: F401
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
from .building import Zone, ZonePart
from .core import Address, CityModel
from .energy_ade import (  # noqa: F401 — importing triggers __init_subclass__
    BuildingUnit,
    ConstantValueSchedule,
    Metadata,
    QualifiedArea,
    QualifiedHeight,
    QualifiedVolume,
)
from .namespaces import CS_NRG3_SCHEDULE_TYPE, NS_NRG3, NS_PREFIX_MAP
from .types import CodeValue, MeasureValue, ScaleValue

_METADATA_KEY = (NS_NRG3, "metadata")

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _str(v: Any) -> str | None:
    return str(v).strip() if v is not None and str(v).strip() != "" else None


def _int(v: Any) -> int | None:
    s = _str(v)
    return int(s) if s is not None else None


def _float(v: Any) -> float | None:
    s = _str(v)
    return float(s) if s is not None else None


def _bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def _code(attrs: dict[str, Any], key: str, cs_key: str | None = None) -> CodeValue | None:
    val = _str(attrs.get(key))
    if val is None:
        return None
    cs_lookup = cs_key or f"{key}_codeSpace"
    cs = _str(attrs.get(cs_lookup))
    return CodeValue(val, cs)


def _measure(attrs: dict[str, Any], key: str, uom_key: str | None = None) -> MeasureValue | None:
    val = _str(attrs.get(key))
    if val is None:
        return None
    uom_lookup = uom_key or f"{key}_uom"
    uom = _str(attrs.get(uom_lookup)) or ""
    return MeasureValue(val, uom)


def _scale(attrs: dict[str, Any], key: str) -> ScaleValue | None:
    val = _str(attrs.get(key))
    if val is None:
        return None
    return ScaleValue(val, "unit interval")


# ---------------------------------------------------------------------------
# auto_from_dict: generic flat-dict → builder via FIELD_MAP + type hints
# ---------------------------------------------------------------------------


def _flat_key(ns: str, local_name: str) -> str:
    """Convert ``(namespace_uri, local_name)`` to a flat attribute key.

    Example: ``(NS_NRG3, "cellType")`` → ``"nrg3_cellType"``
    """
    prefix = NS_PREFIX_MAP.get(ns, "")
    return f"{prefix}_{local_name}" if prefix else local_name


def _unwrap_optional(tp: Any) -> Any:
    """Unwrap ``T | None`` to ``T``."""
    if isinstance(tp, _types.UnionType):
        args = [a for a in tp.__args__ if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


# Per-class dispatch plan: list of (field_name, flat_key, converter_tag)
# tuples precomputed once so auto_from_dict avoids redundant type introspection.
# converter_tag is one of: "str", "int", "float", "bool", "code", "measure",
# "scale", "metadata", or None (skip).
_dispatch_cache: dict[type, list[tuple[str, str, str | None]]] = {}

_CONVERTER_TAGS: dict[type, str] = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    CodeValue: "code",
    MeasureValue: "measure",
    ScaleValue: "scale",
}


def _get_dispatch_plan(cls: type[BaseBuilder]) -> list[tuple[str, str, str | None]]:
    """Return the precomputed dispatch plan for *cls* (cached)."""
    plan = _dispatch_cache.get(cls)
    if plan is not None:
        return plan

    try:
        hints = get_type_hints(cls)
    except Exception:
        hints = {}

    overrides = cls.FLAT_KEY_OVERRIDES
    plan = []

    for field_name, (ns, local_name) in cls.FIELD_MAP.items():
        flat = overrides.get(field_name) or _flat_key(ns, local_name)

        # Metadata assembles from multiple nrg3_metadata_* sub-keys;
        # skip the normal single-key dispatch.
        if (ns, local_name) == _METADATA_KEY:
            plan.append((field_name, flat, "metadata"))
            continue

        hint = hints.get(field_name)
        if hint is None:
            continue

        real_type = _unwrap_optional(hint)

        # Skip complex types (lists, Any, nested builders)
        if real_type is Any:
            continue
        origin = getattr(real_type, "__origin__", None)
        if origin is list:
            continue
        if isinstance(real_type, type) and issubclass(real_type, BaseBuilder):
            continue

        tag = _CONVERTER_TAGS.get(real_type)
        if tag is not None:
            plan.append((field_name, flat, tag))

    _dispatch_cache[cls] = plan
    return plan


def auto_from_dict(cls: type[BaseBuilder], attrs: dict[str, Any]) -> BaseBuilder:
    """Auto-create a builder instance from flat attributes.

    Uses ``cls.FIELD_MAP`` and type annotations to determine how to
    convert each flat attribute key to a constructor kwarg.

    Handles: ``str``, ``int``, ``float``, ``bool``, ``CodeValue``,
    ``MeasureValue``, ``ScaleValue``, and ``Metadata`` fields.
    Skips: ``list`` fields, ``Any`` typed fields, and nested builders
    (those are populated by ``FeatureFactory._attach``).
    """
    kwargs: dict[str, Any] = {"gml_id": _str(attrs.get("gml_id"))}

    for field_name, flat, tag in _get_dispatch_plan(cls):
        if tag == "metadata":
            kwargs[field_name] = _make_metadata(attrs)
        elif tag == "str":
            kwargs[field_name] = _str(attrs.get(flat))
        elif tag == "int":
            kwargs[field_name] = _int(attrs.get(flat))
        elif tag == "float":
            kwargs[field_name] = _float(attrs.get(flat))
        elif tag == "bool":
            kwargs[field_name] = _bool(attrs.get(flat))
        elif tag == "code":
            kwargs[field_name] = _code(attrs, flat)
        elif tag == "measure":
            kwargs[field_name] = _measure(attrs, flat)
        elif tag == "scale":
            kwargs[field_name] = _scale(attrs, flat)

    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Metadata / Qualified helpers (used by custom from_dict functions)
# ---------------------------------------------------------------------------


def _make_metadata(attrs: dict[str, Any], prefix: str = "nrg3_metadata") -> Metadata | None:
    """Build a Metadata from flat attrs with a given prefix."""
    author = _str(attrs.get(f"{prefix}_author"))
    acquisition_method = _code(attrs, f"{prefix}_acquisitionMethod")
    owner = _str(attrs.get(f"{prefix}_owner"))
    quality_description = _str(attrs.get(f"{prefix}_qualityDescription"))
    source = _str(attrs.get(f"{prefix}_source"))
    if not any((author, acquisition_method, owner, quality_description, source)):
        return None
    return Metadata(
        author=author,
        acquisition_method=acquisition_method,
        owner=owner,
        quality_description=quality_description,
        source=source,
    )


def _make_qualified[Q: (QualifiedVolume, QualifiedArea, QualifiedHeight)](
    cls: type[Q], attrs: dict[str, Any], prefix: str
) -> Q | None:
    """Generic constructor for QualifiedVolume / QualifiedArea / QualifiedHeight."""
    if _str(attrs.get(f"{prefix}_value")) is None:
        return None
    return cls(
        description=_str(attrs.get(f"{prefix}_description")),
        source=_str(attrs.get(f"{prefix}_source")),
        value=_measure(attrs, f"{prefix}_value", f"{prefix}_uom"),
        type=_code(attrs, f"{prefix}_type", f"{prefix}_type_codeSpace"),
    )


def _make_qualified_list[Q: (QualifiedVolume, QualifiedArea, QualifiedHeight)](
    cls: type[Q], attrs: dict[str, Any], prefix: str
) -> list[Q]:
    """Build a list of QualifiedVolume / QualifiedArea / QualifiedHeight.

    Supports two flat-key conventions:

    1. **Un-indexed** (single value, backwards compatible)::

           nrg3_bdgVolume_value, nrg3_bdgVolume_uom, ...

    2. **Indexed** (multiple values)::

           nrg3_bdgVolume_0_value, nrg3_bdgVolume_0_uom, ...
           nrg3_bdgVolume_1_value, nrg3_bdgVolume_1_uom, ...

    Both forms can be mixed: the un-indexed entry becomes the first item,
    then indexed entries are appended in order.
    """
    result: list[Q] = []

    # Un-indexed (backwards compatible)
    item = _make_qualified(cls, attrs, prefix)
    if item is not None:
        result.append(item)

    # Indexed: scan for prefix_0_value, prefix_1_value, ...
    idx = 0
    while True:
        indexed_prefix = f"{prefix}_{idx}"
        item = _make_qualified(cls, attrs, indexed_prefix)
        if item is None:
            break
        result.append(item)
        idx += 1

    return result




# ---------------------------------------------------------------------------
# Custom from_dict functions (complex types that need manual logic)
# ---------------------------------------------------------------------------


def building_from_dict(attrs: dict[str, Any]) -> Building:
    """Create a :class:`Building` from a flat attribute dictionary.

    This is a custom constructor because Building has QualifiedVolume/Area/Height
    lists that require nested sub-object assembly from flat keys.
    """
    return Building(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        nrg3_status=_code(attrs, "nrg3_status"),
        nrg3_valid_from=_str(attrs.get("nrg3_validFrom")),
        nrg3_valid_to=_str(attrs.get("nrg3_validTo")),
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
        bdg_is_protected=_bool(attrs.get("nrg3_bdgIsProtected")),
        bdg_number_of_building_units=_int(attrs.get("nrg3_bdgNumberOfBuildingUnits")),
        bdg_owner_name=_str(attrs.get("nrg3_bdgOwnerName")),
        bdg_ownership_type=_code(attrs, "nrg3_bdgOwnershipType"),
        bdg_type=_code(attrs, "nrg3_bdgType"),
        bdg_attic_thermal_status=_str(attrs.get("nrg3_bdgAtticThermalStatus")),
        bdg_basement_thermal_status=_str(attrs.get("nrg3_bdgBasementThermalStatus")),
        bdg_construction_weight=_code(attrs, "nrg3_bdgConstructionWeight"),
        bdg_volumes=_make_qualified_list(QualifiedVolume, attrs, "nrg3_bdgVolume"),
        bdg_areas=_make_qualified_list(QualifiedArea, attrs, "nrg3_bdgArea"),
        bdg_heights=_make_qualified_list(QualifiedHeight, attrs, "nrg3_bdgHeight"),
    )


def _copy_as[T](cls: type[T], src: Any) -> T:
    """Copy all dataclass fields from *src* into a new instance of *cls*."""
    return cls(**{f.name: getattr(src, f.name) for f in dataclasses.fields(src)})


def building_part_from_dict(attrs: dict[str, Any]) -> BuildingPart:
    """Create a :class:`BuildingPart` -- reuses Building logic."""
    return _copy_as(BuildingPart, building_from_dict(attrs))


def building_unit_from_dict(attrs: dict[str, Any]) -> BuildingUnit:
    """Create a :class:`BuildingUnit` from flat attributes.

    Custom constructor because of QualifiedArea/Volume lists.
    """
    return BuildingUnit(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        areas=_make_qualified_list(QualifiedArea, attrs, "nrg3_area"),
        volumes=_make_qualified_list(QualifiedVolume, attrs, "nrg3_volume"),
        bu_type=_code(attrs, "nrg3_buType"),
        floor_number_from=_float(attrs.get("nrg3_floorNumberFrom")),
        floor_number_to=_float(attrs.get("nrg3_floorNumberTo")),
        number_of_rooms=_int(attrs.get("nrg3_numberOfRooms")),
        owner_name=_str(attrs.get("nrg3_ownerName")),
        ownership_type=_code(attrs, "nrg3_ownershipType"),
    )


def address_from_dict(attrs: dict[str, Any]) -> Address:
    """Create a :class:`Address` from flat attributes.

    Custom constructor because Address has no FIELD_MAP (xAL structure).
    """
    return Address(
        gml_id=_str(attrs.get("gml_id")),
        country=_str(attrs.get("xal_country")),
        locality=_str(attrs.get("xal_locality")),
        thoroughfare=_str(attrs.get("xal_thoroughfare")),
        thoroughfare_number=_str(attrs.get("xal_thoroughfareNumber")),
        postal_code=_str(attrs.get("xal_postalCode")),
    )


def zone_from_dict(attrs: dict[str, Any]) -> Zone:
    """Create a :class:`Zone` from flat attributes.

    Supports inline ``nrg3_heatingSetpoint`` / ``nrg3_coolingSetpoint``
    shorthand: the factory wraps each value in a
    :class:`ConstantValueSchedule` automatically.
    """
    gml_id = _str(attrs.get("gml_id")) or ""

    heating_sched = None
    if _str(attrs.get("nrg3_heatingSetpoint")) is not None:
        heating_sched = ConstantValueSchedule(
            gml_id=f"{gml_id}_heating_schedule" if gml_id else None,
            schedule_type=CodeValue("typicalYear", CS_NRG3_SCHEDULE_TYPE),
            value=_measure(attrs, "nrg3_heatingSetpoint"),
        )

    cooling_sched = None
    if _str(attrs.get("nrg3_coolingSetpoint")) is not None:
        cooling_sched = ConstantValueSchedule(
            gml_id=f"{gml_id}_cooling_schedule" if gml_id else None,
            schedule_type=CodeValue("typicalYear", CS_NRG3_SCHEDULE_TYPE),
            value=_measure(attrs, "nrg3_coolingSetpoint"),
        )

    return Zone(
        gml_id=_str(attrs.get("gml_id")),
        gml_description=_str(attrs.get("gml_description")),
        gml_name=_str(attrs.get("gml_name")),
        creation_date=_str(attrs.get("core_creationDate")),
        termination_date=_str(attrs.get("core_terminationDate")),
        nrg3_identifier=_code(attrs, "nrg3_identifier"),
        nrg3_metadata=_make_metadata(attrs),
        nrg3_status=_code(attrs, "nrg3_status"),
        nrg3_valid_from=_str(attrs.get("nrg3_validFrom")),
        nrg3_valid_to=_str(attrs.get("nrg3_validTo")),
        areas=_make_qualified_list(QualifiedArea, attrs, "nrg3_area"),
        volumes=_make_qualified_list(QualifiedVolume, attrs, "nrg3_volume"),
        zone_type=_code(attrs, "nrg3_zoneType"),
        is_cooled=_bool(attrs.get("nrg3_isCooled")),
        is_heated=_bool(attrs.get("nrg3_isHeated")),
        is_mechanically_ventilated=_bool(attrs.get("nrg3_isMechanicallyVentilated")),
        infiltration_rate=_measure(attrs, "nrg3_infiltrationRate"),
        coincides_with_lod2_hull=_bool(attrs.get("nrg3_coincidesWithLod2Hull")),
        coincides_with_lod3_hull=_bool(attrs.get("nrg3_coincidesWithLod3Hull")),
        heating_schedule=heating_sched,
        cooling_schedule=cooling_sched,
    )


def zone_part_from_dict(attrs: dict[str, Any]) -> ZonePart:
    """Create a :class:`ZonePart` -- reuses Zone logic."""
    return _copy_as(ZonePart, zone_from_dict(attrs))


# ---------------------------------------------------------------------------
# Dispatch registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable[[dict[str, Any]], Any]] = {}


def _is_stub(fn: Callable[[dict[str, Any]], Any]) -> bool:
    return bool(getattr(fn, "_is_stub", False))


def _reg(fme_name: str, fn: Callable[[dict[str, Any]], Any]) -> None:
    _REGISTRY[fme_name] = fn


# --- Custom from_dict overrides ---
# Classes with complex construction (QualifiedVolume lists, xAL address,
# core: vs nrg3: namespace differences, or Zone setpoint → schedule conversion)
# need manual from_dict. All others use auto_from_dict via FLAT_KEY_OVERRIDES.
_CUSTOM_FROM_DICT: dict[str, Callable[[dict[str, Any]], Any]] = {
    "bldg_Building": building_from_dict,
    "bldg_BuildingPart": building_part_from_dict,
    "nrg3_BuildingUnit": building_unit_from_dict,
    "core_Address": address_from_dict,
    "nrg3_Zone": zone_from_dict,
    "nrg3_ZonePart": zone_part_from_dict,
}


# --- Auto-register all builder subclasses that declare FEATURE_TYPE ---
def _auto_register_all() -> None:
    """Scan all BaseBuilder subclasses and register those with FEATURE_TYPE.

    Classes in ``_CUSTOM_FROM_DICT`` get their manual constructor;
    all others get ``auto_from_dict``.
    """
    for cls in BaseBuilder._all_subclasses:
        ft = getattr(cls, "FEATURE_TYPE", "")
        if not ft or ft in _REGISTRY:
            continue
        if ft in _CUSTOM_FROM_DICT:
            _reg(ft, _CUSTOM_FROM_DICT[ft])
        else:
            # Bind cls via default arg to avoid late-binding closure issue
            _reg(ft, lambda a, c=cls: auto_from_dict(c, a))


_auto_register_all()

# Register custom from_dict entries for classes that don't inherit BaseBuilder
# (e.g. Address) and therefore aren't picked up by _auto_register_all.
for _ft, _fn in _CUSTOM_FROM_DICT.items():
    if _ft not in _REGISTRY:
        _reg(_ft, _fn)


# ---------------------------------------------------------------------------
# Stub registry: feature types not yet implemented
# ---------------------------------------------------------------------------


def _stub(feature_type: str) -> Callable[[dict[str, Any]], None]:
    """Return a stub callable that raises NotImplementedError for *feature_type*."""

    def _fn(attrs: dict[str, Any]) -> None:
        raise NotImplementedError(
            f"'{feature_type}' is not yet implemented.\n"
            f"Steps to implement:\n"
            f"  1. Create a @dataclass builder class inheriting from BaseBuilder\n"
            f"  2. Set FEATURE_TYPE = {feature_type!r} and PARENT_FIELD if needed\n"
            f"  3. Define ELEMENT_TAG, ELEMENT_ORDER, FIELD_MAP, and fields\n"
            f"  That's it — auto_from_dict + auto-registration handle the rest."
        )

    _fn.__name__ = feature_type + "_stub"
    _fn._is_stub = True  # type: ignore[attr-defined]
    return _fn


# --- CityGML standard modules (not yet implemented) ---
_reg("frn_CityFurniture", _stub("frn_CityFurniture"))
_reg("gen_GenericCityObject", _stub("gen_GenericCityObject"))
_reg("grp_CityObjectGroup", _stub("grp_CityObjectGroup"))
_reg("luse_LandUse", _stub("luse_LandUse"))

# --- Energy ADE: resources / materials ---
_reg("nrg3_ConstructionMaterial", _stub("nrg3_ConstructionMaterial"))
_reg("nrg3_LayeredConstruction", _stub("nrg3_LayeredConstruction"))
_reg("nrg3_LayeredConstructionLibrary", _stub("nrg3_LayeredConstructionLibrary"))
_reg("nrg3_MaterialLibrary", _stub("nrg3_MaterialLibrary"))
_reg("nrg3_ReverseLayeredConstruction", _stub("nrg3_ReverseLayeredConstruction"))
_reg("nrg3_SolidMaterial", _stub("nrg3_SolidMaterial"))

# --- Energy ADE: energy carriers / commodities ---
_reg("nrg3_Liquid", _stub("nrg3_Liquid"))
_reg("nrg3_OtherResource", _stub("nrg3_OtherResource"))
_reg("nrg3_Waste", _stub("nrg3_Waste"))
_reg("nrg3_Water", _stub("nrg3_Water"))

# --- Energy ADE: devices ---
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

# --- Energy ADE: energy networks / distribution ---
_reg("nrg3_PowerDistribution", _stub("nrg3_PowerDistribution"))
_reg("nrg3_ThermalDistribution", _stub("nrg3_ThermalDistribution"))
_reg("nrg3_UtilityNetworkConnection", _stub("nrg3_UtilityNetworkConnection"))

# --- Energy ADE: schedules ---
_reg("nrg3_DualValueSchedule", _stub("nrg3_DualValueSchedule"))
_reg("nrg3_IrregularTimeSeries", _stub("nrg3_IrregularTimeSeries"))
_reg("nrg3_IrregularTimeSeriesFile", _stub("nrg3_IrregularTimeSeriesFile"))
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
_reg("nrg3_TypicalValuesMonthlyTimeSeries", _stub("nrg3_TypicalValuesMonthlyTimeSeries"))
_reg(
    "nrg3_TypicalValuesMonthlyTimeSeriesFile",
    _stub("nrg3_TypicalValuesMonthlyTimeSeriesFile"),
)
_reg("nrg3_TypicalValuesRegularTimeSeries", _stub("nrg3_TypicalValuesRegularTimeSeries"))
_reg(
    "nrg3_TypicalValuesRegularTimeSeriesFile",
    _stub("nrg3_TypicalValuesRegularTimeSeriesFile"),
)

# --- Energy ADE: sensors ---
_reg("nrg3_SensorConnection", _stub("nrg3_SensorConnection"))
_reg("nrg3_SensorData", _stub("nrg3_SensorData"))
_reg("nrg3_WeatherData", _stub("nrg3_WeatherData"))
_reg("nrg3_WeatherStation", _stub("nrg3_WeatherStation"))

# --- Energy ADE: urban / zone objects ---
_reg("nrg3_Intervention", _stub("nrg3_Intervention"))
_reg("nrg3_UrbanFunctionArea", _stub("nrg3_UrbanFunctionArea"))
_reg("nrg3_UrbanSpace", _stub("nrg3_UrbanSpace"))
# nrg3_Zone: auto-registered via Zone.FEATURE_TYPE + _CUSTOM_FROM_DICT
# nrg3_ZonePart: auto-registered via ZonePart.FEATURE_TYPE + _CUSTOM_FROM_DICT

# --- Energy ADE: zone surfaces ---
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


def create_feature(feature_type: str, attrs: dict[str, Any]) -> Any:
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
        raise ValueError(f"Unknown feature type {feature_type!r}. Registered types: {registered}")
    return fn(attrs)


def list_feature_types(*, include_unimplemented: bool = False) -> list[str]:
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

    Parent-child relationships are resolved automatically using the
    ``PARENT_FIELD`` class variable on each builder class.  When a child
    feature has ``gml_parent_id``, the factory appends the child to
    ``getattr(parent, child_cls.PARENT_FIELD)``.

    Usage::

        factory = FeatureFactory(description="My city", name="City 1")
        factory.add("bldg_Building", {"gml_id": "bldg_1", ...})
        factory.add("nrg3_PhotovoltaicCollector", {
            "gml_id": "pv_1",
            "gml_parent_id": "bldg_1",
            ...
        })
        city_model = factory.build()
    """

    def __init__(
        self,
        description: str | None = None,
        name: str | None = None,
    ) -> None:
        self._description = description
        self._name = name
        self._rows: list[tuple[str, str | None, Any]] = []

    def add(self, feature_type: str, attrs: dict[str, Any]) -> FeatureFactory:
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
        id_index: dict[str, Any] = {}
        for ftype, _parent_id, obj in self._rows:
            if obj.gml_id:
                id_index[obj.gml_id] = (ftype, obj)

        # Attach children to parents
        for ftype, parent_id, obj in self._rows:
            if parent_id is None:
                continue
            parent_entry = id_index.get(parent_id)
            if parent_entry is None:
                raise ValueError(
                    f"gml_parent_id {parent_id!r} not found (referenced by {obj.gml_id!r})"
                )
            parent_ftype, parent_obj = parent_entry
            self._attach(ftype, obj, parent_ftype, parent_obj)

        # Collect top-level features
        model = CityModel(
            gml_description=self._description,
            gml_name=self._name,
        )
        for _ftype, parent_id, obj in self._rows:
            if parent_id is None:
                model.add(obj)

        return model

    # ------------------------------------------------------------------
    @staticmethod
    def _attach(child_type: str, child: Any, parent_type: str, parent: Any) -> None:
        """Attach a child feature to its parent using PARENT_FIELD."""
        parent_field = getattr(type(child), "PARENT_FIELD", "")
        if not parent_field:
            raise ValueError(
                f"Don't know how to attach {child_type!r} to {parent_type!r}: "
                f"no PARENT_FIELD defined on {type(child).__name__}"
            )
        if not hasattr(parent, parent_field):
            raise ValueError(
                f"Parent {parent_type!r} ({type(parent).__name__}) has no "
                f"field {parent_field!r} for attaching {child_type!r}"
            )
        target = getattr(parent, parent_field)
        if isinstance(target, list):
            target.append(child)
        else:
            if target is not None:
                raise ValueError(
                    f"Parent {parent_type!r} field {parent_field!r} already set "
                    f"(by {getattr(target, 'gml_id', '?')!r}); cannot attach "
                    f"{child_type!r} ({child.gml_id!r})"
                )
            setattr(parent, parent_field, child)
