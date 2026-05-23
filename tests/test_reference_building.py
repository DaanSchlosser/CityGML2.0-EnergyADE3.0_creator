"""Tests for the reference-building input.

Two concerns are tested:

1. **XSD validity** -- the generated GML validates against the Energy ADE 3.0
   beta8 + CityGML 2.0 XSD schema set, the same check FME performs.

2. **Completeness** -- every feature declared in the JSON input is present in
   the serialized XML.  XSD validation alone cannot catch silently dropped
   features because nearly all child elements are optional (minOccurs=0).

Supplementary tests cover qualities the XSD cannot enforce (CRS propagation)
and input-loader error handling.

Tests are parameterized over every canonical owner-occupier fixture so they stay
value-agnostic: any structurally-equivalent valid input (full or shareable
sample) must satisfy the same assertions. Magic numbers tied to a specific
fixture do not belong here.
"""

from copy import deepcopy
from pathlib import Path

import lxml.etree as etree
import pytest

from citygml_energy import (
    InputFileError,
    build_city_model_from_feature_collection,
    generate_city_model,
    load_feature_collection,
)
from examples.create_building import INPUT
from tools.validate_xsd import load_schema

NS = {
    "core": "http://www.opengis.net/citygml/2.0",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "gml": "http://www.opengis.net/gml",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
    "xlink": "http://www.w3.org/1999/xlink",
}

_SAMPLE_INPUT = INPUT.parent / "owner_occupier_building_sample.json"

_RENODAT_INPUTS = [INPUT]
if _SAMPLE_INPUT.exists():
    _RENODAT_INPUTS.append(_SAMPLE_INPUT)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def xsd_schema():
    return load_schema()


@pytest.fixture(
    scope="module",
    params=_RENODAT_INPUTS,
    ids=[p.stem for p in _RENODAT_INPUTS],
)
def building_input_path(request):
    return request.param


@pytest.fixture(scope="module")
def reference_building_model(building_input_path):
    return generate_city_model(building_input_path)


@pytest.fixture(scope="module")
def reference_building_xml(reference_building_model):
    return reference_building_model.to_string()


@pytest.fixture(scope="module")
def reference_building_root(reference_building_xml):
    return etree.fromstring(reference_building_xml.encode("utf-8"))


# ---------------------------------------------------------------------------
# 1. XSD validity
# ---------------------------------------------------------------------------


def test_generated_validates_against_xsd(xsd_schema, reference_building_root):
    """The full per-building pipeline output validates against the XSD schema set."""
    xsd_schema.assertValid(reference_building_root)


# ---------------------------------------------------------------------------
# 2. Completeness -- every input feature is present in the output XML
#
# XSD says almost every child element is optional, so a building with
# zero devices, zero zones, and zero geometry would still validate.
# These tests verify nothing was silently dropped.
# ---------------------------------------------------------------------------


def test_single_building_as_city_object_member(reference_building_root):
    """The input has one building; it must appear as one cityObjectMember."""
    buildings = reference_building_root.findall("core:cityObjectMember/bldg:Building", NS)
    assert len(buildings) == 1


def test_devices_split_between_building_and_building_unit(reference_building_root):
    """PV lives under the Building; all other devices live under the BuildingUnit.

    The :class:`nrg3:PhotovoltaicCollector` is a physical-structure-level
    feature: the panel array sits on the roof of the Pand, not inside
    any one occupied unit, and the city-pipeline matcher attaches
    panel-derived collectors at the Building level for the same reason
    (see :func:`citygml_energy.city_builder.solar_panels.attach_solar_collectors_to_building`).
    For a single-VBO Pand every other energy device serves and meters
    the single occupied unit, so heat pump, distribution, thermal
    storage, EV charger, and the per-unit electrical appliances
    (cooktop, microwave, cooker tap, coffee machine, dishwasher) all
    parent under the BuildingUnit.
    """
    unit_devices = reference_building_root.findall(
        ".//nrg3:BuildingUnit/nrg3:device", NS,
    )
    assert len(unit_devices) == 9

    building_devices = reference_building_root.findall(
        ".//bldg:Building/nrg3:device", NS,
    )
    assert len(building_devices) == 1

    building_device_path = ".//bldg:Building/nrg3:device"
    assert len(reference_building_root.findall(f"{building_device_path}/nrg3:PhotovoltaicCollector", NS)) == 1

    unit_device_path = ".//nrg3:BuildingUnit/nrg3:device"
    assert len(reference_building_root.findall(f"{unit_device_path}/nrg3:HeatPump", NS)) == 1
    assert len(reference_building_root.findall(f"{unit_device_path}/nrg3:ThermalDistribution", NS)) == 1
    assert len(reference_building_root.findall(f"{unit_device_path}/nrg3:ThermalStorageDevice", NS)) == 1
    assert len(reference_building_root.findall(f"{unit_device_path}/nrg3:EVChargingStation", NS)) == 1
    assert len(reference_building_root.findall(f"{unit_device_path}/nrg3:GenericElectricalDevice", NS)) == 5


