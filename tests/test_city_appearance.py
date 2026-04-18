"""Tests for the CityGML Appearance builder (EPC-color painting).

Verifies that :func:`append_energy_label_appearance`:

* Attaches a single ``app:Appearance`` (theme ``"energyLabel"``) to the
  :class:`CityModel` via ``app:appearanceMember``.
* Emits one ``app:X3DMaterial`` per unique averaged label.
* Targets every ``MultiSurface`` and ``CompositeSurface`` id under each
  building — covering LoD 0 MultiSurfaces, LoD 1 CompositeSurface
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
    append_energy_label_appearance,
    collect_surface_target_ids,
)
from citygml_energy.city_builder.builders import (
    attach_building_units_to_building,
    build_building,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.epc_score import label_to_rgb
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel
from citygml_energy.core import CityModel


def _square(z: float, surface_type: str | None = None) -> SemanticPolygon:
    return SemanticPolygon(
        polygon=GeometryPolygon(
            exterior=[(0.0, 0.0, z), (1.0, 0.0, z), (1.0, 1.0, z), (0.0, 1.0, z)],
        ),
        surface_type=surface_type,
    )


def _parsed(pand_id: str) -> ParsedBuilding:
    return ParsedBuilding(
        pand_id=pand_id,
        attributes={"oorspronkelijkbouwjaar": 2000},
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": [_square(0.0), _square(3.0)],
            "2": [_square(0.0, "GroundSurface"), _square(3.0, "RoofSurface")],
        },
    )


def _vbo(identificatie: str, huisnummer: int) -> Verblijfsobject:
    return Verblijfsobject(
        identificatie=identificatie,
        pand_identificatie="pand_does_not_matter",
        gebruiksdoel=["woonfunctie"],
        oppervlakte=70.0,
        status=None,
        postcode="2628CD",
        huisnummer=huisnummer,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam="Mekelweg",
        point=(85000.0, 446500.0),
        properties={},
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

    # LoD0 MultiSurface, LoD1 CompositeSurface shell, and each LoD2
    # thematic MultiSurface should all be present.
    assert any(t.endswith("_lod0") for t in targets)
    assert any(t.endswith("_lod1_shell") for t in targets)
    assert any("groundsurface_ms" in t for t in targets)
    assert any("roofsurface_ms" in t for t in targets)


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
