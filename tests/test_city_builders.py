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


# ---------------------------------------------------------------------------
# EP-online attribution split:
#
# * Pand-level on the Building (one nrg3:Metadata block):
#   - ``gen:intAttribute name="yearOfConstructionEPOnline"`` (from Bouwjaar)
#   - native ``nrg3:bdgType`` with the Dutch Gebouwtype verbatim and the
#     RVO codespace.
# * Per-VBO on each BuildingUnit (one nrg3:Metadata block per unit):
#   - ``gen:stringAttribute name="bdgSubtypeEPOnline"`` (from Gebouwsubtype,
#     Dutch verbatim — there is no native ``nrg3:bdgSubtype``).
#   - renewable share, thermal-zone area, Energy resources.
# ---------------------------------------------------------------------------


def _label_with(**fields) -> EnergyLabel:
    """Return an EnergyLabel with sensible address defaults plus *fields*."""
    base = dict(
        postcode="7881AA",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=None,
        energieklasse="A",
        registratiedatum=date(2024, 5, 14),
        opnamedatum=date(2024, 5, 1),
        geldig_tot=date(2034, 5, 13),
    )
    base.update(fields)
    return EnergyLabel(**base)


def _resolved_with(label: EnergyLabel | None) -> ResolvedAddress:
    return ResolvedAddress(vbo=_vbo(), energy_label=label)


def test_eponline_gebouwsubtype_lands_on_building_unit_verbatim() -> None:
    """``Gebouwsubtype`` → ``gen:stringAttribute name="bdgSubtypeEPOnline"`` on BuildingUnit.

    Per-VBO because two VBOs in one Pand can carry different subtypes
    (mixed-use, partial conversion). The Dutch RVO term is written
    verbatim: there is no translation step and no native
    ``nrg3:bdgSubtype`` element in EnergyADE 3.0.
    """
    from citygml_energy.city_builder.builders import build_building_unit

    label = _label_with(gebouwsubtype="appartement-portiekflat")
    unit = build_building_unit(_resolved_with(label))

    subtypes = [a for a in unit.string_attribute if a.name == "bdgSubtypeEPOnline"]
    assert len(subtypes) == 1
    assert subtypes[0].value == "appartement-portiekflat"


def test_eponline_gebouwtype_does_not_land_on_building_unit() -> None:
    """``Gebouwtype`` is Pand-level → must NOT appear on the BuildingUnit.

    The primary building type is fixed at the structure level; encoding
    it per-VBO would falsely imply that two VBOs of the same Pand can
    have different primary types. The per-VBO secondary qualifier is
    ``Gebouwsubtype`` instead.
    """
    from citygml_energy.city_builder.builders import build_building_unit

    label = _label_with(gebouwtype="Vrijstaande woning")
    unit = build_building_unit(_resolved_with(label))

    assert all(a.name != "bdgTypeEPOnline" for a in unit.string_attribute)


def test_bouwjaar_does_not_land_on_building_unit() -> None:
    """``Bouwjaar`` is a Pand-level fact and must NOT appear on the BuildingUnit.

    A building is constructed once: the year of construction is shared
    across all VBOs in the Pand. EP-online ships ``Bouwjaar`` per-VBO
    only because the CSV is one-row-per-cert. Encoding it per-VBO would
    falsely imply that two VBOs of the same Pand can have different
    construction years.
    """
    from citygml_energy.city_builder.builders import build_building_unit

    label = _label_with(bouwjaar=1955)
    unit = build_building_unit(_resolved_with(label))

    assert all(
        a.name != "yearOfConstructionEPOnline" for a in unit.int_attribute
    )


