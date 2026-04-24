"""Unit tests for the xsdata construction helpers in the city builder."""

from __future__ import annotations

from datetime import date

import pytest

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.builders import (
    attach_building_units_to_building,
    build_address,
    build_building,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel


def _square(z: float, surface_type: str | None = None) -> SemanticPolygon:
    return SemanticPolygon(
        polygon=GeometryPolygon(
            exterior=[(0.0, 0.0, z), (1.0, 0.0, z), (1.0, 1.0, z), (0.0, 1.0, z)],
        ),
        surface_type=surface_type,
    )


def _parsed() -> ParsedBuilding:
    return ParsedBuilding(
        pand_id="0503100000000001",
        attributes={"oorspronkelijkbouwjaar": 1985},
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(0.0), _square(3.0)],
        },
    )


def _vbo(
    street: str = "Mekelweg",
    point: tuple[float, float] | None = None,
) -> Verblijfsobject:
    return Verblijfsobject(
        identificatie="0503010000000042",
        pand_identificatie="0503100000000001",
        gebruiksdoel=["woonfunctie"],
        oppervlakte=85.0,
        status="Verblijfsobject in gebruik",
        postcode="2628CD",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam=street,
        point=point,
        properties={},
    )


def _resolved(energy: str | None = None, street: str = "Mekelweg") -> ResolvedAddress:
    label = None
    if energy is not None:
        label = EnergyLabel(
            postcode="2628CD",
            huisnummer=42,
            huisletter=None,
            toevoeging=None,
            bag_verblijfsobject_id=None,
            energieklasse=energy,
            registratiedatum=date(2024, 1, 1),
            opnamedatum=None,
            geldig_tot=date(2034, 1, 1),
        )
    return ResolvedAddress(vbo=_vbo(street=street), energy_label=label)


# ---------------------------------------------------------------------------
# build_building
# ---------------------------------------------------------------------------


def test_build_building_sets_id_and_year_of_construction() -> None:
    building = build_building(_parsed())
    # BAG identificaties are pure digits → not valid xs:ID; builder prepends
    # a semantic kind prefix ("pand") to stay schema-valid.
    assert building.id == "pand_0503100000000001"
    assert str(building.year_of_construction) == "1985"


def test_build_building_attaches_only_requested_lods() -> None:
    only_lod0 = build_building(_parsed(), lods=(0,))
    assert only_lod0.lod0_foot_print is not None
    assert only_lod0.lod1_solid is None


def test_build_building_lod1_is_solid_with_composite_surface() -> None:
    building = build_building(_parsed(), lods=(1,))
    shell = building.lod1_solid.solid.exterior.composite_surface
    assert shell.id.endswith("_lod1_shell")


def _posns_of_lod0(building) -> list[list[float]]:
    """Flatten every gml:posList value in the LoD 0 MultiSurface."""
    return [
        poly.polygon.exterior.linear_ring.pos_list.value
        for poly in building.lod0_foot_print.multi_surface.surface_member
    ]


def test_build_building_lifts_lod0_to_b3_h_maaiveld() -> None:
    """3DBAG publishes LoD 0 at NAP=0 while LoD 1/2 sit on the
    terrain height ``b3_h_maaiveld``. In elevated areas (e.g. Emmer-
    Compascuum at ~13 m NAP) the two representations are otherwise
    rendered metres apart vertically. The builder must re-anchor every
    LoD 0 vertex to the maaiveld.
    """
    parsed = ParsedBuilding(
        pand_id="0114100000202121",
        attributes={"oorspronkelijkbouwjaar": 1985, "b3_h_maaiveld": 13.35},
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(13.35), _square(16.9)],
        },
    )
    building = build_building(parsed, lods=(0,))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 13.35 for z in zs), f"expected all z=13.35, got {zs}"


def test_build_building_lod0_falls_back_to_min_lod1_when_maaiveld_missing() -> None:
    """Without ``b3_h_maaiveld`` we still avoid a below-ground LoD 0:
    the builder falls back to the minimum Z observed on LoD 1 (or 2).
    """
    parsed = ParsedBuilding(
        pand_id="0114100000000001",
        attributes={"oorspronkelijkbouwjaar": 1985},  # no maaiveld
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(12.1), _square(16.4)],
        },
    )
    building = build_building(parsed, lods=(0,))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 12.1 for z in zs), f"expected all z=12.1, got {zs}"


def test_build_building_lod0_leaves_geometry_untouched_when_no_ground_hint() -> None:
    """No maaiveld, no LoD 1, no LoD 2: return the polygons as-is
    rather than invent a ground plane.
    """
    parsed = ParsedBuilding(
        pand_id="x",
        attributes={},
        geometries={"0": [_square(0.0, "GroundSurface")]},
    )
    building = build_building(parsed, lods=(0,))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 0.0 for z in zs)


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------