def test_occupants_attached_to_building_unit(reference_building_root):
    """Input declares 1 Occupants feature; it must be nested under the BuildingUnit.

    Energy ADE 3.0 inherits ``occupiedBy`` from ``AbstractBuildingSpace``,
    so it is available on ``BuildingUnit`` (and on ``Zone``) — both more
    specific than ``Building``. For a single-VBO Pand the canonical
    location is the BuildingUnit; in a multi-unit Pand each apartment
    can carry its own ``Occupants`` record.
    """
    occupants = reference_building_root.findall(
        ".//nrg3:BuildingUnit/nrg3:occupiedBy/nrg3:Occupants", NS,
    )
    assert len(occupants) == 1
    # And nothing on the Building itself (would be a duplicate).
    occupants_on_bldg = reference_building_root.findall(
        ".//bldg:Building/nrg3:occupiedBy/nrg3:Occupants", NS,
    )
    assert occupants_on_bldg == []


def test_singular_building_unit_attached_to_building(reference_building_root):
    """Single-VBO Pand carries exactly one ``nrg3:BuildingUnit`` under the Building.

    The BuildingUnit hosts the per-VBO net floor area, occupants,
    ownership, and (when present) the
    ``nrg3:EnergyPerformanceCertificate`` — mirroring the city-scale
    pipeline so a downstream consumer sees the same shape regardless
    of authoring path. The address itself is **not** on the
    BuildingUnit: it lives once on the parent Building under
    ``bldg:address`` (CityGML 2.0 composition slot) and the
    BuildingUnit holds only an xlink reference via ``nrg3:address``
    (Energy ADE 3.0 UML ``BuildingUnit.address`` is tagged
    ``relationType=association``). See
    :func:`test_address_owned_by_building_unit_xlinks_to_it`.
    """
    units = reference_building_root.findall(
        ".//bldg:Building/nrg3:buildingUnit/nrg3:BuildingUnit", NS,
    )
    assert len(units) == 1
    unit = units[0]
    # Mandatory ``nrg3:type`` (gml:CodeType) — the BAG ``gebruiksdoel``
    # ``woonfunctie`` for a residential VBO.
    type_el = unit.find("nrg3:type", NS)
    assert type_el is not None and type_el.text == "woonfunctie"


def test_address_owned_by_building_unit_xlinks_to_it(reference_building_root):
    """Address ownership and unit-side xlink, per Energy ADE 3.0 UML.

    The ``core:Address`` lives once at Building level under the
    CityGML 2.0 composition slot ``bldg:address`` (XSD
    ``building.xsd`` line 78, ``[0..*]``). The ``nrg3:BuildingUnit``
    holds only an ``xlink:href`` pointer via ``nrg3:address`` (XSD
    line 1520-1526, ``relationType="association"``). This test
    asserts no inline ``<core:Address>`` payload survives on a
    ``nrg3:address`` element, and that every unit-side pointer
    resolves to an Address actually emitted by the Building.
    """
    bldg_addr = reference_building_root.findall(
        ".//bldg:Building/bldg:address/core:Address", NS,
    )
    assert len(bldg_addr) == 1, (
        f"expected 1 Address at bldg:address, got {len(bldg_addr)}"
    )
    address_id = bldg_addr[0].get(f"{{{NS['gml']}}}id")
    assert address_id is not None

    unit_addr_inline = reference_building_root.findall(
        ".//nrg3:BuildingUnit/nrg3:address/core:Address", NS,
    )
    assert unit_addr_inline == [], (
        "nrg3:address on a BuildingUnit must NOT carry an inline core:Address "
        "(Energy ADE 3.0 tags BuildingUnit.address as relationType=association)"
    )

    unit_addr_props = reference_building_root.findall(
        ".//nrg3:BuildingUnit/nrg3:address", NS,
    )
    assert len(unit_addr_props) == 1
    href = unit_addr_props[0].get(f"{{{NS['xlink']}}}href")
    assert href == f"#{address_id}", (
        f"unit address xlink:href {href!r} does not resolve to the "
        f"Building-owned Address {address_id!r}"
    )