def test_building_unit_carries_eponline_source_metadata_when_classified() -> None:
    """A single EP-online Metadata block on the BuildingUnit attributes the source.

    Emitted whenever any per-VBO EP-online value lands (Gebouwsubtype,
    renewable share, thermal-zone area, or any of the four Energy
    resources). The qualityDescription explicitly notes that
    ``yearOfConstructionEPOnline`` and ``nrg3:bdgType`` are at the
    Building level (Pand-level facts).
    """
    from citygml_energy.city_builder.builders import build_building_unit

    label = _label_with(gebouwsubtype="rijwoning-tussen")
    unit = build_building_unit(_resolved_with(label))

    metadata_blocks = [
        m for m in unit.metadata if "EP-online" in (m.source or "")
    ]
    assert len(metadata_blocks) == 1
    quality = metadata_blocks[0].quality_description or ""
    assert "bdgSubtypeEPOnline" in quality
    # Confirm the Building-level placement of the Pand-level emissions
    # is documented in the per-VBO Metadata block.
    assert "yearOfConstructionEPOnline" in quality
    assert "nrg3:bdgType" in quality
    assert "Building level" in quality


def test_building_unit_metadata_emitted_for_renewable_share_alone() -> None:
    """A VBO with only the renewable share still gets the Metadata block.

    The block annotates every EP-online-derived per-VBO emission, so it
    must appear whenever any of them appears. Single emissions like a
    bare renewable-share value should not produce an unattributed
    measure attribute.
    """
    from citygml_energy.city_builder.builders import build_building_unit

    label = _label_with(aandeel_hernieuwbare_energie=42.0)
    unit = build_building_unit(_resolved_with(label))

    eponline_metas = [
        m for m in unit.metadata if "EP-online" in (m.source or "")
    ]
    assert len(eponline_metas) == 1


def test_building_unit_metadata_omitted_when_no_eponline_emissions() -> None:
    """A label with no per-VBO EP-online emissions produces no Metadata.

    Lock the empty case: a label with energieklasse and dates but no
    Gebouwsubtype, renewable share, or energy metrics gets no per-VBO
    EP-online Metadata block on the BuildingUnit. (Year-of-construction
    and bdgType metadata, when applicable, live on the Building.)
    """
    from citygml_energy.city_builder.builders import build_building_unit

    label = _label_with(
        gebouwtype=None,
        gebouwsubtype=None,
        bouwjaar=None,
        aandeel_hernieuwbare_energie=None,
        energiebehoefte=None,
        warmtebehoefte=None,
        primaire_fossiele_energie=None,
        berekende_energieverbruik=None,
        berekende_co2_emissie=None,
    )
    unit = build_building_unit(_resolved_with(label))

    eponline_metas = [
        m for m in unit.metadata if "EP-online" in (m.source or "")
    ]
    assert eponline_metas == []


def test_apply_bag_year_metadata_emits_block_when_year_set() -> None:
    """The Building gets one Metadata block per BAG-sourced yearOfConstruction.

    Stays at the Building level because BAG ``bouwjaar`` is structurally
    a Pand-level fact. Symmetric to the per-VBO EP-online Metadata: each
    Metadata block lives co-located with the value it annotates.
    """
    from citygml_energy.city_builder.builders import (
        apply_bag_year_metadata_to_building,
    )

    building = build_building(_parsed())  # BAG year = 1985 from _parsed()
    apply_bag_year_metadata_to_building(building)

    sources = [m.source for m in building.metadata]
    assert any("BAG" in (s or "") for s in sources)


def test_apply_bag_year_metadata_no_op_when_year_unset() -> None:
    """No yearOfConstruction → no Metadata block (nothing to annotate)."""
    from citygml_energy.city_builder.builders import (
        apply_bag_year_metadata_to_building,
    )
    from citygml_energy.city_builder.cityjson_parse import ParsedBuilding

    building = build_building(
        ParsedBuilding(pand_id="0114100000000099", attributes={}, geometries={})
    )
    apply_bag_year_metadata_to_building(building)
    assert building.metadata == []