def test_build_address_composes_xal_structure() -> None:
    address = build_address(_resolved())
    assert address is not None
    locality = address.xal_address.address_details.locality
    assert locality is not None
    assert locality.thoroughfare.thoroughfare_name[0].content[0] == "Mekelweg"
    assert locality.thoroughfare.thoroughfare_number[0].content[0] == "42"
    assert locality.postal_code.postal_code_number[0].content[0] == "2628CD"


def test_build_address_returns_none_without_street() -> None:
    resolved = _resolved(street="")
    assert build_address(resolved) is None


# ---------------------------------------------------------------------------
# BuildingUnit + EPC
# ---------------------------------------------------------------------------


def test_attach_building_units_creates_one_per_address() -> None:
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved("A"), _resolved("B")])
    assert len(building.building_unit) == 2


def test_building_unit_without_label_omits_epc() -> None:
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved(None)])
    unit = building.building_unit[0].building_unit
    assert unit.energy_performance_certificate == []


def test_building_unit_with_label_emits_epc_with_valid_from() -> None:
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved("A")])
    unit = building.building_unit[0].building_unit
    epc = unit.energy_performance_certificate[0].energy_performance_certificate
    assert epc.label == "A"
    assert epc.valid_from is not None


# ---------------------------------------------------------------------------
# BAG-id cross-reference (point 3)
# ---------------------------------------------------------------------------


def test_building_carries_bag_pand_identifier_with_codespace() -> None:
    """The Pand identificatie is exposed as an nrg3:identifier with the
    Dutch BAG linked-data URL as its codeSpace, matching the per-building-input
    sample at ``inputs/owner_occupier_building.json:35``. Concatenating the
    codeSpace + value reconstructs the full dereferenceable URL.
    """
    from citygml_energy.namespaces import CS_BAG_PAND

    building = build_building(_parsed())
    assert len(building.identifier) == 1
    ident = building.identifier[0]
    assert ident.value == "0503100000000001"
    assert ident.code_space == CS_BAG_PAND
    # Round-trip the URL to make sure the codeSpace is the right prefix.
    assert CS_BAG_PAND.endswith("/")
    assert (ident.code_space + ident.value).startswith("http://bag.")


def test_building_unit_carries_bag_vbo_identifier_with_codespace() -> None:
    """Mirror of the Pand-identifier test for VBOs. Same per-building-input
    pattern, different codeSpace base.
    """
    from citygml_energy.namespaces import CS_BAG_VERBLIJFSOBJECT

    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved()])
    unit = building.building_unit[0].building_unit
    assert len(unit.identifier) == 1
    ident = unit.identifier[0]
    assert ident.value == "0503010000000042"
    assert ident.code_space == CS_BAG_VERBLIJFSOBJECT


# ---------------------------------------------------------------------------
# VBO oppervlakte → nrg3:area QualifiedArea (point 4)
# ---------------------------------------------------------------------------


def test_building_unit_carries_vbo_oppervlakte_as_qualified_area() -> None:
    """BAG ``oppervlakte`` (NEN 2580 usable floor area) is attached as
    a ``nrg3:area`` / ``QualifiedArea`` entry on the BuildingUnit with
    type ``netFloorArea`` (the closest match in the Energy ADE 3.0
    ``AreaTypeValue`` codelist). Source text pins BAG provenance so
    a reader can recover the exact NEN 2580 semantics.
    """
    from citygml_energy.namespaces import CS_NRG3_AREA_TYPE

    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved()])
    unit = building.building_unit[0].building_unit
    assert len(unit.area) == 1
    qa = unit.area[0].qualified_area
    assert qa.value.value == 85.0
    assert qa.value.uom == "m2"
    assert qa.type_value.value == "netFloorArea"
    assert qa.type_value.code_space == CS_NRG3_AREA_TYPE
    # Provenance is documented in the source string so downstream tools
    # can resolve the precise NEN 2580 definition (gebruiksoppervlakte
    # != international netFloorArea at the edges).
    assert "BAG" in qa.source
    assert "NEN 2580" in (qa.description or "")


def test_building_unit_without_oppervlakte_omits_qualified_area() -> None:
    """A VBO with ``oppervlakte=None`` must not emit an empty area entry."""
    resolved = _resolved()
    object.__setattr__(resolved.vbo, "oppervlakte", None)  # frozen dataclass workaround
    building = build_building(_parsed())
    attach_building_units_to_building(building, [resolved])
    unit = building.building_unit[0].building_unit
    assert unit.area == []


# ---------------------------------------------------------------------------
# 3DBAG attributes → Building (point 5)
# ---------------------------------------------------------------------------


