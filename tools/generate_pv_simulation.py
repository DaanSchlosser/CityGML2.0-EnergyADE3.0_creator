"""Generate the daily simulated-PV series for the owner-occupier reference building.

The series is an *independent* NTA 8800 estimate of the array's electricity
production, written into ``id_daily_ts_pv_production_simulated_1`` so it can be
plotted against the metered ``id_pv_production_1`` series. It is not a metered
quantity.

NTA 8800:2024 method (clause 16.2, "Bijdrage van zonnestroomsystemen (PV)")
---------------------------------------------------------------------------
The monthly on-site electricity produced by a PV system i is, per formula
(16.2):

    E_el;PV;out;i,mi = E_sol;mi * P_pk;i * f_perf;i * c_sh,PV;mi;i * f_prac,PV;i
                       -----------------------------------------------------------
                                              I_ref

with the monthly incident irradiation on the plane, per formula (16.3):

    E_sol;mi = I_sol;mi * t_mi * F_sh;obst;mi / 1000     [kWh/m2]

where
  * ``I_sol;mi``  monthly mean total irradiation on the plane, table 17.2,
    a function of orientation gamma and tilt beta, for the NEN 5060 Dutch
    reference climate                                              [W/m2]
  * ``t_mi``      reference length of month mi, table 17.1          [h]
  * ``P_pk;i``    sum of the panels' Watt-peak power (formula 16.4b,
    n_panels * P_pk;panel / 1000)                                  [kW]
  * ``f_perf;i``  yield factor, table 16.2 (DC->AC conversion, operating
    temperature, building integration/ventilation, soiling)        [-]
  * ``c_sh``      shading correction factor, table 16.3            [-]
  * ``f_prac``    practical-performance (ageing) factor, 16.2.2.5  [-]
  * ``I_ref``     reference irradiance, 1 kW/m2                    [kW/m2]
  * ``F_sh;obst`` monthly shading-reduction factor, clause 17.3   [-]

NTA 8800 is a *monthly* method built on a fixed reference climate, so the
result does not depend on the calendar year. The daily ``RegularTimeSeries``
this tool writes is therefore the month's NTA 8800 production divided evenly
over the days of that month: no sub-monthly weather is modelled, because the
standard provides none. The daily values for the same month are identical
across years, save for February in a leap year (the same monthly energy spread
over 29 days instead of 28).

System parameters below are read off ``pv_panel_1`` in
``inputs/buildings/owner_occupier_building.json``.
"""

from __future__ import annotations

import argparse
import calendar
import json
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from citygml_energy.generation import DEFAULT_INPUT_PATH

__all__ = [
    "PEAK_POWER_KWP",
    "main",
    "monthly_production_kwh",
    "simulate_daily_kwh",
]

# --- pv_panel_1 system parameters (owner_occupier_building.json) -------------
# 36 panels x 270 Wp = 9720 W; formula (16.4b): P_pk = n * P_pk;panel / 1000.
PEAK_POWER_KWP: float = 9.72
# Compass azimuth of the array (0 deg = N, 90 = E, 180 = S, 270 = W), matching
# table 17.2's gamma convention. 235.65 deg is roughly SW.
AZIMUTH_DEG: float = 235.65
# Tilt from horizontal (beta in table 17.2). 0 = flat, 90 = vertical.
INCLINATION_DEG: float = 44.51

# Yield factor f_perf, table 16.2. The roof-mounted array has a small air gap
# behind the panels ("matig geventileerd": op of in dak gemonteerd, met een
# luchtspouw), so the 0.80 row applies.
F_PERF: float = 0.80
# Practical-performance factor f_prac;PV, clause 16.2.2.5 (fixed; models the
# ageing of the system averaged over a >=20-year life).
F_PRAC: float = 0.95
# Shading correction c_sh;PV, table 16.3 at F_sh;obst = 1.00 (no obstruction
# modelled for this building).
C_SHADING: float = 1.00
# Monthly shading-reduction factor F_sh;obst;mi, clause 17.3. 1.0 = unshaded.
F_SH_OBST: float = 1.00
# Reference irradiance I_ref, clause 16.2.2 (1 kW/m2).
I_REF_KW_M2: float = 1.0

# Retained for backwards compatibility with the previous stochastic placeholder
# generator and the CLI: the NTA 8800 method is deterministic, so the seed does
# not affect the output.
DEFAULT_SEED: int = 0

