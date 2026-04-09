"""Import RenoDAT-style LOD3 STEP geometry into typed CityGML builders."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import lxml.etree as etree

from .building import Building, Door, GroundSurface, RoofSurface, WallSurface, Window
from .core import CityModel, Envelope
from .energy_ade import CityObjectRelation, PhotovoltaicCollector
from .namespaces import CS_NRG3_RELATION_TYPE, NS_GML, qn
from .types import CodeValue
from .xml_support import RawXmlElement

_STEP_GEOMETRY_SOURCE_TYPE = "step-renodat-lod3"
_SOLAR_PANEL_PREFIX = "SolarPanelSurface_"

DEFAULT_SRS_NAME = "urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109"
DEFAULT_SRS_DIMENSION = 3

_STEP_ENTITY_RE = re.compile(
    r"^#(?P<entity_id>\d+)\s*=\s*(?P<entity_type>[A-Z0-9_]+)\((?P<args>.*)\);$",
    re.DOTALL,
)

Coord3D = tuple[float, float, float]

_SURFACE_NAME_PREFIXES = {
    "GroundSurface_": GroundSurface,
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

    for source in geometry_sources:
        source_type = source.get("type")
        target_pv_id = (
            str(source["target_pv_id"]) if source.get("target_pv_id") is not None else None
        )

        if source_type == _STEP_GEOMETRY_SOURCE_TYPE:
            coords = apply_step_geometry(
                model,
                step_path=Path(str(source["path"])),
                target_building_id=str(source["target_building_id"]),
                target_pv_id=target_pv_id,
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
) -> list[Coord3D]:
    """Attach STEP-derived semantic geometry to an existing building and PV collector.

    Returns all coordinates encountered for bounding box computation.
    """
    parsed_features = _parse_step_file(step_path)
    return _attach_geometry_features(
        model,
        parsed_features,
        source_path=step_path,
        target_building_id=target_building_id,
        target_pv_id=target_pv_id,
    )


def _compute_envelope(coordinates: list[Coord3D]) -> Envelope:
    xs = [c[0] for c in coordinates]
    ys = [c[1] for c in coordinates]
    zs = [c[2] for c in coordinates]
    return Envelope(
        srs_name=DEFAULT_SRS_NAME,
        srs_dimension=DEFAULT_SRS_DIMENSION,
        lower_corner=f"{min(xs):.6f} {min(ys):.6f} {min(zs):.6f}",
        upper_corner=f"{max(xs):.6f} {max(ys):.6f} {max(zs):.6f}",
    )


def _attach_geometry_features(
    model: CityModel,
    features: Iterable[_ParsedGeometryFeature],
    *,
    source_path: Path,
    target_building_id: str,
    target_pv_id: str | None,
) -> list[Coord3D]:
    building = _require_feature(model, target_building_id, Building)

    surface_index: dict[str, Any] = {}
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
            if feature.object_name in surface_index:
                raise ValueError(
                    f"Geometry source {source_path} contains duplicate surface name {feature.object_name!r}"
                )

            multi_surface, _polygon_ids = _build_multi_surface(
                f"{feature.object_name}_lod3",
                feature.polygons,
            )
            surface = feature.element_cls(
                gml_id=feature.object_name,
                gml_name=feature.object_name,
                lod3_multi_surface=multi_surface,
            )
            building.bounded_by_surfaces.append(surface)
            surface_index[feature.object_name] = surface
            continue

        if feature.kind == _FEATURE_KIND_OPENING:
            pending_openings.append(feature)
            continue

        raise ValueError(
            f"Geometry source {source_path} produced unsupported feature kind {feature.kind!r}"
        )

    for feature in pending_openings:
        if not feature.parent_name:
            raise ValueError(
                f"Opening {feature.object_name!r} in {source_path} is missing a parent=... tag"
            )

        parent_surface = surface_index.get(feature.parent_name)
        if parent_surface is None:
            raise ValueError(
                f"Opening {feature.object_name!r} in {source_path} references unknown parent "
                f"surface {feature.parent_name!r}"
            )

        if feature.element_cls is None:
            raise ValueError(
                f"Geometry source {source_path} produced an opening without a builder class"
            )

        multi_surface, _ = _build_multi_surface(
            f"{feature.object_name}_lod3",
            feature.polygons,
        )
        parent_surface.openings.append(
            feature.element_cls(
                gml_id=feature.object_name,
                gml_name=feature.object_name,
                lod3_multi_surface=multi_surface,
            )
        )

    if solar_panel_polygons:
        if target_pv_id is None:
            raise ValueError(
                f"Geometry source {source_path} contains solar panel faces but no target_pv_id was configured"
            )

        pv_collector = _require_feature(model, target_pv_id, PhotovoltaicCollector)
        pv_collector.lod3_multi_surface = _build_multi_surface(
            f"{target_pv_id}_lod3",
            solar_panel_polygons,
        )[0]

        for roof_name in sorted(solar_panel_roof_parents):
            roof_surface = surface_index.get(roof_name)
            if roof_surface is not None:
                pv_collector.nrg3_related_to.append(
                    CityObjectRelation(
                        relation_type=CodeValue(
                            value="installedOn",
                            code_space=CS_NRG3_RELATION_TYPE,
                        ),
                        related_to_href=f"#{roof_name}",
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
            for face_ref in _parse_step_ref_list(shell_entity.args[1]):
                polygons.append(_parse_step_face(path, entities, face_ref))

        features.append(
            _build_step_geometry_feature(
                path,
                object_name=object_name,
                parent_name=parent_name,
                polygons=polygons,
            )
        )

    return features


def _build_step_geometry_feature(
    path: Path,
    *,
    object_name: str,
    parent_name: str | None,
    polygons: list[_GeometryPolygon],
) -> _ParsedGeometryFeature:
    if object_name.startswith(_SOLAR_PANEL_PREFIX):
        return _ParsedGeometryFeature(
            object_name=object_name,
            parent_name=parent_name,
            kind=_FEATURE_KIND_SOLAR,
            element_cls=None,
            polygons=polygons,
        )

    for prefix, surface_cls in _SURFACE_NAME_PREFIXES.items():
        if object_name.startswith(prefix):
            return _ParsedGeometryFeature(
                object_name=object_name,
                parent_name=parent_name,
                kind=_FEATURE_KIND_SURFACE,
                element_cls=surface_cls,
                polygons=polygons,
            )

    for prefix, opening_cls in _OPENING_NAME_PREFIXES.items():
        if object_name.startswith(prefix):
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