def _parsed_with_3dbag_attrs(**extra) -> ParsedBuilding:
    """Parsed building with a 3DBAG-like attribute payload."""
    attrs = {
        "oorspronkelijkbouwjaar": 1985,
        "b3_bouwlagen": 3,
        "b3_h_maaiveld": 0.175,
        "b3_h_dak_max": 9.925,
        "b3_dak_type": "slanted",
        "b3_volume_lod22": 752.575,
    }
    attrs.update(extra)
    return ParsedBuilding(
        pand_id="0503100000000001",
        attributes=attrs,
        geometries={
            "0": [_square(0.175, "GroundSurface")],
            "1": [_square(0.175), _square(9.925)],
        },
    )


def test_building_maps_b3_bouwlagen_to_storeys_above_ground() -> None:
    """``b3_bouwlagen`` is the 3DBAG floor-count attribute (non-negative
    integer). It maps directly to ``bldg:storeysAboveGround``.
    """
    building = build_building(_parsed_with_3dbag_attrs())
    assert building.storeys_above_ground == 3


def test_building_computes_measured_height_from_b3_h_dak_max_minus_maaiveld() -> None:
    """``bldg:measuredHeight`` is "the measured height of the building"
    (``gml:LengthType``). The Dutch convention is
    ground-to-highest-roof-point, exactly ``b3_h_dak_max - b3_h_maaiveld``
    for 3DBAG-derived data. Using ``b3_h_dak_max`` (not ``b3_h_dak_70p``)
    so antenna/chimney tips register as part of the physical extent.
    """
    building = build_building(_parsed_with_3dbag_attrs())
    assert building.measured_height is not None
    # 9.925 - 0.175 = 9.750
    assert building.measured_height.value == 9.75
    assert building.measured_height.uom == "m"


def test_building_omits_measured_height_when_roof_below_maaiveld() -> None:
    """Defensive: a corrupt tile where roof < ground must not produce
    a negative measuredHeight. The builder skips the field instead.
    """
    building = build_building(_parsed_with_3dbag_attrs(
        b3_h_maaiveld=10.0, b3_h_dak_max=8.0,
    ))
    assert building.measured_height is None


def test_building_maps_b3_dak_type_to_roof_type_with_3dbag_codespace() -> None:
    """3DBAG's string roof-type enumeration (``slanted`` / ``horizontal``
    / ``multiple horizontal``) is NOT a member of SIG3D's numeric
    roof-type codelist. Emitting the 3DBAG value with a 3DBAG-owned
    codeSpace documents the source vocabulary honestly; mapping to SIG3D
    would mis-label the enumeration.
    """
    from citygml_energy.namespaces import CS_3DBAG_DAK_TYPE

    building = build_building(_parsed_with_3dbag_attrs())
    assert building.roof_type is not None
    assert building.roof_type.value == "slanted"
    assert building.roof_type.code_space == CS_3DBAG_DAK_TYPE


def test_building_attaches_b3_volume_lod22_as_bdg_volume() -> None:
    """Building volume at LoD 2.2 lands as ``nrg3:bdgVolume`` (Energy ADE
    extension on AbstractBuildingType) with type ``grossVolume``,
    mirroring the per-building-input ``bdg_volume`` pattern. uom is ``m3``
    (primary id in UOMList.xml). ``bldg:Building`` itself has no
    native ``volume`` slot — the Energy ADE adds it.
    """
    from citygml_energy.namespaces import CS_NRG3_VOLUME_TYPE

    building = build_building(_parsed_with_3dbag_attrs())
    assert len(building.bdg_volume) == 1
    qv = building.bdg_volume[0].qualified_volume
    assert qv.value.value == 752.575
    assert qv.value.uom == "m3"
    assert qv.type_value.value == "grossVolume"
    assert qv.type_value.code_space == CS_NRG3_VOLUME_TYPE
    assert "3DBAG" in qv.source


def test_building_skips_3dbag_attributes_when_absent() -> None:
    """A building without any ``b3_*`` attributes (e.g. a hand-curated
    fixture, not a 3DBAG-derived one) must not populate the new fields.
    """
    building = build_building(_parsed())  # only oorspronkelijkbouwjaar
    assert building.storeys_above_ground is None
    assert building.measured_height is None
    assert building.roof_type is None
    assert building.bdg_volume == []


# ---------------------------------------------------------------------------
# EPC certification_method from EP-online Berekeningstype (point 6 partial)
# ---------------------------------------------------------------------------