def test_zone_with_two_heated_zone_parts(reference_building_root):
    """Input declares 1 Zone with 2 conditioned ZoneParts.

    The attic ZonePart was removed from the input because it is neither
    heated nor cooled, and the EnergyADE model does not require listing
    unconditioned spaces.
    """
    zones = reference_building_root.findall(".//bldg:Building/nrg3:zone//nrg3:Zone", NS)
    assert len(zones) == 1

    zone_parts = zones[0].findall("nrg3:zonePart/nrg3:ZonePart", NS)
    assert len(zone_parts) == 2


def test_zone_references_its_building_unit(reference_building_root):
    """The Zone carries an xlink to its BuildingUnit.

    Energy ADE 3.0 encodes Zone -> BuildingUnit as ``byReference`` on
    ``AbstractZone`` (UML pg 10/12). Without the xlink a downstream
    consumer cannot tell which unit the thermal zone serves -- a gap
    that matters for the single-unit owner-occupier case where the
    unit-scoped devices, occupants, EPC and energy resources all live
    under the BuildingUnit while the Zone sits at Building level (the
    PhotovoltaicCollector is the lone exception, parented under the
    Building itself as a physical-structure-level device).
    """
    zone = reference_building_root.find(".//bldg:Building/nrg3:zone/nrg3:Zone", NS)
    assert zone is not None

    refs = zone.findall("nrg3:buildingUnit", NS)
    assert len(refs) == 1
    href = refs[0].get(f"{{{NS['xlink']}}}href")
    assert href is not None and href.startswith("#")

    target_id = href[1:]
    unit = reference_building_root.find(
        f".//nrg3:BuildingUnit[@gml:id='{target_id}']", NS,
    )
    assert unit is not None, f"Zone buildingUnit xlink points at missing id {target_id!r}"


def test_zone_hull_coincidence_flags_are_false(reference_building_root):
    """Zone carries coincidesWithLod2Hull and coincidesWithLod3Hull, both false.

    The building has LoD 2 geometry but the thermal zone does not exactly
    coincide with the building hull. No LoD 3 hull exists. Both flags are
    explicitly false; ``findtext`` with default="false" handles both the
    case where xsdata emits the element and the case where it relies on the
    XSD-declared default.
    """
    zone = reference_building_root.find(".//nrg3:Zone", NS)
    assert zone is not None

    lod2 = zone.findtext("nrg3:coincidesWithLod2Hull", default="false", namespaces=NS)
    lod3 = zone.findtext("nrg3:coincidesWithLod3Hull", default="false", namespaces=NS)
    assert lod2 == "false", f"coincidesWithLod2Hull: expected false, got {lod2!r}"
    assert lod3 == "false", f"coincidesWithLod3Hull: expected false, got {lod3!r}"


def test_heating_and_cooling_schedules_on_zone_parts(reference_building_root):
    """Both conditioned zone parts carry a heating and a cooling schedule."""
    zone_parts = reference_building_root.findall(".//nrg3:Zone/nrg3:zonePart/nrg3:ZonePart", NS)
    assert len(zone_parts) == 2

    parts_with_heating = [
        zp for zp in zone_parts if zp.find("nrg3:heatingSchedule", NS) is not None
    ]
    parts_with_cooling = [
        zp for zp in zone_parts if zp.find("nrg3:coolingSchedule", NS) is not None
    ]
    assert len(parts_with_heating) == 2
    assert len(parts_with_cooling) == 2


def test_energy_resources_attached_to_devices(reference_building_root):
    """Input declares 2 Energy resources: one on the EV, one on the PV."""
    ev_resources = reference_building_root.findall(".//nrg3:EVChargingStation/nrg3:resource/nrg3:Energy", NS)
    assert len(ev_resources) == 1

    pv_resources = reference_building_root.findall(
        ".//nrg3:PhotovoltaicCollector/nrg3:resource/nrg3:Energy", NS
    )
    assert len(pv_resources) == 1


