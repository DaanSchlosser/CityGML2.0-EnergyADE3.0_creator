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
from citygml_energy.city_builder.config import BuildContext
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel


from tests._factories import make_parsed_building, make_square_polygon, make_vbo

_square = make_square_polygon


def _parsed() -> ParsedBuilding:
    return make_parsed_building()


def _vbo(
    street: str = "Mekelweg",
    point: tuple[float, float] | None = None,
) -> Verblijfsobject:
    """Mekelweg-style VBO with status set (used by Building unit tests)."""
    return make_vbo(
        status="Verblijfsobject in gebruik",
        street=street,
        point=point,
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
    only_lod0 = build_building(_parsed(), BuildContext(lods=(0,)))
    assert only_lod0.lod0_foot_print is not None
    assert only_lod0.lod1_solid is None


def test_build_building_lod1_is_solid_with_composite_surface() -> None:
    building = build_building(_parsed(), BuildContext(lods=(1,)))
    shell = building.lod1_solid.solid.exterior.composite_surface
    assert shell.id.endswith("_lod1_shell")


def _posns_of_lod0(building) -> list[list[float]]:
    """Flatten every gml:posList value in the LoD 0 MultiSurface."""
    return [
        poly.polygon.exterior.linear_ring.pos_list.value
        for poly in building.lod0_foot_print.multi_surface.surface_member
    ]


def test_build_building_lod0_lifted_to_b3_h_maaiveld() -> None:
    """LoD 0 vertices are lifted from 3DBAG's nominal Z=0 to the
    per-building terrain height ``b3_h_maaiveld`` so the footprint sits
    co-planar with the LoD 1 ground face. Single-pass viewers can then
    draw LoD 0 and LoD 1 together without a vertical-datum jump.
    """
    parsed = ParsedBuilding(
        pand_id="0114100000202121",
        attributes={"oorspronkelijkbouwjaar": 1985, "b3_h_maaiveld": 13.35},
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(13.35), _square(16.9)],
        },
    )
    building = build_building(parsed, BuildContext(lods=(0,)))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 13.35 for z in zs), f"expected all z=13.35, got {zs}"


def test_build_building_lod0_falls_through_when_maaiveld_absent() -> None:
    """When ``b3_h_maaiveld`` is missing, LoD 0 keeps its source Z.

    3DBAG always ships ``b3_h_maaiveld`` in practice, but the builder
    must not crash on the rare missing-attribute case; verifying the
    fall-through here keeps the contract explicit.
    """
    parsed = ParsedBuilding(
        pand_id="0114100000202121",
        attributes={"oorspronkelijkbouwjaar": 1985},
        geometries={"0": [_square(0.0, "GroundSurface")]},
    )
    building = build_building(parsed, BuildContext(lods=(0,)))
    for ring in _posns_of_lod0(building):
        zs = ring[2::3]
        assert all(z == 0.0 for z in zs), f"expected all z=0.0, got {zs}"


# ---------------------------------------------------------------------------
# LoD 2 per-planar thematic surfaces
# ---------------------------------------------------------------------------


def _multi_facet_parsed() -> ParsedBuilding:
    """3DBAG-shaped LoD 2 input: 1 ground, 2 walls, 3 roof facets, plus
    one polygon with no semantic type (must fall back to WallSurface).

    Shape and z-values are arbitrary; only the surface_type sequencing
    matters for the per-planar id assignment.
    """
    return ParsedBuilding(
        pand_id="0114100000000999",
        attributes={"oorspronkelijkbouwjaar": 1985},
        geometries={
            "2": [
                _square(0.0, "GroundSurface"),
                _square(1.0, "WallSurface"),
                _square(3.0, "RoofSurface"),
                _square(3.0, "RoofSurface"),
                _square(3.5, "RoofSurface"),
                _square(2.0, "WallSurface"),
                _square(2.5, None),  # unknown semantics → WallSurface fallback
            ],
        },
    )


