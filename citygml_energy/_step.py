"""ISO 10303-21 (STEP) geometry parser.

Parses the ``DATA`` section of a Rhino-exported STEP file into a flat list
of polygons with exterior + interior rings. Intentionally independent of
xsdata / CityGML: this module knows nothing about buildings, surfaces, or
LODs. The CityGML-aware layer lives in :mod:`citygml_energy.geometry`.

Supported entity types:

``SHELL_BASED_SURFACE_MODEL`` with ``OPEN_SHELL``
    The canonical export from Rhino for boundary surfaces. Each top-level
    entity carries a user-facing name (used by callers to classify the
    polygons it produces, e.g. ``"WallSurface_1"``).
``MANIFOLD_SOLID_BREP`` with ``CLOSED_SHELL``
    Used for closed zone volumes (``step-zonepart-lod{1..3}``). The parser
    emits anonymous polygons; callers aggregate them as appropriate.

Complex parenthesised entity instances (``#N=( TYPE1(...) TYPE2(...) )``)
are skipped because they only carry unit / measure aggregations, never
BREP geometry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

Coord3D = tuple[float, float, float]


@dataclass(frozen=True)
class GeometryPolygon:
    """A single planar face with exterior ring and optional interior holes."""

    exterior: list[Coord3D]
    interiors: list[list[Coord3D]] = field(default_factory=list)


@dataclass(frozen=True)
class StepShell:
    """A named shell produced by ``SHELL_BASED_SURFACE_MODEL`` in the STEP file.

    *object_name* is the raw ``SHELL_BASED_SURFACE_MODEL`` label; STEP
    authors typically encode semantics there (``WallSurface_3``,
    ``Window_2|parent=WallSurface_3``). *parent_name* is populated from a
    ``|parent=...`` suffix if present; otherwise ``None``.

    The geometric parent linkage is a *geometry* concern: "this opening
    is a hole in this wall". Semantic device-to-surface relations
    (``installedOn``, etc.) are carried in the input JSON, not derived
    from STEP layer names.
    """

    object_name: str
    parent_name: str | None
    polygons: list[GeometryPolygon]


@dataclass(frozen=True)
class _StepEntity:
    entity_type: str
    args: list[str]


_STEP_ENTITY_RE = re.compile(
    r"^#(?P<entity_id>\d+)\s*=\s*(?P<entity_type>[A-Z0-9_]+)\((?P<args>.*)\);$",
    re.DOTALL,
)
_STEP_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# Complex (parenthesised) entity instance: ``#N=( TYPE1(...) TYPE2(...) );``.
# These are valid ISO 10303-21 aggregations (e.g. derived units) but never
# carry BREP geometry, so we skip them deliberately rather than failing.
_STEP_COMPLEX_ENTITY_RE = re.compile(r"^#\d+\s*=\s*\(.*\)\s*;$", re.DOTALL)
# Only chars that can end a run of literal arg-text in the STEP tokeniser.
# Used by ``_split_step_args`` to jump over long numeric runs (CARTESIAN_POINT
# tuples routinely carry 1 000+ chars between special chars) in native code.
_STEP_ARG_SPECIALS_RE = re.compile(r"[',()]")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_named_shells(path: Path, *, origin: Coord3D = (0.0, 0.0, 0.0)) -> list[StepShell]:
    """Return every ``SHELL_BASED_SURFACE_MODEL`` in *path* as a ``StepShell``.

    Shells are returned in entity-ID order (stable across runs). *origin*
    is added to every coordinate so callers can collapse a Rhino local
    frame onto real-world coordinates in one pass.
    """
    entities = _parse_step_entities(path)
    shells: list[StepShell] = []

    for _entity_id, entity in sorted(entities.items()):
        if entity.entity_type != "SHELL_BASED_SURFACE_MODEL":
            continue

        object_name, parent_name = _split_object_name(_unquote_step_string(entity.args[0]))
        shell_refs = _parse_step_ref_list(entity.args[1])
        polygons: list[GeometryPolygon] = []

        for shell_ref in shell_refs:
            shell_entity = _require_step_entity(
                entities, shell_ref, expected_type="OPEN_SHELL", source_path=path
            )
            polygons.extend(
                _parse_step_face(path, entities, face_ref)
                for face_ref in _parse_step_ref_list(shell_entity.args[1])
            )

        if origin != (0.0, 0.0, 0.0):
            polygons = [_offset_polygon(p, origin) for p in polygons]

        shells.append(
            StepShell(object_name=object_name, parent_name=parent_name, polygons=polygons)
        )

    return shells


def parse_all_polygons(
    path: Path, *, origin: Coord3D = (0.0, 0.0, 0.0)
) -> tuple[list[GeometryPolygon], list[Coord3D]]:
    """Collect every face from *path* regardless of shell naming or topology.

    Walks both ``SHELL_BASED_SURFACE_MODEL``/``OPEN_SHELL`` and
    ``MANIFOLD_SOLID_BREP``/``CLOSED_SHELL`` entities. Returns
    ``(polygons, all_coordinates)``; the coordinate list is handy for
    bounding-box computation without re-iterating the polygons.
    """
    entities = _parse_step_entities(path)
    all_polygons: list[GeometryPolygon] = []
    all_coordinates: list[Coord3D] = []
    needs_offset = origin != (0.0, 0.0, 0.0)

    for entity_id in sorted(entities):
        entity = entities[entity_id]

        if entity.entity_type == "SHELL_BASED_SURFACE_MODEL":
            shell_refs = _parse_step_ref_list(entity.args[1])
            for shell_ref in shell_refs:
                shell_entity = _require_step_entity(
                    entities, shell_ref, expected_type="OPEN_SHELL", source_path=path
                )
                for face_ref in _parse_step_ref_list(shell_entity.args[1]):
                    _collect_face(
                        entities,
                        face_ref,
                        path,
                        origin,
                        needs_offset,
                        all_polygons,
                        all_coordinates,
                    )
            continue

        if entity.entity_type == "MANIFOLD_SOLID_BREP":
            shell_ref = _parse_step_ref(entity.args[1])
            shell_entity = _require_step_entity(
                entities, shell_ref, expected_type="CLOSED_SHELL", source_path=path
            )
            for face_ref in _parse_step_ref_list(shell_entity.args[1]):
                _collect_face(
                    entities, face_ref, path, origin, needs_offset, all_polygons, all_coordinates
                )
            continue

    return all_polygons, all_coordinates


# ---------------------------------------------------------------------------
# Coordinate helpers (exported for callers that need them)
# ---------------------------------------------------------------------------


def points_close(first: Coord3D, second: Coord3D, tolerance: float = 1e-9) -> bool:
    """Return whether two 3D points agree within *tolerance* on every axis.

    Direct unpack (rather than ``zip`` + ``all``) because this sits in
    the ring-closure hot loop; assumes :data:`Coord3D` is a 3-tuple.
    """
    x1, y1, z1 = first
    x2, y2, z2 = second
    return abs(x1 - x2) <= tolerance and abs(y1 - y2) <= tolerance and abs(z1 - z2) <= tolerance


def offset_coords(coords: list[Coord3D], origin: Coord3D) -> list[Coord3D]:
    """Translate a list of coordinates by *origin* and return a new list."""
    ox, oy, oz = origin
    return [(x + ox, y + oy, z + oz) for x, y, z in coords]


# ---------------------------------------------------------------------------
# Internal parsing primitives
# ---------------------------------------------------------------------------


def _collect_face(
    entities: dict[int, _StepEntity],
    face_ref: int,
    path: Path,
    origin: Coord3D,
    needs_offset: bool,
    polygons_out: list[GeometryPolygon],
    coords_out: list[Coord3D],
) -> None:
    polygon = _parse_step_face(path, entities, face_ref)
    if needs_offset:
        polygon = _offset_polygon(polygon, origin)
    polygons_out.append(polygon)
    coords_out.extend(polygon.exterior)
    for interior in polygon.interiors:
        coords_out.extend(interior)


def _offset_polygon(polygon: GeometryPolygon, origin: Coord3D) -> GeometryPolygon:
    return GeometryPolygon(
        exterior=offset_coords(polygon.exterior, origin),
        interiors=[offset_coords(ring, origin) for ring in polygon.interiors],
    )


def _parse_step_entities(path: Path) -> dict[int, _StepEntity]:
    entities: dict[int, _StepEntity] = {}

    text = path.read_text(encoding="utf-8-sig")
    data_start = text.find("DATA;")
    if data_start == -1:
        return entities
    data_end = text.find("ENDSEC;", data_start)
    if data_end == -1:
        data_end = len(text)
    data_section = text[data_start + len("DATA;") : data_end]

    # Strip ISO 10303-21 comments (/* ... */, possibly multi-line) before tokenising.
    data_section = _STEP_COMMENT_RE.sub(" ", data_section)

    current_parts: list[str] = []
    for raw_line in data_section.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        current_parts.append(line)
        if not line.endswith(";"):
            continue

        entity_text = " ".join(current_parts)
        current_parts.clear()
        match = _STEP_ENTITY_RE.match(entity_text)
        if match is None:
            if _STEP_COMPLEX_ENTITY_RE.match(entity_text):
                continue
            raise ValueError(
                f"STEP geometry {path} contains an unparseable entity line: {entity_text!r}"
            )

        entity_id = int(match.group("entity_id"))
        entity_type = match.group("entity_type")
        args = _split_step_args(match.group("args"))
        entities[entity_id] = _StepEntity(entity_type=entity_type, args=args)

    return entities


def _parse_step_face(
    path: Path,
    entities: dict[int, _StepEntity],
    face_ref: int,
) -> GeometryPolygon:
    face_entity = _require_step_entity(
        entities, face_ref, expected_type="ADVANCED_FACE", source_path=path
    )
    bound_refs = _parse_step_ref_list(face_entity.args[1])

    exterior: list[Coord3D] | None = None
    interiors: list[list[Coord3D]] = []

    for bound_ref in bound_refs:
        bound_entity = _require_step_entity(
            entities, bound_ref, expected_type=None, source_path=path
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

    return GeometryPolygon(exterior=exterior, interiors=interiors)


def _parse_step_loop(
    path: Path,
    entities: dict[int, _StepEntity],
    loop_ref: int,
) -> list[Coord3D]:
    loop_entity = _require_step_entity(
        entities, loop_ref, expected_type="EDGE_LOOP", source_path=path
    )
    oriented_edge_refs = _parse_step_ref_list(loop_entity.args[1])

    ring: list[Coord3D] = []
    for oriented_edge_ref in oriented_edge_refs:
        oriented_edge = _require_step_entity(
            entities, oriented_edge_ref, expected_type="ORIENTED_EDGE", source_path=path
        )
        edge_curve_ref = _parse_step_ref(oriented_edge.args[3])
        orientation_is_forward = _parse_step_bool(oriented_edge.args[4])

        edge_curve = _require_step_entity(
            entities, edge_curve_ref, expected_type="EDGE_CURVE", source_path=path
        )
        start_point = _get_step_vertex_coordinates(
            path, entities, _parse_step_ref(edge_curve.args[1])
        )
        end_point = _get_step_vertex_coordinates(
            path, entities, _parse_step_ref(edge_curve.args[2])
        )

        if not orientation_is_forward:
            start_point, end_point = end_point, start_point

        if not ring:
            ring.append(start_point)
        elif not points_close(ring[-1], start_point):
            if points_close(ring[-1], end_point):
                start_point, end_point = end_point, start_point
            else:
                raise ValueError(
                    f"STEP geometry {path} contains a non-contiguous loop "
                    f"at edge #{oriented_edge_ref}"
                )

        ring.append(end_point)

    if not ring:
        raise ValueError(f"STEP geometry {path} contains an empty edge loop #{loop_ref}")

    if not points_close(ring[0], ring[-1]):
        ring.append(ring[0])

    return ring


def _split_step_args(raw_args: str) -> list[str]:
    """Split a STEP arg list on top-level commas, respecting strings + nesting.

    Uses ``re.Pattern.search`` to jump over long literal runs
    (``CARTESIAN_POINT`` tuples routinely carry thousands of numeric
    characters between the next ``,``/``(``/``)``/``'``) rather than
    iterating character-by-character in Python.
    """
    n = len(raw_args)
    if n == 0:
        return []

    args: list[str] = []
    append = args.append
    specials_search = _STEP_ARG_SPECIALS_RE.search
    find = raw_args.find

    depth = 0
    i = 0
    start = 0  # Beginning of the current top-level segment.
    in_string = False

    while i < n:
        if in_string:
            # Inside a single-quoted literal: skip to the next quote.
            # STEP escapes an embedded apostrophe as ``''``; treat two
            # consecutive quotes as data, close the string otherwise.
            q = find("'", i)
            if q == -1:
                # Unterminated string: mirror the old behaviour, which
                # absorbed everything into the final segment.
                break
            if q + 1 < n and raw_args[q + 1] == "'":
                i = q + 2
                continue
            in_string = False
            i = q + 1
            continue

        m = specials_search(raw_args, i)
        if m is None:
            break
        i = m.start()
        char = raw_args[i]

        if char == "'":
            in_string = True
            i += 1
        elif char == "(":
            depth += 1
            i += 1
        elif char == ")":
            depth -= 1
            i += 1
        else:  # "," is the only remaining special in the class.
            if depth == 0:
                append(raw_args[start:i].strip())
                start = i + 1
            i += 1

    if start < n:
        append(raw_args[start:].strip())

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
        entities, vertex_ref, expected_type="VERTEX_POINT", source_path=path
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
