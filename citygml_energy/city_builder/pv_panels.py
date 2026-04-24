"""Attach external PV panel polygons to LoD 2 roofs as ``nrg3:PhotovoltaicCollector``.

The city-scale pipeline consumes 3DBAG + BAG + EP-online. This module
plugs a third geometry source on top: an OGC GeoPackage of 2D panel
array polygons (e.g. the University of Groningen aerial-imagery dataset
at Zenodo 14860030, CC-BY-4.0).

The integration is deliberately narrow:

* **Matching is 2D, max-overlap.** Each panel polygon is intersected
  with every LoD 2 ``RoofSurface`` facet; the facet with the largest
  overlap area wins. Panels that intersect no roof are skipped and
  counted. Per-facet splitting is not supported: panels that straddle a
  ridge land entirely on their largest overlap. The source dataset is
  per-array, not per-module, so a split would not buy extra fidelity.
* **Projection is flat-Z, not slope-following.** The roof facet's
  Newell plane gives a Z at the panel centroid; every panel vertex is
  stamped with that Z plus a small offset. Rationale: the source
  annotation is a 2D footprint from aerial imagery with no tilt
  information, so stamping a planar projection avoids inventing
  geometry we cannot verify. One consequence: the emitted
  :class:`PhotovoltaicCollector` leaves ``azimuth`` and ``inclination``
  unset — a slope-derived value would contradict the horizontal polygon.

All CPU-heavy work (GPKG read, spatial index build, matching,
projection) runs **once** in the pipeline's main process before the
per-pand worker pool is spawned. What each worker receives is a small
list of :class:`ProjectedPanel` dataclasses already keyed by
``pand_id``: pickling cost is minimal and the per-building attach is
pure xsdata construction.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._step import GeometryPolygon
from ..bindings import (
    AbstractCityObjectPropertyType,
    AngleType,
    AreaType,
    CityObjectRelation,
    CodeType,
    Device,
    PhotovoltaicCollector,
    Point,
    Pos,
    ReferencePoint,
    RelatedTo,
)
from ..gml_builders import build_multi_surface, newell_normal
from ..namespaces import CS_NRG3_CELL_TYPE, CS_NRG3_RELATION_TYPE
from .cityjson_parse import ParsedBuilding, SemanticPolygon

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

__all__ = [
    "DEFAULT_Z_OFFSET_M",
    "ProjectedPanel",
    "PvPanelsSource",
    "attach_pv_collectors_to_building",
    "load_panels_in_bbox",
    "match_and_project_panels",
]

_LOG = logging.getLogger(__name__)

DEFAULT_Z_OFFSET_M: float = 0.1
# RD New. Panels are expected in the same CRS as 3DBAG so the 2D
# intersection math stays exact; we fail loudly on any other SRS id.
_EXPECTED_SRS_ID: int = 28992
_UNDEFINED_SRS_IDS: frozenset[int] = frozenset({0, -1})

# uom tokens match the KIT SDM_KITModelViewer Data/UOMList.xml @id
# values so the viewer recognises them in its Properties panel. The
# XSD types @uom as xs:anyURI so the string is not schema-constrained;
# this is a downstream-viewer compatibility choice. "deg" is the altId
# of "grad" (DEGREE) and is accepted by the viewer.
_UOM_AREA_M2: str = "m2"
_UOM_DEGREES: str = "deg"

# Below this, the roof is effectively horizontal and the azimuth is
# numerically meaningless. 1e-6 is well below single-panel noise and
# still catches the textbook "flat roof" case.
_HORIZONTAL_EPS: float = 1e-6

# gml:id prefix for the collectors. BAG identificaties lead with a
# digit, so the prefix is what keeps them as valid XML NCNames.
_PV_ID_PREFIX: str = "pv_"

# Pre-built CodeType singletons. Every collector we emit shares these
# exact values, and xsdata serialisation is read-only, so caching at
# module scope saves a few hundred allocations on a full-town run.
_CELL_TYPE_UNKNOWN: CodeType = CodeType(value="unknown", code_space=CS_NRG3_CELL_TYPE)
_RELATION_INSTALLED_ON: CodeType = CodeType(
    value="installedOn", code_space=CS_NRG3_RELATION_TYPE
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PvPanelsSource:
    """Declarative pointer to an external PV panel polygon GeoPackage.

    :attr:`path`: absolute or already-resolved path to the ``.gpkg``.
    :attr:`layer`: the table name inside the GPKG that holds the panel
    geometries (not the human-readable identifier).
    :attr:`z_offset_m`: flat Z offset above the roof plane, in metres.
    """

    path: Path
    layer: str
    z_offset_m: float = DEFAULT_Z_OFFSET_M


# ---------------------------------------------------------------------------
# Per-pand projected panel (picklable across worker pool)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProjectedPanel:
    """A panel matched to its parent Pand and pre-projected to LoD 2.

    Pre-computing orientation in the main process means workers never
    re-derive it from the polygons; ``slots=True`` keeps the pickle
    cost across the ``multiprocessing.Pool`` boundary minimal.

    * ``lod2_polygons`` — panel vertices dropped onto the roof plane,
      then offset perpendicular to it by ``z_offset_m``.
    * ``footprint_area_m2`` — the 2D polygon area. Emitted as
      ``nrg3:moduleArea``. On a tilted roof the true surface area is
      larger by ``1/cos(inclination)``; we keep the footprint value
      because it is what the source dataset annotated.
    * ``azimuth_deg`` — compass bearing (0° N, clockwise) of the roof
      normal's horizontal projection. ``None`` on horizontal roofs.
    * ``inclination_deg`` — tilt from horizontal, 0 = flat, 90 = vertical.
    * ``reference_point`` — (x, y, z) of the panel centroid lifted to
      the offset plane; emitted as ``nrg3:referencePoint``.
    """

    original_fid: int
    lod2_polygons: tuple[GeometryPolygon, ...]
    footprint_area_m2: float
    azimuth_deg: float | None
    inclination_deg: float
    reference_point: tuple[float, float, float]


# ---------------------------------------------------------------------------
# GeoPackage reading
# ---------------------------------------------------------------------------


_GPKG_ENVELOPE_LENGTHS: dict[int, int] = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def _strip_gpkg_header(blob: bytes) -> bytes:
    """Strip the GPKG geometry envelope header, return the inner WKB bytes.

    Per OGC GeoPackage 1.x "GeoPackage Binary": magic ``"GP"`` (2 bytes),
    version (1), flags (1), int32 SRS id (4), optional envelope (0/32/
    48/64 bytes by indicator), then raw WKB.
    """
    if len(blob) < 8 or blob[:2] != b"GP":
        raise ValueError("not a GPKG geometry blob")
    flags = blob[3]
    env_indicator = (flags >> 1) & 0x07
    env_len = _GPKG_ENVELOPE_LENGTHS.get(env_indicator)
    if env_len is None:
        raise ValueError(f"unsupported GPKG envelope indicator {env_indicator}")
    return blob[8 + env_len :]


def load_panels_in_bbox(
    source: PvPanelsSource,
    bbox: tuple[float, float, float, float],
) -> list[tuple[int, BaseGeometry]]:
    """Load panel rows whose geometry intersects *bbox*.

    Prefers the GeoPackage R-tree virtual table
    (``rtree_<layer>_<geom>``) for the initial spatial filter so a
    small-bbox smoke test does not scan the whole layer; falls back to
    a full scan if the index is missing. The layer SRS must be RD New
    (EPSG:28992) to match 3DBAG; other SRSs raise.
    """
    try:
        from shapely import wkb as shapely_wkb
        from shapely.geometry import box as shapely_box
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "PV panel integration needs shapely; install with: pip install -e .[city]"
        ) from exc

    clip = shapely_box(*bbox)
    # URI form forces read-only; we never mutate the source GPKG.
    try:
        con = sqlite3.connect(f"file:{source.path}?mode=ro", uri=True)
    except sqlite3.OperationalError as exc:
        raise FileNotFoundError(
            f"pv_panels.path could not be opened: {source.path}"
        ) from exc
    try:
        _assert_gpkg_layer_is_rd_new(con, source)
        geom_col, rtree_name = _gpkg_geometry_column_and_rtree(con, source.layer)
        rows_iter = _iter_candidate_rows(
            con, layer=source.layer, geom_col=geom_col, rtree=rtree_name, bbox=bbox
        )
        out: list[tuple[int, BaseGeometry]] = []
        for fid, blob in rows_iter:
            if blob is None:
                continue
            geom = shapely_wkb.loads(_strip_gpkg_header(blob))
            if not geom.intersects(clip):
                continue
            out.append((int(fid), geom))
    finally:
        con.close()
    return out


def _assert_gpkg_layer_is_rd_new(con: sqlite3.Connection, source: PvPanelsSource) -> None:
    meta = con.execute(
        "SELECT data_type, srs_id FROM gpkg_contents WHERE table_name = ?",
        (source.layer,),
    ).fetchone()
    if meta is None:
        raise ValueError(
            f"layer {source.layer!r} not declared in gpkg_contents of {source.path}"
        )
    data_type, srs_id = meta
    if data_type != "features":
        raise ValueError(
            f"layer {source.layer!r} is not a features table "
            f"(data_type={data_type!r}) in {source.path}"
        )
    if srs_id != _EXPECTED_SRS_ID and srs_id not in _UNDEFINED_SRS_IDS:
        raise ValueError(
            f"layer {source.layer!r} has srs_id={srs_id}; expected "
            f"{_EXPECTED_SRS_ID} (Amersfoort / RD New) to match 3DBAG"
        )


def _gpkg_geometry_column_and_rtree(
    con: sqlite3.Connection, layer: str
) -> tuple[str, str | None]:
    """Return ``(geom_col, rtree_table_or_None)`` for *layer*.

    The R-tree virtual table is optional in GPKG; when missing, the
    caller falls back to a full-layer scan.
    """
    row = con.execute(
        "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
        (layer,),
    ).fetchone()
    geom_col = row[0] if row else "geom"
    rtree = f"rtree_{layer}_{geom_col}"
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (rtree,),
    ).fetchone()
    return geom_col, rtree if exists else None


def _iter_candidate_rows(
    con: sqlite3.Connection,
    *,
    layer: str,
    geom_col: str,
    rtree: str | None,
    bbox: tuple[float, float, float, float],
):
    """Yield ``(fid, geom_blob)`` rows whose bbox intersects *bbox*.

    Uses the GPKG R-tree when available (roughly O(log n) for the
    spatial filter) and falls back to a full scan otherwise. Table and
    column names are quoted; layer names come from the config and go
    through :func:`_assert_gpkg_layer_is_rd_new` first.
    """
    minx, miny, maxx, maxy = bbox
    if rtree is None:
        return con.execute(f'SELECT fid, "{geom_col}" FROM "{layer}"')
    return con.execute(
        f'SELECT t.fid, t."{geom_col}" '
        f'FROM "{layer}" AS t '
        f'JOIN "{rtree}" AS r ON t.fid = r.id '
        f"WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?",
        (minx, maxx, miny, maxy),
    )


# ---------------------------------------------------------------------------
# Matching + flat-Z projection
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _RoofFacet:
    """Internal: one LoD 2 RoofSurface polygon projected to its 2D footprint."""

    pand_id: str
    sp: SemanticPolygon
    xy_polygon: Any  # shapely Polygon; avoid top-level import for optional dep


def match_and_project_panels(
    *,
    panels: Iterable[tuple[int, BaseGeometry]],
    parsed_buildings: Iterable[ParsedBuilding],
    z_offset_m: float,
) -> tuple[dict[str, list[ProjectedPanel]], int]:
    """Return ``({pand_id: [ProjectedPanel, ...]}, skipped_panels)``.

    Builds an R-tree over every LoD 2 RoofSurface facet, picks the
    facet with the largest 2D overlap per panel, and stamps each panel
    vertex with the Newell-plane Z at the panel centroid plus
    *z_offset_m*. ``shapely.STRtree`` turns the match step from
    :math:`O(P \\cdot F)` into effectively :math:`O(P \\log F)` once the
    number of roof facets climbs above a few thousand.
    """
    try:
        from shapely import STRtree, force_2d, prepare
        from shapely.geometry import Polygon
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "PV panel matching needs shapely; install with: pip install -e .[city]"
        ) from exc

    facets = _collect_roof_facets(parsed_buildings, Polygon)
    if not facets:
        return {}, sum(1 for _ in panels)

    tree = STRtree([f.xy_polygon for f in facets])

    matches: dict[str, list[ProjectedPanel]] = {}
    skipped = 0
    for fid, geom in panels:
        panel_xy = force_2d(geom)
        if panel_xy.is_empty or panel_xy.area <= 0:
            skipped += 1
            continue
        # Prepared geometries cache the PIP/intersects predicate; the
        # STRtree hit list is small but each intersection() still walks
        # the panel ring, so this is a ~free win on the hot path.
        prepare(panel_xy)
        best = _best_overlap(panel_xy, tree, facets)
        if best is None:
            skipped += 1
            continue
        facet, _overlap_area = best
        projected = _project_panel_on_roof(panel_xy, facet.sp, z_offset_m)
        if projected is None:
            skipped += 1
            continue
        matches.setdefault(facet.pand_id, []).append(
            ProjectedPanel(
                original_fid=fid,
                lod2_polygons=projected.lod2_polygons,
                footprint_area_m2=float(panel_xy.area),
                azimuth_deg=projected.azimuth_deg,
                inclination_deg=projected.inclination_deg,
                reference_point=projected.reference_point,
            )
        )
    return matches, skipped


def _collect_roof_facets(
    parsed_buildings: Iterable[ParsedBuilding], polygon_cls: Any
) -> list[_RoofFacet]:
    """Index every LoD 2 RoofSurface polygon as a 2D shapely Polygon.

    ``buffer(0)`` rescues self-intersecting source rings; facets that
    stay empty or non-polygonal after the heal are dropped. Passing
    *polygon_cls* (the ``shapely.geometry.Polygon`` class itself) in as
    an argument avoids a second import dance at module top level for
    an optional dependency.
    """
    from shapely.errors import ShapelyError  # local; shapely is optional

    facets: list[_RoofFacet] = []
    for pb in parsed_buildings:
        for sp in pb.geometries.get("2") or ():
            if sp.surface_type != "RoofSurface":
                continue
            ring = sp.polygon.exterior
            if len(ring) < 3:
                continue
            exterior = [(x, y) for (x, y, _z) in ring]
            interiors = [
                [(x, y) for (x, y, _z) in hole] for hole in sp.polygon.interiors
            ]
            try:
                poly = polygon_cls(exterior, interiors)
                if not poly.is_valid:
                    poly = poly.buffer(0)
            except (ShapelyError, ValueError, TypeError, IndexError) as exc:
                _LOG.debug("skipping malformed roof facet ring: %s", exc)
                continue
            if poly.is_empty or poly.geom_type not in {"Polygon", "MultiPolygon"}:
                continue
            facets.append(_RoofFacet(pand_id=pb.pand_id, sp=sp, xy_polygon=poly))
    return facets


def _best_overlap(
    panel_xy: BaseGeometry,
    tree: Any,
    facets: list[_RoofFacet],
) -> tuple[_RoofFacet, float] | None:
    """Return the (facet, overlap_area) with the largest 2D overlap, or None."""
    candidate_ids = tree.query(panel_xy, predicate="intersects")
    best: _RoofFacet | None = None
    best_area = 0.0
    for idx in candidate_ids:
        facet = facets[int(idx)]
        inter = panel_xy.intersection(facet.xy_polygon)
        if inter.is_empty:
            continue
        area = float(inter.area)
        if area > best_area:
            best_area = area
            best = facet
    if best is None:
        return None
    return best, best_area


@dataclass(frozen=True, slots=True)
class _RoofPlane:
    """A roof facet's fitted plane and the unit normal pointing upward.

    ``n_unit`` has ``|n_unit| == 1`` and ``n_unit.z >= 0``. The plane
    passes through ``anchor``. ``nz_raw`` carries the un-normalised Z
    component, so callers can detect degenerate (near-vertical) facets
    without recomputing.
    """

    anchor: tuple[float, float, float]
    n_unit: tuple[float, float, float]
    nz_raw: float


@dataclass(frozen=True, slots=True)
class _ProjectedGeometry:
    lod2_polygons: tuple[GeometryPolygon, ...]
    azimuth_deg: float | None
    inclination_deg: float
    reference_point: tuple[float, float, float]


def _project_panel_on_roof(
    panel_xy: BaseGeometry,
    roof_sp: SemanticPolygon,
    z_offset_m: float,
) -> _ProjectedGeometry | None:
    """Project a 2D panel onto the roof plane, parallel to it, offset by the roof normal.

    Steps, per the user's "slope-following" spec:

    1. Fit the Newell plane through the matched roof facet and flip it
       so the normal points up (``n_unit.z >= 0``).
    2. Drop every panel vertex ``(x, y)`` onto the plane to get a 3D
       point on the roof.
    3. Offset each point by ``z_offset_m * n_unit`` (perpendicular to
       the roof, so the emitted panel is truly coplanar with the roof
       rather than simply hovering at a higher Z).
    4. Derive azimuth + inclination from the same normal and lift the
       panel centroid as the collector's ``referencePoint``.

    Returns ``None`` when the roof plane is degenerate (zero-area
    facet), so the caller can count it as skipped rather than emit
    geometry with undefined orientation.
    """
    plane = _fit_roof_plane(roof_sp)
    if plane is None:
        return None

    ox, oy, oz = (z_offset_m * c for c in plane.n_unit)

    def to_panel_plane(x: float, y: float) -> tuple[float, float, float]:
        z_on_plane = _z_on_plane(plane, x, y)
        return (float(x) + ox, float(y) + oy, z_on_plane + oz)

    def polygon_to_geom(poly: Any) -> GeometryPolygon:
        return GeometryPolygon(
            exterior=[to_panel_plane(x, y) for (x, y) in poly.exterior.coords],
            interiors=[
                [to_panel_plane(x, y) for (x, y) in ring.coords]
                for ring in poly.interiors
            ],
        )

    from shapely.geometry import MultiPolygon, Polygon

    if isinstance(panel_xy, Polygon):
        polys = [polygon_to_geom(panel_xy)]
    elif isinstance(panel_xy, MultiPolygon):
        polys = [polygon_to_geom(p) for p in panel_xy.geoms]
    else:
        raise ValueError(f"unsupported panel geometry type {panel_xy.geom_type!r}")

    centroid = panel_xy.centroid
    refpoint = to_panel_plane(centroid.x, centroid.y)

    return _ProjectedGeometry(
        lod2_polygons=tuple(polys),
        azimuth_deg=_azimuth_from_normal(plane.n_unit),
        inclination_deg=_inclination_from_normal(plane.n_unit),
        reference_point=refpoint,
    )


def _fit_roof_plane(roof_sp: SemanticPolygon) -> _RoofPlane | None:
    """Return the up-facing unit normal and an anchor point on the roof.

    The Newell normal is ambiguous up to sign because it depends on
    vertex winding. CityGML roof polygons should wind so the outward
    normal points away from the building (upward), but we defensively
    flip any facet whose computed normal points down. Returns ``None``
    if the polygon is degenerate (``|n| ~ 0``), which would otherwise
    produce a division by zero downstream.
    """
    ring = roof_sp.polygon.exterior
    if len(ring) < 3:
        return None
    nx, ny, nz = newell_normal(ring)
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag < 1e-9:
        return None
    # Flip to the up-facing half-space (Z+). Roof facets should already
    # obey this convention in 3DBAG CityJSON; the guard is a safety net.
    if nz < 0.0:
        nx, ny, nz = -nx, -ny, -nz
    n_unit = (nx / mag, ny / mag, nz / mag)
    x0, y0, z0 = ring[0]
    return _RoofPlane(anchor=(float(x0), float(y0), float(z0)), n_unit=n_unit, nz_raw=nz)


def _z_on_plane(plane: _RoofPlane, x: float, y: float) -> float:
    """Evaluate Z on the roof plane at ``(x, y)``.

    Degenerate (near-vertical) facets are screened out by
    :func:`_fit_roof_plane`, so ``nz`` is strictly positive here.
    """
    x0, y0, z0 = plane.anchor
    nx, ny, nz = plane.n_unit
    return z0 - (nx * (x - x0) + ny * (y - y0)) / nz


def _azimuth_from_normal(n_unit: tuple[float, float, float]) -> float | None:
    """Compass azimuth (0° N, 90° E, clockwise) of the up-facing normal.

    A flat roof has a vertical normal and no meaningful azimuth, so
    return ``None``. Callers should omit ``nrg3:azimuth`` in that case
    rather than emit an arbitrary bearing for a horizontal panel.
    """
    nx, ny, _nz = n_unit
    horizontal2 = nx * nx + ny * ny
    if horizontal2 < _HORIZONTAL_EPS:
        return None
    # atan2(nx, ny) gives the clockwise angle from +Y (north) by
    # construction, which is exactly the compass bearing we want.
    return (math.degrees(math.atan2(nx, ny)) + 360.0) % 360.0


def _inclination_from_normal(n_unit: tuple[float, float, float]) -> float:
    """Tilt from horizontal in degrees, clamped to [0, 90]."""
    nz = max(-1.0, min(1.0, n_unit[2]))
    return math.degrees(math.acos(nz))


# ---------------------------------------------------------------------------
# xsdata authoring: per-building PhotovoltaicCollector attach
# ---------------------------------------------------------------------------


def attach_pv_collectors_to_building(
    building: Any,
    panels_for_pand: list[ProjectedPanel],
    *,
    srs_name: str,
    srs_dimension: int,
) -> int:
    """Append one ``nrg3:PhotovoltaicCollector`` per panel; return the count.

    A collector carries:

    * ``gml:id = "pv_{pand_id}_{original_fid}"`` — NCName-safe via the
      ``pv_`` prefix (BAG identificatie starts with a digit).
    * ``lod2MultiSurface`` — the pre-projected polygons from
      :func:`match_and_project_panels`.
    * ``moduleArea`` (m²) — the 2D polygon area, which equals the
      emitted surface area because the panel is stamped flat.
    * ``cellType = "unknown"`` — the aerial-imagery source has no
      module-level detail.
    * ``relatedTo[installedOn] → #<roof_gml_id>`` — intra-document
      xlink to the Building's single LoD 2 RoofSurface.

    Returns 0 when the building has no LoD 2 RoofSurface (e.g. the run
    was configured with ``lods=[0, 1]``); the panels are silently dropped
    because there is no valid xlink target inside the document.
    """
    if not panels_for_pand:
        return 0
    roof_gml_id = _find_roof_surface_id(building)
    if roof_gml_id is None:
        _LOG.warning(
            "building %r has no LoD 2 RoofSurface; %d PV panel(s) dropped",
            getattr(building, "id", None),
            len(panels_for_pand),
        )
        return 0

    building_id = getattr(building, "id", None) or "unknown"
    pand_id = (
        building_id.removeprefix("pand_") if building_id.startswith("pand_") else building_id
    )

    for panel in panels_for_pand:
        pv = _build_pv_collector(
            pv_gml_id=f"{_PV_ID_PREFIX}{pand_id}_{panel.original_fid}",
            roof_gml_id=roof_gml_id,
            panel=panel,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )
        building.device.append(Device(photovoltaic_collector=pv))
    return len(panels_for_pand)


def _build_pv_collector(
    *,
    pv_gml_id: str,
    roof_gml_id: str,
    panel: ProjectedPanel,
    srs_name: str,
    srs_dimension: int,
) -> PhotovoltaicCollector:
    """Materialise one ``nrg3:PhotovoltaicCollector`` from a :class:`ProjectedPanel`.

    Populated fields match the Alderaan reference in
    ``Energy_ADE-3.0beta8/test_data/Alderaan_Energy_ADE_All.gml``.
    Device-catalog fields (``model``, ``yearOfManufacture``,
    ``numberOfDevices``, ``installedPower``, ``nominalEfficiency``,
    ``heatDissipation*``, ``apertureArea``, ``deviceOperation``,
    ``validFrom``/``validTo``) are deliberately left unset: a single
    2D aerial polygon carries no information about any of them.
    """
    pv = PhotovoltaicCollector(
        id=pv_gml_id,
        cell_type=_CELL_TYPE_UNKNOWN,
        module_area=AreaType(value=round(panel.footprint_area_m2, 3), uom=_UOM_AREA_M2),
        inclination=AngleType(
            value=round(panel.inclination_deg, 2), uom=_UOM_DEGREES
        ),
        lod2_multi_surface=build_multi_surface(
            f"{pv_gml_id}_lod2",
            list(panel.lod2_polygons),
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        ),
    )
    if panel.azimuth_deg is not None:
        pv.azimuth = AngleType(value=round(panel.azimuth_deg, 2), uom=_UOM_DEGREES)

    rx, ry, rz = panel.reference_point
    pv.reference_point.append(
        ReferencePoint(
            point=Point(
                id=f"{pv_gml_id}_refpoint",
                srs_name_attribute=srs_name,
                srs_dimension=srs_dimension,
                pos=Pos(value=[rx, ry, rz]),
            )
        )
    )

    pv.related_to.append(
        RelatedTo(
            city_object_relation=CityObjectRelation(
                relation_type=_RELATION_INSTALLED_ON,
                related_to=AbstractCityObjectPropertyType(href=f"#{roof_gml_id}"),
            )
        )
    )
    return pv


def _find_roof_surface_id(building: Any) -> str | None:
    """Return the Building's LoD 2 RoofSurface gml:id, or ``None``.

    The city builder emits exactly one ``bldg:RoofSurface`` per Building
    at LoD 2 (all facets merged into one ``lod2MultiSurface``); see
    :func:`citygml_energy.city_builder.builders._attach_lod2_thematic_surfaces`.
    We introspect ``building.bounded_by`` rather than reconstructing the
    id by string templating so a future rename of the id convention
    doesn't silently break the xlinks we emit here.
    """
    for wrapper in getattr(building, "bounded_by", None) or []:
        surf = getattr(wrapper, "roof_surface", None)
        if surf is not None and getattr(surf, "id", None) is not None:
            return surf.id
    return None