def test_lod2_emits_one_thematic_surface_per_polygon() -> None:
    """Per-planar split: every polygon in the parsed CityJSON LoD 2
    list becomes its own ``bldg:boundedBy`` element. Per-face attributes
    (azimuth, slope, area) on a CityGML/Energy-ADE thematic surface are
    only meaningful when the surface is actually planar, so the split
    is structurally required, not cosmetic.
    """
    building = build_building(_multi_facet_parsed(), BuildContext(lods=(2,)))

    # 7 source polygons → 7 thematic surfaces, one per polygon, no merging.
    assert len(building.bounded_by) == 7

    # Each surface carries a single-polygon lod2MultiSurface; that's the
    # invariant that lets the matcher's roof_index unambiguously address
    # one specific facet.
    for wrapper in building.bounded_by:
        surf = (
            wrapper.ground_surface
            or wrapper.wall_surface
            or wrapper.roof_surface
        )
        assert surf is not None
        members = surf.lod2_multi_surface.multi_surface.surface_member
        assert len(members) == 1


def test_lod2_thematic_surface_ids_are_per_type_one_based_in_source_order() -> None:
    """The matcher relies on this exact id convention to label each
    PV facet's ``installedOn`` xlink target without re-walking the
    xsdata tree. If this drifts, the xlinks dangle silently — XSD
    validation accepts dangling intra-document hrefs, so a regression
    test is the only safety net.
    """
    building = build_building(_multi_facet_parsed(), BuildContext(lods=(2,)))

    by_kind: dict[str, list[str]] = {"ground": [], "wall": [], "roof": []}
    for wrapper in building.bounded_by:
        if wrapper.ground_surface is not None:
            by_kind["ground"].append(wrapper.ground_surface.id)
        elif wrapper.wall_surface is not None:
            by_kind["wall"].append(wrapper.wall_surface.id)
        elif wrapper.roof_surface is not None:
            by_kind["roof"].append(wrapper.roof_surface.id)

    bid = "pand_0114100000000999"
    # Per-type 1-based numbering, in source-CityJSON order. The
    # untyped polygon gets the next wallsurface index (3 walls total:
    # the two explicit WallSurface entries + the None fallback).
    assert by_kind["ground"] == [f"{bid}_groundsurface_1"]
    assert by_kind["wall"] == [
        f"{bid}_wallsurface_1",
        f"{bid}_wallsurface_2",
        f"{bid}_wallsurface_3",
    ]
    assert by_kind["roof"] == [
        f"{bid}_roofsurface_1",
        f"{bid}_roofsurface_2",
        f"{bid}_roofsurface_3",
    ]


def test_lod2_iterator_is_single_source_of_truth_for_indices() -> None:
    """The PV-panel matcher and the building builder use one shared
    iterator (:func:`iter_lod2_thematic_classification`) so they cannot
    drift on the per-type 1-based index. This test pins the iterator
    contract: source order preserved, unknown semantics collapsed to
    WallSurface, indices counted per resolved type.
    """
    from citygml_energy.city_builder.builders import (
        iter_lod2_thematic_classification,
    )

    polygons = _multi_facet_parsed().geometries["2"]
    # Materialise the iterator into a list of (type, index) pairs so the
    # ordering is observable without re-iterating.
    type_index_pairs = [
        (t, i) for t, i, _sp in iter_lod2_thematic_classification(polygons)
    ]
    assert type_index_pairs == [
        ("GroundSurface", 1),
        ("WallSurface", 1),
        ("RoofSurface", 1),
        ("RoofSurface", 2),
        ("RoofSurface", 3),
        ("WallSurface", 2),
        ("WallSurface", 3),  # untyped polygon collapses to WallSurface
    ]