_FEATURE_ID: str = "id_daily_ts_pv_production_simulated_1"

# --- table 17.1: reference length of each month, t_mi, in hours -------------
_MONTH_LENGTH_H: tuple[int, ...] = (
    744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744,
)

# --- table 17.2: monthly mean total irradiation I_sol;mi, in W/m2 -----------
# Ground-reflection coefficient rho = 0.2, averaged over all hours, NEN 5060
# reference climate. Each list is Jan..Dec.
#
# Orientation keys are compass degrees: 0 = N, 45 = NE, 90 = E, 135 = SE,
# 180 = S, 225 = SW, 270 = W, 315 = NW (table prints N as 360).
_ISOL_HORIZONTAL: tuple[float, ...] = (
    28.0, 49.3, 96.6, 160.5, 197.0, 209.3, 191.0, 177.2, 123.9, 73.2, 34.3, 21.0,
)
# beta = 180 deg (downward-facing); single orientation-independent column.
_ISOL_DOWNWARD: tuple[float, ...] = (
    5.6, 9.8, 19.3, 32.1, 39.3, 41.8, 38.2, 35.3, 24.7, 14.6, 6.9, 4.2,
)
_ISOL_TILT: dict[int, dict[int, tuple[float, ...]]] = {
    30: {
        180: (50.5, 69.1, 122.5, 189.5, 211.1, 211.2, 196.1, 197.9, 154.0, 102.4, 54.8, 38.3),
        225: (44.4, 61.2, 109.3, 174.5, 201.5, 210.7, 193.2, 198.3, 146.2, 91.5, 47.7, 32.6),
        270: (29.0, 46.2, 87.7, 146.5, 179.9, 199.4, 180.2, 178.4, 121.1, 68.8, 32.9, 20.6),
        315: (16.2, 32.9, 66.7, 115.6, 155.8, 180.6, 162.1, 147.6, 91.6, 47.3, 20.5, 12.5),
        0: (14.9, 27.2, 56.4, 104.6, 148.5, 171.0, 153.0, 125.8, 73.7, 36.3, 18.6, 12.2),
        45: (15.8, 34.5, 72.8, 125.1, 160.6, 173.0, 156.9, 127.5, 86.5, 48.9, 20.9, 12.5),
        90: (26.9, 49.4, 97.6, 158.9, 186.3, 189.7, 175.0, 152.8, 113.7, 71.6, 33.8, 21.2),
        135: (42.2, 63.7, 117.7, 184.1, 206.3, 204.4, 190.0, 179.3, 140.1, 93.6, 48.6, 33.1),
    },
    45: {
        180: (57.9, 74.1, 126.6, 189.7, 202.7, 197.3, 185.0, 193.5, 157.6, 109.4, 61.0, 44.1),
        225: (49.4, 63.2, 109.1, 171.0, 191.1, 199.3, 182.5, 194.9, 147.0, 94.2, 51.1, 36.1),
        270: (28.7, 44.0, 82.0, 136.7, 164.4, 186.2, 166.8, 169.8, 115.3, 64.8, 31.3, 19.9),
        315: (14.9, 29.2, 56.6, 96.5, 128.7, 156.3, 139.0, 127.2, 78.0, 40.2, 18.5, 11.7),
        0: (14.3, 25.9, 44.3, 70.0, 113.6, 139.6, 123.5, 91.5, 52.9, 33.5, 17.8, 11.7),
        45: (14.5, 30.4, 63.1, 107.1, 134.5, 145.9, 132.7, 102.9, 72.2, 41.4, 18.8, 11.7),
        90: (26.2, 47.9, 94.2, 152.2, 172.0, 173.3, 160.4, 137.9, 106.2, 68.4, 32.4, 20.5),
        135: (46.3, 66.5, 120.2, 183.5, 197.3, 190.7, 179.1, 171.0, 139.2, 97.2, 52.2, 36.7),
    },
    60: {
        180: (62.2, 75.4, 124.3, 180.2, 184.5, 175.1, 165.9, 179.7, 153.3, 110.7, 63.9, 47.4),
        225: (51.8, 62.1, 103.9, 160.4, 173.4, 180.9, 165.4, 182.9, 141.5, 92.6, 51.8, 37.6),
        270: (27.8, 41.1, 74.8, 125.1, 146.3, 169.1, 150.6, 156.9, 107.2, 59.9, 28.9, 19.0),
        315: (13.8, 26.4, 49.6, 83.1, 107.5, 134.1, 119.2, 110.2, 68.6, 35.9, 17.0, 10.9),
        0: (13.4, 24.1, 41.5, 57.8, 78.5, 102.9, 90.4, 68.0, 48.6, 31.5, 16.6, 10.9),
        45: (13.5, 27.3, 56.3, 93.9, 113.2, 123.3, 112.3, 85.8, 62.3, 36.6, 17.3, 10.9),
        90: (24.7, 45.4, 88.5, 142.0, 154.7, 154.5, 143.2, 122.0, 97.2, 63.5, 30.4, 19.6),
        135: (48.1, 66.3, 116.9, 174.2, 179.9, 170.7, 161.8, 156.4, 132.6, 96.0, 53.2, 38.4),
    },
    90: {
        180: (60.1, 66.7, 101.8, 135.1, 124.9, 112.7, 109.7, 128.5, 122.3, 96.2, 59.5, 46.2),
        225: (48.1, 52.2, 82.1, 121.9, 122.1, 127.8, 117.1, 137.1, 112.2, 76.3, 45.6, 34.9),
        270: (23.4, 32.8, 57.3, 96.2, 107.3, 125.7, 112.7, 120.0, 83.9, 46.7, 22.7, 15.2),
        315: (11.4, 20.9, 38.5, 64.1, 78.9, 97.8, 88.5, 83.1, 53.6, 28.7, 13.8, 8.9),
        0: (11.1, 19.5, 34.8, 49.4, 61.9, 73.0, 66.7, 55.9, 41.4, 26.4, 13.6, 8.9),
        45: (11.1, 21.5, 44.2, 72.9, 82.9, 92.0, 81.2, 63.9, 47.9, 29.1, 14.0, 8.9),
        90: (20.2, 36.5, 70.7, 112.2, 114.6, 114.8, 104.9, 89.0, 73.7, 49.8, 23.9, 15.9),
        135: (43.9, 56.8, 95.4, 135.8, 128.4, 118.0, 113.2, 112.4, 103.6, 80.3, 47.1, 35.8),
    },
    135: {
        180: (33.4, 31.5, 37.3, 39.0, 45.5, 48.3, 44.9, 41.6, 40.2, 41.6, 30.9, 26.3),
        225: (25.1, 24.2, 35.1, 50.7, 50.4, 52.3, 49.7, 54.3, 47.5, 33.2, 21.7, 18.3),
        270: (12.7, 17.3, 29.9, 49.9, 55.2, 62.4, 57.7, 59.6, 43.2, 24.7, 12.0, 8.1),
        315: (7.6, 13.2, 25.2, 41.8, 50.7, 57.8, 53.5, 50.2, 33.8, 19.3, 9.2, 5.8),
        0: (7.5, 12.9, 24.5, 38.3, 46.7, 50.6, 46.5, 42.1, 30.4, 18.6, 9.1, 5.8),
        45: (7.5, 13.5, 27.6, 45.5, 51.9, 55.4, 48.9, 42.9, 31.4, 19.4, 9.3, 5.8),
        90: (10.6, 18.6, 36.7, 57.1, 57.8, 59.9, 53.0, 47.7, 37.9, 25.4, 12.7, 8.4),
        135: (22.2, 26.7, 42.0, 56.3, 51.9, 51.7, 48.0, 47.5, 43.2, 35.2, 22.7, 19.0),
    },
}