def test_per_vbo_subtype_does_not_aggregate() -> None:
    """Two VBOs in one Pand each emit their own ``bdgSubtypeEPOnline``.

    Gebouwsubtype is genuinely per-VBO: a mixed-use Pand can host VBOs
    with different secondary qualifiers (e.g. one apartment and one
    ground-floor shop unit). There is no Pand-level reduction at the
    subtype scope; both VBOs surface their own subtype independently.
    """
    from citygml_energy.city_builder.builders import build_building_unit

    older = _label_with(
        registratiedatum=date(2020, 1, 1),
        gebouwsubtype="appartement-galerijflat",
    )
    newer = _label_with(
        registratiedatum=date(2024, 1, 1),
        gebouwsubtype="rijwoning-tussen",
    )
    older_unit = build_building_unit(_resolved_with(older))
    newer_unit = build_building_unit(_resolved_with(newer))

    older_subtype = next(
        a.value for a in older_unit.string_attribute if a.name == "bdgSubtypeEPOnline"
    )
    newer_subtype = next(
        a.value for a in newer_unit.string_attribute if a.name == "bdgSubtypeEPOnline"
    )
    assert older_subtype == "appartement-galerijflat"
    assert newer_subtype == "rijwoning-tussen"


# ---------------------------------------------------------------------------
# Pand-level emissions on the Building: yearOfConstructionEPOnline (from
# Bouwjaar) and native nrg3:bdgType (from Gebouwtype, Dutch verbatim with
# the RVO codespace), each picked from the most-recently-registered cert
# that carries the field, sharing one nrg3:Metadata block.
# ---------------------------------------------------------------------------


def test_apply_eponline_year_emits_int_attribute_on_building() -> None:
    """Single VBO with Bouwjaar → ``gen:intAttribute`` on the Building."""
    from citygml_energy.city_builder.builders import (
        apply_eponline_pand_attribution_to_building,
    )

    building = build_building(_parsed())  # BAG year = 1985 from _parsed()
    label = _label_with(bouwjaar=1986)
    apply_eponline_pand_attribution_to_building(building, [_resolved_with(label)])

    int_attrs = [
        a for a in building.int_attribute if a.name == "yearOfConstructionEPOnline"
    ]
    assert len(int_attrs) == 1
    assert int_attrs[0].value == 1986


def test_apply_eponline_bdg_type_emits_dutch_value_on_building() -> None:
    """Gebouwtype lands on the Building as native ``nrg3:bdgType``.

    Dutch RVO term verbatim, no translation. The ``@codeSpace``
    identifies the EP-online publication that defines the vocabulary
    so a downstream reader does not mistake the value for an Energy-ADE
    ``BuildingTypeValue.xml`` codelist member.
    """
    from citygml_energy.city_builder.builders import (
        apply_eponline_pand_attribution_to_building,
    )
    from citygml_energy.namespaces import CS_RVO_GEBOUWTYPE

    building = build_building(_parsed())
    label = _label_with(gebouwtype="Vrijstaande woning")
    apply_eponline_pand_attribution_to_building(building, [_resolved_with(label)])

    assert len(building.bdg_type) == 1
    assert building.bdg_type[0].value == "Vrijstaande woning"
    assert building.bdg_type[0].code_space == CS_RVO_GEBOUWTYPE


def test_apply_eponline_pand_attribution_emits_one_shared_metadata_block() -> None:
    """One ``nrg3:Metadata`` block covers both Pand-level emissions.

    The block lists every Pand-level field it backs in
    ``qualityDescription`` so the auditor can see at a glance what the
    EP-online source is responsible for. Distinct from the BAG-source
    Metadata block — both can co-exist on the Building when both
    sources contribute.
    """
    from citygml_energy.city_builder.builders import (
        apply_bag_year_metadata_to_building,
        apply_eponline_pand_attribution_to_building,
    )

    building = build_building(_parsed())
    label = _label_with(bouwjaar=1986, gebouwtype="Vrijstaande woning")
    apply_bag_year_metadata_to_building(building)
    apply_eponline_pand_attribution_to_building(building, [_resolved_with(label)])

    eponline_metas = [
        m for m in building.metadata if "EP-online" in (m.source or "")
    ]
    assert len(eponline_metas) == 1
    quality = eponline_metas[0].quality_description or ""
    assert "yearOfConstructionEPOnline" in quality
    assert "nrg3:bdgType" in quality
    assert any("BAG" in (m.source or "") for m in building.metadata)