def _ade_attrs(surf: object) -> tuple[float | None, float | None, float | None]:
    """Pick the (area, inclination, azimuth) values off a thematic surface.

    Each Energy ADE per-surface field is a ``list[...]`` on the binding
    (substitution-group remnant) but our builder emits ``maxOccurs=1``,
    so we read element 0 when present.
    """
    area = surf.bdg_bdry_surf_total_surface_area[0].value if surf.bdg_bdry_surf_total_surface_area else None
    incl = surf.bdg_bdry_surf_inclination[0].value if surf.bdg_bdry_surf_inclination else None
    azim = surf.bdg_bdry_surf_azimuth[0].value if surf.bdg_bdry_surf_azimuth else None
    return area, incl, azim


def _surfaces_by_kind(building: object) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {"ground": [], "wall": [], "roof": []}
    for wrapper in building.bounded_by:
        if wrapper.ground_surface is not None:
            out["ground"].append(wrapper.ground_surface)
        elif wrapper.wall_surface is not None:
            out["wall"].append(wrapper.wall_surface)
        elif wrapper.roof_surface is not None:
            out["roof"].append(wrapper.roof_surface)
    return out


def test_lod2_each_surface_carries_total_surface_area() -> None:
    """``nrg3:bdgBdrySurfTotalSurfaceArea`` is the only LoD 2 attribute
    that is well-defined for every surface type (ground, wall, roof,
    flat or sloped). The XSD types it as ``gml:AreaType`` with
    ``maxOccurs=1`` per the UML appinfo, so we emit it on every
    emitted surface in m² (uom token matches the KIT viewer's
    UOMList.xml ``m2`` primary id).
    """
    building = build_building(_multi_facet_parsed(), BuildContext(lods=(2,)))
    for wrapper in building.bounded_by:
        surf = wrapper.ground_surface or wrapper.wall_surface or wrapper.roof_surface
        assert surf is not None
        assert len(surf.bdg_bdry_surf_total_surface_area) == 1
        ade_area = surf.bdg_bdry_surf_total_surface_area[0]
        assert ade_area.uom == "m2"
        assert ade_area.value > 0


def test_lod2_ground_surface_inclination_is_180_with_no_azimuth() -> None:
    """Per Alderaan (ALL.gml line 1506) the ground floor's outward
    normal points down, so its inclination is 180°. Azimuth is
    geometrically undefined for a horizontal surface and the
    corresponding element must be omitted.

    The fixture's GroundSurface is a CCW-from-above z=0 square; that
    winding produces an upward Newell normal, so we explicitly use the
    3DBAG convention (CW from above → outward-down) here.
    """
    parsed = ParsedBuilding(
        pand_id="0114100000000777",
        attributes={"oorspronkelijkbouwjaar": 1985},
        geometries={
            "2": [
                # Outward normal (0, 0, -1): wind CW viewed from above.
                SemanticPolygon(
                    polygon=GeometryPolygon(
                        exterior=[
                            (0.0, 0.0, 0.0),
                            (0.0, 1.0, 0.0),
                            (1.0, 1.0, 0.0),
                            (1.0, 0.0, 0.0),
                        ],
                    ),
                    surface_type="GroundSurface",
                ),
            ],
        },
    )
    building = build_building(parsed, BuildContext(lods=(2,)))
    [ground] = _surfaces_by_kind(building)["ground"]
    area, incl, azim = _ade_attrs(ground)
    assert area == pytest.approx(1.0, abs=1e-9)
    assert incl == pytest.approx(180.0, abs=1e-9)
    assert azim is None


