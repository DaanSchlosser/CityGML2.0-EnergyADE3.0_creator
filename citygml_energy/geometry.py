"""Attach STEP-imported geometry to xsdata CityGML/Energy-ADE bindings.

High-level flow:

* :func:`apply_geometry_sources` orchestrates the pipeline: it dispatches
  each geometry-source dict to the handler declared in
  :data:`GEOMETRY_SOURCE_SPECS`, then writes the accumulated bounding
  envelope onto the ``CityModel``.
* :func:`apply_construction_mapping` post-processes the model to append
  ``nrg3:layeredConstruction`` xlink:href references wherever the bindings
  permit them.

XSD-agnostic by design:

* No concrete xsdata class (``Building``, ``WallSurface2``,
  ``BoundarySurfacePropertyType2``, ...) is imported at module scope. Target
  types are resolved by XSD-qualified name (``"bldg:Building"``) through
  :func:`citygml_energy.mapping.resolve_class`, and the surface / opening
  taxonomies are auto-discovered from the generated dataclass metadata on
  the ``bounded_by`` and ``opening`` wrappers. Regenerating the bindings
  from a modified XSD — new surface classes, renamed dedup suffixes,
  extended Energy-ADE variants — is therefore picked up automatically.
* Only GML primitives (``Polygon``, ``MultiSurface``, ``Solid``,
  ``Envelope``, ``PosList`` ...) are imported up-front; those are GML
  3.1.1 wire types that would need to stay stable for any CityGML-derived
  schema to keep working.

Domain knowledge still encoded here:

* STEP layer-naming conventions (``WallSurface_1``, ``Window_2``,
  ``SolarPanelSurface_1``, optional ``lod3_`` prefix, ``|parent=...``
  suffix). This is the RenoDAT authoring convention and is expressed as
  configuration (:data:`_SOLAR_PANEL_PREFIX`, :func:`_strip_lod_prefix`).
* The set of supported JSON geometry-source types — see
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
    points_close,
)
from .bindings import (
    AbstractCityObjectPropertyType,
    BoundedBy,
    CityObjectRelation,
    CodeType,
    CompositeSurface,
    DirectPositionType,
    Envelope,
    Exterior,
    Interior,
    LayeredConstruction2,
    LinearRing,
    MultiSurface,
    MultiSurfacePropertyType,
    Polygon,
    PosList,
    RelatedTo,
    Solid,
    SolidPropertyType,
    SurfaceMember,
    SurfacePropertyType,
)
from .core import CityModel
from .mapping import find_by_id, get_fields, iter_instances, resolve_class
from .namespaces import (
    CS_NRG3_RELATION_TYPE,
    DEFAULT_SRS_DIMENSION,
    DEFAULT_SRS_NAME,
)

# ---------------------------------------------------------------------------
# STEP layer naming convention (RenoDAT)
# ---------------------------------------------------------------------------
_LOD_PREFIX_RE = re.compile(r"^lod\d+(?:\.\d+)?_", re.IGNORECASE)
_SOLAR_PANEL_PREFIX = "SolarPanelSurface_"

_FEATURE_KIND_SURFACE = "surface"
_FEATURE_KIND_OPENING = "opening"
_FEATURE_KIND_SOLAR = "solar"


# ---------------------------------------------------------------------------
# Geometry-source specs — single source of truth for JSON dispatch
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetFieldSpec:
    """A feature-ID reference that a geometry source may carry.

    *xsd_type* is the XSD-qualified element name (e.g. ``"bldg:Building"``);
    it is resolved through :func:`citygml_energy.mapping.resolve_class` at
    application time so nothing is coupled to a specific xsdata class.
    """

    xsd_type: str
    required: bool = True


@dataclass(frozen=True)
class GeometrySourceSpec:
    """Contract for one JSON ``geometry_sources[*]`` type.

    The input loader uses the :attr:`target_fields` mapping to validate
    each source; :func:`apply_geometry_sources` uses :attr:`handler` to
    know which routine to dispatch to.
    """

    source_type: str
    lod_level: int
    target_fields: dict[str, TargetFieldSpec]
    primary_target_field: str
    handler: str

    def required_fields(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self.target_fields.items() if spec.required)

    def optional_fields(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self.target_fields.items() if not spec.required)


_BUILDING_TARGET = TargetFieldSpec(xsd_type="bldg:Building", required=True)
_PV_TARGET = TargetFieldSpec(xsd_type="nrg3:PhotovoltaicCollector", required=False)
_ZONEPART_TARGET = TargetFieldSpec(xsd_type="nrg3:ZonePart", required=True)


def _build_source_specs() -> dict[str, GeometrySourceSpec]:
    specs: dict[str, GeometrySourceSpec] = {}
    for lod in range(5):
        specs[f"step-renodat-lod{lod}"] = GeometrySourceSpec(
            source_type=f"step-renodat-lod{lod}",
            lod_level=lod,
            target_fields={
                "target_building_id": _BUILDING_TARGET,
                "target_pv_id": _PV_TARGET,
            },
            primary_target_field="target_building_id",
            handler="building",
        )
    for lod in range(4):
        specs[f"step-zonepart-lod{lod}"] = GeometrySourceSpec(
            source_type=f"step-zonepart-lod{lod}",
            lod_level=lod,
            target_fields={
                "target_zone_part_id": _ZONEPART_TARGET,
            },
            primary_target_field="target_zone_part_id",
            handler="zonepart",
        )
    return specs


GEOMETRY_SOURCE_SPECS: dict[str, GeometrySourceSpec] = _build_source_specs()
"""Registry keyed by ``source_type`` (e.g. ``"step-renodat-lod3"``)."""

SUPPORTED_GEOMETRY_SOURCE_TYPES: frozenset[str] = frozenset(GEOMETRY_SOURCE_SPECS)
"""Public allowlist consumed by the input loader — derived from the specs."""


# ---------------------------------------------------------------------------
# Auto-discovery — derive the surface / opening taxonomy from bindings
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
        entries.setdefault(info.xml_name, _PropertyEntry(
            xsd_name=info.xml_name,
            element_cls=info.inner_type,
            field_name=info.name,
        ))
    return entries


def _discover_wrapper(parent_cls: type, list_field: str) -> type | None:
    """Return the property-type wrapper for a list field on *parent_cls*.

    Example: ``_discover_wrapper(Building, "bounded_by")`` →
    ``BoundarySurfacePropertyType2``.
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
    """
    all_coordinates: list[Coord3D] = []

    # Shared counters across sources so surfaces produced at different
    # LOD levels for the same building get unique gml:ids.
    type_counters: dict[tuple[str, str], int] = {}

    for source in geometry_sources:
        source_type = source.get("type")
        spec = GEOMETRY_SOURCE_SPECS.get(source_type) if isinstance(source_type, str) else None
        if spec is None:
            raise ValueError(f"Unsupported geometry source type: {source_type!r}")

        step_path = Path(str(source["path"]))
        if spec.handler == "building":
            coords = _apply_building_source(
                model,
                spec=spec,
                step_path=step_path,
                source=source,
                type_counters=type_counters,
                origin=origin,
                srs_name=srs_name,
                srs_dimension=srs_dimension,
            )
        elif spec.handler == "zonepart":
            coords = _apply_zonepart_source(
                model,
                spec=spec,
                step_path=step_path,
                source=source,
                origin=origin,
                srs_name=srs_name,
                srs_dimension=srs_dimension,
            )
        else:
            raise RuntimeError(
                f"GeometrySourceSpec {spec.source_type!r} has unknown handler {spec.handler!r}"
            )
        all_coordinates.extend(coords)

    if all_coordinates:
        _set_envelope(
            model,
            _compute_envelope(all_coordinates, srs_name=srs_name, srs_dimension=srs_dimension),
        )


def apply_construction_mapping(
    model: CityModel,
    mapping: dict[str, Any],
) -> None:
    """Append ``nrg3:layeredConstruction`` references wherever the XSD permits them.

    Traverses the entire ``CityModel`` and, for each dataclass instance
    that carries a ``layered_construction`` *list* field (per the generated
    bindings), resolves a construction ID via ``by_id`` (keyed by
    ``gml:id``) or falls back to ``by_type`` (keyed by the class's XSD
    element name). A ``LayeredConstruction2`` xlink:href is appended when
    a mapping is found.

    Scope is therefore determined by the bindings, not by hand-maintained
    taxonomy: boundary surfaces, openings, zone boundaries, and any other
    class the XSD gives ``layered_construction`` receive matching mappings
    without code changes. The caller is responsible for keeping the mapping
    keys semantically appropriate for its domain.
    """
    by_type: dict[str, str] = mapping.get("by_type", {})
    by_id: dict[str, str] = mapping.get("by_id", {})

    for obj in iter_instances(model.xsd):
        construction_list = _layered_construction_list(obj)
        if construction_list is None:
            continue
        constr_id = _resolve_construction_id(obj, by_id, by_type)
        if constr_id is not None:
            construction_list.append(_make_construction_ref(constr_id))


# ---------------------------------------------------------------------------
# Per-source-type dispatch
# ---------------------------------------------------------------------------


def _apply_building_source(
    model: CityModel,
    *,
    spec: GeometrySourceSpec,
    step_path: Path,
    source: dict[str, Any],
    type_counters: dict[tuple[str, str], int],
    origin: Coord3D,
    srs_name: str,
    srs_dimension: int,
) -> list[Coord3D]:
    target_building_id = str(source["target_building_id"])
    target_pv_id = (
        str(source["target_pv_id"]) if source.get("target_pv_id") is not None else None
    )

    if spec.lod_level <= 1:
        return _apply_aggregate_building_geometry(
            model,
            step_path=step_path,
            target_building_id=target_building_id,
            lod_level=spec.lod_level,
            origin=origin,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )

    building_cls = resolve_class("bldg:Building")
    building = _require_feature(model, target_building_id, building_cls)

    surface_wrapper = _discover_wrapper(building_cls, "bounded_by")
    if surface_wrapper is None:
        raise RuntimeError(
            "bldg:Building has no 'bounded_by' list field in the current bindings"
        )
    surface_map = _discover_property_map(surface_wrapper)

    shells = parse_named_shells(step_path, origin=origin)
    features = [_classify_shell(step_path, shell, surface_map) for shell in shells]

    return _attach_building_features(
        building=building,
        features=features,
        surface_wrapper=surface_wrapper,
        source_path=step_path,
        target_building_id=target_building_id,
        target_pv_id=target_pv_id,
        lod_level=spec.lod_level,
        type_counters=type_counters,
        srs_name=srs_name,
        srs_dimension=srs_dimension,
        model=model,
    )


def _apply_zonepart_source(
    model: CityModel,
    *,
    spec: GeometrySourceSpec,
    step_path: Path,
    source: dict[str, Any],
    origin: Coord3D,
    srs_name: str,
    srs_dimension: int,
) -> list[Coord3D]:
    target_zone_part_id = str(source["target_zone_part_id"])
    polygons, all_coordinates = parse_all_polygons(step_path, origin=origin)
    if not polygons:
        raise ValueError(f"STEP geometry {step_path} contains no polygon geometry")

    zone_cls = resolve_class("nrg3:ZonePart")
    zone = _require_feature(model, target_zone_part_id, zone_cls)
    gml_id = f"{target_zone_part_id}_lod{spec.lod_level}"

    if spec.lod_level == 0:
        zone.lod0_multi_surface = _build_multi_surface(
            gml_id, polygons, srs_name=srs_name, srs_dimension=srs_dimension
        )
    else:
        solid = _build_solid(gml_id, polygons, srs_name=srs_name, srs_dimension=srs_dimension)
        setattr(zone, f"lod{spec.lod_level}_solid", solid)

    return all_coordinates


def _apply_aggregate_building_geometry(
    model: CityModel,
    *,
    step_path: Path,
    target_building_id: str,
    lod_level: int,
    origin: Coord3D,
    srs_name: str,
    srs_dimension: int,
) -> list[Coord3D]:
    polygons, all_coordinates = parse_all_polygons(step_path, origin=origin)
    if not polygons:
        raise ValueError(f"STEP geometry {step_path} contains no polygon geometry")

    building_cls = resolve_class("bldg:Building")
    building = _require_feature(model, target_building_id, building_cls)
    gml_id = f"{target_building_id}_lod{lod_level}"

    if lod_level == 0:
        building.lod0_foot_print = _build_multi_surface(
            gml_id, polygons, srs_name=srs_name, srs_dimension=srs_dimension
        )
    elif lod_level == 1:
        building.lod1_solid = _build_solid(
            gml_id, polygons, srs_name=srs_name, srs_dimension=srs_dimension
        )
    else:
        raise ValueError(
            f"Aggregate building geometry only supports LOD 0 or 1, got {lod_level}"
        )

    return all_coordinates


# ---------------------------------------------------------------------------
# Shell classification — STEP layer name → parent-wrapper entry
# ---------------------------------------------------------------------------


def _classify_shell(
    path: Path,
    shell: StepShell,
    surface_map: dict[str, _PropertyEntry],
) -> _ClassifiedFeature:
    """Classify one STEP shell against the parent's surface taxonomy."""
    classified_name = _strip_lod_prefix(shell.object_name)

    if classified_name.startswith(_SOLAR_PANEL_PREFIX):
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

    # Openings — discover opening map by peeking at any surface class's
    # ``opening`` field. All surface classes in the same wrapper share the
    # same opening wrapper type, so we grab the first one.
    for entry in surface_map.values():
        opening_wrapper = _discover_wrapper(entry.element_cls, "opening")
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

    known = sorted(surface_map)
    raise ValueError(
        f"STEP geometry {path} contains unsupported shell name {shell.object_name!r}. "
        f"Known surface types: {', '.join(known)}; solar layer prefix: "
        f"{_SOLAR_PANEL_PREFIX!r}"
    )


