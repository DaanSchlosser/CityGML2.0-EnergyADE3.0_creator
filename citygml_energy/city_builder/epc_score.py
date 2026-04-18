"""EPC-label scoring, averaging, and EU-standard color mapping.

This module converts Dutch/EU energy-label letters (``A+++++`` … ``G``)
into (a) a numeric score used for aggregating multiple labels on one
building and (b) an RGB color used by the CityGML Appearance builder.

The numeric mapping mirrors the reference implementation in
``VdB_Optoppen_lokaal/exporting_sql_tables/2. export_aangrenzende_
dakdelen_woningcorporaties_excel.py`` (``label_to_kwh`` /
``kwh_to_avg_label``): each letter maps to a representative primary
fossil-energy use (kWh/m²/yr), labels are averaged by taking the simple
arithmetic mean of those kWh values, and the mean is then snapped back
to a letter via a fixed threshold table.

The color palette is the EU energy-label graphic scale (Regulation
2017/1369, extended upward with RVO's ``A++++`` / ``A+++++`` tints and
downward with grey for "no label"). The EU Regulation does not specify
RGB values directly — the printed reference is CMYK. The hex values
below are the de-facto digital rendering used across Dutch tools
(EP-online, RVO "Uitgebreid Energielabel" graphics). They are isolated
in :data:`LABEL_HEX` so a swap to a different authoritative palette is
a one-line change.
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
# Letter ↔ kWh mapping (from VdB reference script, `label_to_kwh`)
# ---------------------------------------------------------------------------
# Each letter is represented by the midpoint of its BENG-1 band (primary
# fossil energy use in kWh/m²/yr). Values copied verbatim from the
# reference script so this pipeline produces identical numeric scores.
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

# Reverse thresholds: kWh mean → letter. Upper exclusive bounds, in order.
# Copied verbatim from `kwh_to_avg_label` in the reference script.
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
# EU energy-label colors (hex, as digitally rendered by Dutch tools)
# ---------------------------------------------------------------------------
LABEL_HEX: dict[str | None, str] = {
    "A+++++": "#009A3E",
    "A++++": "#2CA24C",
    "A+++": "#5AB24B",
    "A++": "#85C247",
    "A+": "#BDD631",
    "A": "#FFED00",
    "B": "#FDD100",
    "C": "#F8AE1A",
    "D": "#F18E1C",
    "E": "#E94E1B",
    "F": "#E30613",
    "G": "#B40000",
    None: "#808080",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_label(raw: str | None) -> str | None:
    """Return *raw* stripped and upper-cased, or ``None`` for empty input.

    Mirrors the reference script's ``normalize_label``. Labels in EP-online
    CSVs arrive with inconsistent case (``"a+"``, ``"A+"``) and trailing
    whitespace; this collapses both so lookups never miss due to casing.
    """
    if raw is None:
        return None
    trimmed = str(raw).strip().upper()
    return trimmed or None


def average_labels(labels: Iterable[str | None]) -> str | None:
    """Mean EPC label across *labels*, or ``None`` if none are recognised.

    Each input is normalised, mapped to its kWh value, averaged (simple
    arithmetic mean — no area/occupant weighting, matching the reference
    script), then mapped back to a letter via ``_KWH_THRESHOLDS``.
    Unrecognised entries (``None`` or labels not in :data:`LABEL_TO_KWH`)
    are dropped; the mean is taken over the rest.
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
