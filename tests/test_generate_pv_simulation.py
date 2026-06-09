"""Tests for the simulated-PV generator (`tools/generate_pv_simulation.py`).

`simulate_monthly_kwh` is checked through its interface with value-agnostic
invariants (one value per month, summer brighter than winter, a given calendar
month repeated across years, annual yield in a sane Dutch band), so the model
can be retuned without a silent regression. A round-trip test covers the
in-place JSON patch.
"""

from __future__ import annotations

import json
from datetime import date

from citygml_energy.generation import DEFAULT_INPUT_PATH
from tools.generate_pv_simulation import (
    PEAK_POWER_KWP,
    main,
    simulate_monthly_kwh,
)

_SAMPLE_INPUT = DEFAULT_INPUT_PATH.parent / "NL-single-family-house_sample.json"
_FEATURE_ID = "id_monthly_ts_pv_production_simulated_1"


def test_simulate_is_one_nonnegative_value_per_month():
    values = simulate_monthly_kwh(date(2022, 1, 1), date(2023, 1, 1))
    assert len(values) == 12
    assert all(v >= 0 for v in values)


def test_simulate_repeats_each_calendar_month_across_years():
    """The NEN 5060 reference climate is fixed, so a calendar month is identical
    from one year to the next."""
    four_years = simulate_monthly_kwh(date(2022, 1, 1), date(2026, 1, 1))
    assert len(four_years) == 48
    assert four_years[0:12] == four_years[12:24] == four_years[24:36] == four_years[36:48]


def test_simulate_summer_outproduces_winter():
    values = simulate_monthly_kwh(date(2022, 1, 1), date(2023, 1, 1))
    summer = sum(values[m] for m in (5, 6, 7))  # Jun, Jul, Aug
    winter = sum(values[m] for m in (11, 0, 1))  # Dec, Jan, Feb
    assert summer > 2 * winter, f"summer {summer} kWh should dwarf winter {winter} kWh"


def test_simulate_annual_specific_yield_in_dutch_band():
    """Annual yield should sit in a believable NL band (~600-1100 kWh/kWp)."""
    annual = sum(simulate_monthly_kwh(date(2022, 1, 1), date(2023, 1, 1)))
    specific = annual / PEAK_POWER_KWP
    assert 600.0 < specific < 1100.0, f"{specific:.0f} kWh/kWp is outside the plausible NL band"


def test_main_writes_monthly_values_into_the_json(tmp_path):
    """End-to-end: `main` patches the feature's values_list in place.

    The sample's simulated series declares a six-month span, so the patched
    array must hold exactly those six monthly values and nothing else in the
    curated JSON changes shape.
    """
    target = tmp_path / "building.json"
    target.write_text(_SAMPLE_INPUT.read_text(encoding="utf-8"), encoding="utf-8")

    main(["--input", str(target)])

    patched = json.loads(target.read_text(encoding="utf-8"))
    series = next(f for f in patched["features"] if f.get("id") == _FEATURE_ID)
    expected = simulate_monthly_kwh(date(2003, 7, 1), date(2004, 1, 1))
    assert series["values_list"]["value"] == expected


def _outside_target_array(raw: bytes) -> tuple[str, str]:
    """The JSON text before/after the target values_list array (exclusive)."""
    text = raw.decode("utf-8")
    start = text.index(f'"id": "{_FEATURE_ID}"')
    open_bracket = text.index("[", text.index('"value"', text.index('"values_list"', start)))
    close_bracket = text.index("]", open_bracket)
    return text[: open_bracket + 1], text[close_bracket:]


def test_main_patch_touches_only_the_target_array(tmp_path):
    """`main` rewrites only the array interior, byte-for-byte elsewhere.

    The patch is deliberate text surgery (not `json.dump`) so the curated
    input keeps its formatting AND its CRLF line endings on Windows. Read and
    compare as raw bytes -- `read_text` would normalise newlines and hide a
    regression where the whole file gets reflowed.
    """
    target = tmp_path / "building.json"
    original = _SAMPLE_INPUT.read_bytes()
    target.write_bytes(original)

    main(["--input", str(target)])
    patched = target.read_bytes()

    assert _outside_target_array(original) == _outside_target_array(patched)
    assert original != patched  # the array interior did change
    assert (b"\r\n" in original) == (b"\r\n" in patched)  # line endings preserved


def test_main_is_idempotent(tmp_path):
    """Re-running leaves the file byte-identical (the method is deterministic)."""
    target = tmp_path / "building.json"
    target.write_bytes(_SAMPLE_INPUT.read_bytes())

    main(["--input", str(target)])
    once = target.read_bytes()
    main(["--input", str(target)])
    twice = target.read_bytes()

    assert once == twice
