"""Attach STEP-imported geometry to xsdata CityGML/Energy-ADE bindings.

High-level flow:

* :func:`apply_geometry_sources` orchestrates the pipeline: it dispatches
  each geometry-source dict to the handler declared in
  :data:`GEOMETRY_SOURCE_SPECS`, then writes the accumulated bounding
  envelope onto the ``CityModel``.
* Energy ADE 3.0 derived properties (``nrg3:layeredConstruction``,
  ``bdgBdrySurf*``, ``bdgOpn*``) are appended in a single post-processing
  pass by :func:`citygml_energy.derived_attributes.apply_derived_attributes`,
  which consumes per-ADE emitter registrations from
  :mod:`.construction_mapping` and :mod:`.boundary_attributes`. Adding
  a new ADE (e.g. Scenario ADE) is a matter of dropping a sibling
  emitter module and appending its ``EMITTERS`` at the call site.

XSD-agnostic by design:

* No concrete xsdata class (``Building``, ``WallSurface2``,
  ``BoundarySurfacePropertyType2``, ...) is imported at module scope. Target
  types are resolved by XSD-qualified name through
  :func:`citygml_energy.mapping.resolve_class`, with the qualified names
  pulled from :mod:`citygml_energy.schema_types` so every schema-bound
  string literal in the pipeline lives in one reviewable place. Surface
  and opening taxonomies are auto-discovered from the generated dataclass
  metadata on the ``bounded_by`` and ``opening`` wrappers. Regenerating
  the bindings from a modified XSD (new surface classes, renamed dedup
  suffixes, extended Energy-ADE variants) is therefore picked up
  automatically.
* Only GML primitives (``Polygon``, ``MultiSurface``, ``Solid``,
  ``Envelope``, ``PosList`` ...) are imported up-front; those are GML
  3.1.1 wire types that would need to stay stable for any CityGML-derived
  schema to keep working.

Domain knowledge still encoded here:

* STEP layer-naming conventions (``WallSurface_1``, ``Window_2``,
  ``SolarPanelSurface_1``, optional ``lod3_`` prefix, ``|parent=...``
  suffix). This is an ad-hoc authoring convention (originated with the
  Rhino-exported owner-occupier reference building in this repo);
  alternatives are expressed as configuration
  (:data:`_SOLAR_PANEL_PREFIX`, :func:`_strip_lod_prefix`).
* The set of supported JSON geometry-source types: see
  :data:`GEOMETRY_SOURCE_SPECS`. Adding a new source type only requires
  registering a spec; the input loader and the JSON-schema generator both
  consume this registry.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from ._step import (
    Coord3D,
    GeometryPolygon,
    StepShell,
    parse_all_polygons,
    parse_named_shells,
)
from .bindings import Envelope
from .core import CityModel
from .device_relations import (  # re-exported; also sole source of _index_features
    DEFAULT_INSTALLED_ON_RELATION,
    _index_features,
    apply_device_relations,
)
from .gml_builders import (
    build_envelope,
    build_multi_surface,
    build_solid,
    open_ring,
)
from .mapping import get_fields, resolve_class
from .namespaces import (
    DEFAULT_SRS_DIMENSION,
    DEFAULT_SRS_NAME,
)
from .schema_types import BUILDING, PHOTOVOLTAIC_COLLECTOR, ZONE_PART

# ---------------------------------------------------------------------------
# STEP layer naming convention (owner-occupier authoring default,
# overridable per source)
# ---------------------------------------------------------------------------
_LOD_PREFIX_RE = re.compile(r"^lod\d+(?:\.\d+)?_", re.IGNORECASE)
DEFAULT_SOLAR_PANEL_PREFIX = "SolarPanelSurface_"
# ``DEFAULT_INSTALLED_ON_RELATION`` is imported above from :mod:`.device_relations`
# and re-exported at the module top for back-compat; no redefinition here.

_FEATURE_KIND_SURFACE = "surface"
_FEATURE_KIND_OPENING = "opening"
_FEATURE_KIND_SOLAR = "solar"

# ZonePart STEP shells follow the same author-facing CityGML 2.0 surface
# vocabulary as building-level shells (``WallSurface_*``, ``GroundSurface_*``,
# ``RoofSurface_*``, etc.) so that one Rhino export convention serves both.
# When a zonepart source is processed, names are rewritten through this map
# before classification so the matching XSD class is the EnergyADE
# ``Zone…Surface`` subclass that ``nrg3:zoneBoundary`` accepts. Building
# sources pass an empty remap and continue to use the ``bldg:_BoundarySurface``
# subclasses directly.
_BLDG_TO_ZONE_SURFACE_NAME_REMAP: dict[str, str] = {
    "WallSurface": "ZoneWallSurface",
    "GroundSurface": "ZoneGroundSurface",
    "RoofSurface": "ZoneRoofSurface",
    "FloorSurface": "ZoneOuterFloorSurface",
    "CeilingSurface": "ZoneOuterCeilingSurface",
    "IntermediateFloorSurface": "ZoneIntermediateFloorSurface",
    "ClosureSurface": "ZoneClosureSurface",
}


# ---------------------------------------------------------------------------
# Per-invocation rendering context
# ---------------------------------------------------------------------------


@dataclass
class _RenderContext:
    """Bundle of per-run configuration and shared caches.

    Built once by :func:`apply_geometry_sources` and threaded through the
    handlers, so deeply-nested helpers don't accumulate long parameter
    lists. ``feature_index`` is built up front from the existing model
    tree (``gml:id → object``), giving handlers O(1) lookups instead of
    one DFS per target reference. ``surface_name_index`` maps the pair
    ``(STEP layer name, LoD level)`` to the auto-assigned ``gml:id`` for
    every attached boundary surface. The LoD axis is part of the key so
    that the same STEP layer name (e.g. ``"RoofSurface_01"``) appearing
    in both a LoD 2 STEP and a LoD 3 STEP does not silently overwrite;
    callers that resolve a bare-name relation (``installed_on``) collapse
    the LoD axis themselves by picking the highest LoD present.
    """

    origin: Coord3D
    srs_name: str
    srs_dimension: int
    type_counters: dict[tuple[str, str], int]
    feature_index: dict[str, Any]
    surface_name_index: dict[tuple[str, int], str]

    def require_feature(self, gml_id: str, expected_type: type[Any]) -> Any:
        """Return the indexed feature for *gml_id*, asserting its xsdata class."""
        match = self.feature_index.get(gml_id)
        if match is None:
            raise ValueError(f"Feature {gml_id!r} was not found in the generated city model")
        if not isinstance(match, expected_type):
            raise ValueError(
                f"Feature {gml_id!r} exists but is not a {expected_type.__name__} "
                f"(found {type(match).__name__})"
            )
        return match

    def next_gml_id(self, prefix: str, element_cls: type[Any]) -> str:
        """Allocate ``"<prefix>_<TypeName>_<n>"`` and bump the counter."""
        key = (prefix, element_cls.__name__)
        self.type_counters[key] = self.type_counters.get(key, 0) + 1
        return f"{prefix}_{element_cls.__name__}_{self.type_counters[key]}"


@dataclass(frozen=True)
class _SurfaceRecord:
    """A bounded_by surface that has been attached to a building."""

    surface: Any
    polygons: list[GeometryPolygon]
    gml_id: str


@dataclass
class _AttachmentBuckets:
    """Intermediate state collected while walking classified STEP features."""

    surface_data: dict[str, _SurfaceRecord]
    pending_openings: list[_ClassifiedFeature]
    solar_polygons: list[GeometryPolygon]
    solar_roof_parents: set[str]
    all_coordinates: list[Coord3D]


# ---------------------------------------------------------------------------
# Geometry-source specs: single source of truth for JSON dispatch
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetFieldSpec:
    """A feature-ID reference that a geometry source may carry.

    *xsd_type* is the XSD-qualified element name; see
    :mod:`citygml_energy.schema_types` for the central set of constants.
    Resolution through :func:`citygml_energy.mapping.resolve_class` at
    application time means nothing here is coupled to a specific xsdata
    class or to a specific bindings revision.
    """

    xsd_type: str
    required: bool = True


@dataclass(frozen=True)
class GeometrySourceSpec:
    """Contract for one JSON ``geometry_sources[*]`` type.

    The input loader uses :attr:`target_fields` to validate each source;
    :func:`apply_geometry_sources` uses :attr:`handler` to know which
    routine to dispatch to. :attr:`solar_panel_prefix` lets callers that
    follow a different STEP-layer convention rename the prefix that
    triggers solar-panel handling. Device-to-surface ``installedOn``
    relations are declared in the JSON input, not derived from STEP
    naming (see :func:`apply_device_relations`).
    """

    source_type: str
    lod_level: int
    target_fields: dict[str, TargetFieldSpec]
    handler: str
    solar_panel_prefix: str = DEFAULT_SOLAR_PANEL_PREFIX

    def required_fields(self) -> tuple[str, ...]:
        """Required ``target_*`` field names for JSON-schema ``required``."""
        return tuple(name for name, spec in self.target_fields.items() if spec.required)


_BUILDING_TARGET = TargetFieldSpec(xsd_type=BUILDING, required=True)
_PV_TARGET = TargetFieldSpec(xsd_type=PHOTOVOLTAIC_COLLECTOR, required=False)
_ZONEPART_TARGET = TargetFieldSpec(xsd_type=ZONE_PART, required=True)


def _build_source_specs() -> dict[str, GeometrySourceSpec]:
    specs: dict[str, GeometrySourceSpec] = {}
    for lod in range(5):
        # PV geometry only exists at LoD 2 and 3 in the EnergyADE XSD
        # (AbstractSolarCollectorType defines lod{2,3}MultiSurface and
        # nothing else). Surface the constraint at the spec level so a
        # mistakenly-placed ``target_pv_id`` on a LoD0/1/4 source is
        # rejected by the input validator instead of silently dropped.
        target_fields: dict[str, TargetFieldSpec] = {
            "target_building_id": _BUILDING_TARGET,
        }
        if lod in (2, 3):
            target_fields["target_pv_id"] = _PV_TARGET
        specs[f"step-building-lod{lod}"] = GeometrySourceSpec(
            source_type=f"step-building-lod{lod}",
            lod_level=lod,
            target_fields=target_fields,
            handler="building",
        )
    for lod in range(4):
        specs[f"step-zonepart-lod{lod}"] = GeometrySourceSpec(
            source_type=f"step-zonepart-lod{lod}",
            lod_level=lod,
            target_fields={
                "target_zone_part_id": _ZONEPART_TARGET,
            },
            handler="zonepart",
        )
    return specs


GEOMETRY_SOURCE_SPECS: dict[str, GeometrySourceSpec] = _build_source_specs()
"""Registry keyed by ``source_type`` (e.g. ``"step-building-lod3"``)."""

SUPPORTED_GEOMETRY_SOURCE_TYPES: frozenset[str] = frozenset(GEOMETRY_SOURCE_SPECS)
"""Public allowlist consumed by the input loader; derived from the specs."""


# ---------------------------------------------------------------------------
# Auto-discovery: derive the surface / opening taxonomy from bindings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PropertyEntry:
    """One slot on a property-type wrapper (``BoundarySurfacePropertyType`` etc.)."""

    xsd_name: str  # e.g. "WallSurface" or "ZoneWallSurface"
    element_cls: type[Any]  # the concrete xsdata class
    field_name: str  # the Python field name on the wrapper


@cache
def _discover_property_map(wrapper_cls: type) -> dict[str, _PropertyEntry]:
    """Derive ``{xsd_name: _PropertyEntry}`` for a property-type wrapper.

    Reads the dataclass metadata on each non-attribute field to pair the
    XSD element name (``metadata["name"]``) with the Python field name
    and the concrete element class (the field's unwrapped type hint).
    """
    entries: dict[str, _PropertyEntry] = {}
    for info in get_fields(wrapper_cls).values():
        if info.is_attribute or info.xml_name is None:
            continue
        if not (isinstance(info.inner_type, type) and dataclasses.is_dataclass(info.inner_type)):
            continue
        # The xlink attributes on every property-type wrapper don't carry an XSD
        # element namespace; only real member elements do. Filter them out.
        if info.namespace is None:
            continue
        entries.setdefault(
            info.xml_name,
            _PropertyEntry(
                xsd_name=info.xml_name,
                element_cls=info.inner_type,
                field_name=info.name,
            ),
        )
    return entries


@cache
def _discover_wrapper(parent_cls: type, list_field: str) -> type | None:
    """Return the property-type wrapper for a list field on *parent_cls*.

    Example: ``_discover_wrapper(Building, "bounded_by")`` →
    ``BoundarySurfacePropertyType2``. Cached because we call it repeatedly
    with the same ``(surface_class, "opening")`` pairs during classification
    and attachment.
    """
    info = get_fields(parent_cls).get(list_field)
    if info is None or not info.is_list:
        return None
    inner = info.inner_type
    if not (isinstance(inner, type) and dataclasses.is_dataclass(inner)):
        return None
    return inner


# ---------------------------------------------------------------------------
# Internal dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ClassifiedFeature:
    """A STEP shell after classification against the parent's wrapper maps."""

    object_name: str
    parent_name: str | None
    kind: str
    entry: _PropertyEntry | None  # None for solar panels
    polygons: list[GeometryPolygon]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def apply_geometry_sources(
    model: CityModel,
    geometry_sources: Iterable[dict[str, Any]],
    *,
    origin: Coord3D = (0.0, 0.0, 0.0),
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
) -> None:
    """Apply every configured geometry source to *model* in place.

    *origin* is added to every imported STEP point so the output is
    expressed in real-world coordinates. *srs_name* and *srs_dimension*
    are written verbatim onto every produced ``gml:MultiSurface`` /
    ``gml:Solid`` and onto the computed ``gml:Envelope``.

    Features are indexed by ``gml:id`` once up front, so each source
    resolves its targets (Building, ZonePart, PhotovoltaicCollector) in
    O(1) regardless of how many sources the caller passes.
    """
    ctx = _RenderContext(
        origin=origin,
        srs_name=srs_name,
        srs_dimension=srs_dimension,
        type_counters={},
        feature_index=_index_features(model),
        surface_name_index=model.surface_name_index,
    )

    all_coordinates: list[Coord3D] = []

    for source in geometry_sources:
        source_type = source.get("type")
        spec = GEOMETRY_SOURCE_SPECS.get(source_type) if isinstance(source_type, str) else None
        if spec is None:
            raise ValueError(f"Unsupported geometry source type: {source_type!r}")

        step_path = Path(str(source["path"]))
        if spec.handler == "building":
            coords = _apply_building_source(ctx, spec=spec, step_path=step_path, source=source)
        elif spec.handler == "zonepart":
            coords = _apply_zonepart_source(ctx, spec=spec, step_path=step_path, source=source)
        else:
            raise RuntimeError(
                f"GeometrySourceSpec {spec.source_type!r} has unknown handler {spec.handler!r}"
            )
        all_coordinates.extend(coords)

    if all_coordinates:
        _set_envelope(
            model,
            build_envelope(all_coordinates, srs_name=srs_name, srs_dimension=srs_dimension),
        )


# ---------------------------------------------------------------------------
# Per-source-type dispatch
#
# ``apply_device_relations`` used to live here; it now sits in its own
# module (:mod:`.device_relations`) and is re-imported at the top of
# this file so the public API (``from .geometry import
# apply_device_relations``) is preserved for existing callers.
#
# ``apply_construction_mapping`` and ``attach_boundary_surface_attributes``
# have been replaced by :func:`citygml_energy.derived_attributes.apply_derived_attributes`,
# which walks the model once and dispatches to per-ADE emitter
# registrations declared in :mod:`.construction_mapping` and
# :mod:`.boundary_attributes`. See :mod:`.derived_attributes` for the
# seam contract.
# ---------------------------------------------------------------------------


def _apply_building_source(
    ctx: _RenderContext,
    *,
    spec: GeometrySourceSpec,
    step_path: Path,
    source: dict[str, Any],
) -> list[Coord3D]:
    """Handle one ``step-building-lod{0..4}`` source."""
    target_building_id = str(source["target_building_id"])
    target_pv_id = str(source["target_pv_id"]) if source.get("target_pv_id") is not None else None

    if spec.lod_level <= 1:
        return _apply_aggregate_building_geometry(
            ctx,
            step_path=step_path,
            target_building_id=target_building_id,
            lod_level=spec.lod_level,
        )

    building_cls = resolve_class(BUILDING)
    building = ctx.require_feature(target_building_id, building_cls)

    surface_wrapper = _discover_wrapper(building_cls, "bounded_by")
    if surface_wrapper is None:
        raise RuntimeError("bldg:Building has no 'bounded_by' list field in the current bindings")
    surface_map = _discover_property_map(surface_wrapper)

    shells = parse_named_shells(step_path, origin=ctx.origin)
    # When the source declares a target_pv_id, any shell that does not
    # match the surface / opening taxonomies falls through to the solar
    # bucket. This accommodates aggregated LoD 2 / LoD 1 PV
    # representations (a single unnamed "shell_1" in Rhino = the whole
    # array) without loosening classification on sources that do not
    # target a PV collector.
    pv_target_declared = source.get("target_pv_id") is not None
    features = [
        _classify_shell(
            step_path,
            shell,
            surface_map,
            spec.solar_panel_prefix,
            pv_target_declared=pv_target_declared,
        )
        for shell in shells
    ]

    buckets = _process_classified_features(
        ctx,
        features=features,
        parent_obj=building,
        parent_list_field="bounded_by",
        surface_wrapper=surface_wrapper,
        parent_id_prefix=target_building_id,
        lod_level=spec.lod_level,
        source_path=step_path,
    )

    _attach_pending_openings(
        ctx,
        buckets=buckets,
        parent_id_prefix=target_building_id,
        lod_level=spec.lod_level,
        source_path=step_path,
    )

    _attach_solar_panels(
        ctx,
        buckets=buckets,
        target_pv_id=target_pv_id,
        lod_level=spec.lod_level,
        source_path=step_path,
    )

    return buckets.all_coordinates


def _apply_zonepart_source(
    ctx: _RenderContext,
    *,
    spec: GeometrySourceSpec,
    step_path: Path,
    source: dict[str, Any],
) -> list[Coord3D]:
    """Handle one ``step-zonepart-lod{0..3}`` source.

    LoD 0/1 produce only the aggregate hull (footprint MultiSurface or
    block Solid). LoD 2/3 additionally classify each named STEP shell into
    a ``nrg3:Zone…Surface`` subclass and attach it as a ``zoneBoundary``
    child of the ZonePart, with ``Window``/``Door`` openings punched into
    walls. The aggregate Solid is still emitted at LoD 2/3 so viewers that
    only consume the hull keep working; thermal-analysis consumers iterate
    the per-face children for ``bdgBdrySurf*`` attributes.
    """
    target_zone_part_id = str(source["target_zone_part_id"])
    polygons, all_coordinates = parse_all_polygons(step_path, origin=ctx.origin)
    if not polygons:
        raise ValueError(f"STEP geometry {step_path} contains no polygon geometry")

    zone_cls = resolve_class(ZONE_PART)
    zone = ctx.require_feature(target_zone_part_id, zone_cls)
    gml_id = f"{target_zone_part_id}_lod{spec.lod_level}"

    if spec.lod_level == 0:
        zone.lod0_multi_surface = build_multi_surface(
            gml_id, polygons, srs_name=ctx.srs_name, srs_dimension=ctx.srs_dimension
        )
    else:
        setattr(
            zone,
            f"lod{spec.lod_level}_solid",
            build_solid(gml_id, polygons, srs_name=ctx.srs_name, srs_dimension=ctx.srs_dimension),
        )

    if spec.lod_level >= 2:
        _apply_zonepart_boundary_surfaces(
            ctx,
            zone=zone,
            zone_cls=zone_cls,
            target_zone_part_id=target_zone_part_id,
            step_path=step_path,
            lod_level=spec.lod_level,
        )

    return all_coordinates


def _apply_zonepart_boundary_surfaces(
    ctx: _RenderContext,
    *,
    zone: Any,
    zone_cls: type,
    target_zone_part_id: str,
    step_path: Path,
    lod_level: int,
) -> None:
    """Classify named STEP shells and attach them as ``zoneBoundary`` children.

    Mirrors :func:`_apply_building_source` (LoD ≥ 2) but targets ZonePart's
    ``zone_boundary`` slot and the ``nrg3:Zone…Surface`` taxonomy. Names
    are remapped from the building-style STEP convention
    (``WallSurface_*``) to the matching zone subclass name
    (``ZoneWallSurface``) before classification — the convention deliberately
    matches the building convention so one Rhino export style serves both
    pipelines. ``Window_*`` / ``Door_*`` openings carry the same vocabulary
    on both sides and need no remap.
    """
    surface_wrapper = _discover_wrapper(zone_cls, "zone_boundary")
    if surface_wrapper is None:
        raise RuntimeError(
            "nrg3:ZonePart has no 'zone_boundary' list field in the current bindings"
        )
    surface_map = _discover_property_map(surface_wrapper)

    shells = parse_named_shells(step_path, origin=ctx.origin)
    features = [
        _classify_shell(
            step_path,
            shell,
            surface_map,
            solar_panel_prefix="",  # ZoneParts never carry PV geometry
            pv_target_declared=False,
            surface_name_remap=_BLDG_TO_ZONE_SURFACE_NAME_REMAP,
        )
        for shell in shells
    ]

    buckets = _process_classified_features(
        ctx,
        features=features,
        parent_obj=zone,
        parent_list_field="zone_boundary",
        surface_wrapper=surface_wrapper,
        parent_id_prefix=target_zone_part_id,
        lod_level=lod_level,
        source_path=step_path,
        register_surface_name_index=False,
    )

    _attach_pending_openings(
        ctx,
        buckets=buckets,
        parent_id_prefix=target_zone_part_id,
        lod_level=lod_level,
        source_path=step_path,
    )


def _apply_aggregate_building_geometry(
    ctx: _RenderContext,
    *,
    step_path: Path,
    target_building_id: str,
    lod_level: int,
) -> list[Coord3D]:
    """LOD 0/1 aggregate attachment: footprint or block solid on a Building."""
    polygons, all_coordinates = parse_all_polygons(step_path, origin=ctx.origin)
    if not polygons:
        raise ValueError(f"STEP geometry {step_path} contains no polygon geometry")

    building_cls = resolve_class(BUILDING)
    building = ctx.require_feature(target_building_id, building_cls)
    gml_id = f"{target_building_id}_lod{lod_level}"

    if lod_level == 0:
        building.lod0_foot_print = build_multi_surface(
            gml_id, polygons, srs_name=ctx.srs_name, srs_dimension=ctx.srs_dimension
        )
    elif lod_level == 1:
        building.lod1_solid = build_solid(
            gml_id, polygons, srs_name=ctx.srs_name, srs_dimension=ctx.srs_dimension
        )
    else:
        raise ValueError(f"Aggregate building geometry only supports LOD 0 or 1, got {lod_level}")

    return all_coordinates


# ---------------------------------------------------------------------------
# Shell classification: STEP layer name → parent-wrapper entry
# ---------------------------------------------------------------------------


def _classify_shell(
    path: Path,
    shell: StepShell,
    surface_map: dict[str, _PropertyEntry],
    solar_panel_prefix: str,
    *,
    pv_target_declared: bool = False,
    surface_name_remap: dict[str, str] | None = None,
) -> _ClassifiedFeature:
    """Classify one STEP shell against the parent's surface taxonomy.

    When *pv_target_declared* is True (the enclosing source declared a
    ``target_pv_id``), shells that do not match the surface / opening
    taxonomies fall through to the solar bucket. This accommodates
    aggregated-array LoD exports where Rhino emits a single unnamed
    ``shell_1`` for the whole PV field instead of N named
    ``SolarPanelSurface_*`` panels.

    *solar_panel_prefix* is treated as "no solar handling" when empty (used
    by zonepart sources, which never carry PV geometry).

    *surface_name_remap* rewrites a recognised shell-name prefix before the
    surface-map lookup, so a single STEP authoring vocabulary
    (``WallSurface_*``, ``GroundSurface_*``, …) can target either the
    ``bldg:_BoundarySurface`` taxonomy (no remap) or the EnergyADE
    ``nrg3:Zone…Surface`` taxonomy (remap via
    :data:`_BLDG_TO_ZONE_SURFACE_NAME_REMAP`).
    """
    classified_name = _strip_lod_prefix(shell.object_name)
    if surface_name_remap:
        classified_name = _apply_surface_name_remap(classified_name, surface_name_remap)

    if solar_panel_prefix and classified_name.startswith(solar_panel_prefix):
        return _ClassifiedFeature(
            object_name=shell.object_name,
            parent_name=shell.parent_name,
            kind=_FEATURE_KIND_SOLAR,
            entry=None,
            polygons=shell.polygons,
        )

    for xsd_name, entry in surface_map.items():
        if classified_name.startswith(xsd_name + "_") or classified_name == xsd_name:
            return _ClassifiedFeature(
                object_name=shell.object_name,
                parent_name=shell.parent_name,
                kind=_FEATURE_KIND_SURFACE,
                entry=entry,
                polygons=shell.polygons,
            )

    # Openings: discover opening map by peeking at any surface class's
    # ``opening`` field. All surface classes in the same wrapper share the
    # same opening wrapper type, so we grab the first one.
    for entry in surface_map.values():
        # mypy stub for ``_lru_cache_wrapper`` rejects ``type[Any]``; safe.
        opening_wrapper = _discover_wrapper(entry.element_cls, "opening")  # type: ignore[arg-type]
        if opening_wrapper is None:
            continue
        opening_map = _discover_property_map(opening_wrapper)
        for xsd_name, opening_entry in opening_map.items():
            if classified_name.startswith(xsd_name + "_") or classified_name == xsd_name:
                return _ClassifiedFeature(
                    object_name=shell.object_name,
                    parent_name=shell.parent_name,
                    kind=_FEATURE_KIND_OPENING,
                    entry=opening_entry,
                    polygons=shell.polygons,
                )
        break  # opening wrapper is uniform across surface siblings

    # Fallthrough for "source declared a PV target but this shell has no
    # solar / surface / opening name match": treat it as solar. The
    # opt-in via *pv_target_declared* keeps typos on non-PV sources
    # failing loudly; on a source that *is* the PV export, unnamed
    # shells are what Rhino produces by default and we accept them.
    if pv_target_declared:
        return _ClassifiedFeature(
            object_name=shell.object_name,
            parent_name=shell.parent_name,
            kind=_FEATURE_KIND_SOLAR,
            entry=None,
            polygons=shell.polygons,
        )

    known = sorted(surface_map)
    raise ValueError(
        f"STEP geometry {path} contains unsupported shell name {shell.object_name!r}. "
        f"Known surface types: {', '.join(known)}; solar layer prefix: "
        f"{solar_panel_prefix!r}"
    )


# ---------------------------------------------------------------------------
# Attach features to a Building: LOD 2..4 path
# ---------------------------------------------------------------------------


def _process_classified_features(
    ctx: _RenderContext,
    *,
    features: list[_ClassifiedFeature],
    parent_obj: Any,
    parent_list_field: str,
    surface_wrapper: type,
    parent_id_prefix: str,
    lod_level: int,
    source_path: Path,
    register_surface_name_index: bool = True,
) -> _AttachmentBuckets:
    """Walk classified STEP features, attaching surfaces and collecting the rest.

    Surfaces become children of *parent_obj* (under ``parent_list_field``,
    which is ``"bounded_by"`` for buildings and ``"zone_boundary"`` for
    zoneparts) immediately so they are visible to subsequent
    opening-matching; openings and solar panels are queued for the
    dedicated helpers below. Every exterior and interior vertex seen along
    the way contributes to the envelope bounding box.
    """
    buckets = _AttachmentBuckets(
        surface_data={},
        pending_openings=[],
        solar_polygons=[],
        solar_roof_parents=set(),
        all_coordinates=[],
    )
    lod_field = f"lod{lod_level}_multi_surface"

    for feature in features:
        if not feature.polygons:
            continue

        for polygon in feature.polygons:
            buckets.all_coordinates.extend(polygon.exterior)
            for interior in polygon.interiors:
                buckets.all_coordinates.extend(interior)

        if feature.kind == _FEATURE_KIND_SOLAR:
            buckets.solar_polygons.extend(feature.polygons)
            if feature.parent_name:
                buckets.solar_roof_parents.add(feature.parent_name)
            continue

        if feature.kind == _FEATURE_KIND_SURFACE:
            assert feature.entry is not None
            _attach_surface(
                ctx,
                feature=feature,
                parent_obj=parent_obj,
                parent_list_field=parent_list_field,
                surface_wrapper=surface_wrapper,
                lod_field=lod_field,
                lod_level=lod_level,
                parent_id_prefix=parent_id_prefix,
                buckets=buckets,
                register_surface_name_index=register_surface_name_index,
            )
            continue

        if feature.kind == _FEATURE_KIND_OPENING:
            buckets.pending_openings.append(feature)
            continue

        raise ValueError(
            f"Geometry source {source_path} produced unsupported feature kind {feature.kind!r}"
        )

    return buckets


def _attach_surface(
    ctx: _RenderContext,
    *,
    feature: _ClassifiedFeature,
    parent_obj: Any,
    parent_list_field: str,
    surface_wrapper: type,
    lod_field: str,
    lod_level: int,
    parent_id_prefix: str,
    buckets: _AttachmentBuckets,
    register_surface_name_index: bool = True,
) -> None:
    """Build one boundary surface, append it to the parent's surface list.

    *register_surface_name_index* controls whether the STEP layer name is
    exposed on the model-wide ``surface_name_index`` for ``installed_on``
    resolution. Set to False for ZonePart sources: zonepart faces are an
    internal thermal-envelope description, not the publicly-attachable
    surface vocabulary that devices physically sit on (a roof-mounted PV
    is "installedOn" the building's ``bldg:RoofSurface``, not on the
    upstairs ZonePart's ``ZoneRoofSurface``). Indexing zonepart shells
    under the same STEP names would silently overwrite the building
    entries (the canonical input has ``RoofSurface_01`` shells in both
    the building's LoD3 export and the upstairs ZonePart export).
    """
    assert feature.entry is not None
    gml_id = ctx.next_gml_id(parent_id_prefix, feature.entry.element_cls)
    surface = feature.entry.element_cls(
        id=gml_id,
        **{
            lod_field: build_multi_surface(
                f"{gml_id}_lod{lod_level}",
                feature.polygons,
                srs_name=ctx.srs_name,
                srs_dimension=ctx.srs_dimension,
            )
        },
    )
    getattr(parent_obj, parent_list_field).append(
        surface_wrapper(**{feature.entry.field_name: surface})
    )
    buckets.surface_data[feature.object_name] = _SurfaceRecord(
        surface=surface, polygons=feature.polygons, gml_id=gml_id
    )
    if register_surface_name_index:
        # Expose (STEP-name, LoD) ↔ gml:id mapping on the model-wide index
        # so JSON-declared relations (installed_on, …) can resolve against
        # author-facing STEP layer names instead of auto-generated gml:ids.
        # The LoD axis prevents silent overwrite when the same layer name
        # appears at multiple LoDs (e.g. the canonical input has
        # ``RoofSurface_01`` in both LoD 2 and LoD 3 STEPs but the two
        # refer to different physical faces, since LoD 3 numbers
        # sub-faces fresh and re-uses low indices).
        ctx.surface_name_index[(feature.object_name, lod_level)] = gml_id


def _attach_pending_openings(
    ctx: _RenderContext,
    *,
    buckets: _AttachmentBuckets,
    parent_id_prefix: str,
    lod_level: int,
    source_path: Path,
) -> None:
    """Match each opening to a parent surface (interior-ring overlap) and attach."""
    lod_field = f"lod{lod_level}_multi_surface"
    for feature in buckets.pending_openings:
        assert feature.entry is not None
        parent_step_name = _match_opening_to_parent(feature, buckets.surface_data)
        if parent_step_name is None:
            raise ValueError(
                f"Opening in {source_path} could not be matched to any parent "
                f"surface by interior-ring geometry"
            )
        parent_surface = buckets.surface_data[parent_step_name].surface

        gml_id = ctx.next_gml_id(parent_id_prefix, feature.entry.element_cls)
        opening_obj = feature.entry.element_cls(
            id=gml_id,
            **{
                lod_field: build_multi_surface(
                    f"{gml_id}_lod{lod_level}",
                    feature.polygons,
                    srs_name=ctx.srs_name,
                    srs_dimension=ctx.srs_dimension,
                )
            },
        )
        # mypy stub for ``_lru_cache_wrapper`` rejects ``type[Any]``; safe.
        opening_wrapper = _discover_wrapper(type(parent_surface), "opening")  # type: ignore[arg-type]
        if opening_wrapper is None:
            raise RuntimeError(
                f"{type(parent_surface).__name__} has no 'opening' field; "
                f"cannot attach {feature.entry.xsd_name}"
            )
        parent_surface.opening.append(opening_wrapper(**{feature.entry.field_name: opening_obj}))


def _attach_solar_panels(
    ctx: _RenderContext,
    *,
    buckets: _AttachmentBuckets,
    target_pv_id: str | None,
    lod_level: int,
    source_path: Path,
) -> None:
    """Attach solar-panel polygons to the PV collector as ``lodNMultiSurface``.

    Device-to-surface relations (``installedOn`` etc.) are *metadata*
    and belong in the JSON input (see :func:`apply_device_relations`),
    so this function deliberately no longer derives them from STEP layer
    names. The geometric ``|parent=RoofSurface_…`` link is still parsed
    for opening-to-wall matching; it just no longer drives ADE relations.
    """
    if not buckets.solar_polygons:
        if target_pv_id is not None:
            raise ValueError(
                f"Geometry source {source_path} configured target_pv_id={target_pv_id!r} "
                f"but no solar panel faces were found"
            )
        return

    if target_pv_id is None:
        raise ValueError(
            f"Geometry source {source_path} contains solar panel faces but no "
            f"target_pv_id was configured"
        )

    pv_cls = resolve_class(PHOTOVOLTAIC_COLLECTOR)
    pv_collector = ctx.require_feature(target_pv_id, pv_cls)
    lod_field = f"lod{lod_level}_multi_surface"
    setattr(
        pv_collector,
        lod_field,
        build_multi_surface(
            f"{target_pv_id}_lod{lod_level}",
            buckets.solar_polygons,
            srs_name=ctx.srs_name,
            srs_dimension=ctx.srs_dimension,
        ),
    )


def _match_opening_to_parent(
    opening: _ClassifiedFeature,
    surface_data: dict[str, _SurfaceRecord],
) -> str | None:
    """Return the STEP name of the surface whose interior ring matches *opening*.

    Openings are linked to surfaces geometrically: Rhino exports a window as
    a separate shell and punches its outline into the parent wall as an
    interior (hole) ring. We match by comparing the opening's exterior
    vertices to every surface's interior rings; the shared-edge floating-
    point noise is absorbed by rounding (:func:`_ring_vertex_key`).
    """
    opening_keys = {_ring_vertex_key(p.exterior) for p in opening.polygons}
    for step_name, record in surface_data.items():
        for polygon in record.polygons:
            for interior in polygon.interiors:
                if _ring_vertex_key(interior) in opening_keys:
                    return step_name
    return None


def _ring_vertex_key(
    ring: list[Coord3D],
    precision: int = 4,
) -> frozenset[tuple[float, float, float]]:
    """Hashable vertex set for opening/interior matching.

    Rounds to *precision* decimals (default 4 → 0.1 mm) so floating-point
    noise from shared STEP edges doesn't block matching.
    """
    return frozenset(
        (round(v[0], precision), round(v[1], precision), round(v[2], precision))
        for v in open_ring(ring)
    )


def _strip_lod_prefix(name: str) -> str:
    """Strip an optional leading ``lod{N}_`` prefix (case-insensitive)."""
    return _LOD_PREFIX_RE.sub("", name)


def _apply_surface_name_remap(name: str, remap: dict[str, str]) -> str:
    """Rewrite the leading surface-class token in *name* via *remap*.

    Matches whole-token only (``"WallSurface_01"`` rewrites to
    ``"ZoneWallSurface_01"`` under ``{"WallSurface": "ZoneWallSurface"}``;
    ``"WallSurfaceish_01"`` does not match). Unknown names pass through
    unchanged so opening shells (``Window_*``, ``Door_*``) — which use the
    same vocabulary on building and zonepart — fall through to the
    opening-map lookup downstream.
    """
    for src, dst in remap.items():
        if name == src:
            return dst
        if name.startswith(src + "_"):
            return dst + name[len(src) :]
    return name


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


def _set_envelope(model: CityModel, envelope: Envelope) -> None:
    model.set_envelope(envelope)


# Construction-mapping and feature-lookup helpers now live in
# :mod:`.construction_mapping` and :mod:`.device_relations` respectively.


__all__ = [
    "DEFAULT_INSTALLED_ON_RELATION",
    "DEFAULT_SOLAR_PANEL_PREFIX",
    "DEFAULT_SRS_DIMENSION",
    "DEFAULT_SRS_NAME",
    "GEOMETRY_SOURCE_SPECS",
    "SUPPORTED_GEOMETRY_SOURCE_TYPES",
    "GeometrySourceSpec",
    "TargetFieldSpec",
    "apply_device_relations",
    "apply_geometry_sources",
]
