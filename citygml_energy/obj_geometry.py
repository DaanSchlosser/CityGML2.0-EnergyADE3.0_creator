"""Import RenoDAT-style LOD3 OBJ geometry into typed CityGML builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from lxml import etree

from .building import Building, Door, GroundSurface, RoofSurface, WallSurface, Window
from .core import CityModel
from .energy_ade import PhotovoltaicCollector
from .namespaces import NS_GML, qn
from .xml_support import RawXmlElement

_OBJ_GEOMETRY_SOURCE_TYPE = "obj-renodat-lod3"
_SOLAR_PANEL_PREFIX = "SolarPanelSurface_"

_SURFACE_GROUPS = {
    "GroundSurface": GroundSurface,
    "RoofSurface": RoofSurface,
    "WallSurface": WallSurface,
    "nrg3_ZoneGroundSurface": GroundSurface,
    "nrg3_ZoneRoofSurface": RoofSurface,
    "nrg3_ZoneWallSurface": WallSurface,
}

_OPENING_GROUPS = {
    "Door": Door,
    "Window": Window,
    "nrg3_ZoneDoor": Door,
    "nrg3_ZoneWindow": Window,
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


@dataclass
class _ObjFeature:
    group_name: str
    object_name: str
    parent_name: Optional[str]
    faces: list[list[int]] = field(default_factory=list)

    @property
    def gml_id(self) -> str:
        return self.object_name


def apply_geometry_sources(
    model: CityModel, geometry_sources: Iterable[dict[str, Any]]
) -> None:
    """Apply all configured geometry sources to *model* in place."""
    for source in geometry_sources:
        source_type = source.get("type")
        if source_type != _OBJ_GEOMETRY_SOURCE_TYPE:
            raise ValueError(f"Unsupported geometry source type: {source_type!r}")

        apply_obj_geometry(
            model,
            obj_path=Path(str(source["path"])),
            target_building_id=str(source["target_building_id"]),
            target_pv_id=(
                str(source["target_pv_id"])
                if source.get("target_pv_id") is not None
                else None
            ),
        )


def apply_obj_geometry(
    model: CityModel,
    *,
    obj_path: Path,
    target_building_id: str,
    target_pv_id: str | None,
) -> None:
    """Attach OBJ-derived geometry to an existing building and PV collector."""
    vertices, features = _parse_obj_file(obj_path)
    building = _require_feature(model, target_building_id, Building)

    surface_index: dict[str, Any] = {}
    pending_openings: list[_ObjFeature] = []
    solar_panel_faces: list[list[int]] = []

    for feature in features:
        if not feature.faces:
            continue

        if feature.object_name.startswith(_SOLAR_PANEL_PREFIX):
            solar_panel_faces.extend(feature.faces)
            continue

        surface_cls = _SURFACE_GROUPS.get(feature.group_name)
        if surface_cls is not None:
            if feature.gml_id in surface_index:
                raise ValueError(
                    f"OBJ geometry {obj_path} contains duplicate surface name {feature.gml_id!r}"
                )

            surface = surface_cls(
                gml_id=feature.gml_id,
                gml_name=feature.gml_id,
                lod3_multi_surface=_build_multi_surface(
                    f"{feature.gml_id}_lod3",
                    vertices,
                    feature.faces,
                ),
            )
            building.bounded_by_surfaces.append(surface)
            surface_index[feature.gml_id] = surface
            continue

        if feature.group_name in _OPENING_GROUPS:
            pending_openings.append(feature)
            continue

        raise ValueError(
            f"OBJ geometry {obj_path} contains unsupported group {feature.group_name!r} "
            f"for object {feature.object_name!r}"
        )

    for feature in pending_openings:
        if not feature.parent_name:
            raise ValueError(
                f"OBJ opening {feature.object_name!r} in {obj_path} is missing a parent=... tag"
            )

        parent_surface = surface_index.get(feature.parent_name)
        if parent_surface is None:
            raise ValueError(
                f"OBJ opening {feature.object_name!r} references unknown parent "
                f"surface {feature.parent_name!r}"
            )

        opening_cls = _OPENING_GROUPS[feature.group_name]
        parent_surface.openings.append(
            opening_cls(
                gml_id=feature.gml_id,
                gml_name=feature.gml_id,
                lod3_multi_surface=_build_multi_surface(
                    f"{feature.gml_id}_lod3",
                    vertices,
                    feature.faces,
                ),
            )
        )

    if solar_panel_faces:
        if target_pv_id is None:
            raise ValueError(
                f"OBJ geometry {obj_path} contains solar panel faces but no target_pv_id was configured"
            )

        pv_collector = _require_feature(model, target_pv_id, PhotovoltaicCollector)
        pv_collector.lod3_multi_surface = _build_multi_surface(
            f"{target_pv_id}_lod3",
            vertices,
            solar_panel_faces,
        )
    elif target_pv_id is not None:
        raise ValueError(
            f"Geometry source {obj_path} configured target_pv_id={target_pv_id!r} but no solar panel faces were found"
        )


def _parse_obj_file(
    path: Path,
) -> tuple[list[tuple[float, float, float]], list[_ObjFeature]]:
    vertices: list[tuple[float, float, float]] = []
    features: list[_ObjFeature] = []
    current_group: str | None = None
    current_feature: _ObjFeature | None = None

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("g "):
            current_group = line[2:].strip().split()[0]
            continue

        if line.startswith("o "):
            if current_group is None:
                raise ValueError(
                    f"OBJ geometry {path} defines object before group at line {line_number}"
                )

            object_name, parent_name = _split_object_name(line[2:].strip())
            current_feature = _ObjFeature(
                group_name=current_group,
                object_name=object_name,
                parent_name=parent_name,
            )
            features.append(current_feature)
            continue

        if line.startswith("v "):
            parts = line.split()
            if len(parts) < 4:
                raise ValueError(
                    f"OBJ geometry {path} has invalid vertex at line {line_number}"
                )
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            continue

        if line.startswith("f "):
            if current_feature is None:
                raise ValueError(
                    f"OBJ geometry {path} defines face before object at line {line_number}"
                )

            face = [
                _parse_face_index(token, len(vertices)) for token in line.split()[1:]
            ]
            if len(face) < 3:
                raise ValueError(
                    f"OBJ geometry {path} has a face with fewer than 3 vertices at line {line_number}"
                )
            current_feature.faces.append(face)

    return vertices, features


def _split_object_name(raw_name: str) -> tuple[str, str | None]:
    parent_name: str | None = None
    object_name = raw_name

    for fragment in raw_name.split("|"):
        if fragment.startswith("parent="):
            parent_name = fragment.split("=", 1)[1] or None
            continue
        object_name = fragment

    return object_name, parent_name


def _parse_face_index(token: str, vertex_count: int) -> int:
    token_value = token.split("/", 1)[0]
    index = int(token_value)
    if index == 0:
        raise ValueError("OBJ face indices are 1-based and cannot be zero")
    return index - 1 if index > 0 else vertex_count + index


def _build_multi_surface(
    gml_id: str,
    vertices: list[tuple[float, float, float]],
    faces: list[list[int]],
) -> RawXmlElement:
    multi_surface = etree.Element(qn("gml", "MultiSurface"))
    multi_surface.set(f"{{{NS_GML}}}id", gml_id)

    for index, face in enumerate(faces, start=1):
        surface_member = etree.SubElement(multi_surface, qn("gml", "surfaceMember"))
        polygon = etree.SubElement(surface_member, qn("gml", "Polygon"))
        polygon.set(f"{{{NS_GML}}}id", f"{gml_id}_poly_{index}")
        exterior = etree.SubElement(polygon, qn("gml", "exterior"))
        linear_ring = etree.SubElement(exterior, qn("gml", "LinearRing"))
        pos_list = etree.SubElement(linear_ring, qn("gml", "posList"))
        pos_list.text = _format_face(vertices, face)

    return RawXmlElement.from_element(multi_surface)


def _format_face(vertices: list[tuple[float, float, float]], face: list[int]) -> str:
    coordinates = [vertices[index] for index in face]
    if coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])

    return " ".join(
        _format_coordinate(value) for coordinate in coordinates for value in coordinate
    )


def _format_coordinate(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return format(value, ".15g")


def _require_feature(model: CityModel, gml_id: str, expected_type: type[Any]) -> Any:
    for member in model.city_object_members:
        match = _find_feature(member, gml_id)
        if match is not None:
            if not isinstance(match, expected_type):
                raise ValueError(
                    f"Feature {gml_id!r} exists but is not a {expected_type.__name__}"
                )
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
