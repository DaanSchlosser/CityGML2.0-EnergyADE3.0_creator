"""Phase 0 spike test: prove xsdata-generated classes serialize to XSD-valid XML.

Creates a Building inside a CityModel using the generated bindings, serializes
with xsdata's XmlSerializer, then validates the output against the full
CityGML 2.0 + Energy ADE 3.0 XSD schema set.
"""

from __future__ import annotations

import pytest
from lxml import etree
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from citygml_energy.bindings import (
    BoundedBy,
    Building,
    CityModel,
    CityObjectMember,
    CodeType,
    DirectPositionType,
    Envelope,
)
from tools.validate_xsd import load_schema

# ---------------------------------------------------------------------------
# Namespace prefix map (matches the project's existing convention)
# ---------------------------------------------------------------------------
NS_MAP = {
    "gml": "http://www.opengis.net/gml",
    "core": "http://www.opengis.net/citygml/2.0",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "xAL": "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def xsd_schema():
    return load_schema()


@pytest.fixture(scope="session")
def serializer():
    config = SerializerConfig(
        xml_declaration=True,
        encoding="UTF-8",
        indent="  ",
    )
    return XmlSerializer(config=config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_building_round_trip(xsd_schema, serializer):
    """A minimal Building in a CityModel must serialize to XSD-valid XML."""

    # -- Build a Building with a few fields --
    building = Building(
        id="bldg_001",
        class_value=CodeType(value="1000"),
        year_of_construction="2020",
    )

    # -- Wrap in CityModel with envelope --
    lower = DirectPositionType(value=[0.0, 0.0, 0.0], srs_dimension=3)
    upper = DirectPositionType(value=[10.0, 10.0, 10.0], srs_dimension=3)
    envelope = Envelope(
        lower_corner=lower,
        upper_corner=upper,
        srs_name="urn:ogc:def:crs:EPSG::28992",
        srs_dimension=3,
    )

    city_model = CityModel(
        id="cm_001",
        opengis_net_gml_bounded_by=BoundedBy(envelope=envelope),
        city_object_member=[
            CityObjectMember(building=building),
        ],
    )

    # -- Serialize --
    xml_str = serializer.render(city_model, ns_map=NS_MAP)

    # -- Parse and validate against XSD --
    doc = etree.fromstring(xml_str.encode("UTF-8"))
    xsd_schema.validate(doc)
    errors = [str(e) for e in xsd_schema.error_log]
    assert not errors, f"XSD validation errors:\n" + "\n".join(errors)


def test_building_has_expected_elements(serializer):
    """Verify the serialized XML contains the expected element structure."""

    building = Building(
        id="bldg_test",
        class_value=CodeType(value="1000"),
    )

    member = CityObjectMember(building=building)
    city_model = CityModel(
        id="cm_test",
        city_object_member=[member],
    )

    xml_str = serializer.render(city_model, ns_map=NS_MAP)
    doc = etree.fromstring(xml_str.encode("UTF-8"))

    ns = {
        "core": "http://www.opengis.net/citygml/2.0",
        "bldg": "http://www.opengis.net/citygml/building/2.0",
        "gml": "http://www.opengis.net/gml",
    }

    # CityModel root
    assert doc.tag == "{http://www.opengis.net/citygml/2.0}CityModel"

    # cityObjectMember > Building
    members = doc.findall("core:cityObjectMember", ns)
    assert len(members) == 1

    bldg = members[0].find("bldg:Building", ns)
    assert bldg is not None
    assert bldg.get("{http://www.opengis.net/gml}id") == "bldg_test"

    # class element
    cls = bldg.find("bldg:class", ns)
    assert cls is not None
    assert cls.text == "1000"