# ---------------------------------------------------------------------------
# Attach features to a Building — LOD 2..4 path
# ---------------------------------------------------------------------------


def _attach_building_features(
    *,
    model: CityModel,
    building: Any,
    features: list[_ClassifiedFeature],
    surface_wrapper: type,
    source_path: Path,
    target_building_id: str,
    target_pv_id: str | None,
    lod_level: int,
    type_counters: dict[tuple[str, str], int],
    srs_name: str,
    srs_dimension: int,
) -> list[Coord3D]:
    lod_field = f"lod{lod_level}_multi_surface"

    # step_name → (surface_instance, polygons, gml_id)
    surface_data: dict[str, tuple[Any, list[GeometryPolygon], str]] = {}
    pending_openings: list[_ClassifiedFeature] = []
    solar_panel_polygons: list[GeometryPolygon] = []
    solar_panel_roof_parents: set[str] = set()
    all_coordinates: list[Coord3D] = []

    for feature in features:
        if not feature.polygons:
            continue

        for polygon in feature.polygons:
            all_coordinates.extend(polygon.exterior)
            for interior in polygon.interiors:
                all_coordinates.extend(interior)

        if feature.kind == _FEATURE_KIND_SOLAR:
            solar_panel_polygons.extend(feature.polygons)
            if feature.parent_name:
                solar_panel_roof_parents.add(feature.parent_name)
            continue

        if feature.kind == _FEATURE_KIND_SURFACE:
            assert feature.entry is not None
            gml_id = _next_feature_id(
                type_counters, target_building_id, feature.entry.element_cls
            )
            surface = feature.entry.element_cls(
                id=gml_id,
                **{
                    lod_field: _build_multi_surface(
                        f"{gml_id}_lod{lod_level}",
                        feature.polygons,
                        srs_name=srs_name,
                        srs_dimension=srs_dimension,
                    )
                },
            )
            building.bounded_by.append(
                surface_wrapper(**{feature.entry.field_name: surface})
            )
            surface_data[feature.object_name] = (surface, feature.polygons, gml_id)
            continue

        if feature.kind == _FEATURE_KIND_OPENING:
            pending_openings.append(feature)
            continue

        raise ValueError(
            f"Geometry source {source_path} produced unsupported feature kind {feature.kind!r}"
        )

    # Match openings to parent surfaces by interior-ring geometry.
    for feature in pending_openings:
        assert feature.entry is not None
        parent_step_name = _match_opening_to_parent(feature, surface_data)
        if parent_step_name is None:
            raise ValueError(
                f"Opening in {source_path} could not be matched to any parent "
                f"surface by interior-ring geometry"
            )
        parent_surface = surface_data[parent_step_name][0]

        gml_id = _next_feature_id(
            type_counters, target_building_id, feature.entry.element_cls
        )
        opening_obj = feature.entry.element_cls(
            id=gml_id,
            **{
                lod_field: _build_multi_surface(
                    f"{gml_id}_lod{lod_level}",
                    feature.polygons,
                    srs_name=srs_name,
                    srs_dimension=srs_dimension,
                )
            },
        )
        opening_wrapper = _discover_wrapper(type(parent_surface), "opening")
        if opening_wrapper is None:
            raise RuntimeError(
                f"{type(parent_surface).__name__} has no 'opening' field; "
                f"cannot attach {feature.entry.xsd_name}"
            )
        parent_surface.opening.append(
            opening_wrapper(**{feature.entry.field_name: opening_obj})
        )

    if solar_panel_polygons:
        if target_pv_id is None:
            raise ValueError(
                f"Geometry source {source_path} contains solar panel faces but no "
                f"target_pv_id was configured"
            )

        pv_cls = resolve_class("nrg3:PhotovoltaicCollector")
        pv_collector = _require_feature(model, target_pv_id, pv_cls)
        setattr(
            pv_collector,
            lod_field,
            _build_multi_surface(
                f"{target_pv_id}_lod{lod_level}",
                solar_panel_polygons,
                srs_name=srs_name,
                srs_dimension=srs_dimension,
            ),
        )

        for roof_step_name in sorted(solar_panel_roof_parents):
            entry = surface_data.get(roof_step_name)
            if entry is not None:
                pv_collector.related_to.append(
                    RelatedTo(
                        city_object_relation=CityObjectRelation(
                            relation_type=CodeType(
                                value="installedOn",
                                code_space=CS_NRG3_RELATION_TYPE,
                            ),
                            related_to=_make_city_object_ref(entry[2]),
                        ),
                    )
                )
    elif target_pv_id is not None:
        raise ValueError(
            f"Geometry source {source_path} configured target_pv_id={target_pv_id!r} "
            f"but no solar panel faces were found"
        )

    return all_coordinates


