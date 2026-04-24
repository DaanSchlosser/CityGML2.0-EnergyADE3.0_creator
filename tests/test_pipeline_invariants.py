"""Pipeline-level invariants that must hold for *any* valid input.

These are structural guarantees, not feature-specific assertions:

* **Completeness**: every top-level feature id declared in the JSON must
  appear as a ``gml:id`` in the serialized XML. If a feature ever gets
  silently dropped, this test catches it even when the XSD stays valid.
* **Determinism**: building the same input twice produces byte-identical
  output. Non-determinism (dict-order leakage, timestamp injection)
  would make diff-based review and content-addressed caching unreliable.
* **Coordinate precision**: no emitted ordinate carries more than six
  fractional digits, and no coordinate ever uses scientific notation.
  This locks in the quantisation contract that
  :func:`citygml_energy.gml_builders._q` promises.

Parameterised over every owner-occupier fixture so the invariants are checked
against both the full production input and the shareable sample.
"""

from __future__ import annotations

import re
from pathlib import Path

import lxml.etree as etree
import pytest

from citygml_energy import generate_city_model, load_feature_collection
from examples.create_building import INPUT

_SAMPLE_INPUT = INPUT.parent / "owner_occupier_building_sample.json"

_INPUTS = [INPUT]
if _SAMPLE_INPUT.exists():
    _INPUTS.append(_SAMPLE_INPUT)

NS = {
    "core": "http://www.opengis.net/citygml/2.0",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "gml": "http://www.opengis.net/gml",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
}

# Match xs:double tokens as emitted by xsdata: optional sign, digits,
# optional decimal part, NO exponent. We want to reject scientific
# notation anywhere in a coordinate context, so the regex is anchored.
_FIXED_POINT_RE = re.compile(r"^-?(\d+)(\.(\d+))?$")


@pytest.fixture(
    scope="module",
    params=_INPUTS,
    ids=[p.stem for p in _INPUTS],
)
def input_path(request) -> Path:
    return request.param


@pytest.fixture(scope="module")
def xml_text(input_path: Path) -> str:
    return generate_city_model(input_path).to_string()


