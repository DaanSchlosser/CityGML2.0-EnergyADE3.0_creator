"""End-to-end test of the address-driven city pipeline.

The address mode is the one path through ``build_city_model`` where the
extent resolver, the box clip, and the highlight painter all cooperate:
``resolve_address_extent`` turns a free-text query into a centred square
box plus target Panden, ``BuildExtent(clip_to_box=True)`` hard-cuts the
scene to that box, and :class:`HighlightPainter` contrasts the targets
with their surroundings. Each piece has unit tests; this file runs the
whole chain through the orchestrator and validates the emitted GML
against the bundled XSD set.

The geocoder and the BAG seed fetch are faked at the seams inside
``address_extent`` so the real query parsing, street verification,
target selection, and square-extent maths run. The pipeline-level
fetchers are faked as in ``test_city_pipeline``. No network is involved.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import lxml.etree as etree
import pytest

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder import CityBuildConfig, address_extent, build_city_model
from citygml_energy.city_builder import pipeline as pipeline_module
from citygml_energy.city_builder.appearance import BUILDING_HIGHLIGHT_THEME
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.config import AddressSource
from citygml_energy.city_builder.fetchers import bag as bag_fetchers
from citygml_energy.city_builder.fetchers import municipality as muni_fetchers
from citygml_energy.city_builder.fetchers.locatieserver import GeocodeHit
from citygml_energy.core import _resolve_bounded_by_field
from tests._factories import make_pand, make_parsed_building, make_vbo
from tools.validate_xsd import load_schema

_QUERY = "Teststraat 1-5 Leiden"
_EXTENT_M = 300.0

# The two target VBO points below average to this centre, so the square
# box is (850, 850, 1150, 1150) for the 300 m extent.
_BOX = (850.0, 850.0, 1150.0, 1150.0)

_TARGET_A = "0546100000000001"  # target, 3DBAG geometry inside the box
_TARGET_B = "0546100000000002"  # target, no 3DBAG geometry (warning path)
_NEIGHBOUR = "0546100000000003"  # surroundings, inside the box
_STRADDLER = "0546100000000004"  # surroundings, straddles the box edge
_OUTSIDE = "0546100000000005"  # surroundings, wholly outside the box

_TARGET_COLOR = (0.9, 0.2, 0.1)
_SURROUNDINGS_COLOR = (0.7, 0.7, 0.7)


def _cube_shell(x0: float, y0: float, size: float, height: float) -> list[SemanticPolygon]:
    x1, y1 = x0 + size, y0 + size
    p = [
        (x0, y0, 0.0),
        (x1, y0, 0.0),
        (x1, y1, 0.0),
        (x0, y1, 0.0),
        (x0, y0, height),
        (x1, y0, height),
        (x1, y1, height),
        (x0, y1, height),
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


def _cube_building(
    pand_id: str, x0: float, y0: float, *, size: float = 10.0, height: float = 3.0
) -> ParsedBuilding:
    """A ``size`` x ``size`` cube at (x0, y0) with LoD 0 + 1 + 2 geometry."""
    x1, y1 = x0 + size, y0 + size
    footprint = SemanticPolygon(
        polygon=GeometryPolygon(
            exterior=[(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)],
        ),
        surface_type="GroundSurface",
    )
    return make_parsed_building(
        pand_id=pand_id,
        attributes={"oorspronkelijkbouwjaar": 1985, "identificatie": pand_id},
        geometries={
            "0": [footprint],
            "1": _cube_shell(x0, y0, size, height),
            "2": _cube_shell(x0, y0, size, height),
        },
    )


def _geocode_hit() -> GeocodeHit:
    return GeocodeHit(
        type="adres",
        weergavenaam="Teststraat 1, Leiden",
        point_rd=(1000.0, 1000.0),
        straatnaam="Teststraat",
        huisnummer=1,
        woonplaatsnaam="Leiden",
        gemeentenaam="Leiden",
    )


def _seed_vbos() -> list:
    # The two in-range VBOs sit on distinct panden; their per-pand
    # centroids average to (1000, 1000), the centre the box is built on.
    # Huisnummer 9 is on the right street but outside 1-5, so the
    # neighbour pand is fetched by the pipeline yet never a target.
    return [
        make_vbo(
            identificatie="0546010000000001",
            pand_identificatie=_TARGET_A,
            huisnummer=1,
            street="Teststraat",
            point=(990.0, 1000.0),
        ),
        make_vbo(
            identificatie="0546010000000002",
            pand_identificatie=_TARGET_B,
            huisnummer=5,
            street="Teststraat",
            point=(1010.0, 1000.0),
        ),
        make_vbo(
            identificatie="0546010000000003",
            pand_identificatie=_NEIGHBOUR,
            huisnummer=9,
            street="Teststraat",
            point=(905.0, 905.0),
        ),
    ]


def _pipeline_vbos() -> list:
    return [
        make_vbo(
            identificatie="0546010000000001",
            pand_identificatie=_TARGET_A,
            huisnummer=1,
            street="Teststraat",
            point=(990.0, 1000.0),
        ),
        make_vbo(
            identificatie="0546010000000003",
            pand_identificatie=_NEIGHBOUR,
            huisnummer=9,
            street="Teststraat",
            point=(905.0, 905.0),
        ),
    ]


def _config(tmp_path: Path) -> CityBuildConfig:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True)
    source = tmp_path / "city.json"
    source.write_text(json.dumps({}), encoding="utf-8")
    return CityBuildConfig(
        source_path=source,
        municipality="",
        bbox=None,
        lods=(0, 1, 2),
        include_addresses=True,
        include_energy_labels=False,
        ep_online_api_key_file=None,
        cache_dir=cache,
        output_path=tmp_path / "extract.gml",
        srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
        srs_dimension=3,
        city_model_name=None,
        city_model_description="Address e2e fixture",
        gml_id_prefix="",
        address_source=AddressSource(
            query=_QUERY,
            extent_m=_EXTENT_M,
            target_color=_TARGET_COLOR,
            surroundings_color=_SURROUNDINGS_COLOR,
        ),
    )


@pytest.fixture
def mocked_address_pipeline(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Fake the address seams and the pipeline fetchers; record the 3DBAG bbox."""
    seen: dict = {}

    def _no_outline(*args, **kwargs):
        raise AssertionError("municipality outline must not be fetched in address mode")

    monkeypatch.setattr(muni_fetchers, "fetch_municipality_outline", _no_outline)

    # Seams inside address_extent: the geocoder and the BAG seed fetch.
    # _best_hit's street/place verification and _select_targets' range
    # selection run for real against these fakes.
    monkeypatch.setattr(
        address_extent.locatieserver,
        "geocode_free",
        lambda session, text, *, type_filter="adres", rows=10: [_geocode_hit()],
    )
    monkeypatch.setattr(
        address_extent, "fetch_verblijfsobjecten", lambda session, *, bbox: _seed_vbos()
    )

    panden = [
        make_pand(identificatie=pand_id)
        for pand_id in (_TARGET_A, _TARGET_B, _NEIGHBOUR, _STRADDLER, _OUTSIDE)
    ]
    monkeypatch.setattr(
        bag_fetchers, "fetch_panden", lambda session, *, bbox, cbs_code=None: panden
    )
    monkeypatch.setattr(
        bag_fetchers,
        "fetch_verblijfsobjecten",
        lambda session, *, bbox, cbs_code=None: _pipeline_vbos(),
    )

    def fake_fetch_parsed(session, *, clip_geom, bbox):
        seen["bbox"] = bbox
        return [
            _cube_building(_TARGET_A, 995.0, 995.0),
            _cube_building(_NEIGHBOUR, 900.0, 900.0),
            # Crosses the box's east edge at x=1150, so the clip cuts and
            # caps it rather than keeping or dropping it whole.
            _cube_building(_STRADDLER, 1145.0, 1000.0),
            _cube_building(_OUTSIDE, 1200.0, 1200.0),
        ]

    monkeypatch.setattr(pipeline_module, "_fetch_parsed_buildings", fake_fetch_parsed)
    return seen