# Tabulated nodes for interpolation, including the orientation-independent
# endpoints beta = 0 (horizontal) and beta = 180 (downward).
_TILT_NODES: tuple[int, ...] = (0, 30, 45, 60, 90, 135, 180)
_ORIENTATIONS: tuple[int, ...] = (0, 45, 90, 135, 180, 225, 270, 315)


def _angular_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _nearest_orientation(azimuth_deg: float, tilt_node: int, month_idx: int) -> int:
    """Snap an azimuth to the nearest tabulated orientation (table 17.2 rule).

    For intermediate orientations the value of the nearest tabulated
    orientation is used; if the azimuth falls exactly between two, the
    higher-irradiation neighbour is taken.
    """
    az = azimuth_deg % 360.0
    best = min(
        _ORIENTATIONS,
        key=lambda g: (_angular_distance(az, g), -_ISOL_TILT[tilt_node][g][month_idx]),
    )
    return best


def _isol_at_node(tilt_node: int, azimuth_deg: float, month_idx: int) -> float:
    if tilt_node == 0:
        return _ISOL_HORIZONTAL[month_idx]
    if tilt_node == 180:
        return _ISOL_DOWNWARD[month_idx]
    orient = _nearest_orientation(azimuth_deg, tilt_node, month_idx)
    return _ISOL_TILT[tilt_node][orient][month_idx]