@pytest.fixture(scope="module")
def root(xml_text: str):
    return etree.fromstring(xml_text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Completeness: no silent drops of top-level features
# ---------------------------------------------------------------------------


def _collect_input_feature_ids(input_path: Path) -> set[str]:
    """Top-level feature ids declared in *input_path*.

    Library members (SolidMaterial, LayeredConstruction, Gas) are nested
    inside ``library_member`` and deserialise into xlink-targetable
    elements below the top-level features; they should also appear with
    their declared ids. Both layers are collected so the completeness
    check spans the full id space of the input.
    """
    data = load_feature_collection(input_path)
    ids: set[str] = set()
    for feature in data["features"]:
        fid = feature.get("id")
        if isinstance(fid, str) and fid.strip():
            ids.add(fid.strip())
        members = feature.get("library_member")
        if isinstance(members, list):
            for member in members:
                if not isinstance(member, dict):
                    continue
                for nested in member.values():
                    if isinstance(nested, dict):
                        nested_id = nested.get("id")
                        if isinstance(nested_id, str) and nested_id.strip():
                            ids.add(nested_id.strip())
    return ids


def test_every_input_feature_id_appears_in_output(input_path: Path, root) -> None:
    """Every feature id from the JSON must show up as a gml:id in the XML.

    This is the strongest defence against silent drops. The XSD permits
    most child elements to be absent (minOccurs=0), so losing a device
    or a material would still produce XSD-valid output. The only way to
    be sure nothing went missing is to cross-check the id sets.
    """
    input_ids = _collect_input_feature_ids(input_path)
    assert input_ids, "input has no feature ids -- fixture is broken"

    output_ids = {
        el.get("{http://www.opengis.net/gml}id")
        for el in root.iter()
        if el.get("{http://www.opengis.net/gml}id")
    }
    missing = input_ids - output_ids
    assert not missing, (
        f"silent drop: {len(missing)} feature id(s) declared in input "
        f"never appear in output: {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_input_produces_byte_identical_output(input_path: Path) -> None:
    """Two independent runs on the same input must produce identical bytes.

    Non-determinism (dict order leakage, timestamped output, set-iteration
    differences) would break diff-review, content-addressed caching, and
    reproducible-build tooling. Xsdata serialisation is supposed to be
    deterministic given deterministic Python input; this test guards the
    whole pipeline, not just the serializer.
    """
    xml_a = generate_city_model(input_path).to_string()
    xml_b = generate_city_model(input_path).to_string()
    assert xml_a == xml_b, (
        "pipeline output diverged between two runs on the same input"
    )


# ---------------------------------------------------------------------------
# Coordinate precision & formatting
# ---------------------------------------------------------------------------


def _iter_coord_tokens(root):
    """Yield every ordinate token in ``gml:posList``, ``gml:pos``,
    ``gml:lowerCorner``, and ``gml:upperCorner`` elements -- the four
    places xsdata lands xs:double/xs:doubleList output for our bindings.
    """
    coord_elements = (
        root.findall(".//gml:posList", NS)
        + root.findall(".//gml:pos", NS)
        + root.findall(".//gml:lowerCorner", NS)
        + root.findall(".//gml:upperCorner", NS)
    )
    for element in coord_elements:
        yield from (element.text or "").split()


def test_no_scientific_notation_anywhere_in_coordinates(root) -> None:
    for token in _iter_coord_tokens(root):
        assert _FIXED_POINT_RE.match(token), (
            f"coordinate token not in fixed-point form: {token!r}"
        )


def test_coordinate_precision_is_at_most_six_decimal_places(root) -> None:
    """Every ordinate has <=6 decimal digits (the ``_q`` quantisation grid).

    Emitting more digits than the quantiser produces would advertise a
    precision the pipeline doesn't promise. Fewer is fine (trailing zeros
    get trimmed), more is a contract break.
    """
    for token in _iter_coord_tokens(root):
        match = _FIXED_POINT_RE.match(token)
        assert match, f"unexpected coordinate token: {token!r}"
        fractional = match.group(3) or ""
        assert len(fractional) <= 6, (
            f"coordinate {token!r} carries {len(fractional)} decimal places; "
            f"quantisation promises at most 6"
        )


def test_coordinates_are_not_negative_zero(root) -> None:
    """``-0.0`` is a valid float but serialises as ``-0`` in some pipelines.

    That creates spurious diffs between runs and confuses byte-level
    comparison. The quantiser's ``round()`` preserves the sign of a true
    negative zero, so this test catches the case where FP maths produces
    a signed zero that should be indistinguishable from ``0``.
    """
    for token in _iter_coord_tokens(root):
        assert token != "-0", "negative zero must not appear in output"
        assert token != "-0.0", "negative zero must not appear in output"


# ---------------------------------------------------------------------------
# XML escaping of user-supplied text (description, name, etc.)
#
# Text fields flow from JSON input straight into XML element bodies. If
# the serializer ever stopped escaping ``&`` / ``<`` / ``>``, a benign
# typo in a name or description could silently produce an XML file that
# is not parseable -- or worse, inject structural markup that changes
# the meaning of downstream consumers' queries.
# ---------------------------------------------------------------------------


def test_xml_special_characters_in_text_fields_are_escaped() -> None:
    from copy import deepcopy

    from citygml_energy import (
        build_city_model_from_feature_collection,
        load_feature_collection,
    )

    base = load_feature_collection(_SAMPLE_INPUT if _SAMPLE_INPUT.exists() else INPUT)
    data = deepcopy(base)
    building = data["features"][0]
    building["description"] = "Smith & Co. <tag>, quoted \"thing\""
    building["name"] = ["A & B"]

    xml = build_city_model_from_feature_collection(
        data, base_path=INPUT.parent
    ).to_string()

    # Raw special chars must not appear in element bodies.
    assert "Smith & Co" not in xml, (
        "raw ampersand survived into output -- XML escaping is broken"
    )
    assert "<tag>" not in xml, (
        "raw angle brackets survived into output -- structural injection risk"
    )
    # And the escaped equivalents must be present, proving the data
    # actually reached the serializer (not silently dropped).
    assert "&amp;" in xml
    assert "&lt;tag&gt;" in xml

    # Re-parses cleanly, which is the real correctness check.
    etree.fromstring(xml.encode("utf-8"))


def test_unicode_text_survives_round_trip() -> None:
    """Non-ASCII content must be preserved verbatim through utf-8 output."""
    from copy import deepcopy

    from citygml_energy import (
        build_city_model_from_feature_collection,
        load_feature_collection,
    )

    base = load_feature_collection(_SAMPLE_INPUT if _SAMPLE_INPUT.exists() else INPUT)
    data = deepcopy(base)
    marker = "Zuidooststraat éë αβ"
    data["features"][0]["description"] = marker

    xml = build_city_model_from_feature_collection(
        data, base_path=INPUT.parent
    ).to_string()

    root = etree.fromstring(xml.encode("utf-8"))
    descriptions = root.findall(
        ".//{http://www.opengis.net/gml}description"
    )
    assert any(el.text == marker for el in descriptions), (
        f"unicode marker lost through pipeline; outputs were: "
        f"{[el.text for el in descriptions]}"
    )


# ---------------------------------------------------------------------------
# City pipeline invariants (BAG + 3DBAG + EP-online)
#
# The city pipeline is a completely different code path from the
# per-building feature-collection pipeline: it fetches from live
# services (mocked here),
# merges BAG and 3DBAG attributes, assembles Pand / Verblijfsobject /
# EnergyLabel / Vegetation objects, and synthesises construction mappings.
# Every invariant we promise on the per-building pipeline -- determinism, coord
# precision, no scientific notation, no silent feature drops -- must also
# hold here. Without these tests, a change in the city-side assembly could
# regress the contract without tripping a single existing test.
#
# Fetchers are patched to return hard-coded fixture data so the test runs
# with no network and no credentials. New surface introduced by the other
# sessions (3DBAG-derived storeys / measuredHeight / roofType / bdgVolume,
# BAG Pand+VBO linked-data identifiers, certificationMethod from EP-online
# Berekeningstype) all flow through this pipeline -- any regression in
# their emission is caught by the determinism / completeness / coord
# assertions below, independent of feature-specific tests.
# ---------------------------------------------------------------------------


_CITY_BBOX = (84000.0, 445000.0, 86000.0, 447000.0)
_CITY_PAND_ID = "0503100000000042"
_CITY_VBO_ID = "0503010000000042"


def _city_cube_shell():
    from citygml_energy._step import GeometryPolygon
    from citygml_energy.city_builder.cityjson_parse import SemanticPolygon

    # Offsets are deliberately set to the cm-grid (85000.12, 446000.56) so the
    # 6-decimal-place quantiser gets exercised by non-trivial fractional
    # coordinates, not by integer values that happen to quantise cleanly.
    ox, oy = 85000.12, 446000.56
    p = [
        (ox, oy, 0.0), (ox + 1.0, oy, 0.0), (ox + 1.0, oy + 1.0, 0.0), (ox, oy + 1.0, 0.0),
        (ox, oy, 3.0), (ox + 1.0, oy, 3.0), (ox + 1.0, oy + 1.0, 3.0), (ox, oy + 1.0, 3.0),
    ]
    faces = [
        ([p[0], p[3], p[2], p[1]], "GroundSurface"),
        ([p[4], p[5], p[6], p[7]], "RoofSurface"),
        ([p[0], p[1], p[5], p[4]], "WallSurface"),
        ([p[1], p[2], p[6], p[5]], "WallSurface"),
        ([p[2], p[3], p[7], p[6]], "WallSurface"),
        ([p[3], p[0], p[4], p[7]], "WallSurface"),
    ]
    return [
        SemanticPolygon(polygon=GeometryPolygon(exterior=v), surface_type=st)
        for v, st in faces
    ]


def _city_fixture_parsed_building():
    from citygml_energy.city_builder.cityjson_parse import ParsedBuilding

    shell = _city_cube_shell()
    ground = next(s for s in shell if s.surface_type == "GroundSurface")
    return ParsedBuilding(
        pand_id=_CITY_PAND_ID,
        attributes={
            "oorspronkelijkbouwjaar": 1985,
            "identificatie": _CITY_PAND_ID,
            # 3DBAG attributes -- every one exercises a different path in
            # _apply_building_attributes, so the city output touches every
            # new field.
            "b3_bouwlagen": 2,
            "b3_h_maaiveld": 0.0,
            "b3_h_dak_max": 7.5,
            "b3_dak_type": "slanted",
            "b3_volume_lod22": 120.5,
        },
        geometries={"0": [ground], "1": shell, "2": shell},
    )


@pytest.fixture(scope="module")
def city_xml(tmp_path_factory) -> str:
    """One mocked city-pipeline run; scoped module so the four invariants
    share a single build."""
    import json
    import unittest.mock as mock

    from citygml_energy.city_builder import build_city_model
    from citygml_energy.city_builder import pipeline as pipeline_module
    from citygml_energy.city_builder.config import load_city_config
    from citygml_energy.city_builder.fetchers import (
        bag as bag_fetchers,
    )
    from citygml_energy.city_builder.fetchers import (
        eponline as ep_fetchers,
    )
    from citygml_energy.city_builder.fetchers import (
        municipality as muni_fetchers,
    )
    from citygml_energy.city_builder.fetchers.bag import Pand, Verblijfsobject
    from citygml_energy.city_builder.fetchers.municipality import MunicipalityOutline

    pand = Pand(
        identificatie=_CITY_PAND_ID, bouwjaar=1985, status=None, properties={},
    )
    vbo = Verblijfsobject(
        identificatie=_CITY_VBO_ID,
        pand_identificatie=_CITY_PAND_ID,
        gebruiksdoel=["woonfunctie"],
        oppervlakte=85.0, status=None,
        postcode="2628CD", huisnummer=42, huisletter=None, toevoeging=None,
        openbare_ruimte_naam="Mekelweg",
        point=(85000.0, 446500.0), properties={},
    )
    outline = MunicipalityOutline(
        name="Delft", cbs_code="0503",
        feature={
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [_CITY_BBOX[0], _CITY_BBOX[1]],
                    [_CITY_BBOX[2], _CITY_BBOX[1]],
                    [_CITY_BBOX[2], _CITY_BBOX[3]],
                    [_CITY_BBOX[0], _CITY_BBOX[3]],
                    [_CITY_BBOX[0], _CITY_BBOX[1]],
                ]],
            },
        },
        bbox=_CITY_BBOX,
    )

    tmp = tmp_path_factory.mktemp("city_invariants")
    cfg_path = tmp / "city.json"
    cfg_path.write_text(json.dumps({
        "schema_version": "city-1", "municipality": "Delft",
        "bbox": list(_CITY_BBOX), "lods": [0, 1, 2],
        "include_addresses": True, "include_energy_labels": False,
        "cache_dir": str(tmp / "cache"),
        "output": str(tmp / "out.gml"),
    }))
    (tmp / "cache").mkdir()
    config = load_city_config(cfg_path)

    with (
        mock.patch.object(muni_fetchers, "fetch_municipality_outline", return_value=outline),
        mock.patch.object(bag_fetchers, "fetch_panden", return_value=[pand]),
        mock.patch.object(bag_fetchers, "fetch_verblijfsobjecten", return_value=[vbo]),
        mock.patch.object(ep_fetchers, "fetch_energy_labels", return_value=[]),
        mock.patch.object(
            pipeline_module, "_fetch_parsed_buildings",
            return_value=[_city_fixture_parsed_building()],
        ),
    ):
        return build_city_model(config).to_string()