def test_address_pipeline_builds_the_clipped_highlighted_extract(
    tmp_path: Path, mocked_address_pipeline: dict
) -> None:
    model = build_city_model(_config(tmp_path))

    # The model titles itself after the query and the square's size.
    assert model.gml_name == "Address extract: Teststraat 1-5 Leiden (300 m)"

    # The square-extent maths reached the 3DBAG fetch: 300 m centred on
    # the mean of the two target panden's VBO points.
    assert mocked_address_pipeline["bbox"] == pytest.approx(_BOX)

    buildings = {
        m.building.id: m.building for m in model.xsd.city_object_member if m.building is not None
    }
    # The outside building is dropped by the box clip; the target without
    # 3DBAG geometry never reaches the build; the straddler survives cut.
    assert set(buildings) == {
        f"pand_{_TARGET_A}",
        f"pand_{_NEIGHBOUR}",
        f"pand_{_STRADDLER}",
    }

    # The straddler reached to x=1155 before the clip; an envelope capped
    # at the box's east edge proves it was cut there, not kept whole.
    bounded = getattr(model.xsd, _resolve_bounded_by_field())
    assert bounded.envelope.upper_corner.value[0] == pytest.approx(1150.0)

    # BuildingUnits for the panden whose VBOs the pipeline fetched.
    assert len(buildings[f"pand_{_TARGET_A}"].building_unit) == 1
    assert len(buildings[f"pand_{_NEIGHBOUR}"].building_unit) == 1
    assert buildings[f"pand_{_STRADDLER}"].building_unit == []

    # The gemeente name resolved from the geocode (not the empty config
    # municipality) supplies the address locality fallback.
    addr_details = buildings[f"pand_{_TARGET_A}"].address[0].address.xal_address.address_details
    locality_names = addr_details.country.locality.locality_name
    assert locality_names and locality_names[0].content == ["Leiden"]


