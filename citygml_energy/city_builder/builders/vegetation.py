"""Construct ``veg:SolitaryVegetationObject`` from a parsed CFTree tree.

Three concerns live in this module:

1. :func:`build_solitary_vegetation_object`: the public entry point.
   Wires the geometry, CFTree morphometrics, and the optional BGT and
   BOR enrichments together.
2. CFTree morphometric mapping: which CFTree per-tree attribute lands
   in which native CityGML 2.0 vegetation slot vs which generic
   attribute. The mapping is encoded in the
   :data:`_CFTREE_NATIVE_FIELDS` dict and the
   :data:`_CFTREE_GENERIC_DOUBLE` frozenset so a future CFTree release
   adding a new metric is a one-line edit.
3. Register cross-reference / enrichment helpers. BGT writes only a
   ``core:externalReference`` (the layer carries no per-tree
   attributes); Emmen BOR additionally fills ``veg:species`` plus
   ``gen:*Attribute`` siblings for fields without a native CityGML
   2.0 slot. See ``docs/mapping_city.md`` for the full
   per-field mapping rationale.
"""

from __future__ import annotations

from typing import Any

from ..._step import GeometryPolygon
from ...bindings import (
    CodeType,
    DateAttribute,
    DoubleAttribute,
    ExternalObjectReferenceType1,
    ExternalReferenceType1,
    IntAttribute,
    LengthType,
    Name,
    StringAttribute,
)
from ...gml_builders import build_multi_surface
from ...mapping import resolve_class
from ...namespaces import CS_EMMEN_BOR_TREES
from ...schema_types import SOLITARY_VEGETATION_OBJECT
from .._helpers import safe_gml_id, to_finite_float
from ..cityjson_trees_parse import ParsedTree
from ..config import BuildContext
from ..fetchers.bgt import (
    BGT_INFORMATION_SYSTEM_URL,
    BgtTree,
    bgt_feature_uri,
)
from ..fetchers.emmen_bor import (
    BOR_INFORMATION_SYSTEM_URL,
    BorTree,
    bor_feature_uri,
)
from ._common import UOM_METRES

__all__ = ["build_solitary_vegetation_object"]


# CFTree attribute keys → CityGML field / generic-attribute destination. Keys
# are the attribute names as written by CFTree's
# :func:`construct_geometry._normalize_attributes`. Splitting the table out
# makes the mapping reviewable at a glance and easy to extend when CFTree
# adds new morphometrics in a future release.
_CFTREE_NATIVE_FIELDS: dict[str, str] = {
    # CFTree key        → CityGML SolitaryVegetationObject field (xsdata name)
    "trunk_H_m": "height",
    "trunk_DBH_m": "trunk_diameter",
    "crown_width_m": "crown_diameter",
}
_CFTREE_GENERIC_DOUBLE: frozenset[str] = frozenset({
    # Morphometrics without a native CityGML slot. Preserved as generic
    # double attributes so downstream consumers that care (CFD, microclimate)
    # can still reach them; everything else safely ignores them.
    #
    # Actual keys observed in CFTree's
    # ``construct_geometry._normalize_attributes`` output (verified
    # against generated tiles, not taken from the source at face value).
    #
    # NB: ``trunk_radius_m`` is deliberately NOT in this set. CFTree
    # computes it as ``0.5 * trunk_DBH_m`` (see
    # ``extract_tree_metrics.estimate_trunk_dimensions``), so emitting
    # both the radius and the DBH-derived ``veg:trunkDiameter`` would
    # doubly-signal the same measurement. The CityGML ``veg:trunkDiameter``
    # field keeps the primary value; any consumer that wants the radius
    # can compute it on the fly.
    "crown_median_z",
    "crown_r50_m",
    "crown_porosity",
    "trunk_base_height_m",
})