def _next_feature_id(
    counters: dict[tuple[str, str], int],
    building_id: str,
    element_cls: type[Any],
) -> str:
    """Allocate ``"<building_id>_<TypeName>_<n>"`` and bump the counter."""
    key = (building_id, element_cls.__name__)
    counters[key] = counters.get(key, 0) + 1
    return f"{building_id}_{element_cls.__name__}_{counters[key]}"


def _match_opening_to_parent(
    opening: _ClassifiedFeature,
    surface_data: dict[str, tuple[Any, list[GeometryPolygon], str]],
) -> str | None:
    """Return the STEP name of the surface whose interior ring matches *opening*."""
    opening_keys = {_ring_vertex_key(p.exterior) for p in opening.polygons}
    for step_name, (_, polygons, _) in surface_data.items():
        for polygon in polygons:
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
        for v in _open_ring(ring)
    )


def _open_ring(ring: list[Coord3D]) -> list[Coord3D]:
    if len(ring) > 1 and points_close(ring[0], ring[-1]):
        return ring[:-1]
    return ring


def _strip_lod_prefix(name: str) -> str:
    """Strip an optional leading ``lod{N}_`` prefix (case-insensitive)."""
    return _LOD_PREFIX_RE.sub("", name)


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


def _set_envelope(model: CityModel, envelope: Envelope) -> None:
    model.xsd.opengis_net_gml_bounded_by = BoundedBy(envelope=envelope)