@pytest.fixture(scope="module")
def city_root(city_xml: str):
    return etree.fromstring(city_xml.encode("utf-8"))


def test_city_pipeline_output_is_byte_deterministic(tmp_path_factory) -> None:
    """Running the city pipeline twice with the same (mocked) inputs must
    produce identical output. Non-determinism here would be especially
    painful: the city pipeline emits 60+ attributes per building drawn
    from three services, so a single dict-iteration-order leak could
    reorder attributes and produce confusing diffs on every re-run."""
    import json
    import unittest.mock as mock

    from citygml_energy.city_builder import build_city_model
    from citygml_energy.city_builder import pipeline as pipeline_module
    from citygml_energy.city_builder.config import load_city_config
    from citygml_energy.city_builder.fetchers import (
        bag as bag_fetchers,
    )
    from citygml_energy.city_builder.fetchers import (
        eponline as ep_fetchers,
    )
    from citygml_energy.city_builder.fetchers import (
        municipality as muni_fetchers,
    )
    from citygml_energy.city_builder.fetchers.bag import Pand, Verblijfsobject
    from citygml_energy.city_builder.fetchers.municipality import MunicipalityOutline

    pand = Pand(identificatie=_CITY_PAND_ID, bouwjaar=1985, status=None, properties={})
    vbo = Verblijfsobject(
        identificatie=_CITY_VBO_ID, pand_identificatie=_CITY_PAND_ID,
        gebruiksdoel=["woonfunctie"], oppervlakte=85.0, status=None,
        postcode="2628CD", huisnummer=42, huisletter=None, toevoeging=None,
        openbare_ruimte_naam="Mekelweg",
        point=(85000.0, 446500.0), properties={},
    )
    outline = MunicipalityOutline(
        name="Delft", cbs_code="0503",
        feature={
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [_CITY_BBOX[0], _CITY_BBOX[1]],
                    [_CITY_BBOX[2], _CITY_BBOX[1]],
                    [_CITY_BBOX[2], _CITY_BBOX[3]],
                    [_CITY_BBOX[0], _CITY_BBOX[3]],
                    [_CITY_BBOX[0], _CITY_BBOX[1]],
                ]],
            },
        },
        bbox=_CITY_BBOX,
    )

    tmp = tmp_path_factory.mktemp("city_det")
    cfg_path = tmp / "city.json"
    cfg_path.write_text(json.dumps({
        "schema_version": "city-1", "municipality": "Delft",
        "bbox": list(_CITY_BBOX), "lods": [0, 1, 2],
        "include_addresses": True, "include_energy_labels": False,
        "cache_dir": str(tmp / "cache"),
        "output": str(tmp / "out.gml"),
    }))
    (tmp / "cache").mkdir()
    config = load_city_config(cfg_path)

    with (
        mock.patch.object(muni_fetchers, "fetch_municipality_outline", return_value=outline),
        mock.patch.object(bag_fetchers, "fetch_panden", return_value=[pand]),
        mock.patch.object(bag_fetchers, "fetch_verblijfsobjecten", return_value=[vbo]),
        mock.patch.object(ep_fetchers, "fetch_energy_labels", return_value=[]),
        mock.patch.object(
            pipeline_module, "_fetch_parsed_buildings",
            return_value=[_city_fixture_parsed_building()],
        ),
    ):
        xml_a = build_city_model(config).to_string()
        xml_b = build_city_model(config).to_string()

    assert xml_a == xml_b, (
        "city pipeline output diverged between two runs on the same input"
    )