def test_apply_eponline_year_picks_most_recent_registratiedatum() -> None:
    """Multi-VBO Pand: the Pand-level Bouwjaar comes from the newest cert.

    The reduction rule mirrors :func:`address_match._label_timestamp` so
    the Pand-level pick agrees with how the rest of the pipeline
    de-duplicates labels on the same address.
    """
    from citygml_energy.city_builder.builders import (
        apply_eponline_pand_attribution_to_building,
    )

    older = _label_with(registratiedatum=date(2020, 1, 1), bouwjaar=1970)
    newer = _label_with(registratiedatum=date(2024, 1, 1), bouwjaar=1955)
    building = build_building(_parsed())
    apply_eponline_pand_attribution_to_building(
        building, [_resolved_with(older), _resolved_with(newer)]
    )

    int_attrs = [
        a for a in building.int_attribute if a.name == "yearOfConstructionEPOnline"
    ]
    assert int_attrs[0].value == 1955  # newer wins


def test_apply_eponline_bdg_type_picks_most_recent_with_value() -> None:
    """Bouwjaar and Gebouwtype are picked per-field.

    The newest cert may have Bouwjaar but leave Gebouwtype empty; an
    older cert under the same Pand may carry Gebouwtype. The per-field
    canonical pick keeps both values rather than coupling them to a
    single canonical label and dropping whichever the newest cert lacks.
    """
    from citygml_energy.city_builder.builders import (
        apply_eponline_pand_attribution_to_building,
    )

    older_with_type = _label_with(
        registratiedatum=date(2020, 1, 1),
        bouwjaar=None,
        gebouwtype="Vrijstaande woning",
    )
    newer_with_year = _label_with(
        registratiedatum=date(2024, 1, 1),
        bouwjaar=1986,
        gebouwtype=None,
    )
    building = build_building(_parsed())
    apply_eponline_pand_attribution_to_building(
        building,
        [_resolved_with(older_with_type), _resolved_with(newer_with_year)],
    )

    assert len(building.bdg_type) == 1
    assert building.bdg_type[0].value == "Vrijstaande woning"
    int_attrs = [
        a for a in building.int_attribute if a.name == "yearOfConstructionEPOnline"
    ]
    assert int_attrs[0].value == 1986


def test_apply_eponline_pand_attribution_no_op_when_no_pand_level_fields() -> None:
    """No Bouwjaar AND no Gebouwtype → no Building-level emissions, no Metadata.

    Symmetric with the BAG path: only emit when there's an actual value
    to attribute. A label that ships only per-VBO fields (e.g. only
    Gebouwsubtype) must not trigger a Building-level Metadata block.
    """
    from citygml_energy.city_builder.builders import (
        apply_eponline_pand_attribution_to_building,
    )

    building = build_building(_parsed())
    label = _label_with(bouwjaar=None, gebouwtype=None, gebouwsubtype="rijwoning-tussen")
    apply_eponline_pand_attribution_to_building(building, [_resolved_with(label)])

    assert all(
        a.name != "yearOfConstructionEPOnline" for a in building.int_attribute
    )
    assert building.bdg_type == []
    assert all("EP-online" not in (m.source or "") for m in building.metadata)


def test_apply_eponline_pand_attribution_no_op_when_no_labels() -> None:
    """A Pand whose VBOs have no EP-online labels gets nothing extra."""
    from citygml_energy.city_builder.builders import (
        apply_eponline_pand_attribution_to_building,
    )

    building = build_building(_parsed())
    apply_eponline_pand_attribution_to_building(building, [_resolved_with(None)])

    assert all(
        a.name != "yearOfConstructionEPOnline" for a in building.int_attribute
    )
    assert building.bdg_type == []


# ---------------------------------------------------------------------------
# EPC: certificationMethod composes Berekeningstype + SoortOpname
# ---------------------------------------------------------------------------


def _resolved_with_label(**label_kwargs) -> ResolvedAddress:
    label = _label_with(**label_kwargs)
    return ResolvedAddress(vbo=_vbo(), energy_label=label)


