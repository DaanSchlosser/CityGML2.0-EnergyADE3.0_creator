"""End-to-end test of the city-scale pipeline with every fetcher mocked.

This is the top-level guarantee that:

* the pipeline orchestrator wires the fetchers together correctly,
* the resulting ``CityModel`` serialises to GML that validates against
  the Energy ADE 3.0 beta8 + CityGML 2.0 + GML 3.1.1 XSD set,
* BAG addresses and EP-online labels survive the round trip into
  ``core:Address`` / ``nrg3:BuildingUnit`` / ``nrg3:EnergyPerformanceCertificate``.

No network is involved; every fetcher is monkeypatched to return
deterministic fixture data.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import lxml.etree as etree
import pytest

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder import (
    CityBuildConfig,
    build_city_model,
)
from citygml_energy.city_builder import pipeline as pipeline_module
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.fetchers import (
    bag as bag_fetchers,
)
from citygml_energy.city_builder.fetchers import (
    eponline as eponline_fetchers,
)
from citygml_energy.city_builder.fetchers import (
    municipality as muni_fetchers,
)
from citygml_energy.city_builder.fetchers.bag import Pand, Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel
from citygml_energy.city_builder.fetchers.municipality import MunicipalityOutline
from tests._factories import make_pand, make_parsed_building, make_square_polygon, make_vbo
from tools.validate_xsd import load_schema

_PAND_ID = "0503100000000042"
_VBO_ID = "0503010000000042"

_square = make_square_polygon


def _cube_shell() -> list[SemanticPolygon]:
    p = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 3.0),
        (1.0, 0.0, 3.0),
        (1.0, 1.0, 3.0),
        (0.0, 1.0, 3.0),
    ]
    faces_and_types = [
        ([p[0], p[3], p[2], p[1]], "GroundSurface"),
        ([p[4], p[5], p[6], p[7]], "RoofSurface"),
        ([p[0], p[1], p[5], p[4]], "WallSurface"),
        ([p[1], p[2], p[6], p[5]], "WallSurface"),
        ([p[2], p[3], p[7], p[6]], "WallSurface"),
        ([p[3], p[0], p[4], p[7]], "WallSurface"),
    ]
    return [
        SemanticPolygon(polygon=GeometryPolygon(exterior=verts), surface_type=st)
        for verts, st in faces_and_types
    ]


def _fixture_parsed_building() -> ParsedBuilding:
    return make_parsed_building(
        pand_id=_PAND_ID,
        attributes={
            "oorspronkelijkbouwjaar": 1985,
            "identificatie": _PAND_ID,
        },
        geometries={
            "0": [_square(0.0, "GroundSurface")],
            "1": _cube_shell(),
            "2": _cube_shell(),
        },
    )


def _fixture_outline() -> MunicipalityOutline:
    return MunicipalityOutline(
        name="Delft",
        cbs_code="0503",
        feature={
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [84000.0, 445000.0],
                        [86000.0, 445000.0],
                        [86000.0, 447000.0],
                        [84000.0, 447000.0],
                        [84000.0, 445000.0],
                    ]
                ],
            },
        },
        bbox=(84000.0, 445000.0, 86000.0, 447000.0),
    )


def _fixture_pand() -> Pand:
    return make_pand(identificatie=_PAND_ID, bouwjaar=1985)


def _fixture_vbo() -> Verblijfsobject:
    return make_vbo(
        identificatie=_VBO_ID,
        pand_identificatie=_PAND_ID,
        point=(85000.0, 446500.0),
    )


def _fixture_label() -> EnergyLabel:
    return EnergyLabel(
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


def _config(tmp_path: Path, *, with_labels: bool = True) -> CityBuildConfig:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True)
    source = tmp_path / "city.json"
    source.write_text(json.dumps({}), encoding="utf-8")
    return CityBuildConfig(
        source_path=source,
        municipality="Delft",
        bbox=None,
        lods=(0, 1, 2),
        include_addresses=True,
        include_energy_labels=with_labels,
        ep_online_api_key_file=(tmp_path / "ep.key" if with_labels else None),
        cache_dir=cache,
        output_path=tmp_path / "delft.gml",
        srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
        srs_dimension=3,
        city_model_name="Delft",
        city_model_description="Test fixture",
        gml_id_prefix="",
    )


@pytest.fixture
def mocked_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Patch every fetcher to return the fixture data above."""
    # EP key file content (only read when include_energy_labels=True).
    (tmp_path / "ep.key").write_text("fake-token", encoding="utf-8")

    monkeypatch.setattr(
        muni_fetchers,
        "fetch_municipality_outline",
        lambda session, *, name: _fixture_outline(),
    )
    monkeypatch.setattr(
        bag_fetchers,
        "fetch_panden",
        lambda session, *, bbox, cbs_code=None: [_fixture_pand()],
    )
    monkeypatch.setattr(
        bag_fetchers,
        "fetch_verblijfsobjecten",
        lambda session, *, bbox, cbs_code=None: [_fixture_vbo()],
    )
    monkeypatch.setattr(
        eponline_fetchers,
        "fetch_energy_labels",
        lambda session, *, api_key, wanted_ids=None, wanted_keys=None: [_fixture_label()],
    )
    # Bypass the 3DBAG tile fetch with one fixture return. The extent
    # resolver still runs (using the mocked municipality outline above)
    # and hands a real clip geometry to _fetch_parsed_buildings; patching
    # the fetch here keeps the test off the 3DBAG HTTP path.
    monkeypatch.setattr(
        pipeline_module,
        "_fetch_parsed_buildings",
        lambda session, *, clip_geom, bbox: [_fixture_parsed_building()],
    )