def test_lod2_sloped_roof_emits_azimuth_and_45_degree_inclination() -> None:
    """A south-facing 45° pitch (low at y=0, high at y=1; outward
    normal up & -Y) emits ``bdgBdrySurfInclination = 45`` and
    ``bdgBdrySurfAzimuth = 180`` — both with the KIT-viewer-friendly
    ``uom="deg"`` token.
    """
    parsed = ParsedBuilding(
        pand_id="0114100000000888",
        attributes={"oorspronkelijkbouwjaar": 1985},
        geometries={
            "2": [
                SemanticPolygon(
                    polygon=GeometryPolygon(
                        exterior=[
                            (0.0, 0.0, 3.0),
                            (1.0, 0.0, 3.0),
                            (1.0, 1.0, 4.0),
                            (0.0, 1.0, 4.0),
                        ],
                    ),
                    surface_type="RoofSurface",
                ),
            ],
        },
    )
    building = build_building(parsed, BuildContext(lods=(2,)))
    [roof] = _surfaces_by_kind(building)["roof"]
    area, incl, azim = _ade_attrs(roof)
    # √2 m² for a 1×1 horizontal projection on a 45° slope.
    assert area == pytest.approx(round(2 ** 0.5, 3), abs=1e-9)
    assert incl == pytest.approx(45.0, abs=1e-9)
    assert azim == pytest.approx(180.0, abs=1e-9)
    # uom tokens — must match KIT UOMList.xml entries.
    assert roof.bdg_bdry_surf_inclination[0].uom == "deg"
    assert roof.bdg_bdry_surf_azimuth[0].uom == "deg"


def test_lod2_flat_roof_omits_azimuth_but_keeps_zero_inclination() -> None:
    """A flat roof has a vertical normal: inclination 0, azimuth
    geometrically undefined. The Energy ADE 3.0 ``bdgBdrySurfAzimuth``
    element must be absent (rather than emitted with a sentinel like
    Alderaan's ``-1``, which is not a valid bearing).
    """
    parsed = ParsedBuilding(
        pand_id="0114100000000999",
        attributes={},
        geometries={
            "2": [
                SemanticPolygon(
                    polygon=GeometryPolygon(
                        exterior=[
                            (0.0, 0.0, 3.0),
                            (1.0, 0.0, 3.0),
                            (1.0, 1.0, 3.0),
                            (0.0, 1.0, 3.0),
                        ],
                    ),
                    surface_type="RoofSurface",
                ),
            ],
        },
    )
    building = build_building(parsed, BuildContext(lods=(2,)))
    [roof] = _surfaces_by_kind(building)["roof"]
    area, incl, azim = _ade_attrs(roof)
    assert area == pytest.approx(1.0, abs=1e-9)
    assert incl == pytest.approx(0.0, abs=1e-9)
    assert azim is None
    # The list field is empty, not a list with a sentinel value.
    assert roof.bdg_bdry_surf_azimuth == []


def test_lod2_skipped_construction_attrs_are_not_emitted() -> None:
    """Per the city pipeline's rationale, only the three geometry-
    derived ADE attributes are emitted. Construction-property and
    scene-radiation attributes (Thickness, HeatCapacity, IsShared,
    OpaqueSurfaceArea, ground/sky view factors, additional thermal-
    bridge U-value) are intentionally absent until that data is
    actually available — emitting placeholders would silently
    contaminate downstream energy analyses.
    """
    building = build_building(_multi_facet_parsed(), BuildContext(lods=(2,)))
    for wrapper in building.bounded_by:
        surf = wrapper.ground_surface or wrapper.wall_surface or wrapper.roof_surface
        assert surf.bdg_bdry_surf_thickness == []
        assert surf.bdg_bdry_surf_heat_capacity == []
        assert surf.bdg_bdry_surf_is_shared == []
        assert surf.bdg_bdry_surf_opaque_surface_area == []
        assert surf.bdg_bdry_surf_ground_view_factor == []
        assert surf.bdg_bdry_surf_sky_view_factor == []
        assert surf.bdg_bdry_surf_additional_thermal_bridge_uvalue == []


def test_lod2_targets_collected_once_per_emitted_surface() -> None:
    """The pre-collected ``surface_targets_out`` list must enumerate
    every emitted surface exactly once (container ms id + member poly
    id), so the appearance builder can paint each facet without re-
    walking the xsdata tree per building.
    """
    targets: list[str] = []
    build_building(_multi_facet_parsed(), BuildContext(lods=(2,)), surface_targets_out=targets)

    # 7 surfaces × (1 _ms container + 1 _poly_1 member) = 14 LoD 2 targets.
    lod2_targets = [t for t in targets if "_ms" in t]
    assert len(lod2_targets) == 14
    # Half are container references, half polygons; per the convention,
    # a polygon target is a strict suffix of its container's id.
    container_ids = {t for t in lod2_targets if not t.endswith("_poly_1")}
    polygon_ids = {t for t in lod2_targets if t.endswith("_poly_1")}
    assert len(container_ids) == 7
    assert len(polygon_ids) == 7


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------


