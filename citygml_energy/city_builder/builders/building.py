"""Construct ``bldg:Building`` and its ``nrg3:BuildingUnit`` children.

LoD layout, per :func:`build_building`:

* LoD 0 → ``lod0FootPrint`` (``gml:MultiSurface``).
* LoD 1 → ``lod1Solid`` (``gml:CompositeSurface`` shell).
* LoD 2 → ``boundedBy`` with one ``bldg:GroundSurface`` / ``bldg:WallSurface``
  / ``bldg:RoofSurface`` element **per planar polygon** in the source
  CityJSON. Each thematic surface carries a single-polygon
  ``bldg:lod2MultiSurface``, so per-face attributes like azimuth, slope
  and area refer to a real planar surface rather than an aggregate.
  Polygons without a recognised semantic type fall back to
  ``WallSurface``.

3DBAG attribute mapping is in :func:`_apply_building_attributes`; the
table maps the subset of 3DBAG's ~60 attributes that have a clean
native CityGML / Energy ADE target. The full source-to-XSD mapping
index for buildings lives in ``docs/mapping_city.md``.

BuildingUnit construction is co-located here because it is the only
caller of :func:`build_building_unit` aside from a handful of focused
unit tests; pulling it into its own module would just add an import
cycle (BuildingUnit needs the Address builder, and the Building needs
to attach BuildingUnits). The address + EPC bits are imported from
sibling modules.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from ..._step import GeometryPolygon
from ...bindings import (
    BdgBdrySurfAzimuth,
    BdgBdrySurfInclination,
    BdgBdrySurfTotalSurfaceArea,
    BdgHeight,
    BdgVolume,
    CodeType,
    Identifier,
    LengthType,
    MeasureAttribute,
    MeasureType,
    QualifiedArea,
    QualifiedAreaPropertyType,
    QualifiedHeight,
    QualifiedVolume,
)
from ...gml_builders import build_multi_surface, build_solid, planar_surface_attributes
from ...mapping import resolve_class
from ...namespaces import (
    CS_BAG_GEBRUIKSDOEL,
    CS_BAG_PAND,
    CS_BAG_VERBLIJFSOBJECT,
    CS_BUILDING_FUNCTION,
    CS_BUILDING_ROOFTYPE,
    CS_NRG3_AREA_TYPE,
    CS_NRG3_HEIGHT_TYPE,
    CS_NRG3_VOLUME_TYPE,
)
from ...schema_types import (
    BUILDING,
    BUILDING_UNIT,
    CITYGML_SURFACE_TYPES,
)
from .._helpers import safe_gml_id, to_float, to_int
from ..address_match import ResolvedAddress
from ..cityjson_parse import ParsedBuilding, SemanticPolygon
from ..config import BuildContext
from ..energy_resources import attach_energy_resources_to_building_unit
from ._common import (
    UOM_AREA_M2,
    UOM_DEGREES,
    UOM_METRES,
    UOM_PERCENT,
    UOM_VOLUME_M3,
    inner_type,
)
from .address import build_address
from .epc import _apply_eponline_classification_to_building_unit, build_epc

__all__ = [
    "attach_building_units_to_building",
    "build_building",
    "build_building_unit",
    "iter_lod2_thematic_classification",
    "lod2_thematic_surface_gml_id",
]


# 3DBAG ``b3_dak_type`` -> SIG3D ``_AbstractBuilding_roofType.xml`` numeric
# code. The SIG3D vocabulary (verified live, see
# https://www.sig3d.org/codelists/citygml/2.0/building/2.0/_AbstractBuilding_roofType.xml)
# is: 1000 flat, 1010 monopitch, 1020 dual pent, 1030 gabled, 1040 hipped,
# 1050 half-hipped, 1060 mansard, 1070 pavilion, 1080 cone, 1090 copula,
# 1100 sawtooth, 1110 arch, 1120 pyramidal broach, 1130 combination of
# roof forms.
#
# 3DBAG only emits three values, and ``slanted`` does not say which kind
# of pitched roof it is. Mapping decisions:
#
# * ``horizontal`` -> 1000 (flat). Clean 1:1.
# * ``slanted`` -> 1030 (gabled). Most common Dutch residential pitched
#   roof, used as the deterministic fallback when 3DBAG cannot
#   disambiguate. A consumer that needs the exact SIG3D type must
#   consult the LoD 2 roof geometry directly; ``b3_dak_type`` was never
#   precise enough for it.
# * ``multiple horizontal`` -> 1130 (combination of roof forms). The
#   building has multiple distinct flat roof structures at different
#   heights; ``combination of roof forms`` is the SIG3D code closest in
#   spirit, even though all the constituent forms are flat. (Mapping to
#   1000 would equate it with a single coherent flat roof and lose the
#   "stepped" signal.)
_3DBAG_TO_SIG3D_ROOF_TYPE: dict[str, str] = {
    "horizontal": "1000",
    "slanted": "1030",
    "multiple horizontal": "1130",
}


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


def build_building(
    parsed: ParsedBuilding,
    build_context: BuildContext = BuildContext(),
    *,
    surface_targets_out: list[str] | None = None,
) -> Any:
    """Build a ``bldg:Building`` from a parsed 3DBAG Pand.

    LoD 0 → ``lod0FootPrint`` (MultiSurface).
    LoD 1 → ``lod1Solid`` (CompositeSurface shell).
    LoD 2 → ``boundedBy`` with one ``bldg:GroundSurface``,
             ``bldg:WallSurface`` or ``bldg:RoofSurface`` element per
             planar polygon, each carrying a single-polygon
             ``lod2MultiSurface``.  Polygons without a recognised
             semantic type are assigned to WallSurface.

    When *surface_targets_out* is supplied, every colorable surface id
    created here is appended to it: the LoD 0 ``gml:MultiSurface`` plus
    each of its member ``gml:Polygon`` ids, the LoD 1 ``gml:CompositeSurface``
    shell plus each of its member ``gml:Polygon`` ids, and per LoD 2
    thematic surface its single-polygon ``gml:MultiSurface`` plus the
    member ``gml:Polygon`` id. Per-polygon ids are included because some
    viewers (KIT SDM_KITModelViewer among them) only resolve appearance
    targets that point at individual ``gml:Polygon`` elements and
    silently skip targets that point at an enclosing
    ``gml:MultiSurface`` / ``gml:CompositeSurface``. The pipeline uses
    this pre-collected list to avoid a per-building
    :func:`iter_instances` walk when building the ``app:Appearance``
    (see :func:`citygml_energy.city_builder.appearance.append_energy_label_appearance`).
    """
    gml_id = safe_gml_id(build_context.gml_id_prefix, "pand", parsed.pand_id)
    building_cls = resolve_class(BUILDING)
    # No ``gml:name`` is set: the BAG Pand identification is already
    # carried verbatim on ``nrg3:identifier`` below (with the
    # authoritative ``CS_BAG_PAND`` codespace). Repeating the same 16-digit
    # number on ``gml:name`` would duplicate the identifier under a slot
    # the spec reserves for a *human-readable* label, and downstream
    # viewers (FZK FZKViewer) would then surface the BAG number where the
    # user expects an address. Leaving ``gml:name`` empty is honest about
    # the fact that BAG carries no per-Pand human-readable label — only
    # per-VBO addresses (which land on ``nrg3:BuildingUnit/bldg:address``).
    building = building_cls(id=gml_id)

    # BAG Pand id attached as an nrg3:identifier with the authoritative
    # linked-data codeSpace (see schemas/namespace_prefixes.json and
    # CS_BAG_PAND). Matches the pattern in inputs/buildings/owner_occupier_building.json:35.
    # The codeSpace + value concatenate to the full dereferenceable URL
    # (`rdf_seealso` in the PDOK BAG WFS response), so we do not need to
    # round-trip the URL prefix from the fetcher.
    building.identifier.append(
        Identifier(value=parsed.pand_id, code_space=CS_BAG_PAND)
    )

    _apply_building_attributes(building, parsed.attributes)

    if 0 in build_context.lods and parsed.geometries.get("0"):
        # LoD 0 vertices are passed through with the source Z (3DBAG ships
        # the footprint at nominal Z=0 / NAP). LoD 0 is a 2D footprint
        # representation; there is no defined elevation, and the per-building
        # terrain height (b3_h_maaiveld) lives on LoD 1/2 where a
        # consumer querying for "ground level" can find it. An earlier
        # revision of this builder lifted LoD 0 to maaiveld so a single
        # viewer would draw both representations co-planar; the trade-off
        # was misrepresenting the source by stamping a Z onto a feature
        # that has none.
        polygons_lod0 = _unwrap_polygons(parsed.geometries["0"])
        building.lod0_foot_print = build_multi_surface(
            f"{gml_id}_lod0",
            polygons_lod0,
            srs_name=build_context.srs_name,
            srs_dimension=build_context.srs_dimension,
        )
        if surface_targets_out is not None:
            surface_targets_out.append(f"#{gml_id}_lod0")
            _extend_polygon_targets(
                surface_targets_out, f"{gml_id}_lod0", len(polygons_lod0)
            )

    if 1 in build_context.lods and parsed.geometries.get("1"):
        polygons_lod1 = _unwrap_polygons(parsed.geometries["1"])
        # 3DBAG publishes LoD 1/2 CityJSON with outward-facing rings already,
        # per the CityJSON spec. The centroid-based heuristic in
        # ``orient_solid_polygons`` can mis-flip walls on concave facades
        # (L- and U-shapes), which produces inward-facing polygons that
        # viewers then back-face-cull. Trust the source orientation here.
        building.lod1_solid = build_solid(
            f"{gml_id}_lod1",
            polygons_lod1,
            srs_name=build_context.srs_name,
            srs_dimension=build_context.srs_dimension,
            orient=False,
        )
        if surface_targets_out is not None:
            surface_targets_out.append(f"#{gml_id}_lod1_shell")
            _extend_polygon_targets(
                surface_targets_out, f"{gml_id}_lod1", len(polygons_lod1)
            )

    if 2 in build_context.lods and parsed.geometries.get("2"):
        _attach_lod2_thematic_surfaces(
            building,
            parsed.geometries["2"],
            gml_id=gml_id,
            srs_name=build_context.srs_name,
            srs_dimension=build_context.srs_dimension,
            surface_targets_out=surface_targets_out,
        )

    return building


def _apply_building_attributes(building: Any, attrs: dict[str, Any]) -> None:
    """Write commonly-useful 3DBAG attributes onto the building.

    Maps the subset of 3DBAG's ~60 attributes that have a clean native
    CityGML / Energy ADE target:

    * ``oorspronkelijkbouwjaar`` → ``bldg:yearOfConstruction`` (BAG /
      3DBAG always agree; ``_merge_attributes`` ensures BAG wins on
      ties).
    * ``gebruiksdoel`` → ``bldg:function`` (rare on 3DBAG Building
      nodes; the VBO carries the real value).
    * ``b3_bouwlagen`` → ``bldg:storeysAboveGround``: count of
      above-ground storeys (integer, non-negative).
    * ``b3_h_dak_max - b3_h_maaiveld`` → ``nrg3:bdgHeight``: total
      physical height of the building encoded as a ``QualifiedHeight``
      with type ``maxHeightAboveGround``. Ground-to-highest-roof-point
      matches the Dutch convention and the ``maxHeightAboveGround``
      HeightTypeValue code. We prefer ``b3_h_dak_max`` over
      ``b3_h_dak_70p`` so antenna / chimney tips register as part of
      the building's physical extent, not a statistical percentile.
    * ``b3_dak_type`` → ``bldg:roofType`` mapped through
      :data:`_3DBAG_TO_SIG3D_ROOF_TYPE` to a numeric SIG3D code, with
      :data:`CS_BUILDING_ROOFTYPE` (the SIG3D codelist URL) as the
      codeSpace. The 3DBAG enumeration (``horizontal`` / ``slanted`` /
      ``multiple horizontal``) is coarser than the SIG3D codelist:
      ``slanted`` does not disambiguate between monopitch / gabled /
      hipped, so we pick the most-common Dutch residential type
      (``1030`` = gabled roof) as the deterministic fallback. The
      lossiness is intrinsic to 3DBAG; the consistent SIG3D vocabulary
      is preferred over leaving each pipeline with a different
      codeSpace (the per-building input emits SIG3D codes too).
    * ``b3_volume_lod22`` → ``nrg3:area``-style ``QualifiedVolume``
      with type ``grossVolume``. Matches the per-building-input pattern at
      ``inputs/buildings/owner_occupier_building.json::bdg_volume``, so a single GML file
      can mix 3DBAG-measured and per-building-input-declared volumes transparently.
    """
    year = to_int(attrs.get("oorspronkelijkbouwjaar"))
    if year is not None:
        from xsdata.models.datatype import XmlPeriod

        building.year_of_construction = XmlPeriod(f"{year:04d}")

    # ``gebruiksdoel`` is a VBO attribute, not a Pand one; only set when
    # a caller has bubbled it up to the parsed attributes dict.
    function = attrs.get("gebruiksdoel") or attrs.get("function")
    if function:
        building.function.append(
            CodeType(value=str(function), code_space=CS_BUILDING_FUNCTION)
        )

    bouwlagen = to_int(attrs.get("b3_bouwlagen"))
    if bouwlagen is not None and bouwlagen >= 0:
        building.storeys_above_ground = bouwlagen

    h_dak = to_float(attrs.get("b3_h_dak_max"))
    h_maaiveld = to_float(attrs.get("b3_h_maaiveld"))
    if h_dak is not None and h_maaiveld is not None and h_dak > h_maaiveld:
        building.bdg_height.append(
            BdgHeight(
                qualified_height=QualifiedHeight(
                    description=(
                        "Building height from terrain level to highest roof point, "
                        "computed from 3DBAG b3_h_dak_max minus b3_h_maaiveld."
                    ),
                    source="3DBAG b3_h_dak_max - b3_h_maaiveld",
                    value=MeasureType(value=round(h_dak - h_maaiveld, 3), uom=UOM_METRES),
                    type_value=CodeType(
                        value="maxHeightAboveGround", code_space=CS_NRG3_HEIGHT_TYPE,
                    ),
                )
            )
        )

    dak_type = attrs.get("b3_dak_type")
    if isinstance(dak_type, str) and dak_type:
        sig3d_code = _3DBAG_TO_SIG3D_ROOF_TYPE.get(dak_type.strip())
        if sig3d_code is not None:
            building.roof_type = CodeType(
                value=sig3d_code, code_space=CS_BUILDING_ROOFTYPE,
            )

    volume = to_float(attrs.get("b3_volume_lod22"))
    if volume is not None and volume > 0:
        # ``bldg:Building`` is a CityGML class that does not carry a
        # native ``volume`` list; the Energy ADE adds one under the name
        # ``bdgVolume`` whose property type is a
        # ``QualifiedVolumePropertyType`` specialisation ``BdgVolume``.
        # Structure matches ``inputs/buildings/owner_occupier_building.json::bdg_volume``.
        building.bdg_volume.append(
            BdgVolume(
                qualified_volume=QualifiedVolume(
                    description=(
                        "Gross volume computed by 3DBAG from the LoD 2.2 "
                        "roof-shape reconstruction."
                    ),
                    source="3DBAG b3_volume_lod22",
                    value=MeasureType(value=round(volume, 3), uom=UOM_VOLUME_M3),
                    type_value=CodeType(
                        value="grossVolume", code_space=CS_NRG3_VOLUME_TYPE,
                    ),
                )
            )
        )


# ---------------------------------------------------------------------------
# LoD 2 thematic surface helpers
# ---------------------------------------------------------------------------

# Surface-type dispatch is centralised in schema_types so the city-scale and
# per-building pipelines share a single source of truth for CityGML thematic
# surfaces.
_SURFACE_TYPES = CITYGML_SURFACE_TYPES
_FALLBACK_SURFACE = "WallSurface"


def _unwrap_polygons(semantic_polygons: list[SemanticPolygon]) -> list[GeometryPolygon]:
    return [sp.polygon for sp in semantic_polygons]


def lod2_thematic_surface_gml_id(
    building_gml_id: str, surface_type: str, index_one_based: int,
) -> str:
    """Return the gml:id for the *index*-th LoD 2 thematic surface of a type.

    Numbering is per-type, 1-based, in the order polygons appear in the
    source CityJSON ``geometries["2"]`` — see
    :func:`iter_lod2_thematic_classification` for the iteration that
    assigns the index. Stable across reruns because the source order is
    preserved by the parser. Both the building builder
    (:func:`_attach_lod2_thematic_surfaces`) and the PV-panel matcher
    (:mod:`citygml_energy.city_builder.pv_panels`) use this helper so
    the ``installedOn`` xlinks emitted by the matcher resolve to the
    surfaces emitted by the builder by construction.

    *surface_type* is the CityJSON / CityGML name (``"RoofSurface"``,
    ``"WallSurface"``, ``"GroundSurface"``); the id uses its lowercase
    form, suffixed with ``_<index>`` (e.g. ``pand_<id>_roofsurface_1``).
    """
    return f"{building_gml_id}_{surface_type.lower()}_{index_one_based}"


def iter_lod2_thematic_classification(
    semantic_polygons: Iterable[SemanticPolygon],
) -> Iterator[tuple[str, int, SemanticPolygon]]:
    """Yield ``(surface_type, 1-based-index-within-type, sp)`` in source order.

    This is the **single source of truth** for how LoD 2 polygons map
    to per-planar thematic surfaces. The builder consumes every yield
    to emit a ``bldg:boundedBy`` element; the PV-panel matcher consumes
    the same iterator (filtered to ``RoofSurface``) to label each
    facet with the gml:id the builder will assign. Routing both sides
    through one iterator removes the implicit "two counters that must
    happen to agree" coupling that splitting per-planar introduced.

    *surface_type* in each yield is the resolved CityJSON name, with
    unrecognised / missing types collapsed to ``WallSurface`` per
    :data:`_FALLBACK_SURFACE` (so a polygon that the source could not
    classify still ends up as a real boundary surface in the output
    rather than vanishing).

    The iterator is order-preserving and counts independently per
    surface type; index resets are *not* implied by surface-type
    transitions.
    """
    counters: dict[str, int] = {}
    for sp in semantic_polygons:
        key = sp.surface_type if sp.surface_type in _SURFACE_TYPES else _FALLBACK_SURFACE
        counters[key] = counters.get(key, 0) + 1
        yield key, counters[key], sp


def _attach_lod2_thematic_surfaces(
    building: Any,
    semantic_polygons: list[SemanticPolygon],
    *,
    gml_id: str,
    srs_name: str,
    srs_dimension: int,
    surface_targets_out: list[str] | None = None,
) -> None:
    """Emit one ``bldg:boundedBy`` element per planar polygon.

    Each polygon becomes its own ``bldg:GroundSurface`` /
    ``bldg:WallSurface`` / ``bldg:RoofSurface`` carrying a single-polygon
    ``bldg:lod2MultiSurface``. This keeps per-face attributes (azimuth,
    slope, area) referring to an actual planar surface, and isolates
    viewer tessellation failures to one face instead of letting a single
    malformed polygon hide every other facet of the same type.

    Polygons with an unrecognised or missing semantic type fall back to
    WallSurface (see :func:`iter_lod2_thematic_classification`).

    Each emitted surface also carries the three Energy ADE 3.0 per-
    surface attributes that are computable from the planar polygon
    alone (see :func:`_attach_planar_surface_ade_attributes`):
    ``nrg3:bdgBdrySurfTotalSurfaceArea``, ``nrg3:bdgBdrySurfInclination``,
    and ``nrg3:bdgBdrySurfAzimuth`` (the last is omitted on horizontal
    surfaces where azimuth is geometrically undefined). Other Energy
    ADE attributes on AbstractBoundarySurface (Thickness, HeatCapacity,
    IsShared, view factors, OpaqueSurfaceArea, ThermalBridgeUValue) need
    construction or scene-level data the city pipeline does not have, so
    they are deliberately left absent rather than written with placeholder
    values.

    When *surface_targets_out* is supplied, the ``lod2_multi_surface``
    container id and its single member polygon id are appended for every
    emitted surface so the pipeline can build the ``app:Appearance``
    targets without an extra tree walk.
    """
    if not semantic_polygons:
        return

    # mypy stub for ``_lru_cache_wrapper`` rejects ``type[Any]``; safe.
    wrapper_cls = inner_type(type(building), "bounded_by")  # type: ignore[arg-type]
    if wrapper_cls is None:
        return

    for surf_type, index, sp in iter_lod2_thematic_classification(semantic_polygons):
        xsd_name, field_name = _SURFACE_TYPES[surf_type]
        surf_cls = resolve_class(xsd_name)
        surf_id = lod2_thematic_surface_gml_id(gml_id, surf_type, index)
        surf = surf_cls(id=surf_id)
        surf.lod2_multi_surface = build_multi_surface(
            f"{surf_id}_ms",
            [sp.polygon],
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )
        _attach_planar_surface_ade_attributes(surf, sp.polygon)
        building.bounded_by.append(wrapper_cls(**{field_name: surf}))
        if surface_targets_out is not None:
            surface_targets_out.append(f"#{surf_id}_ms")
            _extend_polygon_targets(surface_targets_out, f"{surf_id}_ms", 1)


def _attach_planar_surface_ade_attributes(
    surf: Any, polygon: GeometryPolygon,
) -> None:
    """Populate ``nrg3:bdgBdrySurf{TotalSurfaceArea,Inclination,Azimuth}`` on *surf*.

    All three are derived from the polygon's outward normal (raw, no
    upward flip — see :func:`citygml_energy.gml_builders.planar_surface_attributes`).
    The schema models each as ``minOccurs=0 maxOccurs=1`` substituting
    into ``bldg:_GenericApplicationPropertyOfBoundarySurface``, so they
    serialise as direct children of the ``bldg:RoofSurface`` /
    ``bldg:WallSurface`` / ``bldg:GroundSurface`` element they describe.

    *area* is rounded to mm² (3 decimals) and *angles* to 0.01° — the
    underlying CityJSON vertices are quantised to mm in
    :class:`citygml_energy.city_builder.cityjson_parse.CityJSONTile`,
    so any extra precision past those bounds would be spurious.

    Azimuth is omitted on horizontal surfaces (GroundSurface, flat
    RoofSurface): the underlying ``planar_surface_attributes`` returns
    ``None`` for azimuth there, and silence is more honest than a
    sentinel value (the Alderaan reference writes ``-1`` for the
    ground-surface azimuth, but ``-1`` is not a valid bearing — every
    consumer would have to special-case it).

    Skipped on degenerate polygons: ``planar_surface_attributes``
    returns ``None`` for sub-µm² rings, and we leave the surface
    geometrically attached but attribute-free rather than writing
    NaN-derived values that would propagate downstream.
    """
    attrs = planar_surface_attributes(polygon)
    if attrs is None:
        return
    area_m2, azimuth_deg, inclination_deg = attrs
    surf.bdg_bdry_surf_total_surface_area.append(
        BdgBdrySurfTotalSurfaceArea(value=round(area_m2, 3), uom=UOM_AREA_M2)
    )
    surf.bdg_bdry_surf_inclination.append(
        BdgBdrySurfInclination(value=round(inclination_deg, 2), uom=UOM_DEGREES)
    )
    if azimuth_deg is not None:
        surf.bdg_bdry_surf_azimuth.append(
            BdgBdrySurfAzimuth(value=round(azimuth_deg, 2), uom=UOM_DEGREES)
        )


def _extend_polygon_targets(
    sink: list[str], container_gml_id: str, polygon_count: int
) -> None:
    """Append ``#{container_gml_id}_poly_{i}`` refs for each generated polygon.

    Mirrors the id scheme used by
    :func:`citygml_energy.gml_builders.build_multi_surface` and
    :func:`citygml_energy.gml_builders.build_solid`; kept close to the call
    sites so any future rename breaks the dedicated appearance test rather
    than a surface-data-less-but-still-valid CityGML file.
    """
    sink.extend(
        f"#{container_gml_id}_poly_{i}"
        for i in range(1, polygon_count + 1)
    )


# ---------------------------------------------------------------------------
# BuildingUnit + attached Address + EPC
# ---------------------------------------------------------------------------


def build_building_unit(
    resolved: ResolvedAddress,
    build_context: BuildContext = BuildContext(),
) -> Any:
    """Build an ``nrg3:BuildingUnit`` for one VBO.

    The VBO's address is attached via ``nrg3:address`` (the address
    property on ``nrg3:BuildingUnit`` lives in the Energy ADE namespace,
    not the ``bldg:`` namespace); the EP-online energy label (when
    matched) is attached via ``nrg3:energyPerformanceCertificate``.
    The mandatory ``nrg3:type`` element is filled with the first
    ``gebruiksdoel`` value (``woonfunctie``, ``kantoorfunctie``, …).

    The build context's SRS fields are passed through to
    :func:`build_address` for the VBO ``geometriePunt``
    (``core:Address/core:multiPoint``).
    """
    unit_cls = resolve_class(BUILDING_UNIT)

    gml_id = safe_gml_id(build_context.gml_id_prefix, "bu", resolved.vbo.identificatie)
    # ``nrg3:BuildingUnit/type`` is mandatory (gml:CodeType, no
    # ``minOccurs="0"`` in the XSD), so we must populate it for every
    # VBO. BAG ``gebruiksdoel`` is the closest available signal: a
    # Bouwbesluit-2012 use category (``woonfunctie``,
    # ``kantoorfunctie``, ``winkelfunctie``, ...). We keep the Dutch
    # term verbatim and tag it with the BAG codespace
    # (:data:`citygml_energy.namespaces.CS_BAG_GEBRUIKSDOEL`) so a
    # consumer can resolve the vocabulary; mapping to the EnergyADE
    # ``CurrentUseValue.xml`` codelist would lose BAG distinctions
    # (e.g. ``logiesfunctie`` -> ``residential``) we want to keep
    # auditable. The fallback ``other`` is used only when BAG ships an
    # empty ``gebruiksdoel`` list, which is rare but legal.
    gebruiksdoel = (resolved.vbo.gebruiksdoel or ["other"])[0]
    unit = unit_cls(
        id=gml_id,
        type_value=CodeType(value=gebruiksdoel, code_space=CS_BAG_GEBRUIKSDOEL),
    )

    # BAG VBO id as an authoritative linked-data identifier. Same pattern
    # as the Building (see ``build_building``), with the VBO-specific
    # codespace base.
    unit.identifier.append(
        Identifier(
            value=resolved.vbo.identificatie,
            code_space=CS_BAG_VERBLIJFSOBJECT,
        )
    )

    if resolved.vbo.oppervlakte is not None and resolved.vbo.oppervlakte > 0:
        # BAG's ``oppervlakte`` is the ``gebruiksoppervlakte`` per NEN 2580:
        # the usable floor area, excluding walls and vertical shafts. The
        # closest member of Energy ADE 3.0's ``AreaTypeValue`` codelist is
        # ``netFloorArea`` (which also excludes walls); strictly speaking
        # NEN 2580 gebruiksoppervlakte is a specifically Dutch metric with
        # additional deductions (stairwells, circulation) that do not
        # perfectly coincide with the international "net floor area"
        # definition. The ``source`` text below pins the provenance so a
        # reader can recover the exact semantics.
        unit.area.append(
            QualifiedAreaPropertyType(
                qualified_area=QualifiedArea(
                    description=(
                        "Usable floor area ('gebruiksoppervlakte' per NEN 2580) "
                        "as recorded by the Dutch BAG register for this "
                        "verblijfsobject."
                    ),
                    source=(
                        "BAG bag:verblijfsobject.oppervlakte "
                        "(PDOK WFS v2.0)"
                    ),
                    value=MeasureType(
                        value=float(resolved.vbo.oppervlakte), uom=UOM_AREA_M2,
                    ),
                    type_value=CodeType(
                        value="netFloorArea", code_space=CS_NRG3_AREA_TYPE,
                    ),
                )
            )
        )

    # EP-online ``GebruiksoppervlakteThermischeZone`` is the floor area each
    # per-m² energy metric on this BuildingUnit (BENG-1, BENG-2,
    # Warmtebehoefte, BerekendeEnergieverbruik) is normalised against. It
    # does not always agree with BAG ``oppervlakte`` because EP-online sums
    # only the heated floor area within the thermal envelope, while BAG
    # records the legal usable area per VBO. Encoded as a second
    # ``QualifiedArea`` (same ``netFloorArea`` type, distinct ``source``) so
    # both numbers stay queryable side-by-side; this is the documented
    # multi-source pattern Energy ADE 3.0 supports for QualifiedAttribute.
    label = resolved.energy_label
    if (
        label is not None
        and label.gebruiksoppervlakte_thermische_zone is not None
        and label.gebruiksoppervlakte_thermische_zone > 0
    ):
        unit.area.append(
            QualifiedAreaPropertyType(
                qualified_area=QualifiedArea(
                    description=(
                        "EP-online thermal-zone floor area: the denominator "
                        "every per-m² energy metric on this BuildingUnit is "
                        "normalised against."
                    ),
                    source="EP-online Mutatiebestand v4 (RVO)",
                    value=MeasureType(
                        value=float(label.gebruiksoppervlakte_thermische_zone),
                        uom=UOM_AREA_M2,
                    ),
                    type_value=CodeType(
                        value="netFloorArea", code_space=CS_NRG3_AREA_TYPE,
                    ),
                )
            )
        )

    address = build_address(resolved, build_context)
    if address is not None:
        address_prop_cls = inner_type(unit_cls, "address")
        if address_prop_cls is not None:
            unit.address.append(address_prop_cls(address=address))

    epc = build_epc(resolved, build_context)
    if epc is not None:
        epc_prop_cls = inner_type(unit_cls, "energy_performance_certificate")
        if epc_prop_cls is not None:
            unit.energy_performance_certificate.append(
                epc_prop_cls(energy_performance_certificate=epc)
            )

    # EP-online's renewable-energy share (BENG-3) has no native Energy ADE
    # slot. The mapping doc § 5j keeps it as a ``gen:measureAttribute``;
    # it lands on the BuildingUnit because the CityGML 2.0 generic
    # attribute substitution is on AbstractCityObject (BuildingUnit
    # inherits) and not on EnergyPerformanceCertificate (which extends
    # AbstractFeatureWithLifeSpan, NOT a CityObject).
    if label is not None and label.aandeel_hernieuwbare_energie is not None:
        unit.measure_attribute.append(
            MeasureAttribute(
                name="epOnlineAandeelHernieuwbareEnergie",
                value=MeasureType(
                    value=float(label.aandeel_hernieuwbare_energie),
                    uom=UOM_PERCENT,
                ),
            )
        )

    # nrg3:Energy resources for the four NTA-8800 BENG metrics. Attached
    # to BuildingUnit via the ``nrg3:resource`` substitution (XSD line
    # 1366); see :mod:`citygml_energy.city_builder.energy_resources` for
    # the per-resource construction logic and uom convention.
    attach_energy_resources_to_building_unit(unit, label)

    # Per-VBO EP-online classification: bdgSubtypeEPOnline string
    # attribute (the Dutch RVO Gebouwsubtype, verbatim) plus a single
    # Metadata block on this BuildingUnit attributing the EP-online
    # source for everything attached above (subtype + energy resources
    # + renewable share + thermal-zone area). The Pand-level EP-online
    # emissions (``yearOfConstructionEPOnline`` + ``nrg3:bdgType``) live
    # at the Building level, see
    # :func:`apply_eponline_pand_attribution_to_building`; BAG's
    # ``bldg:yearOfConstruction`` keeps its own Metadata block at the
    # Building level (see :func:`apply_bag_year_metadata_to_building`).
    _apply_eponline_classification_to_building_unit(unit, label)

    return unit


def attach_building_units_to_building(
    building: Any,
    addresses: list[ResolvedAddress],
    build_context: BuildContext = BuildContext(),
) -> None:
    """Wrap each resolved VBO in a ``BuildingUnit2`` and attach to *building*."""
    if not addresses:
        return
    # mypy stub for ``_lru_cache_wrapper`` rejects ``type[Any]``; safe.
    wrapper_cls = inner_type(type(building), "building_unit")  # type: ignore[arg-type]
    if wrapper_cls is None:
        return
    for resolved in addresses:
        unit = build_building_unit(resolved, build_context)
        building.building_unit.append(wrapper_cls(building_unit=unit))