def _compute_envelope(
    coordinates: list[Coord3D],
    *,
    srs_name: str,
    srs_dimension: int,
) -> Envelope:
    xs, ys, zs = zip(*coordinates, strict=True)
    return Envelope(
        lower_corner=DirectPositionType(
            value=[min(xs), min(ys), min(zs)], srs_dimension=srs_dimension
        ),
        upper_corner=DirectPositionType(
            value=[max(xs), max(ys), max(zs)], srs_dimension=srs_dimension
        ),
        srs_name=srs_name,
        srs_dimension=srs_dimension,
    )


# ---------------------------------------------------------------------------
# Construction mapping helpers
# ---------------------------------------------------------------------------


def _make_construction_ref(construction_id: str) -> LayeredConstruction2:
    return LayeredConstruction2(href=f"#{construction_id}")


def _layered_construction_list(obj: Any) -> list[Any] | None:
    """Return the ``layered_construction`` list on *obj* if present."""
    info = get_fields(type(obj)).get("layered_construction")
    if info is None or not info.is_list:
        return None
    value = getattr(obj, "layered_construction", None)
    return value if isinstance(value, list) else None


def _resolve_construction_id(
    obj: Any,
    by_id: dict[str, str],
    by_type: dict[str, str],
) -> str | None:
    gml_id = getattr(obj, "id", None)
    if isinstance(gml_id, str) and gml_id in by_id:
        return by_id[gml_id]
    type_name = _xsd_type_name(type(obj))
    if type_name and type_name in by_type:
        return by_type[type_name]
    return None