def test_pipeline_builds_and_serialises(tmp_path: Path, mocked_pipeline) -> None:
    config = _config(tmp_path, with_labels=True)
    model = build_city_model(config)
    assert len(model.xsd.city_object_member) == 1

    building = model.xsd.city_object_member[0].building
    assert building.id == f"pand_{_PAND_ID}"
    assert building.lod0_foot_print is not None
    assert building.lod1_solid is not None
    # LoD2 is now expressed via thematic boundedBy surfaces, not lod2MultiSurface.
    assert building.lod2_multi_surface is None
    surf_types = {
        type(s.ground_surface or s.wall_surface or s.roof_surface).__name__
        for s in building.bounded_by
    }
    assert "GroundSurface2" in surf_types
    assert "WallSurface2" in surf_types
    assert "RoofSurface2" in surf_types
    assert len(building.building_unit) == 1

    unit = building.building_unit[0].building_unit
    assert unit.energy_performance_certificate  # EP-online matched
    assert unit.energy_performance_certificate[0].energy_performance_certificate.label == "A"

    # The inline ``core:Address`` payload lives once on the Building via
    # the CityGML 2.0 composition slot ``bldg:address`` (XSD line 78);
    # the BuildingUnit carries an xlink reference only. See
    # :func:`attach_building_units_to_building` for the orchestration.
    assert len(building.address) == 1
    assert unit.address and unit.address[0].address is None
    assert unit.address[0].href is not None and unit.address[0].href.startswith("#")
    assert unit.address[0].href == f"#{building.address[0].address.id}"

    # Address now wraps the locality in an ``xAL:Country`` element. The
    # locality name comes from the VBO's BAG ``woonplaats`` when set,
    # falling back to the pipeline's caller-supplied ``city_name`` (the
    # municipality). This fixture's VBO has no woonplaats, so the
    # ``city_name="Delft"`` fallback shows up here; in production every
    # PDOK BAG VBO carries woonplaats directly.
    addr_details = building.address[0].address.xal_address.address_details
    country = addr_details.country
    assert country is not None
    assert country.country_name_code[0].content[0] == "NL"
    locality_names = country.locality.locality_name
    assert locality_names and locality_names[0].content == ["Delft"]


def test_pipeline_output_validates_against_xsd(tmp_path: Path, mocked_pipeline) -> None:
    config = _config(tmp_path, with_labels=True)
    model = build_city_model(config)
    xml = model.to_string()
    schema = load_schema()
    root = etree.fromstring(xml.encode("utf-8"))
    schema.assertValid(root)