def test_build_address_composes_xal_structure() -> None:
    """Country-wrapped xAL with NL alpha-2 + Town/Street type discriminators.

    The Locality lives under ``AddressDetails.country.locality`` (not
    directly under AddressDetails) so the address advertises its
    country unambiguously, matching the EnergyADE 3.0 Alderaan reference
    shape. Type attributes ``Town`` / ``Street`` mirror the conventional
    xAL discriminators.
    """
    address = build_address(_resolved())
    assert address is not None

    country = address.xal_address.address_details.country
    assert country is not None
    assert country.country_name_code[0].content[0] == "NL"
    assert country.country_name_code[0].scheme == "iso.3166-1 alpha-2"
    assert country.country_name[0].content[0] == "The Netherlands"

    locality = country.locality
    assert locality is not None
    assert locality.type_value == "Town"
    assert locality.thoroughfare.type_value == "Street"
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
    sample at ``inputs/buildings/owner_occupier_building.json:35``. Concatenating the
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


def test_building_unit_type_carries_bag_gebruiksdoel_with_codespace() -> None:
    """``nrg3:BuildingUnit/type`` is mandatory in the XSD; we populate
    it from BAG ``gebruiksdoel`` and tag the codeSpace so a consumer
    can resolve "woonfunctie" / "kantoorfunctie" / etc. against the
    BAG vocabulary rather than treating the value as opaque text or
    misreading it against EnergyADE's ``CurrentUseValue.xml`` codelist.
    """
    from citygml_energy.namespaces import CS_BAG_GEBRUIKSDOEL

    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved()])
    unit = building.building_unit[0].building_unit
    assert unit.type_value.value == "woonfunctie"  # from the test VBO fixture
    assert unit.type_value.code_space == CS_BAG_GEBRUIKSDOEL


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


def test_building_computes_bdg_height_from_b3_h_dak_max_minus_maaiveld() -> None:
    """``nrg3:bdgHeight`` encodes ground-to-highest-roof-point as a
    ``QualifiedHeight`` with type ``maxHeightAboveGround``, computed from
    ``b3_h_dak_max - b3_h_maaiveld``. Using ``b3_h_dak_max`` (not
    ``b3_h_dak_70p``) so antenna/chimney tips register as part of the
    physical extent.
    """
    building = build_building(_parsed_with_3dbag_attrs())
    assert len(building.bdg_height) == 1
    qh = building.bdg_height[0].qualified_height
    # 9.925 - 0.175 = 9.750
    assert qh.value.value == 9.75
    assert qh.value.uom == "m"
    assert qh.type_value.value == "maxHeightAboveGround"


def test_building_omits_bdg_height_when_roof_below_maaiveld() -> None:
    """Defensive: a corrupt tile where roof < ground must not produce
    a negative height. The builder skips the field instead.
    """
    building = build_building(_parsed_with_3dbag_attrs(
        b3_h_maaiveld=10.0, b3_h_dak_max=8.0,
    ))
    assert building.bdg_height == []


def test_building_drops_unrecognised_b3_dak_type_silently() -> None:
    """An unknown 3DBAG roof-type string falls through with no
    ``bldg:roofType`` rather than minting an off-codelist SIG3D value.
    Emitting nothing is more honest than guessing an SIG3D code that
    a downstream consumer would then trust.
    """
    parsed = ParsedBuilding(
        pand_id="0114100000999998",
        attributes={"oorspronkelijkbouwjaar": 1985, "b3_dak_type": "unknown_type"},
        geometries={},
    )
    building = build_building(parsed)
    assert building.roof_type is None