def test_monthly_time_series_on_pv_energy(reference_building_root):
    """The PV energy resource has a MonthlyTimeSeries for time-dependent production."""
    ts = reference_building_root.findall(
        ".//nrg3:PhotovoltaicCollector//nrg3:Energy"
        "/nrg3:timeDependentAmount/nrg3:MonthlyTimeSeries",
        NS,
    )
    assert len(ts) == 1


def test_pv_has_two_installed_on_relations_from_json(reference_building_root):
    """PV panel array spans two roofs; both relations originate from the JSON.

    The input's ``installed_on: ["RoofSurface_01", "RoofSurface_02"]`` is
    resolved after geometry attachment, producing two ``CityObjectRelation``
    entries (one xlink:href per target roof) with ``relationType="installedOn"``.
    Geometry alone no longer drives these (every PV panel's STEP layer has
    ``|parent=RoofSurface_02``, so a geometry-derived approach would emit
    only one relation). The two distinct hrefs prove the JSON path is live.
    """
    relations = reference_building_root.findall(
        ".//nrg3:PhotovoltaicCollector/nrg3:relatedTo/nrg3:CityObjectRelation", NS
    )
    assert len(relations) == 2

    for rel in relations:
        rt = rel.find("nrg3:relationType", NS)
        assert rt is not None and rt.text == "installedOn"

    hrefs = {
        rel.find("nrg3:relatedTo", NS).get("{http://www.w3.org/1999/xlink}href")
        for rel in relations
    }
    assert len(hrefs) == 2, f"expected two distinct href targets, got {hrefs}"
    assert all(h and h.startswith("#") for h in hrefs)


def test_pv_installed_on_resolves_to_real_roof_surfaces(reference_building_root):
    """Every installedOn href must point to an existing RoofSurface element."""
    roof_ids = {
        roof.get("{http://www.opengis.net/gml}id")
        for roof in reference_building_root.findall(".//bldg:boundedBy/bldg:RoofSurface", NS)
    }
    relations = reference_building_root.findall(
        ".//nrg3:PhotovoltaicCollector/nrg3:relatedTo/nrg3:CityObjectRelation", NS
    )
    for rel in relations:
        href = rel.find("nrg3:relatedTo", NS).get("{http://www.w3.org/1999/xlink}href")
        assert href.lstrip("#") in roof_ids, (
            f"installedOn href {href!r} does not resolve to any RoofSurface; "
            f"available: {sorted(roof_ids)}"
        )


def test_geometry_imported_from_step(reference_building_root):
    """Input has STEP files for LOD0-3; the building must have geometry at each level."""
    building = reference_building_root.find("core:cityObjectMember/bldg:Building", NS)

    # LOD0 footprint
    assert building.find("bldg:lod0FootPrint", NS) is not None

    # LOD1 solid
    assert building.find("bldg:lod1Solid", NS) is not None

    # LOD2+3 boundary surfaces. A real building must have at least one of
    # each semantic category; ``len > 0`` alone would survive a refactor
    # that drops two of the three types. Check categories explicitly.
    wall_surfaces = building.findall("bldg:boundedBy/bldg:WallSurface", NS)
    roof_surfaces = building.findall("bldg:boundedBy/bldg:RoofSurface", NS)
    ground_surfaces = building.findall("bldg:boundedBy/bldg:GroundSurface", NS)
    assert wall_surfaces, "Building has no WallSurface after STEP import"
    assert roof_surfaces, "Building has no RoofSurface after STEP import"
    assert ground_surfaces, "Building has no GroundSurface after STEP import"

    # Zone parts have lod3Solid from STEP files (attic ZonePart was removed
    # from the input because it is unconditioned).
    zone_parts = reference_building_root.findall(".//nrg3:ZonePart", NS)
    parts_with_solid = [zp for zp in zone_parts if zp.find("nrg3:lod3Solid", NS) is not None]
    assert len(parts_with_solid) == 2