def build_solitary_vegetation_object(
    tree: ParsedTree,
    build_context: BuildContext = BuildContext(),
    *,
    bgt_match: BgtTree | None = None,
    bor_match: BorTree | None = None,
) -> Any:
    """Build a ``veg:SolitaryVegetationObject`` from a CFTree tree.

    Geometry
        Every triangular face from every CityJSON ``Solid`` component
        (crown + trunk + any future components) is flattened into a
        single ``gml:MultiSurface`` and attached as ``veg:lod3Geometry``.
        The watertight crown and trunk meshes stay visually coherent
        because their faces share global RD coordinates; CityGML 2.0
        has no per-component slot for a tree, so merging is the correct
        lossless encoding.

    Morphometrics
        Native CityGML 2.0 fields (``height``, ``trunkDiameter``,
        ``crownDiameter``) are populated directly from CFTree's
        attribute dict. Non-native metrics (``porosity``, ``r50``,
        ``median_z``, trunk radius + base XYZ) go into
        ``gen:doubleAttribute`` children so downstream CFD consumers
        keep access while a plain CityGML viewer still parses cleanly.

    BGT cross-reference (optional)
        When *bgt_match* is given, the tree is cross-linked to the
        authoritative Dutch register:

        * ``core:externalReference`` with
          ``informationSystem = <BGT PDOK URL>`` and
          ``externalObject.uri = <dereferenceable BGT feature URL>``.
        * ``gen:dateAttribute name="bgtCreationDate"`` when BGT has a
          registry creation date. Deliberately *not* written as
          ``core:creationDate`` because CityGML's ``creationDate``
          semantics is "when this CityObject record was created in the
          dataset", not "when the physical feature was first registered
          in an external register"; misusing it would confuse any
          tool that keys lifecycle logic on it.

        Trees without a BGT match have neither attachment: the
        presence/absence of the ``externalReference`` doubles as a
        "known to BGT" flag without a dedicated generic attribute.

    BOR (Emmen) enrichment (optional)
        When *bor_match* is given, attribute slots from Emmen's
        ``bor_groen_bomen_beschermd`` register attach to the
        vegetation object. Only the Latin scientific name lands in a
        typed CityGML 2.0 vegetation slot; everything else goes into
        ``gen:*Attribute`` siblings, because the CityGML 2.0
        vegetation module has no native slots for protection regimes,
        growth-form descriptors, planting years, ecological
        standplaats, or class-band measurements. See
        ``docs/mapping_city.md`` for the per-field rationale.
        In summary:

        * ``veg:species`` ← ``soortnaam`` (Latin binomial)
        * second ``core:externalReference`` keyed on ``boom_id``
        * ``gen:intAttribute name="plantingYear"`` ← ``jaarvanaanleg``
        * ``gen:stringAttribute`` siblings for the Dutch common name,
          height / trunk-diameter class bands, protection status
          (``Bijzondere boom`` / ``Monumentale boom``) plus its
          detail, growth form (``Boom vrij uitgroeiend`` etc.), and
          the ``standplaats`` fields.

        BGT and BOR matches are independent: a tree may carry zero,
        one, or both ``core:externalReference`` siblings. The
        ``maxOccurs="unbounded"`` cardinality on
        ``core:AbstractCityObjectType.externalReference`` allows
        emitting both without conflict.

    Per-attribute failures degrade silently: a ``NaN`` / missing /
    non-numeric value for a single morphometric is skipped via
    :func:`citygml_energy.city_builder._helpers.to_finite_float` rather
    than aborting the tree, so a malformed per-tree CityJSON does not
    kill the whole city build. Binding-resolution failures (e.g. a
    non-existent ``veg:SolitaryVegetationObject``) still raise; those
    are schema errors and should surface loudly.
    """
    tree_cls = resolve_class(SOLITARY_VEGETATION_OBJECT)
    # gtids are globally unique in the merged CFTree output produced by
    # ``tools.merge_cftree_tiles`` (per-tile collisions are resolved at
    # merge time by re-numbering survivors), so the gml:id can be
    # derived directly from the gtid without tile namespacing.
    gml_id = safe_gml_id(build_context.gml_id_prefix, "tree", tree.gtid)
    obj = tree_cls(id=gml_id, name=[Name(value=f"T_{tree.gtid}")])

    if tree.polygons:
        obj.lod3_geometry = _geometry_property_from_polygons(
            f"{gml_id}_lod3", tree.polygons,
            srs_name=build_context.srs_name,
            srs_dimension=build_context.srs_dimension,
        )

    _apply_cftree_morphometrics(obj, tree.attributes)

    if bgt_match is not None:
        _apply_bgt_cross_reference(obj, bgt_match)

    if bor_match is not None:
        _apply_bor_enrichment(obj, bor_match)

    return obj


def _apply_bgt_cross_reference(obj: Any, bgt_match: BgtTree) -> None:
    """Attach a BGT ``vegetatieobject_punt`` cross-reference to *obj*.

    The CityGML 2.0 ``ExternalObjectReferenceType`` is defined as an
    ``xs:choice`` between a ``name`` element and a ``uri`` element;
    exactly one branch must be populated, never both. This function
    populates ``uri`` only; the BGT ``lokaal_id`` is reachable as the
    last path segment of the URL, so picking ``uri`` preserves both
    the dereferenceable-URL and raw-handle semantics in a single
    schema-valid element.

    The creation date, when present, becomes a ``gen:dateAttribute``,
    not a ``core:creationDate`` on the CityObject itself, to avoid
    semantic confusion between "record created in *our* dataset" and
    "record first registered in BGT".
    """
    obj.external_reference.append(
        ExternalReferenceType1(
            information_system=BGT_INFORMATION_SYSTEM_URL,
            external_object=ExternalObjectReferenceType1(
                uri=bgt_feature_uri(bgt_match.lokaal_id),
            ),
        )
    )
    if bgt_match.creation_date is not None:
        from xsdata.models.datatype import XmlDate

        obj.date_attribute.append(
            DateAttribute(
                name="bgtCreationDate",
                value=XmlDate.from_date(bgt_match.creation_date),
            )
        )


