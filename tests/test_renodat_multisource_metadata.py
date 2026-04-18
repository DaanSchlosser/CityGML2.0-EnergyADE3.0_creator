"""Multi-source ``QualifiedArea`` round-trip + feature-level ``Metadata``.

The Energy-ADE 3.0 encoding for "same attribute reported by multiple
sources with different values" is a repeated element rather than a custom
wrapper (``nrg3:bdgArea`` is ``maxOccurs="unbounded"``, and each
``QualifiedArea`` carries its own ``description`` / ``source`` /
``value`` / ``type`` code via ``AbstractQualifiedAttributeType``). These
tests guard that the reference RenoDAT input exercises this encoding
correctly and that the build→serialize pipeline preserves the source and
value of each entry.

XSD validity of the full document is already covered by
``test_renodat_reference.py``; this file focuses on the multi-source
invariants an XSD cannot enforce: two entries with the same ``type`` but
different ``source`` and ``value`` must survive the round-trip.
"""

from __future__ import annotations

import lxml.etree as etree
import pytest

from citygml_energy import generate_city_model
from examples.create_renodat import INPUT

NS = {
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "core": "http://www.opengis.net/citygml/2.0",
    "gml": "http://www.opengis.net/gml",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
}


@pytest.fixture(scope="module")
def building():
    """Parsed ``bldg:Building`` element from the reference RenoDAT output."""
    model = generate_city_model(INPUT)
    root = etree.fromstring(model.to_string().encode("utf-8"))
    (bldg,) = root.findall("core:cityObjectMember/bldg:Building", NS)
    return bldg


def _qualified_areas_by_type(building: etree._Element, type_code: str) -> list:
    """All ``<nrg3:QualifiedArea>`` entries on *building* whose ``type`` matches."""
    return [
        area
        for area in building.findall("nrg3:bdgArea/nrg3:QualifiedArea", NS)
        if (t := area.find("nrg3:type", NS)) is not None and t.text == type_code
    ]


def test_diverging_gfa_entries_preserve_distinct_source_and_value(building):
    """Two ``grossFloorArea`` entries must round-trip with distinct source+value.

    This is the core multi-source claim: repeating the ``bdgArea`` element
    with the same ``type`` code but different sources is the correct
    encoding, and neither entry may collapse into the other during build
    or serialization.
    """
    gfa_entries = _qualified_areas_by_type(building, "grossFloorArea")
    assert len(gfa_entries) == 2

    pairs = [
        (
            entry.find("nrg3:source", NS).text,
            float(entry.find("nrg3:value", NS).text),
        )
        for entry in gfa_entries
    ]
    sources, values = zip(*pairs, strict=True)

    assert len(set(sources)) == 2, f"sources must differ, got {sources}"
    assert len(set(values)) == 2, f"values must differ, got {values}"
    assert sorted(values) == pytest.approx([119.6, 122.0])


def test_nfa_rides_in_its_own_bdg_area_entry(building):
    """``netFloorArea`` occupies a separate ``bdgArea`` per QualifiedAreaType."""
    nfa_entries = _qualified_areas_by_type(building, "netFloorArea")
    assert len(nfa_entries) == 1
    value = nfa_entries[0].find("nrg3:value", NS)
    assert value.get("uom") == "m2"
    assert float(value.text) == pytest.approx(104.2)


def test_qualified_area_type_code_carries_codespace(building):
    """The ``<nrg3:type>`` CodeType must serialize its ``@codeSpace``.

    A missing codeSpace would be silent data loss — validators accept it
    but the receiving toolchain cannot resolve the code to a vocabulary.
    """
    type_elems = building.findall("nrg3:bdgArea/nrg3:QualifiedArea/nrg3:type", NS)
    assert type_elems  # sanity
    for elem in type_elems:
        assert elem.get("codeSpace", "").endswith("AreaTypeValue.xml")


def test_feature_metadata_documents_the_divergence(building):
    """``nrg3:Metadata`` substitutes directly into ``gml:metaDataProperty``.

    Not into a ``<nrg3:metadata>`` wrapper — the XSD uses
    ``substitutionGroup="gml:metaDataProperty"`` on the ``<Metadata>``
    element declaration, so the element appears at top level on any
    gml:AbstractFeature. Guards the XPath shape plus the content that
    explains *why* the two GFA values diverge.
    """
    metas = building.findall("nrg3:Metadata", NS)
    assert len(metas) == 1, (
        "Metadata must appear as a direct child of Building (substitutes "
        "into gml:metaDataProperty), not inside a <nrg3:metadata> wrapper"
    )
    quality = metas[0].find("nrg3:qualityDescription", NS).text
    assert "BAG" in quality and "3D" in quality
