"""Tests for the unit-of-measure vocabulary (:mod:`citygml_energy.units`).

Three layers of protection:

1. **Vocabulary ↔ catalog sync**: every token the pipelines emit, and
   every spelling the read-side factor maps accept, must resolve in the
   bundled KITModelViewer ``Data/UOMList.xml`` (as ``UOM/@id`` or
   ``altId``). This is the same registry the H6 output audit checks, so
   a token added here without a catalog entry fails the suite instead
   of surfacing as a raw-token rendering in the viewer.
2. **:func:`measure_value` semantics**: SI normalisation, catalog-alias
   acceptance, and the warn-and-skip contract for unknown tokens. The
   stakes: ``mm`` / ``cm`` / ``kJ/(kg*K)`` are themselves valid catalog
   tokens, so a mislabelled input passes the output audit; only this
   read-side check can catch it.
3. **Construction-reduction integration**: the one place in the package
   where units participate in arithmetic
   (:func:`citygml_energy.boundary_attributes._reduce_construction`)
   must produce identical physics for equivalent declarations and omit
   what it cannot trust.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from citygml_energy.boundary_attributes import _reduce_construction
from citygml_energy.mapping import build_from_dict, resolve_class
from citygml_energy.units import (
    DENSITY,
    EMITTED_UOM_TOKENS,
    LENGTH,
    REGISTERED_UOM_TOKENS,
    SPECIFIC_HEAT_CAPACITY,
    measure_value,
)

# ---------------------------------------------------------------------------
# Vocabulary <-> UOMList.xml sync
# ---------------------------------------------------------------------------


def _uomlist_tokens() -> frozenset[str] | None:
    """Every ``id`` + ``altId`` from the bundled KIT UOMList, or ``None``."""
    import xml.etree.ElementTree as ET

    repo_root = Path(__file__).resolve().parent.parent
    matches = sorted(repo_root.glob("KITModelViewer_V*/Data/UOMList.xml"))
    if not matches:
        return None
    tokens: set[str] = set()
    for uom in ET.parse(matches[0]).iterfind(".//UOM"):
        uom_id = uom.get("id")
        if uom_id:
            tokens.add(uom_id)
        for alt in uom.iterfind("altId"):
            if alt.text:
                tokens.add(alt.text.strip())
    return frozenset(tokens)


def test_every_emitted_token_is_registered_in_the_kit_catalog() -> None:
    """An unregistered emitted token renders as a raw string in the
    viewer's Properties panel; the vocabulary promises registration."""
    known = _uomlist_tokens()
    if known is None:
        pytest.skip("KITModelViewer UOMList.xml not present in this checkout")
    missing = EMITTED_UOM_TOKENS - known
    assert not missing, f"emitted uom tokens missing from UOMList.xml: {sorted(missing)}"


def test_every_accepted_read_side_spelling_is_registered_in_the_kit_catalog() -> None:
    """The factor maps promise to mirror the catalog's alias structure:
    keys outside the catalog would accept tokens the H6 audit rejects."""
    known = _uomlist_tokens()
    if known is None:
        pytest.skip("KITModelViewer UOMList.xml not present in this checkout")
    for quantity in (LENGTH, DENSITY, SPECIFIC_HEAT_CAPACITY):
        missing = set(quantity.factors) - known
        assert not missing, (
            f"{quantity.name} factor-map keys missing from UOMList.xml: {sorted(missing)}"
        )


def test_registered_uom_tokens_mirror_the_kit_catalog_exactly() -> None:
    """The loader gate (REGISTERED_UOM_TOKENS) is a verbatim catalog
    mirror; set equality means neither side can drift silently: a new
    UOMList entry must be mirrored, a mirror entry must exist upstream."""
    known = _uomlist_tokens()
    if known is None:
        pytest.skip("KITModelViewer UOMList.xml not present in this checkout")
    assert known == REGISTERED_UOM_TOKENS, (
        f"missing from mirror: {sorted(known - REGISTERED_UOM_TOKENS)}; "
        f"stale in mirror: {sorted(REGISTERED_UOM_TOKENS - known)}"
    )


def test_emitted_tokens_are_a_subset_of_the_registered_mirror() -> None:
    """What the pipelines write must pass the gate the loader applies."""
    assert EMITTED_UOM_TOKENS <= REGISTERED_UOM_TOKENS


def test_quantity_si_bases_are_the_identity_factor() -> None:
    for quantity in (LENGTH, DENSITY, SPECIFIC_HEAT_CAPACITY):
        assert quantity.factors[quantity.si_uom] == 1.0


# ---------------------------------------------------------------------------
# measure_value
# ---------------------------------------------------------------------------


def _measure(value: Any, uom: Any) -> SimpleNamespace:
    """Duck-typed stand-in for the xsdata gml:MeasureType classes."""
    return SimpleNamespace(value=value, uom=uom)


def test_measure_value_si_token_is_identity() -> None:
    assert measure_value(_measure(0.2, "m"), LENGTH) == 0.2


def test_measure_value_converts_registered_submultiples() -> None:
    assert measure_value(_measure(200, "mm"), LENGTH) == pytest.approx(0.2)
    assert measure_value(_measure(20, "cm"), LENGTH) == pytest.approx(0.2)
    assert measure_value(_measure(2_000_000.0, "g/m3"), DENSITY) == pytest.approx(2000.0)


def test_measure_value_accepts_every_catalog_alias_of_one_entry() -> None:
    """``J/(kg*K)`` and ``J/(K*kg)`` are altIds of one catalog entry;
    rejecting one spelling would refuse values the catalog itself calls
    well-labelled."""
    for token in ("J/(kg*K)", "J/(K*kg)", "jkg-1k-1"):
        assert measure_value(_measure(840.0, token), SPECIFIC_HEAT_CAPACITY) == 840.0
    for token in ("kJ/(kg*K)", "kJ/(K*kg)", "kjkg-1k-1"):
        assert measure_value(_measure(0.84, token), SPECIFIC_HEAT_CAPACITY) == pytest.approx(840.0)


