"""CBS Postcode6 step: fetch + filter + build + group-join + attach.

This module owns one user story end-to-end: take the user's CBS
Postcode6 source config, fetch the per-postcode dwelling-energy
aggregates from PDOK's CBS WFS, drop areas that fall outside the
optional boundary polygon, build one ``nrg3:UrbanFunctionArea`` per
surviving postcode, populate ``grp:groupMember`` xlinks via 2D
centroid-in-polygon containment, and append every emitted feature to
the city model.

Per [`docs/mapping_city.md`](../../docs/mapping_city.md) §12, CBS
Postcode6 statistics are postcode-level aggregates (one row per
6-position postcode area), not per-building measurements. They cannot
honestly be attached to a ``bldg:Building`` or ``nrg3:BuildingUnit``: a
single value covers every occupied dwelling in the postcode and CBS
suppresses the figure entirely when the area contains fewer than 6
occupied dwellings. EnergyADE 3.0 provides a purpose-built feature for
postcode-/buurt-/wijk-scoped aggregates,
``nrg3:UrbanFunctionArea`` ([`Energy_ADE_3.0_beta8.xsd:2638-2655`](../../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd)),
which extends ``grp:CityObjectGroup`` and therefore carries:

* its own polygon geometry (``grp:geometry``),
* ``groupMember`` xlinks to constituent ``bldg:Building`` features,
* a ``type`` codeSpace that names the kind of area, and
* the standard CityObject hooks for ``nrg3:Energy`` resources,
  ``nrg3:Metadata`` source attribution, and ``core:externalReference``
  to the upstream dataset.

Only one feature kind is emitted today (``type="postalCode6"``); future
CBS area types (buurt / wijk / vierkant) would belong to sibling
modules under the same ``nrg3:UrbanFunctionArea/type`` vocabulary.

The two energy figures (``gemiddeldGasverbruikWoning``,
``gemiddeldElektriciteitsverbruikWoning``) ride as ``nrg3:Energy``
resources tagged ``type="actual"`` (the EnergyADE 3.0 codelist member
for measured/observed energy, distinct from the calculated EP-online
``net``/``primary``/``final`` values that live on the BuildingUnit).
The energy carrier rides on ``Energy/energyCarrier`` (``naturalGas``
or ``electricity``); the ``EnergyTypeValue.actual`` tag plus the
carrier code together distinguish CBS-measured aggregates from
EP-online-calculated indicators on any consumer that filters resources
by their type + carrier pair.

CBS sentinel values (``-99995`` / ``-99997`` / ``-99999`` — the
privacy-suppression / deferred-publication / unknown placeholders
documented in the CBS Longread) ride through the fetcher
(:func:`citygml_energy.city_builder.fetchers.cbs_postcode6._int_preserve_sentinel`)
and land on ``nrg3:Energy/amount`` verbatim: the encoded value is the
raw CBS datum, not a measurement, and a downstream consumer can
distinguish "privacy-suppressed" (``-99997``) from "real measurement"
(positive, rounded to 50) by reading the amount itself. The
``nrg3:Energy`` resource is therefore emitted unconditionally for
both gas and electricity whenever the WFS shipped *any* value (real
or sentinel); only a genuinely null WFS field — the sole case the
fetcher folds to Python ``None`` — translates to "no resource
emitted" on this area. This trade-off favours full source fidelity
(every postcode's CBS row round-trips) over physical plausibility
(negative consumption is meaningless as a measurement); the
``nrg3:Metadata/qualityDescription`` text co-located on the area
spells out the sentinel meanings so the encoding is self-describing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .._step import Coord3D, GeometryPolygon
from ..bindings import (
    CityObjectGroupMemberType,
    CodeType,
    Description,
    Energy,
    ExternalObjectReferenceType1,
    ExternalReferenceType1,
    GeometryPropertyType,
    IntAttribute,
    MeasureType,
    Metadata1,
    Name,
    Resource,
)
from ..core import CityModel
from ..gml_builders import build_multi_surface
from ..mapping import resolve_class
from ..namespaces import (
    CBS_POSTCODE6_INFORMATION_SYSTEM_URL,
    CS_NL_POSTCODE_PC6,
    CS_NRG3_ENERGY_CARRIER,
    CS_NRG3_ENERGY_END_USE,
    CS_NRG3_ENERGY_TYPE,
    CS_NRG3_REFERENCE_PERIOD,
    CS_NRG3_RESOURCE_OPERATION_TYPE,
    CS_NRG3_URBAN_FUNCTION_AREA_TYPE,
)
from ..schema_types import URBAN_FUNCTION_AREA
from ._helpers import safe_gml_id
from .builders._common import UOM_AREA_M2
from .cityjson_parse import ParsedBuilding
from .config import BuildContext, CbsPostcode6Source
from .energy_resources import UOM_KWH_PER_A, UOM_M3_PER_A
from .fetchers import cbs_postcode6 as cbs_postcode6_fetchers
from .fetchers.cbs_postcode6 import Postcode6Area
from .http import CachedSession

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

__all__ = [
    "Postcode6Area",
    "attach_postcode6_areas_to_model",
    "safely_fetch_postcode6_areas",
]

_LOG = logging.getLogger(__name__)


# The single ``nrg3:UrbanFunctionArea/type`` value this module emits
# today. ``gml:CodeType`` is an open vocabulary: future area types
# (CBS buurt / wijk / vierkant) would land in sibling modules under the
# same codeSpace.
_URBAN_FUNCTION_AREA_TYPE_POSTCODE6: str = "postalCode6"

# ``Energy`` knobs that are constant across both CBS resources. Spelled
# out next to the builder rather than imported from
# :mod:`energy_resources`, which keeps regime-aware EP-online routing;
# the CBS knobs are simpler (always demands / year / actual /
# otherOrCombination) so co-locating them keeps the energy_resources
# module focused on the EP-online state machine.
_OPERATION_DEMANDS: str = "demands"
_REFERENCE_YEAR: str = "year"
_ENERGY_TYPE_ACTUAL: str = "actual"
_END_USE_OTHER_OR_COMBINATION: str = "otherOrCombination"

# EnergyCarrierValue.xml members. Both CBS columns are per-carrier
# annual totals, so the carrier slot disambiguates the two resources
# even before a downstream consumer reads the description string.
_CARRIER_NATURAL_GAS: str = "naturalGas"
_CARRIER_ELECTRICITY: str = "electricity"

# ``gen:intAttribute`` names for the BAG-derived dwelling counts that
# CBS publishes alongside the energy aggregates. The XSD has no
# first-class slot for "dwelling count" on UrbanFunctionArea, so they
# ride as generic attributes; the names match the CBS columns'
# semantics translated to English (BAG ``aantalWoningen`` is the total
# registered dwelling count, ``aantalNietBewoondeWoningen`` is the
# unoccupied subset). The two together let a downstream consumer
# reason about *why* an energy figure was suppressed: a postcode with
# ``dwellingCount - vacantDwellingCount < 6`` is below CBS's privacy
# threshold by construction.
_ATTR_DWELLING_COUNT: str = "dwellingCount"
_ATTR_VACANT_DWELLING_COUNT: str = "vacantDwellingCount"

_CBS_SOURCE_LABEL: str = "CBS Statistische gegevens per postcode (PDOK postcode6:postcode6)"

_CBS_QUALITY_DESCRIPTION: str = (
    "Postcode6 aggregate: every nrg3:Energy resource on this "
    "UrbanFunctionArea is the average across all occupied private "
    "dwellings ('particuliere woningen') in the postcode, computed by "
    "CBS from the energienetbedrijven aansluitingenregister. The "
    "values are NOT per-building measurements and must not be "
    "redistributed to individual bldg:Building / nrg3:BuildingUnit "
    "features. CBS rounds both energy figures to fifties. SENTINEL "
    "VALUES IN nrg3:Energy/amount: the pipeline preserves CBS's "
    "documented placeholder integers verbatim instead of dropping the "
    "resource, so any consumer of this file MUST treat negative "
    "amounts as non-measurements. Specifically, -99997 = 'privacy "
    "suppression' (the postcode contains fewer than 6 occupied "
    "dwellings, so CBS withheld the value), -99995 = 'will be "
    "published in a later vintage' (the field is reserved but no value "
    "has been released yet — empirically the entire 2024 vintage "
    "ships every energy field as -99995), -99999 = 'unknown / "
    "reserved'. Only these negative sentinels and real positive "
    "rounded-to-50 values appear; the resource is omitted only when "
    "the WFS shipped no value at all. Gas figures include "
    "stadsverwarming-connected dwellings (district heating), which "
    "lowers the average for postcodes on a shared heat network. "
    "Electricity figures cover individual connections only and "
    "exclude self-generated electricity from rooftop PV and "
    "collective consumption (lifts, gallery lighting). Dwelling "
    "counts (gen:intAttribute name='dwellingCount' and "
    "'vacantDwellingCount') are sourced from BAG via CBS and are not "
    "subject to the 6-dwelling privacy suppression that gates the "
    "energy figures; they fold sentinels to absent rather than "
    "emitting a negative count. Source: "
    "https://www.cbs.nl/nl-nl/longread/diversen/2025/"
    "statistische-gegevens-per-vierkant-en-postcode-2022-2023-2024/"
    "4-beschrijving-cijfers."
)


Bbox = tuple[float, float, float, float]


# ---------------------------------------------------------------------------
# Public seams
# ---------------------------------------------------------------------------


def safely_fetch_postcode6_areas(
    session: CachedSession,
    *,
    source: CbsPostcode6Source,
    bbox: Bbox,
) -> list[Postcode6Area]:
    """Fetch CBS Postcode6 areas inside *bbox*; soft-fail on network error.

    Wraps the strict :func:`citygml_energy.city_builder.fetchers.cbs_postcode6.fetch_postcode6_areas`
    in a network-error trap so the city pipeline can submit it to its
    concurrent-fetch pool without an outage failing the whole build.
    The CBS aggregate is an opportunistic enrichment, not a hard
    dependency: a PDOK outage degrades to "no UrbanFunctionArea
    features in the output GML" rather than failing the whole city
    build. Mirrors the BGT / BOR fetcher's soft-fail contract.
    """
    import requests as _requests

    _LOG.info("Fetching CBS Postcode6 statistics (year=%d) …", source.year)
    try:
        return cbs_postcode6_fetchers.fetch_postcode6_areas(
            session, bbox=bbox, year=source.year,
        )
    except (_requests.RequestException, OSError, ValueError, KeyError) as exc:
        _LOG.warning(
            "CBS Postcode6 fetch failed (%s); skipping UrbanFunctionArea emission",
            exc,
        )
        return []


def attach_postcode6_areas_to_model(
    model: CityModel,
    build_context: BuildContext = BuildContext(),
    *,
    areas: list[Postcode6Area],
    parsed_by_id: dict[str, ParsedBuilding],
    boundary_geom: BaseGeometry | None,
    coords_sink: list[Coord3D],
) -> None:
    """Emit one ``nrg3:UrbanFunctionArea`` per CBS Postcode6 record.

    No-op on empty *areas*. Boundary clip: when a boundary polygon is
    configured, areas whose polygon does not intersect the boundary are
    dropped. The CBS WFS happily ships postcodes that overhang the AOI
    (a postcode is a geographic primitive that has no notion of the
    user's hand-drawn cut-line); without this clip, an
    Emmer-Compascuum-small-area run would emit postcode polygons
    covering all of Emmen.

    GroupMember xlinks: every emitted area carries one
    ``grp:groupMember`` xlink per BAG Pand whose 2D LoD 0 footprint
    centroid lies inside the postcode polygon. The centroid is taken
    from the parsed CityJSON LoD 0 footprint (the same source the
    Building's own ``bldg:lod0FootPrint`` is built from, so the join
    is internally consistent). When LoD 0 is missing, LoD 1 is the
    fallback. A building that fails to produce any 2D centroid
    (degenerate geometry) is silently skipped from the join — its
    ``bldg:Building`` element still exists, but it does not appear as
    a member of any postcode group. ``CityObjectGroupMemberType``
    requires either an inline object or an xlink reference, never both:
    we always populate ``href`` because the Building is already a
    top-level ``core:cityObjectMember``.

    The shapely (Multi)Polygon for each area is materialised once via
    :func:`_polygons_to_shapely` and threaded through the boundary
    intersect, the group-member join, and the area calculation, so
    every spatial predicate sees the same cleaned, prepared geometry.
    """
    if not areas:
        return

    from shapely import prepare
    from shapely.geometry import Point as ShapelyPoint

    # Pre-compute one (gml_id, x, y) per Building for the spatial join.
    # Done once and reused across every area so a city-scale build with
    # 30+ postcodes does not re-walk the building list per-area.
    centroids = _building_centroids_for_join(parsed_by_id, build_context.gml_id_prefix)

    if boundary_geom is not None:
        prepare(boundary_geom)

    emitted = 0
    for area in areas:
        area_geom = _polygons_to_shapely(area.polygons)
        if area_geom is None:
            continue
        if boundary_geom is not None and not boundary_geom.intersects(area_geom):
            continue
        prepare(area_geom)

        ufa = _build_postcode6_urban_function_area(
            area,
            gml_id_prefix=build_context.gml_id_prefix,
            srs_name=build_context.srs_name,
            srs_dimension=build_context.srs_dimension,
            coords_sink=coords_sink,
            area_geom=area_geom,
        )

        # Centroid-in-polygon group-member join, inlined here because
        # the boundary clip, the prepared-geometry cache, and the
        # group-member append all share the same area_geom instance —
        # splitting them across modules earns no leverage and obscures
        # the shared shapely state. Containment uses 2D centroid-in-
        # polygon: a centroid is unambiguous for any valid simple
        # polygon and matches CBS's own per-VBO postcode
        # classification, which keys on the BAG VBO ``geometriePunt``.
        member_count = 0
        for gml_id, x, y in centroids:
            if area_geom.intersects(ShapelyPoint(x, y)):
                ufa.group_member.append(
                    CityObjectGroupMemberType(href=f"#{gml_id}")
                )
                member_count += 1

        model.add(ufa)
        emitted += 1
        _LOG.debug(
            "CBS Postcode6 %s: %d group members",
            area.postcode, member_count,
        )

    _LOG.info(
        "CBS Postcode6: emitted %d UrbanFunctionArea features (of %d fetched)",
        emitted, len(areas),
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _build_postcode6_urban_function_area(
    area: Postcode6Area,
    *,
    gml_id_prefix: str,
    srs_name: str,
    srs_dimension: int,
    coords_sink: list[Coord3D],
    area_geom: BaseGeometry,
) -> Any:
    """Build a single ``nrg3:UrbanFunctionArea`` from a CBS Postcode6 record.

    *area_geom* is the pre-built shapely geometry of the postcode
    polygons (always supplied by the caller). Reused for the
    ``nrg3:area`` calculation so the orchestration does not pay the
    conversion cost twice (once for the boundary clip and the centroid
    join, once here).

    *coords_sink* receives every polygon vertex so the pipeline's
    envelope step can include the postcode geometry in
    ``gml:boundedBy``. Without this the postcode polygon would not
    widen the envelope and viewers would clip part of the area at the
    file boundary.
    """
    cls = resolve_class(URBAN_FUNCTION_AREA)
    gml_id = safe_gml_id(gml_id_prefix, "pc6", area.postcode)

    obj = cls(
        id=gml_id,
        name=[Name(value=area.postcode)],
        type_value=CodeType(
            value=_URBAN_FUNCTION_AREA_TYPE_POSTCODE6,
            code_space=CS_NRG3_URBAN_FUNCTION_AREA_TYPE,
        ),
        code=CodeType(value=area.postcode, code_space=CS_NL_POSTCODE_PC6),
    )

    # ``grp:geometry`` is typed gml:GeometryPropertyType so we wrap the
    # polygon list as a MultiSurface and hand the inner element to a
    # fresh GeometryPropertyType. This mirrors what
    # ``builders.vegetation`` does for ``veg:lod3Geometry`` (the same
    # GeometryProperty container).
    if area.polygons:
        ms_prop = build_multi_surface(
            f"{gml_id}_geom",
            area.polygons,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )
        obj.geometry = GeometryPropertyType(multi_surface=ms_prop.multi_surface)

        if area_geom.area > 0.0:
            obj.area = MeasureType(
                value=round(float(area_geom.area), 3), uom=UOM_AREA_M2,
            )

        for poly in area.polygons:
            coords_sink.extend(poly.exterior)
            for hole in poly.interiors:
                coords_sink.extend(hole)

    obj.external_reference.append(
        ExternalReferenceType1(
            information_system=CBS_POSTCODE6_INFORMATION_SYSTEM_URL,
            external_object=ExternalObjectReferenceType1(name=area.postcode),
        )
    )

    if area.aantal_woningen is not None:
        obj.int_attribute.append(
            IntAttribute(name=_ATTR_DWELLING_COUNT, value=area.aantal_woningen)
        )
    if area.aantal_niet_bewoonde_woningen is not None:
        obj.int_attribute.append(
            IntAttribute(
                name=_ATTR_VACANT_DWELLING_COUNT,
                value=area.aantal_niet_bewoonde_woningen,
            )
        )

    # CBS provenance applies whenever any CBS-derived datum lands on
    # this area, not just the (suppressible) energy figures: the
    # dwelling counts come from the same publication and want the
    # same source attribution.
    if (
        area.gemiddeld_gasverbruik_woning is not None
        or area.gemiddeld_elektriciteitsverbruik_woning is not None
        or area.aantal_woningen is not None
        or area.aantal_niet_bewoonde_woningen is not None
    ):
        obj.metadata.append(
            Metadata1(
                source=_CBS_SOURCE_LABEL,
                quality_description=_CBS_QUALITY_DESCRIPTION,
            )
        )

    if area.gemiddeld_gasverbruik_woning is not None:
        obj.resource.append(
            Resource(
                energy=_build_cbs_energy(
                    amount=float(area.gemiddeld_gasverbruik_woning),
                    uom=UOM_M3_PER_A,
                    carrier=_CARRIER_NATURAL_GAS,
                    description=(
                        "CBS gemiddeldGasverbruikWoning: average annual "
                        "natural-gas consumption per occupied private "
                        "dwelling in this postcode (m3/yr, rounded to 50). "
                        "Includes dwellings on stadsverwarming, which "
                        "lowers the average. Negative amounts are CBS "
                        "sentinels (-99997 privacy-suppressed, -99995 "
                        "deferred publication, -99999 unknown), preserved "
                        "verbatim from the WFS rather than dropped — see "
                        "the area's nrg3:Metadata/qualityDescription."
                    ),
                )
            )
        )

    if area.gemiddeld_elektriciteitsverbruik_woning is not None:
        obj.resource.append(
            Resource(
                energy=_build_cbs_energy(
                    amount=float(area.gemiddeld_elektriciteitsverbruik_woning),
                    uom=UOM_KWH_PER_A,
                    carrier=_CARRIER_ELECTRICITY,
                    description=(
                        "CBS gemiddeldElektriciteitsverbruikWoning: average "
                        "annual electricity consumption per occupied "
                        "private dwelling in this postcode (kWh/yr, "
                        "rounded to 50). Individual connections only; "
                        "excludes self-generated PV and collective "
                        "consumption. Negative amounts are CBS sentinels "
                        "(-99997 privacy-suppressed, -99995 deferred "
                        "publication, -99999 unknown), preserved verbatim "
                        "from the WFS rather than dropped — see the area's "
                        "nrg3:Metadata/qualityDescription."
                    ),
                )
            )
        )

    return obj


def _build_cbs_energy(
    *,
    amount: float,
    uom: str,
    carrier: str,
    description: str,
) -> Energy:
    """One CBS-measured ``nrg3:Energy`` resource (per-dwelling average).

    ``isAmountNormalized=True`` because the value is normalised on a
    per-dwelling basis. ``normalizationParameter="dwelling"`` is the
    free-text slot the schema reserves for "what is the per-X
    denominator?" — kg/m2 etc. encode their normaliser in the uom, but
    "per dwelling" has no SI-flavoured uom token so the parameter slot
    carries the semantics. The ``description`` text repeats the source
    column name so a downstream consumer can identify the exact CBS
    column without reaching for the metadata block.
    """
    return Energy(
        operation_type=CodeType(
            value=_OPERATION_DEMANDS,
            code_space=CS_NRG3_RESOURCE_OPERATION_TYPE,
        ),
        reference_period=CodeType(
            value=_REFERENCE_YEAR, code_space=CS_NRG3_REFERENCE_PERIOD,
        ),
        amount=MeasureType(value=amount, uom=uom),
        is_amount_normalized=True,
        normalization_parameter="dwelling",
        description=Description(value=description),
        type_value=CodeType(
            value=_ENERGY_TYPE_ACTUAL, code_space=CS_NRG3_ENERGY_TYPE,
        ),
        end_use=CodeType(
            value=_END_USE_OTHER_OR_COMBINATION,
            code_space=CS_NRG3_ENERGY_END_USE,
        ),
        energy_carrier=CodeType(
            value=carrier, code_space=CS_NRG3_ENERGY_CARRIER,
        ),
    )


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------


def _polygons_to_shapely(
    polygons: list[GeometryPolygon],
) -> BaseGeometry | None:
    """Return one shapely (Multi)Polygon for *polygons*, or ``None``.

    Single seam where ``GeometryPolygon`` lists become a shapely
    geometry usable for spatial predicates (boundary clip,
    centroid-in-polygon, area). The conversion strips the z-coordinate
    (shapely is 2D), unions multiple parts via ``unary_union`` so a
    fragmented postcode (island + mainland sliver) tests as one
    geometry, and repairs invalid rings with ``buffer(0)`` so a
    self-touching CBS polygon does not flip ``intersects`` to ``False``
    for an unrelated reason.

    Returns ``None`` when *polygons* is empty or every polygon
    collapses to an empty geometry after repair, so callers can use
    the result as a soft "skip this area" signal.
    """
    if not polygons:
        return None
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import unary_union

    parts: list[Any] = []
    for poly in polygons:
        sp = ShapelyPolygon(
            [(x, y) for (x, y, _z) in poly.exterior],
            [[(x, y) for (x, y, _z) in hole] for hole in poly.interiors],
        )
        if not sp.is_valid:
            sp = sp.buffer(0)
        if sp.is_empty:
            continue
        parts.append(sp)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return unary_union(parts)


def _building_centroids_for_join(
    parsed_by_id: dict[str, ParsedBuilding],
    gml_id_prefix: str,
) -> list[tuple[str, float, float]]:
    """Return one ``(building_gml_id, x, y)`` per building with a 2D centroid.

    Centroid is the unweighted mean of the LoD 0 exterior ring vertices
    (matches the area-centroid for regular polygons; biases toward
    vertex-dense sides for irregular ones, which is acceptable for
    3DBAG footprints since they are mostly rectangular and a CBS
    polygon assignment by vertex-mean and area-centroid only diverges
    for L-shapes whose centroid happens to land near a postcode
    boundary). When LoD 0 is unavailable, LoD 1's first polygon is the
    fallback. The gml:id is reconstructed via the same
    :func:`safe_gml_id` rule the building builder uses, so the xlink
    targets resolve.
    """
    centroids: list[tuple[str, float, float]] = []
    for pand_id, pb in parsed_by_id.items():
        ring = _representative_ring(pb)
        if ring is None:
            continue
        x = sum(p[0] for p in ring) / len(ring)
        y = sum(p[1] for p in ring) / len(ring)
        centroids.append((safe_gml_id(gml_id_prefix, "pand", pand_id), x, y))
    return centroids


def _representative_ring(pb: ParsedBuilding) -> list[Coord3D] | None:
    """Return the LoD 0 (or fallback LoD 1) exterior ring for *pb*.

    LoD 0 is preferred because it is the actual 2D footprint; the
    LoD 1 fallback is only consulted when LoD 0 is missing (rare on
    3DBAG, but we defensively handle it). Returns ``None`` when no
    geometry can supply a centroid.
    """
    for lod_key in ("0", "1"):
        sps = pb.geometries.get(lod_key)
        if not sps:
            continue
        for sp in sps:
            ring = sp.polygon.exterior
            if len(ring) >= 3:
                return ring
    return None
