"""A feature collection without ``geometry_sources`` builds a geometry-free document.

CityGML makes every geometry property optional, and the loader treats
``geometry_sources`` the same way, so the non-geometric feature tree
(building, building unit, zone, devices, occupants, resources, and the
construction/material libraries) must build and XSD-validate on its
own. The one thing a geometry-free input cannot carry is a
``related_to`` entry targeting a STEP surface name, because the
surface index those names resolve against is populated during geometry
import; targets that are feature ``gml_id`` values keep working.

The fixture derives the geometry-free input from the shareable sample
rather than shipping a third hand-maintained input: drop
``geometry_sources``, prune the surface-name relation targets, keep
everything else byte-identical.
"""

from __future__ import annotations

import json
from pathlib import Path

import lxml.etree as etree
import pytest

from citygml_energy import generate_city_model
from tools.validate_xsd import load_schema

NS = {
    "core": "http://www.opengis.net/citygml/2.0",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "gml": "http://www.opengis.net/gml",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
    "xlink": "http://www.w3.org/1999/xlink",
}

_SAMPLE_INPUT = (
    Path(__file__).resolve().parents[1]
    / "inputs"
    / "buildings"
    / "NL-single-family-house_sample.json"
)


@pytest.fixture(scope="module")
def xsd_schema():
    return load_schema()


@pytest.fixture(scope="module")
def geometry_free_root(tmp_path_factory):
    data = json.loads(_SAMPLE_INPUT.read_text(encoding="utf-8"))
    data.pop("geometry_sources")

    feature_ids = {
        feature["id"] for feature in data["features"] if isinstance(feature.get("id"), str)
    }
    for feature in data["features"]:
        related = feature.get("related_to")
        if not related:
            continue
        kept = [
            entry
            for entry in related
            if isinstance(entry.get("target"), str) and entry["target"] in feature_ids
        ]
        if kept:
            feature["related_to"] = kept
        else:
            del feature["related_to"]

    path = tmp_path_factory.mktemp("geometry_free") / "geometry-free.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    model = generate_city_model(path)
    return etree.fromstring(model.to_string().encode("utf-8"))


def test_geometry_free_document_validates_against_xsd(xsd_schema, geometry_free_root):
    """The geometry-free document is XSD-valid against the bundled schema set."""
    xsd_schema.assertValid(geometry_free_root)


def test_geometry_free_document_carries_no_coordinates(geometry_free_root):
    """No coordinate-bearing element and no STEP-derived surface survives."""
    for tag in ("posList", "pos", "coordinates"):
        assert geometry_free_root.findall(f".//{{{NS['gml']}}}{tag}") == []
    for tag in ("WallSurface", "RoofSurface", "GroundSurface", "Window", "Door"):
        assert geometry_free_root.findall(f".//{{{NS['bldg']}}}{tag}") == []
    for tag in (
        "ZoneWallSurface",
        "ZoneRoofSurface",
        "ZoneGroundSurface",
        "ZoneWindow",
        "ZoneDoor",
    ):
        assert geometry_free_root.findall(f".//{{{NS['nrg3']}}}{tag}") == []


def test_geometry_free_document_keeps_the_feature_tree(geometry_free_root):
    """The non-geometric tree survives intact, including id-targeted relations."""

    def count(prefix: str, tag: str) -> int:
        return len(geometry_free_root.findall(f".//{{{NS[prefix]}}}{tag}"))

    assert count("bldg", "Building") == 1
    assert count("nrg3", "BuildingUnit") == 1
    assert count("nrg3", "Zone") == 1
    assert count("nrg3", "ZonePart") == 2
    assert count("nrg3", "PhotovoltaicCollector") == 1
    assert count("nrg3", "LayeredConstruction") > 0
    assert count("nrg3", "ConstantValueSchedule") > 0

    pv = geometry_free_root.find(f".//{{{NS['nrg3']}}}PhotovoltaicCollector")
    relations = pv.findall(f".//{{{NS['nrg3']}}}CityObjectRelation")
    assert len(relations) == 1
    relation_type = relations[0].find(f"{{{NS['nrg3']}}}relationType")
    assert relation_type.text == "serving"
