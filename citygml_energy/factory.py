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
    class SolarThermalCollector(_AbstractDevice):
        ELEMENT_TAG: ClassVar = (NS_NRG3, "SolarThermalCollector")
        FEATURE_TYPE: ClassVar = "nrg3_SolarThermalCollector"
        PARENT_FIELD: ClassVar = "devices"
        ELEMENT_ORDER: ClassVar = (*_DEVICE_BASE_ORDER, (NS_NRG3, "fluidType"))
        FIELD_MAP: ClassVar = {**_DEVICE_BASE_FIELD_MAP, "fluid_type": (NS_NRG3, "fluidType")}

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
from .core import Address, CityModel
from .energy_ade import (
    BuildingUnit,
    CompositeSchedule,
    ConstantValueSchedule,
    Energy,
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
from .namespaces import NS_NRG3, NS_PREFIX_MAP
from .types import CodeValue, MeasureValue, ScaleValue

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

# Cache resolved type hints per class (avoids repeated evaluation)
_hints_cache: dict[type, dict[str, Any]] = {}


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


def _get_hints(cls: type) -> dict[str, Any]:
    """Return resolved type hints for *cls* (cached)."""
    if cls not in _hints_cache:
        try:
            _hints_cache[cls] = get_type_hints(cls)
        except Exception:
            _hints_cache[cls] = {}
    return _hints_cache[cls]


def auto_from_dict(cls: type[BaseBuilder], attrs: dict[str, Any]) -> BaseBuilder:
    """Auto-create a builder instance from flat attributes.

    Uses ``cls.FIELD_MAP`` and type annotations to determine how to
    convert each flat attribute key to a constructor kwarg.

    Handles: ``str``, ``int``, ``float``, ``bool``, ``CodeValue``,
    ``MeasureValue``, ``ScaleValue``, and ``Metadata`` fields.
    Skips: ``list`` fields, ``Any`` typed fields, and nested builders
    (those are populated by ``FeatureFactory._attach``).
    """
    hints = _get_hints(cls)
    kwargs: dict[str, Any] = {"gml_id": _str(attrs.get("gml_id"))}

    for field_name, (ns, local_name) in cls.FIELD_MAP.items():
        flat = _flat_key(ns, local_name)

        # Special case: metadata fields → delegate to _make_metadata
        if (ns, local_name) == (NS_NRG3, "metadata"):
            kwargs[field_name] = _make_metadata(attrs)
            continue

        # Resolve type hint
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

        # Dispatch by type
        if real_type is str:
            kwargs[field_name] = _str(attrs.get(flat))
        elif real_type is int:
            kwargs[field_name] = _int(attrs.get(flat))
        elif real_type is float:
            kwargs[field_name] = _float(attrs.get(flat))
        elif real_type is bool:
            kwargs[field_name] = _bool(attrs.get(flat))
        elif real_type is CodeValue:
            kwargs[field_name] = _code(attrs, flat)
        elif real_type is MeasureValue:
            kwargs[field_name] = _measure(attrs, flat)
        elif real_type is ScaleValue:
            kwargs[field_name] = _scale(attrs, flat)

    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Metadata / Qualified helpers (used by custom from_dict functions)
# ---------------------------------------------------------------------------


def _make_metadata(attrs: dict[str, Any], prefix: str = "nrg3_metadata") -> Metadata | None:
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


def _make_qualified_volume(attrs: dict[str, Any], prefix: str = "nrg3_bdgVolume") -> QualifiedVolume | None:
    return _make_qualified(QualifiedVolume, attrs, prefix)


def _make_qualified_area(attrs: dict[str, Any], prefix: str = "nrg3_bdgArea") -> QualifiedArea | None:
    return _make_qualified(QualifiedArea, attrs, prefix)


def _make_qualified_height(attrs: dict[str, Any], prefix: str = "nrg3_bdgHeight") -> QualifiedHeight | None:
    return _make_qualified(QualifiedHeight, attrs, prefix)


# ---------------------------------------------------------------------------
# Custom from_dict functions (complex types that need manual logic)
# ---------------------------------------------------------------------------


def building_from_dict(attrs: dict[str, Any]) -> Building:
    """Create a :class:`Building` from a flat attribute dictionary.

    This is a custom constructor because Building has QualifiedVolume/Area/Height
    lists that require nested sub-object assembly from flat keys.
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


def building_part_from_dict(attrs: dict[str, Any]) -> BuildingPart:
    """Create a :class:`BuildingPart` -- reuses Building logic."""
    b = building_from_dict(attrs)
    return BuildingPart(**{f.name: getattr(b, f.name) for f in dataclasses.fields(b)})


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


# ---------------------------------------------------------------------------
# Backward-compatible aliases (tests import these by name)
# ---------------------------------------------------------------------------


def pv_collector_from_dict(attrs: dict[str, Any]) -> PhotovoltaicCollector:
    """Create a :class:`PhotovoltaicCollector` from flat attributes."""
    return auto_from_dict(PhotovoltaicCollector, attrs)  # type: ignore[return-value]


def heat_pump_from_dict(attrs: dict[str, Any]) -> HeatPump:
    """Create a :class:`HeatPump` from flat attributes."""
    return auto_from_dict(HeatPump, attrs)  # type: ignore[return-value]


def ev_charging_station_from_dict(attrs: dict[str, Any]) -> EVChargingStation:
    """Create an :class:`EVChargingStation` from flat attributes."""
    return auto_from_dict(EVChargingStation, attrs)  # type: ignore[return-value]


def occupants_from_dict(attrs: dict[str, Any]) -> Occupants:
    """Create :class:`Occupants` from flat attributes."""
    return auto_from_dict(Occupants, attrs)  # type: ignore[return-value]


def epc_from_dict(attrs: dict[str, Any]) -> EnergyPerformanceCertificate:
    """Create an :class:`EnergyPerformanceCertificate` from flat attributes."""
    return auto_from_dict(EnergyPerformanceCertificate, attrs)  # type: ignore[return-value]


def energy_from_dict(attrs: dict[str, Any]) -> Energy:
    """Create an :class:`Energy` resource from flat attributes."""
    return auto_from_dict(Energy, attrs)  # type: ignore[return-value]


def constant_value_schedule_from_dict(attrs: dict[str, Any]) -> ConstantValueSchedule:
    """Create a :class:`ConstantValueSchedule` from flat attributes."""
    return auto_from_dict(ConstantValueSchedule, attrs)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Dispatch registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable[[dict[str, Any]], Any]] = {}


def _is_stub(fn: Callable[[dict[str, Any]], Any]) -> bool:
    return bool(getattr(fn, "_is_stub", False))


def _reg(fme_name: str, fn: Callable[[dict[str, Any]], Any]) -> None:
    _REGISTRY[fme_name] = fn


# --- Custom from_dict overrides (complex construction logic) ---
_CUSTOM_FROM_DICT: dict[str, Callable[[dict[str, Any]], Any]] = {
    "bldg_Building": building_from_dict,
    "bldg_BuildingPart": building_part_from_dict,
    "nrg3_BuildingUnit": building_unit_from_dict,
    "core_Address": address_from_dict,
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
_reg("nrg3_Zone", _stub("nrg3_Zone"))
_reg("nrg3_ZonePart", _stub("nrg3_ZonePart"))

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
        target = getattr(parent, parent_field, None)
        if target is None:
            raise ValueError(
                f"Parent {parent_type!r} ({type(parent).__name__}) has no "
                f"field {parent_field!r} for attaching {child_type!r}"
            )
        target.append(child)
