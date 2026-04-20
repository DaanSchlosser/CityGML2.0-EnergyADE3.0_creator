"""EPC-label scoring, averaging, and Dutch energy-label color mapping.

This module converts Dutch energy-label letters (``A+++++`` … ``G``)
into (a) a numeric score used for aggregating multiple labels on one
building and (b) an RGB color used by the CityGML Appearance builder.

Numeric mapping: each letter maps to a representative primary
fossil-energy use (kWh/m²/yr), labels are averaged by taking the simple
arithmetic mean of those kWh values, and the mean is then snapped back
to a letter via a fixed threshold table.

The color palette matches the RVO 2024 "Energielabel woningbouw"
reference card sampled directly from the published example at
https://www.energielabel.nl/media/oednouhj/energielabel_woningbouw_2024_voorbeeld-c-002.pdf
(palette legend on page 2). Per that reference:

* ``G`` red → ``D`` yellow → ``B`` green → ``A`` dark-green (7 primary bands).
* **Every A-variant (``A`` through ``A++++``) shares the same dark green
  ``#009037``.** The visual distinction in RVO materials comes from the
  ``+`` suffix text, not a gradient — this is the spec, not a limitation
  of our renderer.
* ``A+++++`` is not drawn on the RVO card (it is outside the regulatory
  scale); we reuse the same dark green so the best-possible label never
  falls through to grey.
* ``None`` / unrecognised letter → neutral grey so "no label" buildings
  stay visible but unhighlighted.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "LABEL_HEX",
    "LABEL_TO_KWH",
    "average_labels",
    "label_to_rgb",
    "normalize_label",
]


# ---------------------------------------------------------------------------
# Letter to kWh mapping
# ---------------------------------------------------------------------------
# Each letter is represented by the midpoint of its BENG-1 band (primary
# fossil energy use in kWh/m²/yr).
LABEL_TO_KWH: dict[str, float] = {
    "A+++++": -10.0,
    "A++++": 25.0,
    "A+++": 62.5,
    "A++": 90.0,
    "A+": 132.5,
    "A": 175.0,
    "B": 207.5,
    "C": 257.5,
    "D": 312.5,
    "E": 357.5,
    "F": 402.5,
    "G": 450.0,
}

# Reverse thresholds: kWh mean to letter. Upper exclusive bounds, in order.
_KWH_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.0, "A+++++"),
    (50.0, "A++++"),
    (75.0, "A+++"),
    (105.0, "A++"),
    (160.0, "A+"),
    (190.0, "A"),
    (225.0, "B"),
    (290.0, "C"),
    (335.0, "D"),
    (380.0, "E"),
    (425.0, "F"),
)
_WORST_LABEL = "G"


# ---------------------------------------------------------------------------
# Dutch energy-label colours
# ---------------------------------------------------------------------------
_GREEN_A: str = "#009037"
LABEL_HEX: dict[str | None, str] = {
    "A+++++": _GREEN_A,
    "A++++": _GREEN_A,
    "A+++": _GREEN_A,
    "A++": _GREEN_A,
    "A+": _GREEN_A,
    "A": _GREEN_A,
    "B": "#55AB26",
    "C": "#C8D100",
    "D": "#FFEC00",
    "E": "#FABA00",
    "F": "#EB6909",
    "G": "#E2001A",
    None: "#808080",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_label(raw: str | None) -> str | None:
    """Return *raw* stripped and upper-cased, or ``None`` for empty input.

    Labels in EP-online CSVs arrive with inconsistent case (``"a+"``,
    ``"A+"``) and trailing whitespace; this collapses both so lookups
    never miss due to casing.
    """
    if raw is None:
        return None
    trimmed = str(raw).strip().upper()
    return trimmed or None


def average_labels(labels: Iterable[str | None]) -> str | None:
    """Mean EPC label across *labels*, or ``None`` if none are recognised.

    Each input is normalised, mapped to its kWh value, averaged (simple
    arithmetic mean, no area/occupant weighting), then mapped back to a
    letter via ``_KWH_THRESHOLDS``. Unrecognised entries (``None`` or
    labels not in :data:`LABEL_TO_KWH`) are dropped; the mean is taken
    over the rest.
    """
    kwh_values: list[float] = []
    for label in labels:
        normalized = normalize_label(label)
        if normalized is None:
            continue
        kwh = LABEL_TO_KWH.get(normalized)
        if kwh is not None:
            kwh_values.append(kwh)

    if not kwh_values:
        return None

    mean_kwh = sum(kwh_values) / len(kwh_values)
    return _kwh_to_label(mean_kwh)


def label_to_rgb(letter: str | None) -> tuple[float, float, float]:
    """Return the EU-palette RGB triplet (each component in ``[0, 1]``).

    Unknown letters and ``None`` both collapse to the grey fallback so the
    caller never has to special-case missing labels.
    """
    normalized = normalize_label(letter)
    hex_code = LABEL_HEX.get(normalized, LABEL_HEX[None])
    return _hex_to_rgb_floats(hex_code)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _kwh_to_label(kwh: float) -> str:
    for upper, letter in _KWH_THRESHOLDS:
        if kwh < upper:
            return letter
    return _WORST_LABEL


def _hex_to_rgb_floats(hex_code: str) -> tuple[float, float, float]:
    h = hex_code.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b)
