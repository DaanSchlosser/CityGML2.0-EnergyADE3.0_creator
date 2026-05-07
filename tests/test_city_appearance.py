"""Tests for the CityGML Appearance builder (EPC-color painting).

Verifies that :func:`append_energy_label_appearance`:

* Attaches a single ``app:Appearance`` (theme ``"energyLabel"``) to the
  :class:`CityModel` via ``app:appearanceMember``.
* Emits one ``app:X3DMaterial`` per unique averaged label.
* Targets every ``MultiSurface`` and ``CompositeSurface`` id under each
  building, covering LoD 0 MultiSurfaces, LoD 1 CompositeSurface
  shells, and LoD 2 thematic-surface MultiSurfaces.
* Groups buildings without any matched label under the grey fallback.
* Serialises XSD-validly (no ``app:target`` points at a non-existent
  surface id; the ``diffuseColor`` triples respect ``[0, 1]``).
"""

from __future__ import annotations

from datetime import date

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.appearance import (
    ENERGY_LABEL_THEME,
    PV_PANEL_DIFFUSE_COLOR,
    PV_PANEL_THEME,
    append_energy_label_appearance,
    append_pv_panel_appearance,
    collect_surface_target_ids,
)
from citygml_energy.city_builder.builders import (
    attach_building_units_to_building,
    build_building,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.config import BuildContext
from citygml_energy.city_builder.epc_score import label_to_rgb
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel
from citygml_energy.city_builder.pv_panels import (
    ProjectedPanel,
    attach_pv_collectors_to_building,
)
from citygml_energy.core import CityModel
from tests._factories import make_parsed_building, make_square_polygon, make_vbo

_square = make_square_polygon


def _parsed(pand_id: str) -> ParsedBuilding:
    """LoD 0/1/2 cube with year-of-construction 2000 (this file's default)."""
    return make_parsed_building(
        pand_id=pand_id,
        attributes={"oorspronkelijkbouwjaar": 2000},
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(0.0), _square(3.0)],
            "2": [_square(0.0, "GroundSurface"), _square(3.0, "RoofSurface")],
        },
    )


def _vbo(identificatie: str, huisnummer: int) -> Verblijfsobject:
    """Mekelweg-style VBO with a populated locator point (used by appearance smoke)."""
    return make_vbo(
        identificatie=identificatie,
        pand_identificatie="pand_does_not_matter",
        oppervlakte=70.0,
        huisnummer=huisnummer,
        point=(85000.0, 446500.0),
    )


def _resolved(identificatie: str, huisnummer: int, klasse: str | None) -> ResolvedAddress:
    label = None
    if klasse is not None:
        label = EnergyLabel(
            postcode="2628CD",
            huisnummer=huisnummer,
            huisletter=None,
            toevoeging=None,
            bag_verblijfsobject_id=None,
            energieklasse=klasse,
            registratiedatum=date(2024, 1, 1),
            opnamedatum=None,
            geldig_tot=date(2034, 1, 1),
        )
    return ResolvedAddress(vbo=_vbo(identificatie, huisnummer), energy_label=label)


def _build_with_labels(pand_id: str, labels: list[str | None]) -> tuple:
    parsed = _parsed(pand_id)
    building = build_building(parsed)
    resolved = [
        _resolved(f"vbo_{pand_id}_{i}", 42 + i, klasse)
        for i, klasse in enumerate(labels)
    ]
    attach_building_units_to_building(building, resolved)
    return building, resolved


# ---------------------------------------------------------------------------
# collect_surface_target_ids
# ---------------------------------------------------------------------------


def test_collect_targets_includes_lod0_lod1_and_lod2_surfaces() -> None:
    building, _ = _build_with_labels("001", ["A"])
    targets = collect_surface_target_ids(building)

    # All targets are #-prefixed GML-id references.
    assert all(t.startswith("#") for t in targets)

    # LoD0 MultiSurface, LoD1 CompositeSurface shell, and at least one
    # per-planar LoD2 thematic MultiSurface (id pattern
    # ``..._<surface>_<index>_ms``) should all be present.
    assert any(t.endswith("_lod0") for t in targets)
    assert any(t.endswith("_lod1_shell") for t in targets)
    assert any("groundsurface_1_ms" in t for t in targets)
    assert any("roofsurface_1_ms" in t for t in targets)


