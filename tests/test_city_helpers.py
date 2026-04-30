"""Direct unit tests for ``citygml_energy.city_builder._helpers``.

These helpers are exercised heavily through the fetcher and builder
round-trips, but the indirect coverage misses corner-case inputs (NaN,
empty string, ``"None"`` placeholder, sub-centimetre rounding drift in
bbox cache keys). Pinning them here means a future refactor that
silently changes the behaviour will break this suite first instead of
surfacing as a hard-to-localise GML diff.
"""

from __future__ import annotations

import logging

import pytest  # noqa: TC002 (load-bearing at runtime: fixture types are runtime markers)

from citygml_energy.city_builder._helpers import (
    bbox_cache_key,
    safe_gml_id,
    to_clean_str,
    to_finite_float,
    to_float,
    to_int,
)

# ---------------------------------------------------------------------------
# safe_gml_id
# ---------------------------------------------------------------------------


def test_safe_gml_id_prepends_kind() -> None:
    assert safe_gml_id("", "pand", "0503100000000001") == "pand_0503100000000001"


def test_safe_gml_id_layers_user_prefix_on_top() -> None:
    """Multi-city merges need an extra prefix to avoid xs:ID collisions
    when two BAG ids could otherwise produce the same gml:id."""
    assert safe_gml_id("delft", "pand", "12345") == "delft_pand_12345"


# ---------------------------------------------------------------------------
# to_int / to_float
# ---------------------------------------------------------------------------


def test_to_int_handles_string_and_float() -> None:
    """ArcGIS ships ints as floats (1960.0); BAG ships them as strings."""
    assert to_int("1960") == 1960
    assert to_int(1960.0) == 1960
    assert to_int(1960) == 1960


def test_to_int_collapses_empty_to_none() -> None:
    assert to_int(None) is None
    assert to_int("") is None


def test_to_int_returns_none_on_garbage() -> None:
    assert to_int("not a number") is None


def test_to_int_logs_warning_when_logger_passed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tagged logger surfaces the *label* so a bad payload is greppable."""
    log = logging.getLogger(__name__)
    with caplog.at_level(logging.WARNING, logger=log.name):
        result = to_int("garbage", logger=log, label="BAG bouwjaar")
    assert result is None
    assert any("BAG bouwjaar" in r.message for r in caplog.records)


def test_to_float_round_trips_string_and_float() -> None:
    assert to_float("1.5") == 1.5
    assert to_float(1.5) == 1.5
    assert to_float(None) is None
    assert to_float("") is None
    assert to_float("not numeric") is None


# ---------------------------------------------------------------------------
# to_finite_float
# ---------------------------------------------------------------------------


def test_to_finite_float_rejects_nan_and_infinity() -> None:
    """CFTree writes NaN for metrics it could not compute; the GML must
    omit those rather than emit ``<value>NaN</value>``."""
    import math

    assert to_finite_float(math.nan) is None
    assert to_finite_float(math.inf) is None
    assert to_finite_float(-math.inf) is None


def test_to_finite_float_passes_finite_values() -> None:
    assert to_finite_float(12.5) == 12.5
    assert to_finite_float("12.5") == 12.5
    assert to_finite_float(0.0) == 0.0


def test_to_finite_float_collapses_absent() -> None:
    assert to_finite_float(None) is None
    assert to_finite_float("") is None


# ---------------------------------------------------------------------------
# to_clean_str
# ---------------------------------------------------------------------------


def test_to_clean_str_strips_whitespace() -> None:
    assert to_clean_str("  hello  ") == "hello"


def test_to_clean_str_returns_none_for_empty_or_whitespace() -> None:
    assert to_clean_str(None) is None
    assert to_clean_str("") is None
    assert to_clean_str("   \t\n") is None


def test_to_clean_str_default_does_not_drop_literal_none() -> None:
    """BAG flavour: ``"None"`` is preserved so an unexpected sentinel
    value is visible in the output rather than silently swallowed."""
    assert to_clean_str("None") == "None"
    assert to_clean_str("null") == "null"


def test_to_clean_str_with_drop_literal_none_collapses_sentinels() -> None:
    """Emmen flavour: literal placeholders that the ArcGIS Online tenant
    ships for empty cells become Python ``None`` so the GML stays clean."""
    assert to_clean_str("None", drop_literal_none=True) is None
    assert to_clean_str("none", drop_literal_none=True) is None
    assert to_clean_str("NONE", drop_literal_none=True) is None
    assert to_clean_str("null", drop_literal_none=True) is None


# ---------------------------------------------------------------------------
# bbox_cache_key
# ---------------------------------------------------------------------------


def test_bbox_cache_key_clamps_to_two_decimals() -> None:
    """Sub-centimetre rounding drift on the caller side should not
    invalidate an otherwise-fresh cache entry."""
    a = bbox_cache_key("bgt", (267000.001, 537700.0, 267100.0, 537800.0))
    b = bbox_cache_key("bgt", (267000.000, 537700.0, 267100.0, 537800.0))
    assert a == b


def test_bbox_cache_key_distinguishes_pages() -> None:
    a = bbox_cache_key("emmen_bor", (0, 0, 1, 1), page=1)
    b = bbox_cache_key("emmen_bor", (0, 0, 1, 1), page=2)
    assert a != b
    assert a.endswith(".p1")
    assert b.endswith(".p2")


def test_bbox_cache_key_omits_page_segment_when_none() -> None:
    """A non-paginated fetch should not embed a spurious ``.pNone``."""
    key = bbox_cache_key("layer", (0, 0, 1, 1))
    assert ".p" not in key