def _xsd_type_name(cls: type) -> str | None:
    """Return the class's XSD element name (``Meta.name`` or class name)."""
    meta = getattr(cls, "Meta", None)
    if meta is None:
        return None
    return getattr(meta, "name", None) or cls.__name__


# ---------------------------------------------------------------------------
# Feature lookup
# ---------------------------------------------------------------------------


def _require_feature(model: CityModel, gml_id: str, expected_type: type[Any]) -> Any:
    """Locate a feature by ``gml:id`` and assert its xsdata class."""
    match = find_by_id(model.xsd, gml_id)
    if match is None:
        raise ValueError(f"Feature {gml_id!r} was not found in the generated city model")
    if not isinstance(match, expected_type):
        raise ValueError(f"Feature {gml_id!r} exists but is not a {expected_type.__name__}")
    return match


def _make_city_object_ref(gml_id: str) -> AbstractCityObjectPropertyType:
    return AbstractCityObjectPropertyType(href=f"#{gml_id}")


# ---------------------------------------------------------------------------
# GML geometry builders
# ---------------------------------------------------------------------------


def _build_multi_surface(
    gml_id: str,
    polygons: list[GeometryPolygon],
    *,
    srs_name: str,
    srs_dimension: int,
) -> MultiSurfacePropertyType:
    members: list[SurfaceMember] = []
    for index, polygon_geometry in enumerate(polygons, start=1):
        polygon_id = f"{gml_id}_poly_{index}"
        members.append(SurfaceMember(polygon=_build_polygon(polygon_id, polygon_geometry)))

    return MultiSurfacePropertyType(
        multi_surface=MultiSurface(
            id=gml_id,
            srs_name_attribute=srs_name,
            srs_dimension=srs_dimension,
            surface_member=members,
        ),
    )


