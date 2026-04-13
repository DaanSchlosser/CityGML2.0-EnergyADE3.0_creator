"""Import STEP geometry into typed CityGML builders."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

from .building import (
    Building,
    CeilingSurface,
    ClosureSurface,
    Door,
    FloorSurface,
    GroundSurface,
    OuterCeilingSurface,
    OuterFloorSurface,
    RoofSurface,
    WallSurface,
    Window,
    Zone,
)
from .core import CityModel, Envelope
from .energy_ade import CityObjectRelation, PhotovoltaicCollector
from .types import XlinkRef
from .namespaces import CS_NRG3_RELATION_TYPE, NS_GML, qn
from .types import CodeValue
from .xml_support import RawXmlElement

_STEP_GEOMETRY_SOURCE_TYPE_RE = re.compile(r"^step-renodat-lod([0-4])$")
_STEP_ZONEPART_TYPE_RE = re.compile(r"^step-zonepart-lod([0-3])$")
_LOD_PREFIX_RE = re.compile(r"^lod\d+(?:\.\d+)?_", re.IGNORECASE)
_SOLAR_PANEL_PREFIX = "SolarPanelSurface_"

DEFAULT_SRS_NAME = "urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109"
DEFAULT_SRS_DIMENSION = 3

_STEP_ENTITY_RE = re.compile(
    r"^#(?P<entity_id>\d+)\s*=\s*(?P<entity_type>[A-Z0-9_]+)\((?P<args>.*)\);$",
    re.DOTALL,
)

Coord3D = tuple[float, float, float]

_SURFACE_NAME_PREFIXES = {
    "CeilingSurface_": CeilingSurface,
    "ClosureSurface_": ClosureSurface,
    "FloorSurface_": FloorSurface,
    "GroundSurface_": GroundSurface,
    "OuterCeilingSurface_": OuterCeilingSurface,
    "OuterFloorSurface_": OuterFloorSurface,
    "RoofSurface_": RoofSurface,
    "WallSurface_": WallSurface,
}

_OPENING_NAME_PREFIXES = {
    "Door_": Door,
    "Window_": Window,
}

_NESTED_CHILD_LISTS = (
    "devices",
    "bounded_by_surfaces",
    "openings",
    "building_parts",
    "interior_rooms",
    "outer_building_installations",
    "interior_building_installations",
    "building_units",
    "occupied_by",
    "energy_performance_certificates",
    "zones",
    "zone_parts",
)

_FEATURE_KIND_SURFACE = "surface"
_FEATURE_KIND_OPENING = "opening"
_FEATURE_KIND_SOLAR = "solar"

_ZERO_THRESHOLD = 1e-10


@dataclass(frozen=True)
class _GeometryPolygon:
    exterior: list[Coord3D]
    interiors: list[list[Coord3D]] = field(default_factory=list)


@dataclass(frozen=True)
class _ParsedGeometryFeature:
    object_name: str
    parent_name: str | None
    kind: str
    element_cls: type[Any] | None
    polygons: list[_GeometryPolygon]


@dataclass(frozen=True)
class _StepEntity:
    entity_type: str
    args: list[str]


def apply_geometry_sources(model: CityModel, geometry_sources: Iterable[dict[str, Any]]) -> None:
    """Apply all configured geometry sources to *model* in place."""
    all_coordinates: list[Coord3D] = []

    # Shared ID counters across geometry sources so that surfaces created
    # at different LOD levels for the same building get unique gml_ids.
    type_counters: dict[tuple[str, str], int] = {}

    for source in geometry_sources:
        source_type = source.get("type")

        lod_match = _STEP_GEOMETRY_SOURCE_TYPE_RE.match(source_type or "")
        if lod_match:
            target_pv_id = (
                str(source["target_pv_id"]) if source.get("target_pv_id") is not None else None
            )
            lod_level = int(lod_match.group(1))
            coords = apply_step_geometry(
                model,
                step_path=Path(str(source["path"])),
                target_building_id=str(source["target_building_id"]),
                target_pv_id=target_pv_id,
                lod_level=lod_level,
                type_counters=type_counters,
            )
            all_coordinates.extend(coords)
            continue

        zonepart_match = _STEP_ZONEPART_TYPE_RE.match(source_type or "")
        if zonepart_match:
            lod_level = int(zonepart_match.group(1))
            coords = apply_step_zonepart_geometry(
                model,
                step_path=Path(str(source["path"])),
                target_zone_part_id=str(source["target_zone_part_id"]),
                lod_level=lod_level,
            )
            all_coordinates.extend(coords)
            continue

        raise ValueError(f"Unsupported geometry source type: {source_type!r}")

    if all_coordinates:
        model.envelope = _compute_envelope(all_coordinates)


def apply_step_geometry(
    model: CityModel,
    *,
    step_path: Path,
    target_building_id: str,
    target_pv_id: str | None,
    lod_level: int = 3,
    type_counters: dict[tuple[str, str], int] | None = None,
) -> list[Coord3D]:
    """Attach STEP-derived geometry to an existing building.

    * **LOD 0–1** — aggregate geometry placed directly on the Building
      (``lod0FootPrint`` as MultiSurface, ``lod1Solid`` as Solid).
    * **LOD 2–4** — individual thematic surfaces attached via ``boundedBy``.

    Returns all coordinates encountered for bounding box computation.
    """
    if lod_level <= 1:
        return _apply_aggregate_building_geometry(
            model,
            step_path=step_path,
            target_building_id=target_building_id,
            lod_level=lod_level,
        )

    parsed_features = _parse_step_file(step_path)
    return _attach_geometry_features(
        model,
        parsed_features,
        source_path=step_path,
        target_building_id=target_building_id,
        target_pv_id=target_pv_id,
        lod_level=lod_level,
        type_counters=type_counters if type_counters is not None else {},
    )


def apply_step_zonepart_geometry(
    model: CityModel,
    *,
    step_path: Path,
    target_zone_part_id: str,
    lod_level: int = 0,
) -> list[Coord3D]:
    """Attach STEP-derived volume geometry to a Zone or ZonePart.

    All STEP shells in the file are collected into a single geometry:

    * **lod0** → ``lod0MultiSurface`` (gml:MultiSurface)
    * **lod1–3** → ``lod{N}Solid`` (gml:Solid with a CompositeSurface shell)

    Returns all coordinates encountered for bounding-box computation.
    """
    all_polygons, all_coordinates = _collect_all_step_polygons(step_path)

    if not all_polygons:
        raise ValueError(f"STEP geometry {step_path} contains no polygon geometry")

    zone = _require_feature(model, target_zone_part_id, Zone)
    gml_id = f"{target_zone_part_id}_lod{lod_level}"

    if lod_level == 0:
        multi_surface, _ = _build_multi_surface(gml_id, all_polygons)
        zone.lod0_multi_surface = multi_surface
    else:
        solid = _build_solid(gml_id, all_polygons)
        setattr(zone, f"lod{lod_level}_solid", solid)

    return all_coordinates


def _apply_aggregate_building_geometry(
    model: CityModel,
    *,
    step_path: Path,
    target_building_id: str,
    lod_level: int,
) -> list[Coord3D]:
    """Attach aggregate LOD0/LOD1 geometry directly to a Building.

    * **LOD 0** → ``lod0FootPrint`` as ``gml:MultiSurface``
    * **LOD 1** → ``lod1Solid`` as ``gml:Solid``
    """
    all_polygons, all_coordinates = _collect_all_step_polygons(step_path)

    if not all_polygons:
        raise ValueError(f"STEP geometry {step_path} contains no polygon geometry")

    building = _require_feature(model, target_building_id, Building)
    gml_id = f"{target_building_id}_lod{lod_level}"

    if lod_level == 0:
        multi_surface, _ = _build_multi_surface(gml_id, all_polygons)
        building.lod0_foot_print = multi_surface
    elif lod_level == 1:
        solid = _build_solid(gml_id, all_polygons)
        building.lod1_solid = solid

    return all_coordinates


def _compute_envelope(coordinates: list[Coord3D]) -> Envelope:
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    for x, y, z in coordinates:
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
        if z < min_z:
            min_z = z
        if z > max_z:
            max_z = z
    return Envelope(
        srs_name=DEFAULT_SRS_NAME,
        srs_dimension=DEFAULT_SRS_DIMENSION,
        lower_corner=f"{min_x:.6f} {min_y:.6f} {min_z:.6f}",
        upper_corner=f"{max_x:.6f} {max_y:.6f} {max_z:.6f}",
    )


def _attach_geometry_features(
    model: CityModel,
    features: Iterable[_ParsedGeometryFeature],
    *,
    source_path: Path,
    target_building_id: str,
    target_pv_id: str | None,
    lod_level: int = 3,
    type_counters: dict[tuple[str, str], int],
) -> list[Coord3D]:
    """Attach parsed STEP geometry features to a building.

    IDs are auto-generated from *target_building_id* and a per-type counter
    (shared across LOD levels via *type_counters* to avoid collisions).
    Each LOD level creates its own set of ``boundedBy`` entries — no merging
    across LODs, following the Alderaan reference pattern.
    Opening-to-surface relations are derived geometrically by matching the
    opening's exterior ring vertices to interior rings (holes) in surfaces.
    """
    building = _require_feature(model, target_building_id, Building)
    lod_field = f"lod{lod_level}_multi_surface"

    # step_name → (surface instance, polygons at this LOD, gml_id)
    surface_data: dict[str, tuple[Any, list[_GeometryPolygon], str]] = {}

    pending_openings: list[_ParsedGeometryFeature] = []
    solar_panel_polygons: list[_GeometryPolygon] = []
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
            if feature.element_cls is None:
                raise ValueError(
                    f"Geometry source {source_path} produced a surface without a builder class"
                )

            type_name = feature.element_cls.__name__
            counter_key = (target_building_id, type_name)
            type_counters[counter_key] = type_counters.get(counter_key, 0) + 1
            gml_id = f"{target_building_id}_{type_name}_{type_counters[counter_key]}"

            multi_surface, _ = _build_multi_surface(
                f"{gml_id}_lod{lod_level}",
                feature.polygons,
            )
            surface = feature.element_cls(
                gml_id=gml_id,
                **{lod_field: multi_surface},
            )
            building.bounded_by_surfaces.append(surface)
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
        if feature.element_cls is None:
            raise ValueError(
                f"Geometry source {source_path} produced an opening without a builder class"
            )

        parent_step_name = _match_opening_to_parent(feature, surface_data)
        if parent_step_name is None:
            raise ValueError(
                f"Opening in {source_path} could not be matched to any parent "
                f"surface by interior-ring geometry"
            )

        parent_surface = surface_data[parent_step_name][0]

        type_name = feature.element_cls.__name__
        counter_key = (target_building_id, type_name)
        type_counters[counter_key] = type_counters.get(counter_key, 0) + 1
        gml_id = f"{target_building_id}_{type_name}_{type_counters[counter_key]}"

        multi_surface, _ = _build_multi_surface(
            f"{gml_id}_lod{lod_level}",
            feature.polygons,
        )
        parent_surface.openings.append(
            feature.element_cls(
                gml_id=gml_id,
                **{lod_field: multi_surface},
            )
        )

    if solar_panel_polygons:
        if target_pv_id is None:
            raise ValueError(
                f"Geometry source {source_path} contains solar panel faces but no target_pv_id was configured"
            )

        pv_collector = _require_feature(model, target_pv_id, PhotovoltaicCollector)
        setattr(
            pv_collector,
            lod_field,
            _build_multi_surface(
                f"{target_pv_id}_lod{lod_level}",
                solar_panel_polygons,
            )[0],
        )

        for roof_step_name in sorted(solar_panel_roof_parents):
            entry = surface_data.get(roof_step_name)
            if entry is not None:
                pv_collector.nrg3_related_to.append(
                    CityObjectRelation(
                        relation_type=CodeValue(
                            value="installedOn",
                            code_space=CS_NRG3_RELATION_TYPE,
                        ),
                        related_to=XlinkRef(f"#{entry[2]}"),
                    )
                )
    elif target_pv_id is not None:
        raise ValueError(
            f"Geometry source {source_path} configured target_pv_id={target_pv_id!r} but no solar panel faces were found"
        )

    return all_coordinates


def _parse_step_file(path: Path) -> list[_ParsedGeometryFeature]:
    entities = _parse_step_entities(path)
    features: list[_ParsedGeometryFeature] = []

    for entity_id in sorted(entities):
        entity = entities[entity_id]
        if entity.entity_type != "SHELL_BASED_SURFACE_MODEL":
            continue

        object_name, parent_name = _split_object_name(_unquote_step_string(entity.args[0]))
        shell_refs = _parse_step_ref_list(entity.args[1])
        polygons: list[_GeometryPolygon] = []

        for shell_ref in shell_refs:
            shell_entity = _require_step_entity(
                entities,
                shell_ref,
                expected_type="OPEN_SHELL",
                source_path=path,
            )
            polygons.extend(
                _parse_step_face(path, entities, face_ref)
                for face_ref in _parse_step_ref_list(shell_entity.args[1])
            )

        features.append(
            _build_step_geometry_feature(
                path,
                object_name=object_name,
                parent_name=parent_name,
                polygons=polygons,
            )
        )

    return features


def _strip_lod_prefix(name: str) -> str:
    """Strip an optional leading ``lod{N}_`` prefix (case-insensitive)."""
    return _LOD_PREFIX_RE.sub("", name)


def _build_step_geometry_feature(
    path: Path,
    *,
    object_name: str,
    parent_name: str | None,
    polygons: list[_GeometryPolygon],
) -> _ParsedGeometryFeature:
    # Strip optional LoD prefix (e.g. "lod3_WallSurface_1" → "WallSurface_1")
    # so classification works regardless of LoD-level layer naming.
    classified_name = _strip_lod_prefix(object_name)

    if classified_name.startswith(_SOLAR_PANEL_PREFIX):
        return _ParsedGeometryFeature(
            object_name=object_name,
            parent_name=parent_name,
            kind=_FEATURE_KIND_SOLAR,
            element_cls=None,
            polygons=polygons,
        )

    for prefix, surface_cls in _SURFACE_NAME_PREFIXES.items():
        if classified_name.startswith(prefix):
            return _ParsedGeometryFeature(
                object_name=object_name,
                parent_name=parent_name,
                kind=_FEATURE_KIND_SURFACE,
                element_cls=surface_cls,
                polygons=polygons,
            )

    for prefix, opening_cls in _OPENING_NAME_PREFIXES.items():
        if classified_name.startswith(prefix):
            return _ParsedGeometryFeature(
                object_name=object_name,
                parent_name=parent_name,
                kind=_FEATURE_KIND_OPENING,
                element_cls=opening_cls,
                polygons=polygons,
            )

    raise ValueError(f"STEP geometry {path} contains unsupported shell name {object_name!r}")


def _parse_step_face(
    path: Path,
    entities: dict[int, _StepEntity],
    face_ref: int,
) -> _GeometryPolygon:
    face_entity = _require_step_entity(
        entities,
        face_ref,
        expected_type="ADVANCED_FACE",
        source_path=path,
    )
    bound_refs = _parse_step_ref_list(face_entity.args[1])

    exterior: list[Coord3D] | None = None
    interiors: list[list[Coord3D]] = []

    for bound_ref in bound_refs:
        bound_entity = _require_step_entity(
            entities,
            bound_ref,
            expected_type=None,
            source_path=path,
        )
        loop_ref = _parse_step_ref(bound_entity.args[1])
        ring = _parse_step_loop(path, entities, loop_ref)

        if bound_entity.entity_type == "FACE_OUTER_BOUND":
            exterior = ring
            continue

        if bound_entity.entity_type == "FACE_BOUND":
            interiors.append(ring)
            continue

        raise ValueError(
            f"STEP geometry {path} face #{face_ref} references unsupported bound type "
            f"{bound_entity.entity_type!r}"
        )

    if exterior is None:
        raise ValueError(f"STEP geometry {path} face #{face_ref} is missing an outer loop")

    return _GeometryPolygon(exterior=exterior, interiors=interiors)


def _parse_step_loop(
    path: Path,
    entities: dict[int, _StepEntity],
    loop_ref: int,
) -> list[Coord3D]:
    loop_entity = _require_step_entity(
        entities,
        loop_ref,
        expected_type="EDGE_LOOP",
        source_path=path,
    )
    oriented_edge_refs = _parse_step_ref_list(loop_entity.args[1])

    ring: list[Coord3D] = []
    for oriented_edge_ref in oriented_edge_refs:
        oriented_edge = _require_step_entity(
            entities,
            oriented_edge_ref,
            expected_type="ORIENTED_EDGE",
            source_path=path,
        )
        edge_curve_ref = _parse_step_ref(oriented_edge.args[3])
        orientation_is_forward = _parse_step_bool(oriented_edge.args[4])

        edge_curve = _require_step_entity(
            entities,
            edge_curve_ref,
            expected_type="EDGE_CURVE",
            source_path=path,
        )
        start_point = _get_step_vertex_coordinates(
            path,
            entities,
            _parse_step_ref(edge_curve.args[1]),
        )
        end_point = _get_step_vertex_coordinates(
            path,
            entities,
            _parse_step_ref(edge_curve.args[2]),
        )

        if not orientation_is_forward:
            start_point, end_point = end_point, start_point

        if not ring:
            ring.append(start_point)
        elif not _points_close(ring[-1], start_point):
            if _points_close(ring[-1], end_point):
                start_point, end_point = end_point, start_point
            else:
                raise ValueError(
                    f"STEP geometry {path} contains a non-contiguous loop at edge #{oriented_edge_ref}"
                )

        ring.append(end_point)

    if not ring:
        raise ValueError(f"STEP geometry {path} contains an empty edge loop #{loop_ref}")

    if not _points_close(ring[0], ring[-1]):
        ring.append(ring[0])

    return ring


def _parse_step_entities(path: Path) -> dict[int, _StepEntity]:
    entities: dict[int, _StepEntity] = {}
    in_data_section = False
    current_parts: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "DATA;":
            in_data_section = True
            continue
        if not in_data_section:
            continue
        if line == "ENDSEC;":
            break
        if line.startswith("/*"):
            continue

        current_parts.append(line)
        if not line.endswith(";"):
            continue

        entity_text = " ".join(current_parts)
        current_parts.clear()
        match = _STEP_ENTITY_RE.match(entity_text)
        if match is None:
            continue

        entity_id = int(match.group("entity_id"))
        entity_type = match.group("entity_type")
        args = _split_step_args(match.group("args"))
        entities[entity_id] = _StepEntity(entity_type=entity_type, args=args)

    return entities


def _split_step_args(raw_args: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    index = 0

    while index < len(raw_args):
        char = raw_args[index]
        if char == "'":
            current.append(char)
            if in_string and index + 1 < len(raw_args) and raw_args[index + 1] == "'":
                current.append("'")
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue

        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                args.append("".join(current).strip())
                current.clear()
                index += 1
                continue

        current.append(char)
        index += 1

    if current:
        args.append("".join(current).strip())

    return args


def _parse_step_ref(token: str) -> int:
    if not token.startswith("#"):
        raise ValueError(f"Expected STEP reference, received {token!r}")
    return int(token[1:])


def _parse_step_ref_list(token: str) -> list[int]:
    stripped = token.strip()
    if not stripped.startswith("(") or not stripped.endswith(")"):
        raise ValueError(f"Expected STEP reference list, received {token!r}")

    inner = stripped[1:-1].strip()
    if not inner:
        return []

    return [_parse_step_ref(part.strip()) for part in _split_step_args(inner)]


def _parse_step_bool(token: str) -> bool:
    normalized = token.strip().upper()
    if normalized == ".T.":
        return True
    if normalized == ".F.":
        return False
    raise ValueError(f"Expected STEP boolean, received {token!r}")


def _unquote_step_string(token: str) -> str:
    stripped = token.strip()
    if stripped == "$":
        return ""
    if len(stripped) >= 2 and stripped[0] == "'" and stripped[-1] == "'":
        return stripped[1:-1].replace("''", "'")
    return stripped


def _require_step_entity(
    entities: dict[int, _StepEntity],
    entity_id: int,
    *,
    expected_type: str | None,
    source_path: Path,
) -> _StepEntity:
    try:
        entity = entities[entity_id]
    except KeyError as exc:
        raise ValueError(
            f"STEP geometry {source_path} is missing referenced entity #{entity_id}"
        ) from exc

    if expected_type is not None and entity.entity_type != expected_type:
        raise ValueError(
            f"STEP geometry {source_path} entity #{entity_id} is {entity.entity_type!r}, "
            f"expected {expected_type!r}"
        )

    return entity


def _get_step_vertex_coordinates(
    path: Path,
    entities: dict[int, _StepEntity],
    vertex_ref: int,
) -> Coord3D:
    vertex_entity = _require_step_entity(
        entities,
        vertex_ref,
        expected_type="VERTEX_POINT",
        source_path=path,
    )
    point_entity = _require_step_entity(
        entities,
        _parse_step_ref(vertex_entity.args[1]),
        expected_type="CARTESIAN_POINT",
        source_path=path,
    )
    coordinate_values = point_entity.args[1].strip()
    if not coordinate_values.startswith("(") or not coordinate_values.endswith(")"):
        raise ValueError(f"STEP geometry {path} point #{vertex_ref} has invalid coordinates")

    parts = [part.strip() for part in coordinate_values[1:-1].split(",")]
    if len(parts) != 3:
        raise ValueError(f"STEP geometry {path} point #{vertex_ref} does not contain 3 coordinates")

    return (float(parts[0]), float(parts[1]), float(parts[2]))


def _split_object_name(raw_name: str) -> tuple[str, str | None]:
    parent_name: str | None = None
    object_name = raw_name

    for fragment in raw_name.split("|"):
        if fragment.startswith("parent="):
            parent_name = fragment.split("=", 1)[1] or None
            continue
        object_name = fragment

    return object_name, parent_name


def _build_multi_surface(
    gml_id: str,
    polygons: list[_GeometryPolygon],
) -> tuple[RawXmlElement, list[str]]:
    multi_surface = etree.Element(qn("gml", "MultiSurface"))
    multi_surface.set(f"{{{NS_GML}}}id", gml_id)
    multi_surface.set("srsName", DEFAULT_SRS_NAME)
    multi_surface.set("srsDimension", str(DEFAULT_SRS_DIMENSION))
    polygon_ids: list[str] = []

    for index, polygon_geometry in enumerate(polygons, start=1):
        polygon_id = f"{gml_id}_poly_{index}"
        surface_member = etree.SubElement(multi_surface, qn("gml", "surfaceMember"))
        surface_member.append(_build_polygon_element(polygon_id, polygon_geometry))
        polygon_ids.append(polygon_id)

    return RawXmlElement.from_element(multi_surface), polygon_ids


def _build_solid(
    gml_id: str,
    polygons: list[_GeometryPolygon],
) -> RawXmlElement:
    """Build a ``gml:Solid`` whose exterior shell is a ``gml:CompositeSurface``.

    Polygons are re-oriented outward before assembly: shared surfaces between
    adjacent zones often arrive with inward-facing normals because they were
    authored from the neighboring zone's perspective.
    """
    oriented = _orient_solid_polygons(polygons)

    solid = etree.Element(qn("gml", "Solid"))
    solid.set(f"{{{NS_GML}}}id", gml_id)
    solid.set("srsName", DEFAULT_SRS_NAME)
    solid.set("srsDimension", str(DEFAULT_SRS_DIMENSION))

    exterior = etree.SubElement(solid, qn("gml", "exterior"))
    composite_surface = etree.SubElement(exterior, qn("gml", "CompositeSurface"))
    composite_surface.set(f"{{{NS_GML}}}id", f"{gml_id}_shell")

    for index, polygon_geometry in enumerate(oriented, start=1):
        polygon_id = f"{gml_id}_poly_{index}"
        surface_member = etree.SubElement(composite_surface, qn("gml", "surfaceMember"))
        surface_member.append(_build_polygon_element(polygon_id, polygon_geometry))

    return RawXmlElement.from_element(solid)


def _orient_solid_polygons(
    polygons: list[_GeometryPolygon],
) -> list[_GeometryPolygon]:
    """Return *polygons* with exterior-ring normals pointing outward.

    Each polygon's Newell-method normal is compared against a vector
    pointing away from the mean of all exterior vertices; polygons whose
    normals point inward get their vertex winding reversed.
    """
    exterior_vertices = [_open_ring(polygon.exterior) for polygon in polygons]

    all_vertices = [v for ring in exterior_vertices for v in ring]
    if not all_vertices:
        return polygons

    centroid = _mean_point(all_vertices)

    oriented: list[_GeometryPolygon] = []
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
                _GeometryPolygon(
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


def _open_ring(ring: list[Coord3D]) -> list[Coord3D]:
    if len(ring) > 1 and _points_close(ring[0], ring[-1]):
        return ring[:-1]
    return ring


def _collect_all_step_polygons(
    step_path: Path,
) -> tuple[list[_GeometryPolygon], list[Coord3D]]:
    """Collect all polygons from a STEP file regardless of shell naming.

    Handles both ``SHELL_BASED_SURFACE_MODEL`` (with ``OPEN_SHELL``) and
    ``MANIFOLD_SOLID_BREP`` (with ``CLOSED_SHELL``) entity types.

    Returns ``(polygons, coordinates)`` for bounding-box computation.
    """
    entities = _parse_step_entities(step_path)
    all_polygons: list[_GeometryPolygon] = []
    all_coordinates: list[Coord3D] = []

    for entity_id in sorted(entities):
        entity = entities[entity_id]

        if entity.entity_type == "SHELL_BASED_SURFACE_MODEL":
            shell_refs = _parse_step_ref_list(entity.args[1])
            for shell_ref in shell_refs:
                shell_entity = _require_step_entity(
                    entities,
                    shell_ref,
                    expected_type="OPEN_SHELL",
                    source_path=step_path,
                )
                for face_ref in _parse_step_ref_list(shell_entity.args[1]):
                    polygon = _parse_step_face(step_path, entities, face_ref)
                    all_polygons.append(polygon)
                    all_coordinates.extend(polygon.exterior)
                    for interior in polygon.interiors:
                        all_coordinates.extend(interior)
            continue

        if entity.entity_type == "MANIFOLD_SOLID_BREP":
            shell_ref = _parse_step_ref(entity.args[1])
            shell_entity = _require_step_entity(
                entities,
                shell_ref,
                expected_type="CLOSED_SHELL",
                source_path=step_path,
            )
            for face_ref in _parse_step_ref_list(shell_entity.args[1]):
                polygon = _parse_step_face(step_path, entities, face_ref)
                all_polygons.append(polygon)
                all_coordinates.extend(polygon.exterior)
                for interior in polygon.interiors:
                    all_coordinates.extend(interior)
            continue

    return all_polygons, all_coordinates


def _build_polygon_element(
    polygon_id: str,
    polygon_geometry: _GeometryPolygon,
) -> etree._Element:
    polygon = etree.Element(qn("gml", "Polygon"))
    polygon.set(f"{{{NS_GML}}}id", polygon_id)

    exterior = etree.SubElement(polygon, qn("gml", "exterior"))
    exterior_ring = etree.SubElement(exterior, qn("gml", "LinearRing"))
    exterior_pos_list = etree.SubElement(exterior_ring, qn("gml", "posList"))
    exterior_pos_list.text = _format_ring(polygon_geometry.exterior)

    for interior_geometry in polygon_geometry.interiors:
        interior = etree.SubElement(polygon, qn("gml", "interior"))
        interior_ring = etree.SubElement(interior, qn("gml", "LinearRing"))
        interior_pos_list = etree.SubElement(interior_ring, qn("gml", "posList"))
        interior_pos_list.text = _format_ring(interior_geometry)

    return polygon


def _format_ring(ring: list[Coord3D]) -> str:
    if not ring:
        raise ValueError("Geometry rings must contain at least one coordinate")

    coordinates = list(ring)
    if not _points_close(coordinates[0], coordinates[-1]):
        coordinates.append(coordinates[0])

    return " ".join(_format_coordinate(value) for coordinate in coordinates for value in coordinate)


def _points_close(first: Coord3D, second: Coord3D, tolerance: float = 1e-9) -> bool:
    return all(
        abs(a_value - b_value) <= tolerance for a_value, b_value in zip(first, second, strict=True)
    )


def _format_coordinate(value: float) -> str:
    if abs(value) < _ZERO_THRESHOLD:
        return "0"
    if value.is_integer():
        return str(int(value))
    formatted = f"{value:.15f}".rstrip("0").rstrip(".")
    return formatted


def _match_opening_to_parent(
    opening: _ParsedGeometryFeature,
    surface_data: dict[str, tuple[Any, list[_GeometryPolygon], str]],
) -> str | None:
    """Find the parent surface whose interior ring matches the opening's geometry.

    Returns the STEP object name of the matched surface, or ``None``.
    """
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
    """Create a hashable vertex set from a coordinate ring for comparison.

    Strips the closing vertex (if ring is closed) and rounds to *precision*
    decimals (default 4 → 0.1 mm) so that floating-point noise from shared
    STEP edges does not prevent matching.
    """
    return frozenset(
        (round(v[0], precision), round(v[1], precision), round(v[2], precision))
        for v in _open_ring(ring)
    )


def _require_feature(model: CityModel, gml_id: str, expected_type: type[Any]) -> Any:
    for member in model.city_object_members:
        match = _find_feature(member, gml_id)
        if match is not None:
            if not isinstance(match, expected_type):
                raise ValueError(f"Feature {gml_id!r} exists but is not a {expected_type.__name__}")
            return match

    raise ValueError(f"Feature {gml_id!r} was not found in the generated city model")


def _find_feature(feature: Any, gml_id: str) -> Any | None:
    if getattr(feature, "gml_id", None) == gml_id:
        return feature

    for attr_name in _NESTED_CHILD_LISTS:
        children = getattr(feature, attr_name, None)
        if not isinstance(children, list):
            continue
        for child in children:
            match = _find_feature(child, gml_id)
            if match is not None:
                return match

    return None
