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

from .._gml_builders import build_multi_point, build_multi_surface, build_solid
from .._step import GeometryPolygon
from ..bindings import CodeType, Name, ThoroughfareNameType
from ..mapping import get_fields, resolve_class
from ..namespaces import (
    CS_BUILDING_FUNCTION,
    CS_NRG3_EPC_TYPE,
    DEFAULT_SRS_DIMENSION,
    DEFAULT_SRS_NAME,
)
from ..schema_types import (
    ADDRESS,
    BUILDING,
    BUILDING_UNIT,
    CITYGML_SURFACE_TYPES,
    ENERGY_PERFORMANCE_CERTIFICATE,
    XAL_ADDRESS_DETAILS,
    XAL_LOCALITY,
    XAL_POSTAL_CODE,
    XAL_THOROUGHFARE,
    XAL_THOROUGHFARE_NUMBER,
)
from .address_match import ResolvedAddress
from .cityjson_parse import ParsedBuilding, SemanticPolygon
from .fetchers.eponline import EnergyLabel

__all__ = [
    "EnergyLabel",
    "build_address",
    "build_building",
    "build_building_unit",
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

    When *surface_targets_out* is supplied, each colorable surface id
    created here (``#{gml_id}_lod0``, ``#{gml_id}_lod1_shell``, and one
    per LoD 2 thematic surface) is appended to it. The pipeline uses
    this to avoid a per-building :func:`iter_instances` walk when
    building the ``app:Appearance`` (see
    :func:`citygml_energy.city_builder.appearance.append_energy_label_appearance`).
    """
    gml_id = _safe_gml_id(gml_id_prefix, "pand", parsed.pand_id)
    building_cls = resolve_class(BUILDING)
    building = building_cls(id=gml_id, name=[Name(value=parsed.pand_id)])

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

    if 1 in lods and parsed.geometries.get("1"):
        polygons_lod1 = _unwrap_polygons(parsed.geometries["1"])
        building.lod1_solid = build_solid(
            f"{gml_id}_lod1",
            polygons_lod1,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )
        if surface_targets_out is not None:
            surface_targets_out.append(f"#{gml_id}_lod1_shell")

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
    """Write commonly-useful 3DBAG attributes onto the building."""
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


# ---------------------------------------------------------------------------
# LoD 2 thematic surface helpers
# ---------------------------------------------------------------------------

# Surface-type dispatch is centralised in schema_types so the city-scale and
# RenoDAT pipelines share a single source of truth for CityGML thematic
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

    wrapper_cls = _inner_type(type(building), "bounded_by")
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
    wrapper_cls = _inner_type(type(building), "building_unit")
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
    locality_name_cls = locality_cls.LocalityName
    thoroughfare_cls = resolve_class(XAL_THOROUGHFARE)
    thoroughfare_number_cls = resolve_class(XAL_THOROUGHFARE_NUMBER)
    postal_code_cls = resolve_class(XAL_POSTAL_CODE)
    postal_code_number_cls = postal_code_cls.PostalCodeNumber

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
    return epc


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


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