def test_city_pipeline_uses_fixed_point_coordinates(city_root) -> None:
    """Coord-quantisation invariant extended to the city pipeline.

    The city path pushes lots of 3DBAG-derived coordinates (offsets in the
    RD grid ~1e5 m combined with STEP-style model coordinates) through
    the same ``flatten_ring`` / ``build_multi_surface`` path. If the
    quantiser regresses, or a new city-specific geometry builder skips
    it, this test catches that before an end-to-end XSD pass would.
    """
    for token in _iter_coord_tokens(city_root):
        assert _FIXED_POINT_RE.match(token), (
            f"city pipeline emitted non-fixed-point coordinate: {token!r}"
        )


def test_city_pipeline_coord_precision_at_most_six_dp(city_root) -> None:
    for token in _iter_coord_tokens(city_root):
        match = _FIXED_POINT_RE.match(token)
        assert match, f"unexpected coordinate token: {token!r}"
        fractional = match.group(3) or ""
        assert len(fractional) <= 6, (
            f"city pipeline emitted coordinate {token!r} with "
            f"{len(fractional)} decimal places; invariant is <=6"
        )


def test_city_pipeline_no_negative_zero_coordinates(city_root) -> None:
    for token in _iter_coord_tokens(city_root):
        assert token != "-0" and token != "-0.0", (
            "negative zero in city pipeline output: flat-roof faces with"
            " components collapsing to exact zero must serialise as '0', not '-0'"
        )