def test_measure_value_tolerates_whitespace_padded_tokens() -> None:
    assert measure_value(_measure(0.2, " m "), LENGTH) == 0.2


def test_measure_value_rejects_unknown_token_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unrecognised token must not enter arithmetic: warn (naming the
    context, the quantity, and the accepted spellings) and return None."""
    with caplog.at_level(logging.WARNING, logger="citygml_energy.units"):
        result = measure_value(_measure(0.2, "ft"), LENGTH, context="layer 'L1'")
    assert result is None
    assert "layer 'L1'" in caplog.text
    assert "'ft'" in caplog.text
    assert "length" in caplog.text
    assert "mm" in caplog.text  # the accepted spellings are listed


def test_measure_value_rejects_missing_uom_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The XSD requires @uom on every measure, so a missing token only
    arises on hand-built objects; it is still not trusted into physics."""
    with caplog.at_level(logging.WARNING, logger="citygml_energy.units"):
        assert measure_value(_measure(0.2, None), LENGTH) is None
        assert measure_value(_measure(0.2, "   "), LENGTH) is None
    assert caplog.text.count("skipping the value") == 2


def test_measure_value_is_silent_on_absent_or_malformed_measures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``None`` measures (a Gas material has no density) and non-numeric
    values are normal/malformed rather than mislabelled: no warning."""
    with caplog.at_level(logging.WARNING, logger="citygml_energy.units"):
        assert measure_value(None, LENGTH) is None
        assert measure_value(_measure(None, "m"), LENGTH) is None
        assert measure_value(_measure("0.2", "m"), LENGTH) is None
        assert measure_value(_measure(True, "m"), LENGTH) is None
    assert caplog.text == ""


# ---------------------------------------------------------------------------
# Construction-reduction integration
# ---------------------------------------------------------------------------


def _solid_material(
    *,
    density: float = 2000.0,
    density_uom: str = "kg/m3",
    cp: float = 840.0,
    cp_uom: str = "J/(K*kg)",
) -> dict[str, Any]:
    return {
        "solid_material": {
            "id": "mat_test",
            "type_value": "brick",
            "is_transparent": False,
            "density": {"value": density, "uom": density_uom},
            "specific_heat_capacity": {"value": cp, "uom": cp_uom},
        }
    }


def _make_construction(layers: list[dict[str, Any]]) -> Any:
    return build_from_dict(
        resolve_class("nrg3:LayeredConstruction"),
        {
            "id": "constr_test",
            "type_value": "outerWall",
            "u_value": {"value": 0.25, "uom": "W/(m2*K)"},
            "layer": layers,
        },
    )


def _layer(thickness: float, uom: str, material: dict[str, Any]) -> dict[str, Any]:
    return {
        "layer": {
            "id": f"L_{uom.replace('/', '_')}",
            "thickness": {"value": thickness, "uom": uom},
            "material": material,
        }
    }


def test_reduction_si_baseline() -> None:
    """0.2 m of 2000 kg/m³ at 840 J/(kg·K) is 336 kJ/(K·m²)."""
    info = _reduce_construction(
        _make_construction([_layer(0.2, "m", _solid_material())]),
        {},
    )
    assert info.thickness_m == pytest.approx(0.2)
    assert info.heat_capacity_kj_per_k_m2 == pytest.approx(336.0)


def test_reduction_normalises_mm_thickness_and_kj_heat_capacity() -> None:
    """The datasheet spelling (200 mm, 0.84 kJ/(kg·K)) must produce the
    same physics as the SI spelling. Before read-side normalisation this
    construction shipped ``bdgBdrySurfThickness`` of 200 "m" and a heat
    capacity 1000x off, and the H6 output audit could not object because
    ``mm`` and ``kJ/(kg*K)`` are valid catalog tokens."""
    info = _reduce_construction(
        _make_construction(
            [_layer(200, "mm", _solid_material(cp=0.84, cp_uom="kJ/(kg*K)"))],
        ),
        {},
    )
    assert info.thickness_m == pytest.approx(0.2)
    assert info.heat_capacity_kj_per_k_m2 == pytest.approx(336.0)


def test_reduction_skips_layer_with_unknown_thickness_unit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A layer whose thickness unit is unrecognised contributes to
    neither sum; the remaining layers still produce honest totals."""
    with caplog.at_level(logging.WARNING, logger="citygml_energy.units"):
        info = _reduce_construction(
            _make_construction(
                [
                    _layer(0.1, "m", _solid_material(density=1000.0, cp=1000.0)),
                    _layer(0.5, "ft", _solid_material()),
                ],
            ),
            {},
        )
    assert info.thickness_m == pytest.approx(0.1)
    assert info.heat_capacity_kj_per_k_m2 == pytest.approx(100.0)
    assert "'ft'" in caplog.text
    assert "constr_test" in caplog.text


def test_reduction_keeps_thickness_when_only_the_material_units_are_unknown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unrecognised density unit poisons only the heat capacity: the
    layer's thickness is independently trustworthy, the same shape as a
    Gas layer (thickness counts, no thermal mass)."""
    with caplog.at_level(logging.WARNING, logger="citygml_energy.units"):
        info = _reduce_construction(
            _make_construction(
                [_layer(0.2, "m", _solid_material(density_uom="lb/ft3"))],
            ),
            {},
        )
    assert info.thickness_m == pytest.approx(0.2)
    assert info.heat_capacity_kj_per_k_m2 is None
    assert "density" in caplog.text
