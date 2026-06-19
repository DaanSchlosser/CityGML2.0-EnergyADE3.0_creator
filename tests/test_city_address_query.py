"""Tests for the free-text address-query parser.

Covers the formats a user pastes from a listing: a single house, a
house-number range, a "z.n." (no number) query, and several streets
joined with "en", plus the spacing and place quirks the parser must
tolerate.
"""

from __future__ import annotations

import pytest

from citygml_energy.city_builder.address_query import parse_address_query


def test_parses_house_number_range() -> None:
    q = parse_address_query("Annie Romeinsingel 72-152 Leiden")
    assert q.streets == ("Annie Romeinsingel",)
    assert q.number_low == 72
    assert q.number_high == 152
    assert q.place == "Leiden"
    assert q.has_number_range is True


def test_parses_single_house_number() -> None:
    q = parse_address_query("Langegracht 76 Leiden")
    assert q.streets == ("Langegracht",)
    assert q.number_low == 76
    assert q.number_high == 76
    assert q.contains_number(76) is True
    assert q.contains_number(77) is False


def test_parses_zonder_nummer_multi_street() -> None:
    q = parse_address_query("Etta Palmstraat  en Joke Smitstraat z.n. Leiden")
    assert q.streets == ("Etta Palmstraat", "Joke Smitstraat")
    assert q.number_low is None
    assert q.number_high is None
    assert q.has_number_range is False
    # A "z.n." query selects the whole street, so every number is in scope.
    assert q.contains_number(1) is True
    assert q.contains_number(999) is True
    assert q.place == "Leiden"


def test_keeps_two_word_street_with_space() -> None:
    # The street name itself has a space; only the range is the pivot.
    q = parse_address_query("Lange gracht 76-214 Leiden")
    assert q.streets == ("Lange gracht",)
    assert q.number_low == 76
    assert q.number_high == 214


def test_range_endpoints_are_normalised_low_to_high() -> None:
    q = parse_address_query("Voorstraat 200-100 Utrecht")
    assert q.number_low == 100
    assert q.number_high == 200


def test_no_pivot_falls_back_to_last_token_as_place() -> None:
    q = parse_address_query("Stationsweg Leiden")
    assert q.streets == ("Stationsweg",)
    assert q.place == "Leiden"
    assert q.has_number_range is False


def test_parses_house_number_with_toevoeging_letter() -> None:
    # The Dutch toevoeging form "12A" (no space) must be recognised as the
    # house number, not swallowed into the street name. Regression for the
    # \b(\d+)\b pivot, which never matched a digit-then-letter token.
    q = parse_address_query("Kerkstraat 12A Leiden")
    assert q.streets == ("Kerkstraat",)
    assert q.number_low == 12
    assert q.number_high == 12
    assert q.place == "Leiden"


def test_parses_range_with_toevoeging_endpoints() -> None:
    q = parse_address_query("Damstraat 72A-152B Amsterdam")
    assert q.streets == ("Damstraat",)
    assert q.number_low == 72
    assert q.number_high == 152
    assert q.place == "Amsterdam"


def test_embedded_street_number_is_taken_as_house_number() -> None:
    # Documented limitation: a street name with a standalone number ("Plein
    # 1940") has that number read as the house number by the first-number
    # heuristic. Pinned so the behaviour is a conscious choice, not a regression.
    q = parse_address_query("Plein 1940 Rotterdam")
    assert q.streets == ("Plein",)
    assert q.number_low == 1940
    assert q.place == "Rotterdam"


def test_leading_ordinal_street_with_single_number() -> None:
    # Dutch streets often begin with an ordinal ("1e Binnenvestgracht"). The
    # leading "1e" must stay in the street, with the real house number taken
    # from later in the string, not parsed as the house number (which left an
    # empty street and raised ValueError).
    q = parse_address_query("1e Binnenvestgracht 5 Leiden")
    assert q.streets == ("1e Binnenvestgracht",)
    assert q.number_low == 5
    assert q.number_high == 5
    assert q.place == "Leiden"


def test_leading_ordinal_street_with_range() -> None:
    # The range arm already worked (the range pre-empts the single-number
    # search); pinned alongside the single-number arm so both stay consistent.
    q = parse_address_query("2e Helmersstraat 10-20 Amsterdam")
    assert q.streets == ("2e Helmersstraat",)
    assert q.number_low == 10
    assert q.number_high == 20
    assert q.place == "Amsterdam"


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_query_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_address_query(bad)