def _build_solid(
    gml_id: str,
    polygons: list[GeometryPolygon],
    *,
    srs_name: str,
    srs_dimension: int,
) -> SolidPropertyType:
    """Build a ``gml:Solid`` whose exterior shell is a ``CompositeSurface``.

    Polygons are re-oriented outward before assembly: shared surfaces
    between adjacent zones often arrive with inward-facing normals
    because they were authored from the neighbouring zone's perspective.
    """
    oriented = _orient_solid_polygons(polygons)

    members: list[SurfaceMember] = []
    for index, polygon_geometry in enumerate(oriented, start=1):
        polygon_id = f"{gml_id}_poly_{index}"
        members.append(SurfaceMember(polygon=_build_polygon(polygon_id, polygon_geometry)))

    return SolidPropertyType(
        solid=Solid(
            id=gml_id,
            srs_name_attribute=srs_name,
            srs_dimension=srs_dimension,
            exterior=SurfacePropertyType(
                composite_surface=CompositeSurface(
                    id=f"{gml_id}_shell",
                    surface_member=members,
                ),
            ),
        ),
    )


def _build_polygon(polygon_id: str, polygon_geometry: GeometryPolygon) -> Polygon:
    exterior = Exterior(
        linear_ring=LinearRing(
            pos_list=PosList(value=_flatten_ring(polygon_geometry.exterior)),
        ),
    )
    interiors: list[Interior] = [
        Interior(
            linear_ring=LinearRing(
                pos_list=PosList(value=_flatten_ring(interior_geometry)),
            ),
        )
        for interior_geometry in polygon_geometry.interiors
    ]
    return Polygon(id=polygon_id, exterior=exterior, interior=interiors)


def _flatten_ring(ring: list[Coord3D]) -> list[float]:
    """Close a ring (first == last) and flatten into ``gml:posList`` floats."""
    if not ring:
        raise ValueError("Geometry rings must contain at least one coordinate")
    coordinates = list(ring)
    if not points_close(coordinates[0], coordinates[-1]):
        coordinates.append(coordinates[0])
    return [value for coord in coordinates for value in coord]