def test_pv_has_lod2_and_lod3_geometry(reference_building_root):
    """The PV collector carries geometry at both LoD 2 and LoD 3.

    LoD 2 is the aggregated "whole array" surface (one polygon), exported
    from Rhino as a single unnamed shell. LoD 3 is the individually-panelled
    representation (one polygon per physical panel). Both arrive via STEP
    imports and both attach to the same PhotovoltaicCollector, so a reader
    that understands only one LoD still sees the array. The absolute panel
    count depends on the STEP file and is intentionally not asserted here.
    """
    pv = reference_building_root.find(".//nrg3:PhotovoltaicCollector", NS)
    assert pv is not None

    lod2 = pv.find("nrg3:lod2MultiSurface", NS)
    assert lod2 is not None, "PV must carry lod2MultiSurface (aggregated array)"
    lod2_polys = lod2.findall(".//gml:Polygon", NS)
    assert len(lod2_polys) == 1, (
        f"LoD 2 PV must be a single aggregated polygon, got {len(lod2_polys)}"
    )

    lod3 = pv.find("nrg3:lod3MultiSurface", NS)
    assert lod3 is not None, "PV must carry lod3MultiSurface (per-panel array)"
    lod3_polys = lod3.findall(".//gml:Polygon", NS)
    assert len(lod3_polys) > len(lod2_polys), (
        "LoD 3 PV must carry more polygons than LoD 2 (one per physical panel)"
    )


# ---------------------------------------------------------------------------
# XSD validity with modified input
# ---------------------------------------------------------------------------


def test_multiple_buildings_validate_against_xsd(xsd_schema):
    """Adding a second building still produces XSD-valid output."""
    data = load_feature_collection(INPUT)
    second_building = deepcopy(data["features"][0])
    second_building["id"] = "id_building_2"
    second_building["name"] = ["Leia's house"]
    second_building["identifier"] = [
        {"value": "0000000000000002", "code_space": "https://example.invalid/bag"},
    ]

    extended_data = deepcopy(data)
    extended_data["features"].append(second_building)

    model = build_city_model_from_feature_collection(extended_data)
    xml = model.to_string()
    doc = etree.fromstring(xml.encode("utf-8"))
    xsd_schema.assertValid(doc)


# ---------------------------------------------------------------------------
# Supplementary: qualities the XSD cannot enforce
# ---------------------------------------------------------------------------


def test_generated_has_envelope_with_crs(reference_building_root):
    """The gml:Envelope carries srsName and srsDimension (needed by CityGML readers)."""
    envelope = reference_building_root.find(".//gml:Envelope", NS)
    assert envelope is not None, "Missing gml:Envelope"
    assert "srsName" in envelope.attrib
    assert envelope.attrib["srsDimension"] == "3"


def test_geometry_elements_have_srs(reference_building_root):
    """All gml:MultiSurface elements carry srsName and srsDimension.

    Anchors on a concrete lower bound derived from the fixture's structure
    (at least one multi-surface per boundary surface), so the for-loop
    cannot pass vacuously when the count regresses to zero.
    """
    multi_surfaces = reference_building_root.findall(".//gml:MultiSurface", NS)
    bounded_surfaces = reference_building_root.findall(
        ".//bldg:Building/bldg:boundedBy/*", NS
    )
    assert len(multi_surfaces) >= len(bounded_surfaces), (
        f"expected >= {len(bounded_surfaces)} MultiSurface elements "
        f"(one per boundary surface), got {len(multi_surfaces)}"
    )
    for ms in multi_surfaces:
        assert "srsName" in ms.attrib, f"Missing srsName on {ms.attrib}"
        assert "srsDimension" in ms.attrib, f"Missing srsDimension on {ms.attrib}"


def test_coordinates_are_fixed_point_decimals(reference_building_root):
    """Every ordinate is a plain fixed-point decimal, not scientific notation.

    Some CityGML readers choke on ``1.23e-5``-style tokens. The emitter
    quantises to a micrometre grid before serialisation, so sub-um FP
    residuals collapse to zero and every ordinate stays in decimal form.
    """
    for pos_list in reference_building_root.findall(".//gml:posList", NS):
        for token in (pos_list.text or "").split():
            assert "e" not in token.lower(), (
                f"Coordinate emitted in scientific notation: {token!r}"
            )
    for pos in reference_building_root.findall(".//gml:pos", NS):
        for token in (pos.text or "").split():
            assert "e" not in token.lower(), (
                f"Coordinate emitted in scientific notation: {token!r}"
            )


# ---------------------------------------------------------------------------
# Input loader: error handling
# ---------------------------------------------------------------------------


