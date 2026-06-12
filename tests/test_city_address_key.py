"""Unit tests for the canonical address-key normalisers.

The fast paths in :func:`normalise_postcode` / :func:`normalise_letter`
short-circuit the already-clean spelling for the ~5 M-row EP-online
scan. These tests pin the invariant the module exists for: the fast and
slow paths can never disagree. The original fast paths checked only for
literal spaces, so a stray tab/CR rode through unstripped — exactly the
"two spellings of the same key" drift the module docstring promises to
design out.
"""

from __future__ import annotations

from citygml_energy.city_builder.address_key import (
    address_key,
    normalise_letter,
    normalise_postcode,
)


def test_normalise_postcode_clean_value_is_identity() -> None:
    assert normalise_postcode("1234AB") == "1234AB"


def test_normalise_postcode_strips_all_whitespace_kinds() -> None:
    assert normalise_postcode("1234 AB") == "1234AB"
    assert normalise_postcode("1234AB\t") == "1234AB"
    assert normalise_postcode("1234ab\r") == "1234AB"
    assert normalise_postcode(" 1234 ab\n") == "1234AB"


def test_normalise_postcode_fast_path_agrees_with_generic_path() -> None:
    """One spelling per input, regardless of which code path handles it."""
    for raw in ("1234AB", "1234ab", "1234 AB", "1234AB\t", "\r1234ab", "12 34 ab"):
        assert normalise_postcode(raw) == "".join(str(raw).split()).upper()


def test_normalise_letter_trims_and_uppercases() -> None:
    assert normalise_letter("A") == "A"
    assert normalise_letter("a") == "A"
    assert normalise_letter("A\t") == "A"
    assert normalise_letter(" bis\r") == "BIS"
    assert normalise_letter("  ") is None
    assert normalise_letter(None) is None
    assert normalise_letter("") is None


def test_address_key_normalises_every_component() -> None:
    assert address_key("1234 ab\t", 7, "a\r", " bis ") == ("1234AB", 7, "A", "BIS")
