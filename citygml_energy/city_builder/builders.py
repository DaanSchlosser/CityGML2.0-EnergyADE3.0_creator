"""Construct xsdata ``Building``, ``Address``, ``BuildingUnit`` and EPC objects.

Isolating xsdata construction from the pipeline orchestrator keeps
``pipeline.py`` readable and makes these builders independently unit-
testable: each helper returns a fully-populated dataclass that can be
XSD-validated in a handful of lines.

Every xsdata class is resolved through
:func:`citygml_energy.mapping.resolve_class` so regenerating bindings
cannot break this module unless XSD element names themselves change.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from .._step import GeometryPolygon
from ..bindings import (
    BdgVolume,
    CodeType,
    DateAttribute,
    DoubleAttribute,
    ExternalObjectReferenceType1,
    ExternalReferenceType1,
    Identifier,
    LengthType,
    MeasureType,
    Name,
    QualifiedArea,
    QualifiedAreaPropertyType,
    QualifiedVolume,
    ThoroughfareNameType,
)
from ..gml_builders import build_multi_point, build_multi_surface, build_solid
from ..mapping import get_fields, resolve_class
from ..namespaces import (
    CS_3DBAG_DAK_TYPE,
    CS_BAG_PAND,
    CS_BAG_VERBLIJFSOBJECT,
    CS_BUILDING_FUNCTION,
    CS_NRG3_AREA_TYPE,
    CS_NRG3_EPC_TYPE,
    CS_NRG3_VOLUME_TYPE,
    DEFAULT_SRS_DIMENSION,
    DEFAULT_SRS_NAME,
)
from ..schema_types import (
    ADDRESS,
    BUILDING,
    BUILDING_UNIT,
    CITYGML_SURFACE_TYPES,
    ENERGY_PERFORMANCE_CERTIFICATE,
    SOLITARY_VEGETATION_OBJECT,
    XAL_ADDRESS_DETAILS,
    XAL_LOCALITY,
    XAL_POSTAL_CODE,
    XAL_THOROUGHFARE,
    XAL_THOROUGHFARE_NUMBER,
)
from .address_match import ResolvedAddress
from .cityjson_parse import ParsedBuilding, SemanticPolygon
from .cityjson_trees_parse import ParsedTree
from .fetchers.bgt import (
    BGT_INFORMATION_SYSTEM_URL,
    BgtTree,
    bgt_feature_uri,
)
from .fetchers.eponline import EnergyLabel

__all__ = [
    "EnergyLabel",
    "build_address",
    "build_building",
    "build_building_unit",
    "build_solitary_vegetation_object",
]


@cache
def _inner_type(parent_cls: type, field_name: str) -> type | None:
    """Return the unwrapped inner type of ``parent_cls.field_name`` or ``None``.

    Memoised by ``(parent_cls, field_name)``: the answer is a pure
    function of the binding class and never varies across runs.
    """
    info = get_fields(parent_cls).get(field_name)
    if info is None or not isinstance(info.inner_type, type):
        return None
    return info.inner_type


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


def build_building(
    parsed: ParsedBuilding,
    *,
    gml_id_prefix: str = "",
    lods: tuple[int, ...] = (0, 1, 2),
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
    surface_targets_out: list[str] | None = None,
) -> Any:
    """Build a ``bldg:Building`` from a parsed 3DBAG Pand.

    LoD 0 → ``lod0FootPrint`` (MultiSurface).
    LoD 1 → ``lod1Solid`` (CompositeSurface shell).
    LoD 2 → ``boundedBy`` with ``bldg:GroundSurface``, ``bldg:WallSurface``,
             and ``bldg:RoofSurface`` elements, each carrying its own
             ``lod2MultiSurface``.  Polygons without a recognised semantic
             type are assigned to WallSurface.

    When *surface_targets_out* is supplied, every colorable surface id
    created here is appended to it: the LoD 0 ``gml:MultiSurface`` plus
    each of its member ``gml:Polygon`` ids, the LoD 1 ``gml:CompositeSurface``
    shell plus each of its member ``gml:Polygon`` ids, and one
    ``gml:MultiSurface`` per LoD 2 thematic surface plus its member
    ``gml:Polygon`` ids. Per-polygon ids are included because some viewers
    (KIT SDM_KITModelViewer among them) only resolve appearance targets
    that point at individual ``gml:Polygon`` elements and silently skip
    targets that point at a container ``gml:MultiSurface`` /
    ``gml:CompositeSurface``. The pipeline uses this pre-collected list
    to avoid a per-building :func:`iter_instances` walk when building
    the ``app:Appearance`` (see
    :func:`citygml_energy.city_builder.appearance.append_energy_label_appearance`).
    """
    gml_id = _safe_gml_id(gml_id_prefix, "pand", parsed.pand_id)
    building_cls = resolve_class(BUILDING)
    building = building_cls(id=gml_id, name=[Name(value=parsed.pand_id)])

    # BAG Pand id attached as an nrg3:identifier with the authoritative
    # linked-data codeSpace (see schemas/namespace_prefixes.json and
    # CS_BAG_PAND). Matches the pattern in inputs/owner_occupier_building.json:35.
    # The codeSpace + value concatenate to the full dereferenceable URL
    # (`rdf_seealso` in the PDOK BAG WFS response), so we do not need to
    # round-trip the URL prefix from the fetcher.
    building.identifier.append(
        Identifier(value=parsed.pand_id, code_space=CS_BAG_PAND)
    )

    _apply_building_attributes(building, parsed.attributes)

    if 0 in lods and parsed.geometries.get("0"):
        polygons_lod0 = _lift_lod0_to_ground(
            _unwrap_polygons(parsed.geometries["0"]), parsed
        )
        building.lod0_foot_print = build_multi_surface(
            f"{gml_id}_lod0",
            polygons_lod0,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )
        if surface_targets_out is not None:
            surface_targets_out.append(f"#{gml_id}_lod0")
            _extend_polygon_targets(
                surface_targets_out, f"{gml_id}_lod0", len(polygons_lod0)
            )

    if 1 in lods and parsed.geometries.get("1"):
        polygons_lod1 = _unwrap_polygons(parsed.geometries["1"])
        # 3DBAG publishes LoD 1/2 CityJSON with outward-facing rings already,
        # per the CityJSON spec. The centroid-based heuristic in
        # ``orient_solid_polygons`` can mis-flip walls on concave facades
        # (L- and U-shapes), which produces inward-facing polygons that
        # viewers then back-face-cull. Trust the source orientation here.
        building.lod1_solid = build_solid(
            f"{gml_id}_lod1",
            polygons_lod1,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
            orient=False,
        )
        if surface_targets_out is not None:
            surface_targets_out.append(f"#{gml_id}_lod1_shell")
            _extend_polygon_targets(
                surface_targets_out, f"{gml_id}_lod1", len(polygons_lod1)
            )

    if 2 in lods and parsed.geometries.get("2"):
        _attach_lod2_thematic_surfaces(
            building,
            parsed.geometries["2"],
            gml_id=gml_id,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
            surface_targets_out=surface_targets_out,
        )

    return building


def _lift_lod0_to_ground(
    polygons_lod0: list[GeometryPolygon], parsed: ParsedBuilding
) -> list[GeometryPolygon]:
    """Stamp every LoD 0 vertex Z with the building's ground height.

    3DBAG publishes the LoD 0 footprint at nominal Z = 0 (NAP) while
    LoD 1 / 2 sit on the building-specific terrain height
    ``b3_h_maaiveld``. Consequence: in elevated terrain (Emmer-Compascuum
    at ~13 m NAP, Nijmegen 60 m+) the LoD 0 footprint appears floating
    metres below the building base and viewers render the two
    representations pulled apart vertically. Lifting LoD 0 to
    ``b3_h_maaiveld`` (or, if the attribute is missing, the minimum Z of
    LoD 1 / 2, which coincides with the maaiveld in every 3DBAG tile
    inspected) re-aligns the footprint with the building.
    """
    target_z = _as_float(parsed.attributes.get("b3_h_maaiveld"))
    if target_z is None:
        target_z = _min_ring_z_of(parsed.geometries.get("1")) or _min_ring_z_of(
            parsed.geometries.get("2")
        )
    if target_z is None:
        return polygons_lod0  # nothing to anchor against
    if all(
        z == target_z
        for p in polygons_lod0
        for (_x, _y, z) in p.exterior
    ):
        return polygons_lod0  # already at maaiveld: common on flat terrain
    return [
        GeometryPolygon(
            exterior=[(x, y, target_z) for (x, y, _z) in p.exterior],
            interiors=[
                [(x, y, target_z) for (x, y, _z) in ring] for ring in p.interiors
            ],
        )
        for p in polygons_lod0
    ]


def _min_ring_z_of(semantic_polygons: list[SemanticPolygon] | None) -> float | None:
    if not semantic_polygons:
        return None
    zs = [z for sp in semantic_polygons for (_x, _y, z) in sp.polygon.exterior]
    return min(zs) if zs else None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _apply_building_attributes(building: Any, attrs: dict[str, Any]) -> None:
    """Write commonly-useful 3DBAG attributes onto the building.

    Maps the subset of 3DBAG's ~60 attributes that have a clean native
    CityGML / Energy ADE target:

    * ``oorspronkelijkbouwjaar`` → ``bldg:yearOfConstruction`` (BAG /
      3DBAG always agree; ``_merge_attributes`` ensures BAG wins on
      ties).
    * ``gebruiksdoel`` → ``bldg:function`` (rare on 3DBAG Building
      nodes; the VBO carries the real value).
    * ``b3_bouwlagen`` → ``bldg:storeysAboveGround`` — count of
      above-ground storeys (integer, non-negative).
    * ``b3_h_dak_max - b3_h_maaiveld`` → ``bldg:measuredHeight`` —
      total physical height of the building in metres. ``measuredHeight``
      in the CityGML 2.0 XSD is ``gml:LengthType`` ("The measured
      height [of the building]") with no dictated reference point; the
      Dutch convention is ground-to-highest-roof-point, which is
      exactly ``max(roof) - maaiveld``. We prefer ``b3_h_dak_max`` over
      ``b3_h_dak_70p`` so antenna / chimney tips register as part of
      the building's physical extent, not a statistical percentile.
    * ``b3_dak_type`` → ``bldg:roofType`` with
      :data:`CS_3DBAG_DAK_TYPE` as the codeSpace. The 3DBAG vocabulary
      (``horizontal`` / ``slanted`` / ``multiple horizontal``) is NOT
      a member of SIG3D's numeric roof-type codelist, so labelling it
      as SIG3D would mis-represent the vocabulary. A 3DBAG-owned
      codeSpace documents the source enumeration honestly.
    * ``b3_volume_lod22`` → ``nrg3:area``-style ``QualifiedVolume``
      with type ``grossVolume``. Matches the per-building-input pattern at
      ``inputs/owner_occupier_building.json::bdg_volume``, so a single GML file
      can mix 3DBAG-measured and per-building-input-declared volumes transparently.
    """
    year = _as_int(attrs.get("oorspronkelijkbouwjaar"))
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

    bouwlagen = _as_int(attrs.get("b3_bouwlagen"))
    if bouwlagen is not None and bouwlagen >= 0:
        building.storeys_above_ground = bouwlagen

    h_dak = _as_float(attrs.get("b3_h_dak_max"))
    h_maaiveld = _as_float(attrs.get("b3_h_maaiveld"))
    if h_dak is not None and h_maaiveld is not None and h_dak > h_maaiveld:
        building.measured_height = LengthType(
            value=round(h_dak - h_maaiveld, 3), uom=_UOM_METRES,
        )

    dak_type = attrs.get("b3_dak_type")
    if isinstance(dak_type, str) and dak_type:
        building.roof_type = CodeType(value=dak_type, code_space=CS_3DBAG_DAK_TYPE)

    volume = _as_float(attrs.get("b3_volume_lod22"))
    if volume is not None and volume > 0:
        # ``bldg:Building`` is a CityGML class that does not carry a
        # native ``volume`` list; the Energy ADE adds one under the name
        # ``bdgVolume`` whose property type is a
        # ``QualifiedVolumePropertyType`` specialisation ``BdgVolume``.
        # Structure matches ``inputs/owner_occupier_building.json::bdg_volume``.
        building.bdg_volume.append(
            BdgVolume(
                qualified_volume=QualifiedVolume(
                    description=(
                        "Gross volume computed by 3DBAG from the LoD 2.2 "
                        "roof-shape reconstruction."
                    ),
                    source="3DBAG b3_volume_lod22",
                    value=MeasureType(value=round(volume, 3), uom=_UOM_VOLUME_M3),
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


def _attach_lod2_thematic_surfaces(
    building: Any,
    semantic_polygons: list[SemanticPolygon],
    *,
    gml_id: str,
    srs_name: str,
    srs_dimension: int,
    surface_targets_out: list[str] | None = None,
) -> None:
    """Group *semantic_polygons* by surface type and attach as ``bldg:boundedBy``.

    Each recognised surface type (GroundSurface, WallSurface, RoofSurface)
    gets one ``bldg:boundedBy`` element whose inner surface carries a single
    ``bldg:lod2MultiSurface`` containing all polygons of that type.
    Polygons with an unrecognised or missing type fall back to WallSurface.

    When *surface_targets_out* is supplied, every ``lod2_multi_surface`` id
    created here is appended to it so the pipeline can build the
    ``app:Appearance`` targets without an extra tree walk.
    """
    groups: dict[str, list[GeometryPolygon]] = {}
    for sp in semantic_polygons:
        key = sp.surface_type if sp.surface_type in _SURFACE_TYPES else _FALLBACK_SURFACE
        groups.setdefault(key, []).append(sp.polygon)

    if not groups:
        return

    # mypy stub for ``_lru_cache_wrapper`` rejects ``type[Any]``; safe.
    wrapper_cls = _inner_type(type(building), "bounded_by")  # type: ignore[arg-type]
    if wrapper_cls is None:
        return

    for surf_type, polygons in groups.items():
        xsd_name, field_name = _SURFACE_TYPES[surf_type]
        surf_cls = resolve_class(xsd_name)
        surf_id = f"{gml_id}_{surf_type.lower()}"
        surf = surf_cls(id=surf_id)
        surf.lod2_multi_surface = build_multi_surface(
            f"{surf_id}_ms",
            polygons,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )
        building.bounded_by.append(wrapper_cls(**{field_name: surf}))
        if surface_targets_out is not None:
            surface_targets_out.append(f"#{surf_id}_ms")
            _extend_polygon_targets(surface_targets_out, f"{surf_id}_ms", len(polygons))


# ---------------------------------------------------------------------------
# BuildingUnit + attached Address + EPC
# ---------------------------------------------------------------------------


def build_building_unit(
    resolved: ResolvedAddress,
    *,
    gml_id_prefix: str = "",
    city_name: str = "",
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
) -> Any:
    """Build an ``nrg3:BuildingUnit`` for one VBO.

    The VBO's address is attached via ``bldg:address``; the EP-online
    energy label (when matched) is attached via
    ``nrg3:energyPerformanceCertificate``. The mandatory
    ``nrg3:type`` element is filled with the first ``gebruiksdoel``
    value (``woonfunctie``, ``kantoorfunctie``, …).

    ``srs_name`` / ``srs_dimension`` are passed through to
    :func:`build_address` for the VBO ``geometriePunt`` (``core:Address/
    core:multiPoint``).
    """
    unit_cls = resolve_class(BUILDING_UNIT)

    gml_id = _safe_gml_id(gml_id_prefix, "bu", resolved.vbo.identificatie)
    gebruiksdoel = (resolved.vbo.gebruiksdoel or ["other"])[0]
    unit = unit_cls(
        id=gml_id,
        type_value=CodeType(value=gebruiksdoel),
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
                        value=float(resolved.vbo.oppervlakte), uom=_UOM_AREA_M2,
                    ),
                    type_value=CodeType(
                        value="netFloorArea", code_space=CS_NRG3_AREA_TYPE,
                    ),
                )
            )
        )

    address = build_address(
        resolved,
        gml_id_prefix=gml_id_prefix,
        city_name=city_name,
        srs_name=srs_name,
        srs_dimension=srs_dimension,
    )
    if address is not None:
        address_prop_cls = _inner_type(unit_cls, "address")
        if address_prop_cls is not None:
            unit.address.append(address_prop_cls(address=address))

    epc = _build_epc(resolved, gml_id_prefix=gml_id_prefix)
    if epc is not None:
        epc_prop_cls = _inner_type(unit_cls, "energy_performance_certificate")
        if epc_prop_cls is not None:
            unit.energy_performance_certificate.append(
                epc_prop_cls(energy_performance_certificate=epc)
            )

    return unit


def attach_building_units_to_building(
    building: Any,
    addresses: list[ResolvedAddress],
    *,
    gml_id_prefix: str = "",
    city_name: str = "",
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
) -> None:
    """Wrap each resolved VBO in a ``BuildingUnit2`` and attach to *building*."""
    if not addresses:
        return
    # mypy stub for ``_lru_cache_wrapper`` rejects ``type[Any]``; safe.
    wrapper_cls = _inner_type(type(building), "building_unit")  # type: ignore[arg-type]
    if wrapper_cls is None:
        return
    for resolved in addresses:
        unit = build_building_unit(
            resolved,
            gml_id_prefix=gml_id_prefix,
            city_name=city_name,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )
        building.building_unit.append(wrapper_cls(building_unit=unit))


# ---------------------------------------------------------------------------
# core:Address (xAL-flavoured)
# ---------------------------------------------------------------------------


def build_address(
    resolved: ResolvedAddress,
    *,
    gml_id_prefix: str = "",
    city_name: str = "",
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
) -> Any | None:
    """Build a ``core:Address`` for *resolved* or ``None`` when unusable.

    Structure (xAL-inside-core, plus optional ``multiPoint`` for the
    VBO location point):

    .. code-block:: text

        core:Address
          core:xalAddress
            xAL:AddressDetails
              xAL:Locality (type="city")
                xAL:LocalityName ("Delft")
                xAL:Thoroughfare
                  xAL:ThoroughfareNumber ("42")
                  xAL:ThoroughfareName   ("Mekelweg")
                xAL:PostalCode
                  xAL:PostalCodeNumber   ("2628CD")
          core:multiPoint   (present when resolved.point is not None)
            gml:MultiPoint
              gml:pointMember/gml:Point/gml:pos   (VBO geometriePunt)

    The ``core:multiPoint`` element is typed ``gml:MultiPointPropertyType``
    and documented in the XSD as "locating the entrance(s)". BAG's
    ``geometriePunt`` is the authoritative address-locating point for a
    VBO; it always lies within the parent Pand but is not guaranteed
    to be at the entrance. That semantic mismatch is documentation-level
    only: the schema constraint is just "a MultiPoint", and every
    Dutch BAG-to-CityGML converter populates this element the same way.
    """
    street = resolved.street.strip()
    postcode = resolved.postcode.strip()
    huisnummer = resolved.huisnummer
    if not street or huisnummer is None:
        return None

    address_cls = resolve_class(ADDRESS)
    xal_prop_cls = _inner_type(address_cls, "xal_address")
    if xal_prop_cls is None:
        return None

    number_text = _assemble_number(resolved)
    locality = _build_locality(
        street=street,
        number_text=number_text,
        postcode=postcode,
        city_name=city_name,
    )
    details_cls = resolve_class(XAL_ADDRESS_DETAILS)
    address_details = details_cls(locality=locality)

    address_id = _safe_gml_id(gml_id_prefix, "addr", resolved.vbo.identificatie)
    multi_point = None
    if resolved.point is not None:
        multi_point = build_multi_point(
            f"{address_id}_mp",
            [resolved.point],
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )

    address = address_cls(
        id=address_id,
        xal_address=xal_prop_cls(address_details=address_details),
        multi_point=multi_point,
    )
    return address


def _build_locality(*, street: str, number_text: str, postcode: str, city_name: str = "") -> Any:
    locality_cls = resolve_class(XAL_LOCALITY)
    # ``LocalityName`` and ``PostalCodeNumber`` are xsdata-generated nested
    # classes on their parents; ``resolve_class`` returns ``type`` so mypy
    # cannot see the nested attribute. Verified to exist at runtime by the
    # xsd-valid output tests.
    locality_name_cls = locality_cls.LocalityName  # type: ignore[attr-defined]
    thoroughfare_cls = resolve_class(XAL_THOROUGHFARE)
    thoroughfare_number_cls = resolve_class(XAL_THOROUGHFARE_NUMBER)
    postal_code_cls = resolve_class(XAL_POSTAL_CODE)
    postal_code_number_cls = postal_code_cls.PostalCodeNumber  # type: ignore[attr-defined]

    thoroughfare = thoroughfare_cls(
        thoroughfare_number=[thoroughfare_number_cls(content=[number_text])],
        thoroughfare_name=[ThoroughfareNameType(content=[street])],
    )

    postal_code = (
        postal_code_cls(postal_code_number=[postal_code_number_cls(content=[postcode])])
        if postcode
        else None
    )

    return locality_cls(
        locality_name=[locality_name_cls(content=[city_name])],
        thoroughfare=thoroughfare,
        postal_code=postal_code,
    )


def _assemble_number(resolved: ResolvedAddress) -> str:
    parts = [str(resolved.huisnummer)]
    if resolved.huisletter:
        parts.append(resolved.huisletter)
    if resolved.toevoeging:
        parts.append(f"-{resolved.toevoeging}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# EnergyPerformanceCertificate
# ---------------------------------------------------------------------------


def _build_epc(
    resolved: ResolvedAddress,
    *,
    gml_id_prefix: str,
) -> Any | None:
    label = resolved.energy_label
    if label is None or label.energieklasse is None:
        # EPC.label is xs:string and required, so skip when we have no letter.
        return None

    from xsdata.models.datatype import XmlDateTime

    epc_cls = resolve_class(ENERGY_PERFORMANCE_CERTIFICATE)

    epc = epc_cls(
        id=_safe_gml_id(gml_id_prefix, "epc", resolved.vbo.identificatie),
        type_value=CodeType(value="EP-online", code_space=CS_NRG3_EPC_TYPE),
        label=label.energieklasse,
    )
    if label.registratiedatum is not None:
        epc.valid_from = XmlDateTime.from_string(
            f"{label.registratiedatum.isoformat()}T00:00:00"
        )
    if label.geldig_tot is not None:
        epc.valid_to = XmlDateTime.from_string(
            f"{label.geldig_tot.isoformat()}T00:00:00"
        )
    if label.berekeningstype:
        # EP-online's ``Berekeningstype`` names the NTA-8800 variant used
        # for the EPC calculation, e.g.
        # "NTA 8800:2024 (detailopname utiliteitsbouw)". The CityGML /
        # Energy ADE slot for this provenance is
        # ``nrg3:EnergyPerformanceCertificate/certificationMethod``
        # (xs:string, minOccurs=0). Emitting the raw Berekeningstype
        # string keeps the label auditable against the NTA-8800 standard
        # without inventing an intermediate codelist.
        epc.certification_method = label.berekeningstype
    return epc


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


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
# SolitaryVegetationObject (CFTree)
# ---------------------------------------------------------------------------


# gml:id prefix for trees. CFTree's gtid is purely numeric (e.g. ``"42"``),
# which is invalid as ``xs:ID``; the prefix keeps the final id a valid NCName.
_TREE_ID_PREFIX: str = "tree_"

# ``uom`` tokens match the KIT SDM_KITModelViewer Data/UOMList.xml @id values
# so the viewer recognises them in its Properties panel (same convention used
# in :mod:`citygml_energy.city_builder.pv_panels`).
_UOM_METRES: str = "m"  # METRE primary id
_UOM_AREA_M2: str = "m2"  # SQUARE_METRE primary id
_UOM_VOLUME_M3: str = "m3"  # CUBIC_METRE primary id


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
    *,
    gml_id_prefix: str = "",
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
    bgt_match: BgtTree | None = None,
) -> Any:
    """Build a ``veg:SolitaryVegetationObject`` from a CFTree tree.

    Geometry
        Every triangular face from every CityJSON ``Solid`` component
        (crown + trunk + any future components) is flattened into a
        single ``gml:MultiSurface`` and attached as ``veg:lod3Geometry``.
        The watertight crown and trunk meshes stay visually coherent
        because their faces share global RD coordinates — CityGML 2.0
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
          ``externalObject.name = <lokaal_id>`` plus
          ``externalObject.uri = <dereferenceable BGT feature URL>``.
        * ``gen:dateAttribute name="bgtCreationDate"`` when BGT has a
          registry creation date. Deliberately *not* written as
          ``core:creationDate`` because CityGML's ``creationDate``
          semantics is "when this CityObject record was created in the
          dataset", not "when the physical feature was first registered
          in an external register" — misusing it would confuse any
          tool that keys lifecycle logic on it.

        Trees without a BGT match have neither attachment: the
        presence/absence of the ``externalReference`` doubles as a
        "known to BGT" flag without a dedicated generic attribute.

    Per-attribute failures degrade silently: a ``NaN`` / missing /
    non-numeric value for a single morphometric is skipped via
    :func:`_as_finite_float` rather than aborting the tree, so a
    malformed per-tree CityJSON does not kill the whole city build.
    Binding-resolution failures (e.g. a non-existent
    ``veg:SolitaryVegetationObject``) still raise; those are schema
    errors and should surface loudly.
    """
    tree_cls = resolve_class(SOLITARY_VEGETATION_OBJECT)
    gml_id = _safe_gml_id(gml_id_prefix, "tree", tree.gtid)
    obj = tree_cls(id=gml_id, name=[Name(value=f"T_{tree.gtid}")])

    if tree.polygons:
        obj.lod3_geometry = _geometry_property_from_polygons(
            f"{gml_id}_lod3", tree.polygons,
            srs_name=srs_name, srs_dimension=srs_dimension,
        )

    _apply_cftree_morphometrics(obj, tree.attributes)

    if bgt_match is not None:
        _apply_bgt_cross_reference(obj, bgt_match)

    return obj


def _apply_bgt_cross_reference(obj: Any, bgt_match: BgtTree) -> None:
    """Attach a BGT ``vegetatieobject_punt`` cross-reference to *obj*.

    The CityGML 2.0 ``ExternalObjectReferenceType`` is defined as an
    ``xs:choice`` between a ``name`` element and a ``uri`` element —
    exactly one branch must be populated, never both. This function
    populates ``uri`` only; the BGT ``lokaal_id`` is reachable as the
    last path segment of the URL, so picking ``uri`` preserves both
    the dereferenceable-URL and raw-handle semantics in a single
    schema-valid element.

    The creation date, when present, becomes a ``gen:dateAttribute``
    — not a ``core:creationDate`` on the CityObject itself, to avoid
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
    ``MultiSurface`` onto a fresh ``GeometryPropertyType`` — this is a
    single-level re-wrap, not a copy of polygon data, so the cost is
    minimal.
    """
    from ..bindings import GeometryPropertyType

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
    Other attribute keys (``gtid``, ``tile_id``, unknown future
    metrics) are ignored here because they either duplicate ``gml:id``
    or carry no clean CityGML mapping; downstream tools can still
    recover ``gtid`` by stripping the ``tree_`` prefix from ``gml:id``.
    """
    for cftree_key, field_name in _CFTREE_NATIVE_FIELDS.items():
        value = _as_finite_float(attrs.get(cftree_key))
        if value is None:
            continue
        setattr(obj, field_name, LengthType(value=value, uom=_UOM_METRES))

    for cftree_key in _CFTREE_GENERIC_DOUBLE:
        value = _as_finite_float(attrs.get(cftree_key))
        if value is None:
            continue
        obj.double_attribute.append(
            DoubleAttribute(name=cftree_key, value=value)
        )


def _as_finite_float(value: Any) -> float | None:
    """Return *value* as a finite ``float`` or ``None``.

    CFTree writes ``NaN`` for metrics it could not compute (missing DTM
    pixel, degenerate crown, …). We treat NaN, +/-Inf, ``None``, and
    empty strings all as "absent" so they never make it into the GML.
    """
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    # ``math.isnan`` / ``math.isinf`` avoid the float-``==``-NaN trap.
    from math import isfinite

    return result if isfinite(result) else None


def _safe_gml_id(user_prefix: str, kind: str, source_id: str) -> str:
    """Return a valid XML ``xs:ID`` string.

    BAG identificaties are purely numeric, which is invalid as ``xs:ID``
    (it requires the first character to be a letter or underscore). We
    always prepend a semantic prefix (``pand``, ``bu``, ``addr``,
    ``epc``) so the final id is both valid and self-describing. The
    optional caller prefix is layered on top for multi-city merges.
    """
    core = f"{kind}_{source_id}"
    if user_prefix:
        return f"{user_prefix}_{core}"
    return core


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
