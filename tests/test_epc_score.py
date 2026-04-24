"""Unit tests for EPC label scoring, averaging, and color mapping."""

from __future__ import annotations

import pytest

from citygml_energy.city_builder.epc_score import (
    LABEL_HEX,
    LABEL_TO_KWH,
    average_labels,
    label_to_rgb,
    normalize_label,
)

# ---------------------------------------------------------------------------
# normalize_label
# ---------------------------------------------------------------------------


def test_normalize_strips_and_uppercases() -> None:
    assert normalize_label("  a+  ") == "A+"
    assert normalize_label("b") == "B"


def test_normalize_returns_none_for_empty_input() -> None:
    assert normalize_label(None) is None
    assert normalize_label("") is None
    assert normalize_label("   ") is None


# ---------------------------------------------------------------------------
# LABEL_TO_KWH completeness
# ---------------------------------------------------------------------------


def test_label_map_covers_eu_plus_rvo_scale() -> None:
    # The 11-letter scale matches the RVO "Uitgebreid Energielabel" used by
    # EP-online: 5 plus-grades of A, plain A-G. This gives 12 total bands.
    expected = {"A+++++", "A++++", "A+++", "A++", "A+", "A", "B", "C", "D", "E", "F", "G"}
    assert set(LABEL_TO_KWH) == expected


def test_label_kwh_values_are_monotonically_increasing() -> None:
    # Labels are ordered best-to-worst; kWh (primary fossil energy use)
    # should never decrease going down the scale.
    from itertools import pairwise

    values = list(LABEL_TO_KWH.values())
    for prev, curr in pairwise(values):
        assert prev < curr


# ---------------------------------------------------------------------------
# average_labels
# ---------------------------------------------------------------------------


def test_average_of_single_label_returns_that_label() -> None:
    assert average_labels(["A"]) == "A"


def test_average_of_mixed_labels_falls_between_inputs() -> None:
    # A (175) + C (257.5) → mean 216.25 → B (190, 225)
    assert average_labels(["A", "C"]) == "B"


def test_average_skips_unknown_and_none_entries() -> None:
    # Non-label entries are dropped before averaging so one typo cannot
    # silently shift the building's color.
    assert average_labels([None, "A", "not-a-label", ""]) == "A"


def test_average_returns_none_when_nothing_recognized() -> None:
    assert average_labels([]) is None
    assert average_labels([None, "garbage", ""]) is None


def test_average_handles_case_and_whitespace() -> None:
    assert average_labels(["  a  ", "a"]) == "A"


def test_best_and_worst_labels_round_trip_exactly() -> None:
    assert average_labels(["A+++++"]) == "A+++++"
    assert average_labels(["G"]) == "G"


# ---------------------------------------------------------------------------
# label_to_rgb
# ---------------------------------------------------------------------------


def test_rgb_components_are_in_unit_range() -> None:
    # CityGML app:X3DMaterial/diffuseColor requires each RGB component to
    # sit in [0, 1]. Every palette entry must satisfy that.
    for letter in list(LABEL_HEX) + ["not-a-label"]:
        r, g, b = label_to_rgb(letter)
        assert 0.0 <= r <= 1.0
        assert 0.0 <= g <= 1.0
        assert 0.0 <= b <= 1.0


def test_rgb_falls_back_to_grey_for_missing_labels() -> None:
    grey = label_to_rgb(None)
    assert grey == label_to_rgb("not-a-label")
    # #808080 → (128/255, 128/255, 128/255)
    assert grey == pytest.approx((0.5019607843137255,) * 3)


def test_best_label_is_green_and_worst_label_is_red() -> None:
    # Dutch palette sanity: A+++++ should have green dominant, G red dominant.
    best = label_to_rgb("A+++++")
    worst = label_to_rgb("G")
    assert best[1] > best[0] and best[1] > best[2]  # green > red, green > blue
    assert worst[0] > worst[1] and worst[0] > worst[2]  # red dominant


def test_palette_matches_rvo_2024_card_exactly() -> None:
    """Pins the hex values sampled from the official RVO card.

    Regression guard: the EU-generic "A = yellow, G = dark red" palette
    shipped before was sampled from a different document and pushed the
    whole scale one step; never again silently.
    """
    assert LABEL_HEX["G"] == "#E2001A"
    assert LABEL_HEX["F"] == "#EB6909"
    assert LABEL_HEX["E"] == "#FABA00"
    assert LABEL_HEX["D"] == "#FFEC00"
    assert LABEL_HEX["C"] == "#C8D100"
    assert LABEL_HEX["B"] == "#55AB26"
    # Every A-variant shares one green per the RVO spec.
    green = "#009037"
    for letter in ("A", "A+", "A++", "A+++", "A++++", "A+++++"):
        assert LABEL_HEX[letter] == green, f"{letter} should be RVO green"


def test_label_a_is_green_not_yellow() -> None:
    """Direct sanity check against the old, shifted palette where A was
    yellow (``#FFED00``). ``A`` must be green in the Dutch scheme.
    """
    r, g, _b = label_to_rgb("A")
    assert g > 0.4  # substantial green
    assert r < 0.2  # not yellow (yellow has high red + high green)
