"""Tests for ``core:Address/multiPoint`` VBO-point attachment.

BAG's ``geometriePunt`` (a single 2D point in EPSG:28992 that locates
the verblijfsobject inside its parent Pand) is attached to
``core:Address`` via the XSD-sanctioned ``multiPoint`` element. These
tests assert both the in-memory dataclass shape and the serialised XML.
"""

from __future__ import annotations

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.builders import (
    attach_building_units_to_building,
    build_address,
    build_building,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject, _extract_point

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _vbo(point: tuple[float, float] | None) -> Verblijfsobject:
    return Verblijfsobject(
        identificatie="0503010000000042",
        pand_identificatie="0503100000000001",
        gebruiksdoel=["woonfunctie"],
        oppervlakte=85.0,
        status=None,
        postcode="2628CD",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam="Mekelweg",
        woonplaats=None,
        point=point,
        properties={},
    )


def _resolved(point: tuple[float, float] | None) -> ResolvedAddress:
    return ResolvedAddress(vbo=_vbo(point), energy_label=None)


def _parsed() -> ParsedBuilding:
    poly = SemanticPolygon(
        polygon=GeometryPolygon(
            exterior=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        ),
        surface_type="GroundSurface",
    )
    return ParsedBuilding(
        pand_id="0503100000000001",
        attributes={},
        geometries={"0": [poly]},
    )


# ---------------------------------------------------------------------------
# _extract_point (GeoJSON parser)
# ---------------------------------------------------------------------------


def test_extract_point_reads_geojson_point() -> None:
    assert _extract_point({"type": "Point", "coordinates": [85000.5, 446500.25]}) == (
        85000.5,
        446500.25,
    )


def test_extract_point_rejects_non_point_geometries() -> None:
    assert _extract_point({"type": "Polygon", "coordinates": [[[0, 0], [1, 0]]]}) is None
    assert _extract_point(None) is None
    assert _extract_point({"type": "Point"}) is None
    assert _extract_point({"type": "Point", "coordinates": [1.0]}) is None


# ---------------------------------------------------------------------------
# build_address: multiPoint attachment
# ---------------------------------------------------------------------------


def test_address_carries_multi_point_when_vbo_has_one() -> None:
    address = build_address(_resolved(point=(85000.0, 446500.0)))
    assert address is not None
    assert address.multi_point is not None

    mp = address.multi_point.multi_point
    assert mp.id.endswith("_mp")
    # Single point per VBO (one entrance-analogue).
    assert len(mp.point_member) == 1

    point = mp.point_member[0].point
    # 2D BAG point is padded to 3D so srsDimension matches the file CRS.
    assert point.pos.value == [85000.0, 446500.0, 0.0]


def test_address_has_no_multi_point_when_vbo_lacks_one() -> None:
    address = build_address(_resolved(point=None))
    assert address is not None
    assert address.multi_point is None


def test_multi_point_inherits_default_srs_name() -> None:
    address = build_address(_resolved(point=(85000.0, 446500.0)))
    assert address is not None
    assert address.multi_point is not None
    mp = address.multi_point.multi_point
    assert mp is not None
    # The compound RD-New + NAP CRS used by the rest of the file.
    assert mp.srs_name_attribute.startswith("urn:ogc:def:crs")
    assert mp.srs_dimension == 3


# ---------------------------------------------------------------------------
# BuildingUnit integration + serialisation
# ---------------------------------------------------------------------------


def test_building_unit_serialises_address_with_multi_point() -> None:
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved(point=(85000.0, 446500.0))])

    # Walk into the nested address dataclass to confirm the multi_point is
    # present on the attached Address (not just on the builder's output).
    unit = building.building_unit[0].building_unit
    address = unit.address[0].address
    assert address.multi_point is not None


def test_serialised_xml_contains_multi_point_with_pos() -> None:
    from citygml_energy.core import CityModel

    model = CityModel()
    building = build_building(_parsed())
    attach_building_units_to_building(building, [_resolved(point=(85000.0, 446500.0))])
    model.add(building)

    xml = model.to_string()
    # Opening tags of property-type wrappers carry xlink attributes
    # (``xlink:type="simple"``); match the prefix rather than the full tag.
    assert "<core:multiPoint" in xml
    assert "<gml:MultiPoint" in xml
    assert "<gml:pointMember" in xml
    assert "<gml:pos" in xml
    # BAG x=85000, y=446500 appear together in the pos payload.
    assert "85000.0 446500.0" in xml