def _orient_solid_polygons(polygons: list[GeometryPolygon]) -> list[GeometryPolygon]:
    """Ensure exterior-ring normals point outward from the solid's centroid."""
    exterior_vertices = [_open_ring(polygon.exterior) for polygon in polygons]

    all_vertices = [v for ring in exterior_vertices for v in ring]
    if not all_vertices:
        return polygons

    centroid = _mean_point(all_vertices)

    oriented: list[GeometryPolygon] = []
    for polygon, vertices in zip(polygons, exterior_vertices, strict=True):
        normal = _newell_normal(vertices)
        center = _mean_point(vertices)
        dot = (
            normal[0] * (center[0] - centroid[0])
            + normal[1] * (center[1] - centroid[1])
            + normal[2] * (center[2] - centroid[2])
        )
        if dot < 0:
            oriented.append(
                GeometryPolygon(
                    exterior=list(reversed(polygon.exterior)),
                    interiors=[list(reversed(i)) for i in polygon.interiors],
                )
            )
        else:
            oriented.append(polygon)

    return oriented


def _newell_normal(vertices: list[Coord3D]) -> Coord3D:
    nx, ny, nz = 0.0, 0.0, 0.0
    count = len(vertices)
    for i in range(count):
        curr = vertices[i]
        nxt = vertices[(i + 1) % count]
        nx += (curr[1] - nxt[1]) * (curr[2] + nxt[2])
        ny += (curr[2] - nxt[2]) * (curr[0] + nxt[0])
        nz += (curr[0] - nxt[0]) * (curr[1] + nxt[1])
    return (nx, ny, nz)


def _mean_point(points: list[Coord3D]) -> Coord3D:
    n = len(points)
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


# Legacy aliases — the previous geometry module exposed these lower-level
# entry points; keep them importable so external scripts continue to work.
def apply_step_geometry(
    model: CityModel,
    *,
    step_path: Path,
    target_building_id: str,
    target_pv_id: str | None,
    lod_level: int = 3,
    type_counters: dict[tuple[str, str], int] | None = None,
    origin: Coord3D = (0.0, 0.0, 0.0),
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
) -> list[Coord3D]:
    """Attach STEP-derived geometry to an existing building.

    Thin wrapper around :func:`apply_geometry_sources`' building handler,
    kept for backward compatibility with pre-refactor callers.
    """
    spec = GEOMETRY_SOURCE_SPECS.get(f"step-renodat-lod{lod_level}")
    if spec is None:
        raise ValueError(f"No geometry-source spec registered for LOD {lod_level}")
    source = {
        "type": spec.source_type,
        "path": str(step_path),
        "target_building_id": target_building_id,
        "target_pv_id": target_pv_id,
    }
    return _apply_building_source(
        model,
        spec=spec,
        step_path=step_path,
        source=source,
        type_counters=type_counters if type_counters is not None else {},
        origin=origin,
        srs_name=srs_name,
        srs_dimension=srs_dimension,
    )


def apply_step_zonepart_geometry(
    model: CityModel,
    *,
    step_path: Path,
    target_zone_part_id: str,
    lod_level: int = 0,
    origin: Coord3D = (0.0, 0.0, 0.0),
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
) -> list[Coord3D]:
    """Attach STEP-derived volume geometry to a ZonePart."""
    spec = GEOMETRY_SOURCE_SPECS.get(f"step-zonepart-lod{lod_level}")
    if spec is None:
        raise ValueError(f"No geometry-source spec registered for zonepart LOD {lod_level}")
    source = {
        "type": spec.source_type,
        "path": str(step_path),
        "target_zone_part_id": target_zone_part_id,
    }
    return _apply_zonepart_source(
        model,
        spec=spec,
        step_path=step_path,
        source=source,
        origin=origin,
        srs_name=srs_name,
        srs_dimension=srs_dimension,
    )


__all__ = [
    "DEFAULT_SRS_DIMENSION",
    "DEFAULT_SRS_NAME",
    "GEOMETRY_SOURCE_SPECS",
    "SUPPORTED_GEOMETRY_SOURCE_TYPES",
    "GeometrySourceSpec",
    "TargetFieldSpec",
    "apply_construction_mapping",
    "apply_geometry_sources",
    "apply_step_geometry",
    "apply_step_zonepart_geometry",
]
