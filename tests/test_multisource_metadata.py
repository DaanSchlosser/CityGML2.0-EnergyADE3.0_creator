"""Multi-source ``QualifiedArea`` round-trip + feature-level ``Metadata``.

The Energy-ADE 3.0 encoding for "same attribute reported by multiple
sources with different values" is a repeated element rather than a custom
wrapper (``nrg3:bdgArea`` is ``maxOccurs="unbounded"``, and each
``QualifiedArea`` carries its own ``description`` / ``source`` /
``value`` / ``type`` code via ``AbstractQualifiedAttributeType``). These
tests guard that the reference-building input exercises this encoding
correctly and that the build->serialize pipeline preserves the source and
value of each entry.

XSD validity of the full document is already covered by
``test_reference_building.py``; this file focuses on the multi-source
invariants an XSD cannot enforce: two entries with the same ``type`` but
different ``source`` and ``value`` must survive the round-trip. Tests are
value-agnostic: the JSON's actual numeric areas and source names are
never pinned -- only that distinctness and structure are preserved.
"""

from __future__ import annotations

import lxml.etree as etree
import pytest

from citygml_energy import generate_city_model
from examples.create_building import INPUT

NS = {
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "core": "http://www.opengis.net/citygml/2.0",
    "gml": "http://www.opengis.net/gml",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
}

_SAMPLE_INPUT = INPUT.parent / "NL-single-family-house_sample.json"

_RENODAT_INPUTS = [INPUT]
if _SAMPLE_INPUT.exists():
    _RENODAT_INPUTS.append(_SAMPLE_INPUT)


@pytest.fixture(
    scope="module",
    params=_RENODAT_INPUTS,
    ids=[p.stem for p in _RENODAT_INPUTS],
)
def building(request):
    """Parsed ``bldg:Building`` element from an owner-occupier output."""
    model = generate_city_model(request.param)
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


def _unit_areas_by_type(building: etree._Element, type_code: str) -> list:
    """All ``<nrg3:QualifiedArea>`` on the BuildingUnit's ``nrg3:area`` slot."""
    return [
        area
        for area in building.findall(
            "nrg3:buildingUnit/nrg3:BuildingUnit/nrg3:area/nrg3:QualifiedArea", NS
        )
        if (t := area.find("nrg3:type", NS)) is not None and t.text == type_code
    ]


def test_diverging_nfa_entries_preserve_distinct_source_and_value(building):
    """Two ``netFloorArea`` entries must round-trip with distinct source+value.

    This is the core multi-source claim: repeating the qualified-area
    element with the same ``type`` code but different sources is the
    correct encoding, and neither entry may collapse into the other
    during build or serialization. The divergence exemplar is the
    BuildingUnit's usable area (BAG register vs measured model), since
    BAG ``oppervlakte`` is a verblijfsobject attribute. The specific
    numeric areas are not asserted -- only that both sides of the
    divergence survive.
    """
    nfa_entries = _unit_areas_by_type(building, "netFloorArea")
    assert len(nfa_entries) == 2

    pairs = [
        (
            entry.find("nrg3:source", NS).text,
            float(entry.find("nrg3:value", NS).text),
        )
        for entry in nfa_entries
    ]
    sources, values = zip(*pairs, strict=True)

    assert len(set(sources)) == 2, f"sources must differ, got {sources}"
    assert len(set(values)) == 2, f"values must differ, got {values}"
    for value in values:
        assert value > 0, f"area must be a positive magnitude, got {value}"
    for entry in nfa_entries:
        assert entry.find("nrg3:value", NS).get("uom") == "m2"


def test_nfa_lives_on_the_building_unit_not_the_building(building):
    """``netFloorArea`` belongs to the BuildingUnit's ``nrg3:area``, not the Building.

    Energy ADE 3.0 ``BuildingUnit`` extends ``AbstractCityObjectSpace``,
    which natively carries ``area`` (``QualifiedAreaPropertyType``,
    ``maxOccurs="unbounded"``). ``Building`` carries ``bdgArea`` only as
    an ADE extension on ``bldg:_AbstractBuilding``. BAG ``oppervlakte``
    is an attribute of the verblijfsobject (the NEN 2580
    gebruiksoppervlakte of that VBO; a Pand registers no area at all),
    so both the register value and its measured counterpart live on the
    BuildingUnit. The Building's ``bdgArea`` is reserved for whole-Pand
    totals: the single measured ``grossFloorArea``.
    """
    # The Building should carry no ``netFloorArea`` ``bdgArea`` entry.
    building_nfa = _qualified_areas_by_type(building, "netFloorArea")
    assert building_nfa == [], (
        "netFloorArea belongs on BuildingUnit/area (BAG oppervlakte is a "
        "verblijfsobject attribute); Building.bdgArea hosts only Pand-level totals"
    )

    # The Building carries exactly one Pand-level total: the measured
    # gross floor area (BAG registers no Pand-level area to diverge from).
    building_gfa = _qualified_areas_by_type(building, "grossFloorArea")
    assert len(building_gfa) == 1

    # The BuildingUnit carries the register + measured pair.
    nfa_entries = _unit_areas_by_type(building, "netFloorArea")
    assert len(nfa_entries) == 2
    for entry in nfa_entries:
        value = entry.find("nrg3:value", NS)
        assert value.get("uom") == "m2"
        assert float(value.text) > 0


def test_qualified_area_type_code_carries_codespace(building):
    """The ``<nrg3:type>`` CodeType must serialize its ``@codeSpace``.

    A missing codeSpace would be silent data loss: validators accept it
    but the receiving toolchain cannot resolve the code to a vocabulary.
    """
    type_elems = building.findall("nrg3:bdgArea/nrg3:QualifiedArea/nrg3:type", NS)
    assert type_elems  # sanity
    for elem in type_elems:
        assert elem.get("codeSpace", "").endswith("AreaTypeValue.xml")


def test_feature_metadata_documents_the_divergence(building):
    """``nrg3:Metadata`` substitutes directly into ``gml:metaDataProperty``.

    Not into a ``<nrg3:metadata>`` wrapper; the XSD uses
    ``substitutionGroup="gml:metaDataProperty"`` on the ``<Metadata>``
    element declaration, so the element appears at top level on any
    gml:AbstractFeature. Guards the XPath shape and that a non-empty
    ``qualityDescription`` survives; the specific narrative text is an
    input-level concern, not a pipeline invariant.
    """
    metas = building.findall("nrg3:Metadata", NS)
    assert len(metas) == 1, (
        "Metadata must appear as a direct child of Building (substitutes "
        "into gml:metaDataProperty), not inside a <nrg3:metadata> wrapper"
    )
    quality = metas[0].find("nrg3:qualityDescription", NS)
    assert quality is not None and quality.text and quality.text.strip()