def _isol_w_m2(azimuth_deg: float, inclination_deg: float, month_idx: int) -> float:
    """I_sol;mi for an arbitrary orientation/tilt via the table-17.2 rules.

    Linear interpolation between the bracketing tilt nodes (table-17.2 note);
    nearest tabulated orientation per :func:`_nearest_orientation`.
    """
    beta = max(0.0, min(180.0, inclination_deg))
    lo = max(n for n in _TILT_NODES if n <= beta)
    hi = min(n for n in _TILT_NODES if n >= beta)
    v_lo = _isol_at_node(lo, azimuth_deg, month_idx)
    if hi == lo:
        return v_lo
    v_hi = _isol_at_node(hi, azimuth_deg, month_idx)
    frac = (beta - lo) / (hi - lo)
    return v_lo + frac * (v_hi - v_lo)


def monthly_production_kwh() -> list[float]:
    """NTA 8800 on-site PV electricity for each month Jan..Dec, in kWh.

    Implements formulas (16.2) and (16.3) for the ``pv_panel_1`` system.
    """
    out: list[float] = []
    for m in range(12):
        e_sol = _isol_w_m2(AZIMUTH_DEG, INCLINATION_DEG, m) * _MONTH_LENGTH_H[m] * F_SH_OBST / 1000.0
        e_month = e_sol * PEAK_POWER_KWP * F_PERF * C_SHADING * F_PRAC / I_REF_KW_M2
        out.append(e_month)
    return out


def simulate_daily_kwh(dates: Sequence[date], seed: int = DEFAULT_SEED) -> list[float]:
    """Daily PV production [kWh] for each date, one value per day.

    Each day carries its calendar month's NTA 8800 production divided by the
    number of days in that month. The NTA 8800 reference climate is fixed, so
    the value depends only on the month (and, through the day count, on whether
    February falls in a leap year). ``seed`` is accepted for backwards
    compatibility and does not affect the deterministic result.
    """
    monthly = monthly_production_kwh()
    out: list[float] = []
    for d in dates:
        days_in_month = calendar.monthrange(d.year, d.month)[1]
        out.append(round(monthly[d.month - 1] / days_in_month, 1))
    return out


def _daily_dates(start: date, end_exclusive: date) -> list[date]:
    from datetime import timedelta

    days = (end_exclusive - start).days
    return [start + timedelta(days=i) for i in range(days)]


def _feature_span(text: str) -> tuple[date, date]:
    data = json.loads(text)
    feature = next(f for f in data["features"] if f.get("id") == _FEATURE_ID)
    start = datetime.fromisoformat(feature["start_timestamp"]).date()
    end = datetime.fromisoformat(feature["end_timestamp"]).date()
    return start, end


def _patch_values_array(text: str, values: Sequence[float]) -> str:
    """Replace only the interior of the target feature's ``values_list`` array.

    Deliberate text surgery (not ``json.dump``) so the curated input keeps its
    formatting and line endings; only the bytes between ``[`` and ``]`` change.
    """
    start = text.index(f'"id": "{_FEATURE_ID}"')
    values_list = text.index('"values_list"', start)
    value_key = text.index('"value"', values_list)
    open_bracket = text.index("[", value_key)
    close_bracket = text.index("]", open_bracket)
    body = ", ".join(f"{v:.1f}" for v in values)
    return text[: open_bracket + 1] + body + text[close_bracket:]


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    raw = args.input.read_bytes()
    text = raw.decode("utf-8")
    start, end = _feature_span(text)
    values = simulate_daily_kwh(_daily_dates(start, end), seed=args.seed)
    patched = _patch_values_array(text, values)
    args.input.write_bytes(patched.encode("utf-8"))


if __name__ == "__main__":
    main()