def test_building_maps_each_3dbag_dak_type_to_its_sig3d_code() -> None:
    """Pin the full 3DBAG -> SIG3D mapping table so any future tweak
    fails this test rather than silently re-keying real Pand outputs.
    """
    from citygml_energy.namespaces import CS_BUILDING_ROOFTYPE

    cases = [
        ("horizontal", "1000"),  # flat
        ("slanted", "1030"),  # gabled (lossy default for ambiguous pitched)
        ("multiple horizontal", "1130"),  # combination of roof forms
    ]
    for dak, expected in cases:
        parsed = ParsedBuilding(
            pand_id=f"0114100000{dak}",
            attributes={"oorspronkelijkbouwjaar": 1985, "b3_dak_type": dak},
            geometries={},
        )
        building = build_building(parsed)
        assert building.roof_type is not None, f"{dak!r}: no roof_type emitted"
        assert building.roof_type.value == expected
        assert building.roof_type.code_space == CS_BUILDING_ROOFTYPE


def test_building_maps_b3_dak_type_to_sig3d_roof_type_code() -> None:
    """3DBAG's coarse roof-type enumeration (``horizontal`` / ``slanted``
    / ``multiple horizontal``) is mapped to a numeric SIG3D
    ``_AbstractBuilding_roofType.xml`` code so the city pipeline emits
    the same ``bldg:roofType`` vocabulary as the per-building pipeline.
    ``slanted`` is intrinsically ambiguous in 3DBAG (no monopitch /
    gabled / hipped distinction), so we map to ``1030`` (gabled, the
    most common Dutch residential pitched roof) as the deterministic
    fallback; ``horizontal`` -> ``1000`` (flat) is 1:1, and
    ``multiple horizontal`` -> ``1130`` (combination of roof forms).
    """
    from citygml_energy.namespaces import CS_BUILDING_ROOFTYPE

    building = build_building(_parsed_with_3dbag_attrs())
    assert building.roof_type is not None
    # Fixture uses ``slanted`` -> SIG3D 1030 (gabled).
    assert building.roof_type.value == "1030"
    assert building.roof_type.code_space == CS_BUILDING_ROOFTYPE


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
    assert building.bdg_height == []
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
# EPC.value from EP-online BerekendeEnergieverbruik (regime-aware uom)
# ---------------------------------------------------------------------------
#
# ``EnergyPerformanceCertificate.value`` is ``gml:MeasureType``: a single
# double + required ``@uom``. We populate it from BerekendeEnergieverbruik,
# the only EP-online numeric populated for >99% of certs in BOTH regimes,
# but the regimes ship the value in DIFFERENT units (NTA 8800: kWh/m²·yr
# delivered; legacy: MJ/yr total primary). The schema's @uom attribute is
# exactly how heterogeneous regimes coexist on the same field.
#
# These tests pin one assertion per regime + the unknown-regime skip + the
# missing-amount skip. The same uom constants drive the matching
# ``nrg3:Energy.amount`` on the resource side, which keeps EPC.value and
# the Energy resource locked together via UOM_KWH_PER_M2_PER_A /
# UOM_MJ_PER_A in ``energy_resources.py``.
# ---------------------------------------------------------------------------


def _epc_from_label(**fields):
    """Helper: build a Building+Unit, attach a label with *fields*, return EPC."""
    base = dict(
        postcode="2628CD",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=None,
        energieklasse="A",
        registratiedatum=date(2024, 1, 1),
        opnamedatum=None,
        geldig_tot=date(2034, 1, 1),
    )
    base.update(fields)
    label = EnergyLabel(**base)
    resolved = ResolvedAddress(vbo=_vbo(), energy_label=label)
    building = build_building(_parsed())
    attach_building_units_to_building(building, [resolved])
    unit = building.building_unit[0].building_unit
    return unit.energy_performance_certificate[0].energy_performance_certificate