def _apply_bor_enrichment(obj: Any, bor: BorTree) -> None:
    """Attach Emmen BOR attributes to *obj* in their CityGML 2.0 slots.

    Slot reasoning, per ``docs/mapping_city.md``:

    * ``veg:species`` is the only typed CityGML 2.0 vegetation slot
      that fits an Emmen field honestly. ``soortnaam`` is a Latin
      binomial, which is exactly what ``species`` is for.
    * ``veg:class`` / ``veg:function`` / ``veg:usage`` are reserved
      for botanical or horticultural classifications (tree-vs-shrub,
      shade tree, street tree). Emmen's ``beschermingsstatus``
      (``Bijzondere boom`` / ``Monumentale boom``) is a legal /
      heritage status, not a function, and ``type``
      (``Boom vrij uitgroeiend`` / ``niet vrij uitgroeiend``) is a
      growth-form descriptor, not a class. Forcing those into the
      typed slots would mis-signal to any consumer that reads the
      vocabulary semantically, so both go into ``gen:stringAttribute``
      siblings.
    * Height / trunk-diameter class strings (``"18 tot 24 m."``) are
      categorical bands rather than measurements, so they do not
      displace the typed ``veg:height`` / ``veg:trunkDiameter`` slots
      that CFTree already populates from a precise measurement.
    * Planting year stays as ``gen:intAttribute name="plantingYear"``,
      the workaround documented in § 4.1, because
      ``core:creationDate`` is reserved for record-lifecycle semantics
      in this project, and the ``xs:date`` precision would force a
      fake month and day on a year-only source value anyway.

    The cross-reference handle is keyed on Emmen's stable ``boom_id``
    (not the rebuild-volatile ``OBJECTID``) so the URL survives a
    server-side layer republish.
    """
    obj.external_reference.append(
        ExternalReferenceType1(
            information_system=BOR_INFORMATION_SYSTEM_URL,
            external_object=ExternalObjectReferenceType1(
                uri=bor_feature_uri(bor.boom_id),
            ),
        )
    )

    if bor.species_latin is not None:
        obj.species = CodeType(
            value=bor.species_latin, code_space=CS_EMMEN_BOR_TREES,
        )

    if bor.planting_year is not None:
        obj.int_attribute.append(
            IntAttribute(name="plantingYear", value=bor.planting_year)
        )

    for name, value in (
        ("speciesCommonName", bor.species_dutch),
        ("heightClass", bor.height_class),
        ("trunkDiameterClass", bor.trunk_diameter_class),
        ("protectionStatus", bor.protection_status),
        ("protectionStatusDetail", bor.protection_status_detail),
        ("growthForm", bor.growth_form),
        ("standLocation", bor.stand_location),
        ("standLocationDetail", bor.stand_location_detail),
    ):
        if value is None:
            continue
        obj.string_attribute.append(StringAttribute(name=name, value=value))


def _geometry_property_from_polygons(
    gml_id: str,
    polygons: list[GeometryPolygon],
    *,
    srs_name: str,
    srs_dimension: int,
) -> Any:
    """Wrap a polygon list as a ``gml:GeometryPropertyType`` holding a MultiSurface.

    ``SolitaryVegetationObject.lod3Geometry`` is typed
    ``gml:GeometryPropertyType`` (a generic geometry container) so the
    contained element is a ``gml:MultiSurface``. We therefore build a
    ``MultiSurfacePropertyType`` first and then copy its inner
    ``MultiSurface`` onto a fresh ``GeometryPropertyType``; this is a
    single-level re-wrap, not a copy of polygon data, so the cost is
    minimal.
    """
    from ...bindings import GeometryPropertyType

    ms_prop = build_multi_surface(
        gml_id, polygons,
        srs_name=srs_name, srs_dimension=srs_dimension,
    )
    return GeometryPropertyType(multi_surface=ms_prop.multi_surface)


def _apply_cftree_morphometrics(obj: Any, attrs: dict[str, Any]) -> None:
    """Write CFTree morphometric values onto a SolitaryVegetationObject.

    Native fields get :class:`LengthType` measures tagged with the
    viewer-friendly ``m`` uom token. Everything else in
    :data:`_CFTREE_GENERIC_DOUBLE` becomes a ``gen:doubleAttribute``.
    Other attribute keys (``gtid``, ``original_gtid``, unknown future
    metrics) are ignored here because they feed into ``gml:id`` /
    ``gml:name`` upstream or carry no clean CityGML mapping. Downstream
    tools that need the original gtid should read it from ``gml:name``
    (``T_<gtid>``).
    """
    for cftree_key, field_name in _CFTREE_NATIVE_FIELDS.items():
        value = to_finite_float(attrs.get(cftree_key))
        if value is None:
            continue
        setattr(obj, field_name, LengthType(value=value, uom=UOM_METRES))

    for cftree_key in _CFTREE_GENERIC_DOUBLE:
        value = to_finite_float(attrs.get(cftree_key))
        if value is None:
            continue
        obj.double_attribute.append(
            DoubleAttribute(name=cftree_key, value=value)
        )