def test_collect_targets_includes_individual_polygon_ids() -> None:
    """Per-polygon targets are required for viewers (KIT SDM_KITModelViewer
    among them) that ignore container-level targets under
    ``bldg:lod0FootPrint`` / ``bldg:lod1Solid``.
    """
    building, _ = _build_with_labels("001", ["A"])
    targets = collect_surface_target_ids(building)

    # Each lod0 / lod1 / thematic-ms MultiSurface carries at least one
    # Polygon, and those polygons' gml:ids must also be in the target list.
    assert any(t.endswith("_lod0_poly_1") for t in targets)
    assert any("_lod1_poly_" in t for t in targets)
    assert any("groundsurface_1_ms_poly_1" in t for t in targets)
    assert any("roofsurface_1_ms_poly_1" in t for t in targets)


# ---------------------------------------------------------------------------
# append_energy_label_appearance
# ---------------------------------------------------------------------------


def test_single_building_gets_one_material_with_all_its_surface_targets() -> None:
    model = CityModel()
    building, resolved = _build_with_labels("001", ["A"])
    model.add(building)

    append_energy_label_appearance(model, [(building, resolved)])

    [member] = model.xsd.appearance_member
    appearance = member.appearance
    assert appearance is not None
    assert appearance.theme == ENERGY_LABEL_THEME

    [material_prop] = appearance.surface_data_member
    material = material_prop.x3_dmaterial
    assert material is not None
    assert material.diffuse_color == list(label_to_rgb("A"))

    # The single material targets every colorable surface on this building.
    expected_targets = set(collect_surface_target_ids(building))
    assert set(material.target) == expected_targets


def test_buildings_without_labels_use_grey_fallback() -> None:
    model = CityModel()
    building, resolved = _build_with_labels("001", [None, None])
    model.add(building)

    append_energy_label_appearance(model, [(building, resolved)])

    [member] = model.xsd.appearance_member
    [material_prop] = member.appearance.surface_data_member
    material = material_prop.x3_dmaterial
    # Grey = label_to_rgb(None).
    assert material.diffuse_color == list(label_to_rgb(None))


def test_materials_are_grouped_by_averaged_label() -> None:
    # Two buildings avg to different letters → two materials in the
    # Appearance, each targeting only its building's surfaces.
    model = CityModel()

    building_a, resolved_a = _build_with_labels("001", ["A", "A"])  # avg A
    building_g, resolved_g = _build_with_labels("002", ["G", "G"])  # avg G
    model.add(building_a)
    model.add(building_g)

    append_energy_label_appearance(
        model,
        [(building_a, resolved_a), (building_g, resolved_g)],
    )

    [member] = model.xsd.appearance_member
    materials = [p.x3_dmaterial for p in member.appearance.surface_data_member]
    assert len(materials) == 2

    by_color = {tuple(m.diffuse_color): set(m.target) for m in materials}

    a_targets = set(collect_surface_target_ids(building_a))
    g_targets = set(collect_surface_target_ids(building_g))

    assert by_color[tuple(label_to_rgb("A"))] == a_targets
    assert by_color[tuple(label_to_rgb("G"))] == g_targets


def test_average_label_drives_color_for_mixed_unit_building() -> None:
    # Building with mix of A (175 kWh) + C (257.5 kWh) → mean 216.25 → B.
    model = CityModel()
    building, resolved = _build_with_labels("001", ["A", "C"])
    model.add(building)

    append_energy_label_appearance(model, [(building, resolved)])

    [member] = model.xsd.appearance_member
    [material_prop] = member.appearance.surface_data_member
    assert material_prop.x3_dmaterial.diffuse_color == list(label_to_rgb("B"))