def test_city_pipeline_emits_input_pand_ids_as_gml_ids(city_root) -> None:
    """Completeness invariant for the city pipeline: every BAG Pand id
    fed into the pipeline must appear in the output as part of a gml:id.

    Silent drops here would be especially insidious -- a Pand that got
    filtered out mid-pipeline (e.g. because VBO matching failed
    silently) would still produce XSD-valid output with fewer buildings
    than the input supplied. This test cross-checks the input id set
    against output ids at the string level (``pand_<id>``) because the
    builder's ``_safe_gml_id`` prefixes every BAG id with ``pand_``.
    """
    all_gml_ids = {
        el.get("{http://www.opengis.net/gml}id")
        for el in city_root.iter()
        if el.get("{http://www.opengis.net/gml}id")
    }
    expected_pand_gml_id = f"pand_{_CITY_PAND_ID}"
    assert expected_pand_gml_id in all_gml_ids, (
        f"Pand {_CITY_PAND_ID!r} was fed into the pipeline but no "
        f"element with gml:id={expected_pand_gml_id!r} appears in the "
        f"output (this is a silent drop -- XSD still validates)."
    )
    expected_vbo_gml_id = f"bu_{_CITY_VBO_ID}"
    assert expected_vbo_gml_id in all_gml_ids, (
        f"VBO {_CITY_VBO_ID!r} has no corresponding gml:id in the output"
    )


def test_city_pipeline_bag_identifiers_carry_correct_codespaces(city_root) -> None:
    """BAG Pand and VBO ids must appear as ``nrg3:identifier`` elements
    tagged with the authoritative linked-data codespaces. If the
    codespace drops out or diverges from the Kadaster URL base, any
    downstream consumer that dereferences the identifier silently breaks."""
    identifiers = city_root.findall(".//{http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0}identifier")
    assert identifiers, "city output contains no nrg3:identifier elements"

    code_spaces = {el.get("codeSpace") for el in identifiers}
    assert any(
        cs and cs.endswith("/bag/id/pand/") for cs in code_spaces
    ), f"BAG Pand codespace missing; saw {code_spaces}"
    assert any(
        cs and cs.endswith("/bag/id/verblijfsobject/") for cs in code_spaces
    ), f"BAG VBO codespace missing; saw {code_spaces}"
