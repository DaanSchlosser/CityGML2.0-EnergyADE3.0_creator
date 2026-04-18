"""Unit tests for the XSD-agnostic auto-discovery paths in :mod:`.geometry`.

If someone accidentally re-introduces a hardcoded binding import, these
tests catch the regression because they exercise the discovery functions
directly against the generated bindings.
"""

from __future__ import annotations

from citygml_energy.bindings import Building, WallSurface2, WindowType2
from citygml_energy.geometry import (
    GEOMETRY_SOURCE_SPECS,
    SUPPORTED_GEOMETRY_SOURCE_TYPES,
    _discover_property_map,
    _discover_wrapper,
)

# ---------------------------------------------------------------------------
# _discover_wrapper
# ---------------------------------------------------------------------------


def test_discover_wrapper_returns_boundary_surface_property_type_for_building() -> None:
    wrapper = _discover_wrapper(Building, "bounded_by")
    assert wrapper is not None
    # xsdata dedup suffix — name is stable even if the "2" migrates.
    assert wrapper.__name__.startswith("BoundarySurfacePropertyType")


def test_discover_wrapper_returns_opening_property_type_for_surface() -> None:
    wrapper = _discover_wrapper(WallSurface2, "opening")
    assert wrapper is not None
    assert wrapper.__name__.startswith("OpeningPropertyType")


def test_discover_wrapper_returns_none_for_missing_list_field() -> None:
    # Building has no "definitely_absent" field.
    assert _discover_wrapper(Building, "definitely_absent") is None


def test_discover_wrapper_returns_none_for_non_list_field() -> None:
    # year_of_construction is scalar, not list[...].
    assert _discover_wrapper(Building, "year_of_construction") is None


# ---------------------------------------------------------------------------
# _discover_property_map
# ---------------------------------------------------------------------------


def test_property_map_covers_core_boundary_surfaces() -> None:
    wrapper = _discover_wrapper(Building, "bounded_by")
    assert wrapper is not None
    entries = _discover_property_map(wrapper)
    xsd_names = set(entries)
    # Every bldg:boundedBy member CityGML defines must be discovered.
    expected_bldg = {
        "WallSurface", "RoofSurface", "GroundSurface", "CeilingSurface",
        "FloorSurface", "OuterCeilingSurface", "OuterFloorSurface", "ClosureSurface",
    }
    missing = expected_bldg - xsd_names
    assert not missing, f"auto-discovery lost bldg surfaces: {sorted(missing)}"

    # Plus the Energy-ADE zone boundary surfaces share the wrapper.
    assert "ZoneWallSurface" in xsd_names
    assert "ZoneUndergroundWallSurface" in xsd_names


def test_property_map_entries_round_trip_name_and_field() -> None:
    wrapper = _discover_wrapper(Building, "bounded_by")
    assert wrapper is not None
    entries = _discover_property_map(wrapper)
    wall = entries["WallSurface"]
    # Meta.name matches the XSD element name.
    assert wall.xsd_name == "WallSurface"
    # Field name is the xsdata snake_case equivalent.
    assert wall.field_name == "wall_surface"
    # Element class is the concrete binding class.
    assert wall.element_cls is WallSurface2


def test_property_map_includes_opening_classes_on_surface_wrapper() -> None:
    wrapper = _discover_wrapper(WallSurface2, "opening")
    assert wrapper is not None
    entries = _discover_property_map(wrapper)
    assert "Door" in entries
    assert "Window" in entries


# ---------------------------------------------------------------------------
# GEOMETRY_SOURCE_SPECS
# ---------------------------------------------------------------------------


def test_supported_geometry_source_types_matches_spec_registry() -> None:
    assert frozenset(GEOMETRY_SOURCE_SPECS) == SUPPORTED_GEOMETRY_SOURCE_TYPES


def test_every_spec_has_a_resolvable_xsd_target_type() -> None:
    """Every target type string must resolve to an actual binding class.

    This guards against silently stale strings after a binding regeneration.
    """
    from citygml_energy.mapping import resolve_class

    for spec in GEOMETRY_SOURCE_SPECS.values():
        for field_name, target in spec.target_fields.items():
            resolved = resolve_class(target.xsd_type)
            assert resolved is not None, (
                f"{spec.source_type!r}.{field_name} → {target.xsd_type!r} did not resolve"
            )


def test_window_type_is_not_returned_as_opening_entry() -> None:
    """Type aliases (``WindowType*``) must not leak into the discovered map.

    They carry ``target_namespace`` but not ``namespace`` on Meta, so the
    filter in ``_discover_property_map`` should skip them.
    """
    wrapper = _discover_wrapper(WallSurface2, "opening")
    assert wrapper is not None
    entries = _discover_property_map(wrapper)
    assert all(entry.element_cls is not WindowType2 for entry in entries.values())


# ---------------------------------------------------------------------------
# XSD-agnosticism guard — verifies no schema-specific class leaks into imports
# ---------------------------------------------------------------------------


def test_geometry_module_does_not_import_schema_specific_classes() -> None:
    """Regression guard for the no-hardcoded-taxonomy principle.

    Geometry is allowed to import stable GML wire types (``Envelope``,
    ``CodeType``, ...) and abstract wrappers (``AbstractCityObjectPropertyType``,
    ``LayeredConstruction2``, ``RelatedTo``, ``CityObjectRelation``,
    ``BoundedBy``). Every concrete surface / opening / target class must
    come via :func:`citygml_energy.mapping.resolve_class` — if someone
    reintroduces ``from .bindings import WallSurface2`` this fails.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "citygml_energy" / "geometry.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("bindings"):
            imports.update(alias.name for alias in node.names)

    banned = {
        "Building",
        "BuildingPart",
        "BoundarySurfacePropertyType2",
        "CeilingSurface2",
        "ClosureSurface2",
        "Door2",
        "FloorSurface2",
        "GroundSurface2",
        "OpeningPropertyType2",
        "OuterCeilingSurface2",
        "OuterFloorSurface2",
        "PhotovoltaicCollector",
        "RoofSurface2",
        "WallSurface2",
        "Window2",
        "ZonePart",
    }
    leaks = imports & banned
    assert not leaks, (
        f"geometry.py re-imported schema-specific classes: {sorted(leaks)}. "
        f"Use citygml_energy.mapping.resolve_class(...) instead."
    )