def test_pipeline_attaches_semantic_landcover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocked_pipeline
) -> None:
    # Drives landcover through build_city_model so the fetch->attach wiring, the
    # landcover_count done-log basis, the attach-before-set_envelope ordering,
    # and the XSD validity of a building+landcover document are all exercised
    # together (the landcover unit tests cover the seams in isolation only).
    import dataclasses

    from citygml_energy._step import GeometryPolygon
    from citygml_energy.city_builder.cityjson_landcover_parse import ParsedLandcover
    from citygml_energy.city_builder.landcover import LandcoverSource
    from citygml_energy.city_builder.landcover_class import classify_landcover
    from citygml_energy.core import _resolve_bounded_by_field

    # A surface at z=4.0 sits ABOVE the fixture building's 0..3 z-range, so an
    # envelope upper-z of 4 proves the landcover's bbox corners reached
    # coords_sink, i.e. the landcover attach ran before set_envelope. Patch the
    # fetch so no network is needed; the build + attach still run for real.
    ring = [(0.0, 0.0, 4.0), (2.0, 0.0, 4.0), (2.0, 2.0, 4.0), (0.0, 2.0, 4.0)]
    landuse_attrs = {"3df_class": "Terrain", "bgt_type": "groenvoorziening"}
    water_attrs = {"bgt_type": "waterloop"}
    objects = [
        ParsedLandcover(
            object_id="01TESTLANDUSE",
            object_type="LandUse",
            attributes=landuse_attrs,
            polygons=[GeometryPolygon(exterior=ring, interiors=[])],
            disposition=classify_landcover("LandUse", landuse_attrs),
        ),
        ParsedLandcover(
            object_id="01TESTWATER",
            object_type="WaterBody",
            attributes=water_attrs,
            polygons=[GeometryPolygon(exterior=ring, interiors=[])],
            disposition=classify_landcover("WaterBody", water_attrs),
        ),
    ]
    monkeypatch.setattr(
        pipeline_module.landcover_module, "fetch_landcover", lambda *a, **k: objects
    )

    config = dataclasses.replace(_config(tmp_path), landcover_source=LandcoverSource())
    model = build_city_model(config)

    members = model.xsd.city_object_member
    assert sum(1 for m in members if m.land_use is not None) == 1
    assert sum(1 for m in members if m.water_body is not None) == 1
    land_use = next(m.land_use for m in members if m.land_use is not None)
    assert land_use.lod1_multi_surface.multi_surface.surface_member  # non-empty geometry

    bounded = getattr(model.xsd, _resolve_bounded_by_field())
    assert bounded.envelope.upper_corner.value[2] == pytest.approx(4.0)

    schema = load_schema()
    schema.assertValid(etree.fromstring(model.to_string().encode("utf-8")))


def test_pipeline_emits_no_landcover_without_landcover_block(
    tmp_path: Path, mocked_pipeline
) -> None:
    # Landcover is opt-in: with no landcover block, fetch_landcover short-circuits
    # and no landcover surface is emitted (independent of addresses/vegetation).
    config = _config(tmp_path)
    model = build_city_model(config)
    assert not any(
        m.land_use is not None
        or m.road is not None
        or m.water_body is not None
        or m.plant_cover is not None
        or m.bridge is not None
        or m.generic_city_object is not None
        for m in model.xsd.city_object_member
    )


def test_address_model_name_defaults_to_the_query_and_size(tmp_path: Path) -> None:
    # An address build with no explicit city_model.name titles itself after the
    # address and the square's size, so several extracts in one gemeente are
    # self-describing and distinct. An explicit name still wins; a gemeente
    # build with no name stays unnamed.
    import dataclasses

    from citygml_energy.city_builder.config import AddressSource

    cfg = _config(tmp_path)
    addr = AddressSource(query="Annie Romeinsingel 72-152 Leiden", extent_m=250.0)

    named = dataclasses.replace(cfg, address_source=addr, city_model_name="Custom title")
    assert pipeline_module._address_model_name(named) == "Custom title"

    derived = dataclasses.replace(cfg, address_source=addr, city_model_name=None)
    assert (
        pipeline_module._address_model_name(derived)
        == "Address extract: Annie Romeinsingel 72-152 Leiden (250 m)"
    )

    plain = dataclasses.replace(cfg, address_source=None, city_model_name=None)
    assert pipeline_module._address_model_name(plain) is None


def test_pipeline_omits_units_when_addresses_disabled(tmp_path: Path, mocked_pipeline) -> None:
    config = _config(tmp_path, with_labels=False)
    config = CityBuildConfig(
        source_path=config.source_path,
        municipality=config.municipality,
        bbox=config.bbox,
        lods=config.lods,
        include_addresses=False,
        include_energy_labels=False,
        ep_online_api_key_file=None,
        cache_dir=config.cache_dir,
        output_path=config.output_path,
        srs_name=config.srs_name,
        srs_dimension=config.srs_dimension,
        city_model_name=config.city_model_name,
        city_model_description=config.city_model_description,
        gml_id_prefix=config.gml_id_prefix,
    )
    model = build_city_model(config)
    assert model.xsd.city_object_member[0].building.building_unit == []