def test_empty_model_yields_no_appearance() -> None:
    model = CityModel()
    append_energy_label_appearance(model, [])
    assert model.xsd.appearance_member == []


def test_appearance_serialises_in_cityml_output() -> None:
    model = CityModel()
    building, resolved = _build_with_labels("001", ["A"])
    model.add(building)
    append_energy_label_appearance(model, [(building, resolved)])

    xml = model.to_string()
    # Namespaces, theme, and a material all make it to the wire. Opening
    # tags can carry xlink attributes (``xlink:type="simple"``) so we
    # match the tag prefix without the closing ``>``.
    assert 'xmlns:app="http://www.opengis.net/citygml/appearance/2.0"' in xml
    assert "<app:appearanceMember" in xml
    # Appearance now carries gml:id, so match the opening tag prefix only.
    assert "<app:Appearance " in xml
    assert f'gml:id="appearance_{ENERGY_LABEL_THEME}"' in xml
    assert f"<app:theme>{ENERGY_LABEL_THEME}</app:theme>" in xml
    assert "<app:X3DMaterial>" in xml
    assert "<app:diffuseColor>" in xml
    assert "<app:target>" in xml


# ---------------------------------------------------------------------------
# append_pv_panel_appearance
# ---------------------------------------------------------------------------


def _pv_panel(fid: int, z: float = 3.1) -> ProjectedPanel:
    return ProjectedPanel(
        original_fid=fid,
        lod2_polygons=(
            GeometryPolygon(
                exterior=[(0.0, 0.0, z), (1.0, 0.0, z), (1.0, 1.0, z), (0.0, 1.0, z)],
            ),
        ),
        footprint_area_m2=1.0,
        azimuth_deg=180.0,
        inclination_deg=30.0,
        reference_point=(0.5, 0.5, z),
        roof_index=1,
    )


def test_pv_appearance_no_op_when_model_has_no_pv_panels() -> None:
    model = CityModel()
    building, _ = _build_with_labels("001", ["A"])
    model.add(building)

    append_pv_panel_appearance(model)

    # No PV collector under the building → no PV appearance emitted.
    assert model.xsd.appearance_member == []


def test_pv_appearance_targets_every_pv_multisurface_and_polygon() -> None:
    model = CityModel()
    building, _ = _build_with_labels("001", ["A"])
    attach_pv_collectors_to_building(
        building, [_pv_panel(fid=7), _pv_panel(fid=9)],
        BuildContext(
            srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
            srs_dimension=3,
        ),
    )
    model.add(building)

    append_pv_panel_appearance(model)

    [member] = model.xsd.appearance_member
    appearance = member.appearance
    assert appearance.theme == PV_PANEL_THEME
    assert appearance.id == f"appearance_{PV_PANEL_THEME}"

    [material_prop] = appearance.surface_data_member
    material = material_prop.x3_dmaterial
    assert material.diffuse_color == list(PV_PANEL_DIFFUSE_COLOR)
    assert material.transparency is None

    # Two panels × (one MultiSurface id + one Polygon id each) = 4 targets.
    assert set(material.target) == {
        "#pv_001_7_lod2",
        "#pv_001_7_lod2_poly_1",
        "#pv_001_9_lod2",
        "#pv_001_9_lod2_poly_1",
    }


def test_pv_appearance_coexists_with_energy_label_appearance() -> None:
    model = CityModel()
    building, resolved = _build_with_labels("001", ["A"])
    attach_pv_collectors_to_building(
        building, [_pv_panel(fid=7)],
        BuildContext(
            srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
            srs_dimension=3,
        ),
    )
    model.add(building)

    append_energy_label_appearance(model, [(building, resolved)])
    append_pv_panel_appearance(model)

    themes = [m.appearance.theme for m in model.xsd.appearance_member]
    assert themes == [ENERGY_LABEL_THEME, PV_PANEL_THEME]