def test_address_pipeline_paints_targets_apart_from_surroundings(
    tmp_path: Path, mocked_address_pipeline: dict
) -> None:
    model = build_city_model(_config(tmp_path))

    appearances = [m.appearance for m in model.xsd.appearance_member]
    themes = [a.theme for a in appearances]
    assert themes == [BUILDING_HIGHLIGHT_THEME]  # highlight painter, not energy-label

    materials = [p.x3_dmaterial for p in appearances[0].surface_data_member]
    assert len(materials) == 2
    surroundings_mat, target_mat = materials

    assert surroundings_mat.diffuse_color == pytest.approx(list(_SURROUNDINGS_COLOR))
    assert target_mat.diffuse_color == pytest.approx(list(_TARGET_COLOR))

    # Surface-container ids embed the pand id, so the partition of the
    # two target lists is checkable directly.
    assert target_mat.target
    assert all(_TARGET_A in ref for ref in target_mat.target)
    assert surroundings_mat.target
    assert all(_NEIGHBOUR in ref or _STRADDLER in ref for ref in surroundings_mat.target)
    assert any(_NEIGHBOUR in ref for ref in surroundings_mat.target)
    assert any(_STRADDLER in ref for ref in surroundings_mat.target)


def test_address_pipeline_warns_for_target_without_geometry(
    tmp_path: Path, mocked_address_pipeline: dict, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="citygml_energy.city_builder.painters"):
        build_city_model(_config(tmp_path))
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and record.name == "citygml_energy.city_builder.painters"
    ]
    assert any(_TARGET_B in message for message in warnings)
    assert not any(_TARGET_A in message for message in warnings)


def test_address_pipeline_output_validates_against_xsd(
    tmp_path: Path, mocked_address_pipeline: dict
) -> None:
    model = build_city_model(_config(tmp_path))
    schema = load_schema()
    schema.assertValid(etree.fromstring(model.to_string().encode("utf-8")))