def test_epc_carries_berekeningstype_as_certification_method() -> None:
    """EP-online's ``Berekeningstype`` names the NTA-8800 variant used
    for the label calculation. The CityGML target is
    ``nrg3:EnergyPerformanceCertificate/certificationMethod`` (xs:string);
    we emit the raw Berekeningstype so the label's provenance stays
    auditable against the NTA-8800 standard.
    """
    label = EnergyLabel(
        postcode="2628CD",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=None,
        energieklasse="A",
        registratiedatum=date(2024, 1, 1),
        opnamedatum=None,
        geldig_tot=date(2034, 1, 1),
        berekeningstype="NTA 8800:2024 (basisopname woningbouw)",
    )
    resolved = ResolvedAddress(vbo=_vbo(), energy_label=label)
    building = build_building(_parsed())
    attach_building_units_to_building(building, [resolved])
    unit = building.building_unit[0].building_unit
    epc = unit.energy_performance_certificate[0].energy_performance_certificate
    assert epc.certification_method == "NTA 8800:2024 (basisopname woningbouw)"


def test_epc_omits_certification_method_when_berekeningstype_absent() -> None:
    """Labels without a populated Berekeningstype (rare in practice)
    leave ``certificationMethod`` unset, not an empty string.
    """
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved("A")])
    unit = building.building_unit[0].building_unit
    epc = unit.energy_performance_certificate[0].energy_performance_certificate
    assert epc.certification_method is None


# ---------------------------------------------------------------------------
# Boundary cases for the new attribute mappings.
#
# The "happy path" tests above cover the common case (non-empty, positive,
# non-zero). These lock down what happens at the exact boundaries --
# ``oppervlakte == 0``, ``h_dak_max == h_maaiveld``, empty ``dak_type`` --
# which is where ``>`` vs ``>=`` and truthiness-of-empty-string bugs live.
#
# Parametrised per-field so one failure line tells you exactly which
# boundary broke, and adding a new value is one tuple, not a new function.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("oppervlakte", "reason"),
    [
        (0.0, "zero is degenerate (no physical area)"),
        (-1.0, "negative is nonsensical + XSD-invalid"),
    ],
    ids=["zero", "negative"],
)
def test_building_unit_rejects_non_positive_oppervlakte(
    oppervlakte: float, reason: str
) -> None:
    """Guarded by ``> 0`` in the builder; this lock-down confirms ``>= 0``
    would be wrong."""
    resolved = _resolved()
    object.__setattr__(resolved.vbo, "oppervlakte", oppervlakte)
    building = build_building(_parsed())
    attach_building_units_to_building(building, [resolved])
    unit = building.building_unit[0].building_unit
    assert unit.area == [], f"expected no QualifiedArea when {reason}"


@pytest.mark.parametrize(
    ("maaiveld", "dak_max"),
    [
        (5.0, 5.0),    # zero-height building: impossible, must drop
        (10.0, 8.0),   # roof below ground: also drop
    ],
    ids=["equal", "roof_below_ground"],
)
def test_building_omits_measured_height_for_degenerate_geometry(
    maaiveld: float, dak_max: float
) -> None:
    """The strict ``>`` guard in the builder drops both zero-height and
    inverted-roof cases; ``>=`` would emit ``measuredHeight = 0`` which
    is misleading."""
    building = build_building(_parsed_with_3dbag_attrs(
        b3_h_maaiveld=maaiveld, b3_h_dak_max=dak_max,
    ))
    assert building.measured_height is None


@pytest.mark.parametrize(
    ("field", "value", "attr", "expected"),
    [
        ("b3_dak_type", "", "roof_type", None),
        ("b3_volume_lod22", 0.0, "bdg_volume", []),
        ("b3_volume_lod22", -1.0, "bdg_volume", []),
        ("b3_bouwlagen", -1, "storeys_above_ground", None),
        ("b3_bouwlagen", "not-a-number", "storeys_above_ground", None),
    ],
    ids=[
        "empty_dak_type_drops_roof_type",
        "zero_volume_drops_bdg_volume",
        "negative_volume_drops_bdg_volume",
        "negative_bouwlagen_drops_storeys",
        "non_integer_bouwlagen_drops_storeys",
    ],
)
def test_3dbag_attributes_reject_boundary_values(
    field: str, value, attr: str, expected
) -> None:
    """Each (field, value) pair exercises one boundary guard in
    ``_apply_building_attributes``: empty strings, zeros, negatives, and
    non-coercible values must never surface in the output."""
    building = build_building(_parsed_with_3dbag_attrs(**{field: value}))
    assert getattr(building, attr) == expected


def test_building_accepts_zero_storeys_above_ground() -> None:
    """``b3_bouwlagen == 0`` is legitimate (e.g. a free-standing shed or
    storage container at grade). The builder's ``>= 0`` guard accepts
    it; this lock-down makes sure future tightening to ``> 0`` doesn't
    happen silently."""
    building = build_building(_parsed_with_3dbag_attrs(b3_bouwlagen=0))
    assert building.storeys_above_ground == 0
