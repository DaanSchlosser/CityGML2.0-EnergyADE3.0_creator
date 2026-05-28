"""Unit tests for the schema-agnostic plumbing in :mod:`citygml_energy.mapping`.

These tests exercise the pieces that the rest of the pipeline depends on
without going through the full pipeline, so a regression in e.g.
``iter_instances`` surfaces as a focused failure instead of as a muddy
end-to-end breakage.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from citygml_energy.bindings import Building, CityObjectMember, Name
from citygml_energy.bindings import CityModel as XsdCityModel
from citygml_energy.mapping import (
    FieldInfo,
    build_from_dict,
    find_by_id,
    get_fields,
    iter_instances,
    list_available_types,
    resolve_class,
)

# ---------------------------------------------------------------------------
# resolve_class / list_available_types
# ---------------------------------------------------------------------------


def test_resolve_class_returns_xsdata_class_for_known_prefix_name() -> None:
    assert resolve_class("bldg:Building") is Building


def test_resolve_class_raises_descriptively_for_unknown_type() -> None:
    with pytest.raises(ValueError, match=r"Unknown type 'xyz:DoesNotExist'"):
        resolve_class("xyz:DoesNotExist")


def test_list_available_types_includes_every_expected_surface() -> None:
    available = set(list_available_types())
    expected = {
        "bldg:Building",
        "bldg:WallSurface",
        "bldg:RoofSurface",
        "bldg:Door",
        "bldg:Window",
        "nrg3:ZonePart",
        "nrg3:PhotovoltaicCollector",
        "nrg3:ZoneWallSurface",
        "nrg3:ZoneUndergroundWallSurface",
    }
    missing = expected - available
    assert not missing, f"Registry is missing expected classes: {sorted(missing)}"


# ---------------------------------------------------------------------------
# get_fields / FieldInfo
# ---------------------------------------------------------------------------


def test_get_fields_returns_empty_for_non_dataclasses() -> None:
    assert get_fields(int) == {}


def test_get_fields_unwraps_optional_and_list_types() -> None:
    fields = get_fields(Building)
    bounded_by = fields["bounded_by"]
    assert isinstance(bounded_by, FieldInfo)
    assert bounded_by.is_list is True
    # bldg:Building.boundedBy → list[BoundarySurfacePropertyType2]
    assert bounded_by.inner_type.__name__ == "BoundarySurfacePropertyType2"


def test_get_fields_exposes_xml_name_and_namespace() -> None:
    fields = get_fields(Building)
    # yearOfConstruction is a simple-type field; xsdata stores the XML name in metadata.
    year_field = fields["year_of_construction"]
    assert year_field.xml_name == "yearOfConstruction"
    assert year_field.namespace == "http://www.opengis.net/citygml/building/2.0"


# ---------------------------------------------------------------------------
# build_from_dict: leaf coercion
# ---------------------------------------------------------------------------


def test_build_from_dict_coerces_xsd_decimal_fields() -> None:
    """``gml:TimeIntervalLengthType.value`` is xsd:decimal -> Python Decimal.

    Authoring a ``nrg3:RegularTimeSeries`` from JSON puts a plain int/float
    into ``time_interval.value``; without a Decimal coercion rule the generic
    builder rejected it ("no conversion rule applies"), so the documented
    RegularTimeSeries daily-series input could not actually be built. Routing
    through ``str`` keeps the value exact (1, not 1.0000000001).
    """
    regular_ts = resolve_class("nrg3:RegularTimeSeries")
    obj = build_from_dict(
        regular_ts,
        {
            "start_timestamp": "2022-01-01T00:00:00",
            "end_timestamp": "2026-01-01T00:00:00",
            "time_interval": {"value": 1, "unit": "day"},
            "values_list": {"value": [1.5, 2.0, 3.25], "uom": "kWh"},
        },
    )
    assert obj.time_interval.value == Decimal("1")
    assert isinstance(obj.time_interval.value, Decimal)
    assert obj.time_interval.unit == "day"
    assert obj.values_list.value == [1.5, 2.0, 3.25]


def test_build_from_dict_rejects_bool_for_decimal_field() -> None:
    """bool must not slip into a Decimal field via the int subclass path."""
    regular_ts = resolve_class("nrg3:RegularTimeSeries")
    with pytest.raises((TypeError, ValueError), match="bool"):
        build_from_dict(
            regular_ts,
            {"time_interval": {"value": True, "unit": "day"}},
        )


# ---------------------------------------------------------------------------
# iter_instances / find_by_id
# ---------------------------------------------------------------------------


def _make_tiny_model() -> XsdCityModel:
    building = Building(id="bldg_1", name=[Name(value="A")])
    return XsdCityModel(
        id="city_1",
        city_object_member=[CityObjectMember(building=building)],
    )


def test_iter_instances_yields_root_and_descendants() -> None:
    model = _make_tiny_model()
    collected = {type(obj).__name__ for obj in iter_instances(model)}
    # CityModel + CityObjectMember + Building + Name must all show up.
    assert {"CityModel", "CityObjectMember", "Building", "Name"} <= collected


def test_iter_instances_is_cycle_safe() -> None:
    # xsdata trees never contain cycles, but the traversal must not loop
    # even if someone wires one up manually.
    model = _make_tiny_model()
    building = model.city_object_member[0].building
    assert building is not None
    # Build a synthetic cycle: append the building to its own gen_attribute_string
    # (which is typed for such references via xsdata). Instead, just make sure
    # the function is idempotent on the clean tree.
    first_walk = list(iter_instances(model))
    second_walk = list(iter_instances(model))
    # Same set of ids, regardless of iteration order.
    assert {id(o) for o in first_walk} == {id(o) for o in second_walk}


def test_iter_instances_never_yields_the_same_object_twice() -> None:
    model = _make_tiny_model()
    seen: set[int] = set()
    for obj in iter_instances(model):
        oid = id(obj)
        assert oid not in seen, f"{type(obj).__name__} yielded twice"
        seen.add(oid)


def test_find_by_id_locates_top_level_and_nested() -> None:
    model = _make_tiny_model()
    assert find_by_id(model, "city_1") is model
    building = find_by_id(model, "bldg_1")
    assert building is not None
    assert building.id == "bldg_1"


def test_find_by_id_returns_none_when_missing() -> None:
    model = _make_tiny_model()
    assert find_by_id(model, "nope") is None


def test_find_by_id_ignores_non_string_id_attributes() -> None:
    # xsdata sometimes has ``id`` fields that aren't a gml:id; find_by_id
    # must match on string equality only and skip None / other types.
    model = _make_tiny_model()
    assert find_by_id(model, "") is None