def test_epc_value_from_berekendeenergieverbruik_nta8800_uses_kwh_per_m2_a() -> None:
    """NTA 8800 regime emits BerekendeEnergieverbruik (kWh/m²·yr delivered).

    The uom must match the matching nrg3:Energy.amount uom on the resource
    side (both are sourced from the shared UOM_KWH_PER_M2_PER_A constant).
    """
    epc = _epc_from_label(
        berekeningstype="NTA 8800:2024 (detailopname woningbouw)",
        berekende_energieverbruik=42.5,
    )
    assert epc.value is not None
    assert epc.value.value == 42.5
    assert epc.value.uom == "kWh/m2/a"


def test_epc_value_from_berekendeenergieverbruik_legacy_uses_mj_per_a() -> None:
    """Legacy NEN 7120 regime ships BerekendeEnergieverbruik in MJ/yr (total).

    The cross-regime uom divergence on the same column is intentional and
    tracked via ``EnergyLabel.calculation_regime()``. The shared
    ``UOM_MJ_PER_A`` constant keeps EPC.value and the parallel
    nrg3:Energy.amount resource synchronised.
    """
    epc = _epc_from_label(
        berekeningstype=(
            "Rekenmethodiek Definitief Energielabel, "
            "versie 1.2, 16 september 2014"
        ),
        berekende_energieverbruik=293361.52,
    )
    assert epc.value is not None
    assert epc.value.value == 293361.52
    assert epc.value.uom == "MJ/a"


def test_epc_value_skipped_for_unknown_regime() -> None:
    """An unrecognised Berekeningstype yields regime=unknown; EPC.value
    must stay unset because we have no defensible uom to claim.
    """
    epc = _epc_from_label(
        berekeningstype="Some future method we have not classified",
        berekende_energieverbruik=42.5,
    )
    assert epc.value is None


def test_epc_value_skipped_when_berekendeenergieverbruik_missing() -> None:
    """No source value -> no EPC.value, even when the regime is known."""
    epc = _epc_from_label(
        berekeningstype="NTA 8800:2024 (detailopname woningbouw)",
        berekende_energieverbruik=None,
    )
    assert epc.value is None


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
def test_building_omits_bdg_height_for_degenerate_geometry(
    maaiveld: float, dak_max: float
) -> None:
    """The strict ``>`` guard in the builder drops both zero-height and
    inverted-roof cases; ``>=`` would emit a zero-height entry which
    is misleading."""
    building = build_building(_parsed_with_3dbag_attrs(
        b3_h_maaiveld=maaiveld, b3_h_dak_max=dak_max,
    ))
    assert building.bdg_height == []


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
    from citygml_energy.city_builder.builders import build_epc

    resolved = _resolved_with_label(
        soort_opname="Detailopname",
        berekeningstype="NTA 8800:2024 (detailopname woningbouw)",
    )
    epc = build_epc(resolved)
    assert epc is not None
    assert (
        epc.certification_method
        == "Detailopname / NTA 8800:2024 (detailopname woningbouw)"
    )


def test_certification_method_only_berekeningstype() -> None:
    """When SoortOpname is missing, certificationMethod is just the variant."""
    from citygml_energy.city_builder.builders import build_epc

    resolved = _resolved_with_label(
        soort_opname=None,
        berekeningstype="NTA 8800:2024 (basisopname utiliteitsbouw)",
    )
    epc = build_epc(resolved)
    assert epc is not None
    assert epc.certification_method == "NTA 8800:2024 (basisopname utiliteitsbouw)"


def test_certification_method_only_soortopname() -> None:
    """Reverse case: only SoortOpname is set."""
    from citygml_energy.city_builder.builders import build_epc

    resolved = _resolved_with_label(
        soort_opname="Basisopname",
        berekeningstype=None,
    )
    epc = build_epc(resolved)
    assert epc is not None
    assert epc.certification_method == "Basisopname"


def test_certification_method_omitted_when_neither_set() -> None:
    """No SoortOpname AND no Berekeningstype → ``certification_method=None``."""
    from citygml_energy.city_builder.builders import build_epc

    resolved = _resolved_with_label(soort_opname=None, berekeningstype=None)
    epc = build_epc(resolved)
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