def test_building_input_rejects_unknown_feature_type():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["features"][0]["type"] = "nrg3:NotSupported"

    with pytest.raises(InputFileError, match="Unknown type"):
        build_city_model_from_feature_collection(invalid_data)


def test_building_input_rejects_missing_geometry_source_target():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["geometry_sources"][0]["target_building_id"] = "missing_building"

    with pytest.raises(InputFileError, match="target_building_id"):
        build_city_model_from_feature_collection(invalid_data)


def test_building_input_rejects_missing_geometry_source_file():
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    invalid_data["geometry_sources"][0]["path"] = "../does_not_exist.stp"

    with pytest.raises(InputFileError, match="does not exist"):
        build_city_model_from_feature_collection(
            invalid_data,
            base_path=Path(INPUT).parent,
        )


def test_building_input_rejects_unresolved_installed_on():
    """``installed_on`` referencing a nonexistent surface must fail loudly.

    Silent no-op would let JSON typos slip past as missing relations that
    nobody notices until a downstream consumer complains.
    """
    data = load_feature_collection(INPUT)
    invalid_data = deepcopy(data)
    for feature in invalid_data["features"]:
        if feature.get("id") == "pv_panel_1":
            feature["installed_on"] = ["RoofSurface_99"]
            break
    else:
        pytest.fail("pv_panel_1 not in fixture")

    with pytest.raises(InputFileError, match="RoofSurface_99"):
        build_city_model_from_feature_collection(
            invalid_data,
            base_path=Path(INPUT).parent,
        )


def test_installed_on_object_form_pins_relation_to_specific_lod():
    """``{name, lod}`` form pins the relation to the chosen LoD's gml:id.

    The canonical input's ``installed_on: ["RoofSurface_01", "RoofSurface_02"]``
    resolves to LoD 3 RoofSurfaces (highest-LoD-wins). Switching the entries
    to the explicit object form with ``lod: 2`` must instead target the LoD 2
    RoofSurfaces, even though the same names exist at LoD 3.
    """
    data = load_feature_collection(INPUT)
    mutated = deepcopy(data)
    for feature in mutated["features"]:
        if feature.get("id") == "pv_panel_1":
            feature["installed_on"] = [
                {"name": "RoofSurface_01", "lod": 2},
                {"name": "RoofSurface_02", "lod": 2},
            ]
            break
    else:
        pytest.fail("pv_panel_1 not in fixture")

    model = build_city_model_from_feature_collection(
        mutated, base_path=Path(INPUT).parent
    )
    root = etree.fromstring(model.to_string().encode("utf-8"))

    # Collect the gml:id of every LoD 2 RoofSurface (the one that carries a
    # bldg:lod2MultiSurface).
    lod2_roof_ids: set[str] = set()
    for roof in root.findall(".//bldg:boundedBy/bldg:RoofSurface", NS):
        if roof.find("bldg:lod2MultiSurface", NS) is not None:
            lod2_roof_ids.add(roof.get("{http://www.opengis.net/gml}id"))
    assert len(lod2_roof_ids) >= 2, (
        f"need at least two LoD 2 RoofSurfaces in the fixture, found {lod2_roof_ids}"
    )

    relations = root.findall(
        ".//nrg3:PhotovoltaicCollector/nrg3:relatedTo/nrg3:CityObjectRelation", NS
    )
    hrefs = {
        rel.find("nrg3:relatedTo", NS)
        .get("{http://www.w3.org/1999/xlink}href")
        .lstrip("#")
        for rel in relations
    }
    assert len(hrefs) == 2
    assert hrefs.issubset(lod2_roof_ids), (
        f"expected all hrefs to point at LoD 2 RoofSurfaces {lod2_roof_ids}, got {hrefs}"
    )


def test_installed_on_object_form_rejects_unknown_lod():
    """``{name, lod}`` with an LoD the name does not exist at must raise."""
    data = load_feature_collection(INPUT)
    mutated = deepcopy(data)
    for feature in mutated["features"]:
        if feature.get("id") == "pv_panel_1":
            feature["installed_on"] = [{"name": "RoofSurface_01", "lod": 9}]
            break
    else:
        pytest.fail("pv_panel_1 not in fixture")

    with pytest.raises(InputFileError, match=r"LoD 9"):
        build_city_model_from_feature_collection(
            mutated, base_path=Path(INPUT).parent
        )