def test_certification_method_concatenates_soortopname_and_berekeningstype() -> None:
    """Both inspection rigour and NTA-8800 variant land on certificationMethod.

    Separator is `` / `` (space-slash-space), per the Phase-0 spec § 5d
    direction. Order is ``SoortOpname`` first (the inspection rigour),
    then ``Berekeningstype`` (the calculation method).
    """
    from citygml_energy.city_builder.builders import _build_epc

    resolved = _resolved_with_label(
        soort_opname="Detailopname",
        berekeningstype="NTA 8800:2024 (detailopname woningbouw)",
    )
    epc = _build_epc(resolved, gml_id_prefix="")
    assert epc is not None
    assert (
        epc.certification_method
        == "Detailopname / NTA 8800:2024 (detailopname woningbouw)"
    )


def test_certification_method_only_berekeningstype() -> None:
    """When SoortOpname is missing, certificationMethod is just the variant."""
    from citygml_energy.city_builder.builders import _build_epc

    resolved = _resolved_with_label(
        soort_opname=None,
        berekeningstype="NTA 8800:2024 (basisopname utiliteitsbouw)",
    )
    epc = _build_epc(resolved, gml_id_prefix="")
    assert epc is not None
    assert epc.certification_method == "NTA 8800:2024 (basisopname utiliteitsbouw)"


def test_certification_method_only_soortopname() -> None:
    """Reverse case: only SoortOpname is set."""
    from citygml_energy.city_builder.builders import _build_epc

    resolved = _resolved_with_label(
        soort_opname="Basisopname",
        berekeningstype=None,
    )
    epc = _build_epc(resolved, gml_id_prefix="")
    assert epc is not None
    assert epc.certification_method == "Basisopname"


def test_certification_method_omitted_when_neither_set() -> None:
    """No SoortOpname AND no Berekeningstype → ``certification_method=None``."""
    from citygml_energy.city_builder.builders import _build_epc

    resolved = _resolved_with_label(soort_opname=None, berekeningstype=None)
    epc = _build_epc(resolved, gml_id_prefix="")
    assert epc is not None
    assert epc.certification_method is None


# ---------------------------------------------------------------------------
# AandeelHernieuwbareEnergie rides on the BuildingUnit (NOT the EPC)
# ---------------------------------------------------------------------------


def test_renewable_share_lands_as_measure_attribute_on_building_unit() -> None:
    """AandeelHernieuwbareEnergie → gen:measureAttribute on the BuildingUnit.

    The Phase-0 spec originally aimed it at the EPC, but
    ``EnergyPerformanceCertificateType`` extends
    ``AbstractFeatureWithLifeSpanType`` directly (not via CityObject) and
    so cannot host a ``gen:measureAttribute``. The mapping doc is
    updated in P3 to reflect this; the actual emission lives on the
    BuildingUnit (which DOES extend AbstractCityObject).

    uom is ``percent`` (matching FZK UOMList id at line 182), not ``%``
    (which is the sign-glyph and not a uom id).
    """
    from citygml_energy.city_builder.builders import build_building_unit

    resolved = _resolved_with_label(aandeel_hernieuwbare_energie=42.0)
    unit = build_building_unit(resolved)
    measures = [
        a for a in unit.measure_attribute
        if a.name == "epOnlineAandeelHernieuwbareEnergie"
    ]
    assert len(measures) == 1
    assert measures[0].value.uom == "percent"
    assert measures[0].value.value == 42.0


def test_renewable_share_omitted_when_label_has_none() -> None:
    """A label without the renewable-share column omits the measure attribute."""
    from citygml_energy.city_builder.builders import build_building_unit

    resolved = _resolved_with_label(aandeel_hernieuwbare_energie=None)
    unit = build_building_unit(resolved)
    assert all(
        a.name != "epOnlineAandeelHernieuwbareEnergie"
        for a in unit.measure_attribute
    )


def test_renewable_share_zero_is_emitted() -> None:
    """A real zero is meaningful (BENG-3 = 0% on a building with no PV)."""
    from citygml_energy.city_builder.builders import build_building_unit

    resolved = _resolved_with_label(aandeel_hernieuwbare_energie=0.0)
    unit = build_building_unit(resolved)
    measures = [
        a for a in unit.measure_attribute
        if a.name == "epOnlineAandeelHernieuwbareEnergie"
    ]
    assert len(measures) == 1
    assert measures[0].value.value == 0.0
