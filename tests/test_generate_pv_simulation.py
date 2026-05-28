"""Tests for the simulated-PV generator (`tools/generate_pv_simulation.py`).

`simulate_daily_kwh` is checked through its interface with value-agnostic
invariants (reproducible, non-negative, one value per day, summer brighter
than winter, annual yield in a sane Dutch band), so the model can be retuned
without a silent regression. A round-trip test covers the in-place JSON patch.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from citygml_energy.generation import DEFAULT_INPUT_PATH
from tools.generate_pv_simulation import (
    PEAK_POWER_KWP,
    main,
    simulate_daily_kwh,
)

_SAMPLE_INPUT = DEFAULT_INPUT_PATH.parent / "owner_occupier_building_sample.json"


def _dates(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def test_simulate_is_reproducible_under_a_fixed_seed():
    dates = _dates(date(2022, 1, 1), 365)
    assert simulate_daily_kwh(dates, seed=7) == simulate_daily_kwh(dates, seed=7)


def test_simulate_is_one_nonnegative_value_per_day():
    dates = _dates(date(2022, 1, 1), 365)
    values = simulate_daily_kwh(dates)
    assert len(values) == len(dates)
    assert all(v >= 0.0 for v in values)


def test_simulate_summer_outproduces_winter():
    dates = _dates(date(2022, 1, 1), 365)
    values = simulate_daily_kwh(dates)
    by_month: dict[int, list[float]] = {}
    for day, value in zip(dates, values, strict=True):
        by_month.setdefault(day.month, []).append(value)
    summer = sum(sum(by_month[m]) for m in (6, 7, 8))
    winter = sum(sum(by_month[m]) for m in (12, 1, 2))
    assert summer > 2 * winter, f"summer {summer:.0f} kWh should dwarf winter {winter:.0f} kWh"


def test_simulate_annual_specific_yield_in_dutch_band():
    """Annual yield should sit in a believable NL band (~600-1100 kWh/kWp)."""
    dates = _dates(date(2022, 1, 1), 365)
    annual = sum(simulate_daily_kwh(dates))
    specific = annual / PEAK_POWER_KWP
    assert 600.0 < specific < 1100.0, f"{specific:.0f} kWh/kWp is outside the plausible NL band"


def test_main_writes_one_value_per_day_into_the_json(tmp_path):
    """End-to-end: `main` patches the feature's values_list in place.

    The sample's simulated series declares a 10-day span, so the patched array
    must hold exactly the 10 simulated daily values and nothing else in the
    curated JSON changes shape.
    """
    target = tmp_path / "building.json"
    target.write_text(_SAMPLE_INPUT.read_text(encoding="utf-8"), encoding="utf-8")

    main(["--input", str(target)])

    patched = json.loads(target.read_text(encoding="utf-8"))
    series = next(f for f in patched["features"] if f.get("id") == "id_daily_ts_pv_production_simulated_1")
    expected = simulate_daily_kwh(_dates(date(2003, 7, 1), 10))
    assert series["values_list"]["value"] == expected


_FEATURE_ID = "id_daily_ts_pv_production_simulated_1"


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

    main(["--input", str(target), "--seed", "1"])
    patched = target.read_bytes()

    assert _outside_target_array(original) == _outside_target_array(patched)
    assert original != patched  # the array interior did change
    assert (b"\r\n" in original) == (b"\r\n" in patched)  # line endings preserved


def test_main_is_idempotent_for_a_fixed_seed(tmp_path):
    """Re-running with the same seed leaves the file byte-identical."""
    target = tmp_path / "building.json"
    target.write_bytes(_SAMPLE_INPUT.read_bytes())

    main(["--input", str(target), "--seed", "1"])
    once = target.read_bytes()
    main(["--input", str(target), "--seed", "1"])
    twice = target.read_bytes()

    assert once == twice
