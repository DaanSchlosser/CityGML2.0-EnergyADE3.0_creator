"""Parse loosely-formatted Dutch address strings into a structured query.

The address-driven extent accepts the kind of strings a user pastes from
a listing, for example::

    "Annie Romeinsingel 72-152 Leiden"
    "Lange gracht 76-214 Leiden"
    "Etta Palmstraat en Joke Smitstraat z.n. Leiden"

Only the street name(s) and an optional house-number range are extracted
here. The woonplaats / gemeente is left to the geocoder, which resolves
it authoritatively from PDOK rather than from fragile trailing-token
splitting: a place can be multiple words (for example "Den Haag" or
"'s-Hertogenbosch") which a naive last-token rule would mangle. A
best-effort ``place`` string is still returned to bias the geocode
query, but the authoritative name comes back from the geocoder.

The parser locates a "pivot" in the text, the first token that cannot be
part of a street name. The pivot is a house number or range (optionally
carrying a toevoeging letter, so ``Kerkstraat 12A`` resolves), or a "no
number" marker (``z.n.``, the Dutch *zonder nummer*). Everything before
the pivot is the street portion (split on " en " for multi-street
queries) and everything after it is the place.

Three limitations follow from the first-number-wins heuristic and are
left documented rather than worked around. A street name that itself
contains a standalone number (the real square ``Plein 1940``) has that
number taken as the house number. A query with no number and no ``z.n.``
in a multi-word place (``Lange Voorhout Den Haag``) is split by its last
whitespace token, which mangles a multi-word place name; the ``z.n.``
idiom (``Lange Voorhout z.n. Den Haag``) avoids this. A numbered range
selects every house number in the span on both sides of the street,
regardless of even / odd parity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# "z.n." and its spelling variants (zn, z n, z/n), as a whole token.
_ZN_RE = re.compile(r"\bz\.?\s*/?\s*n\.?\b", re.IGNORECASE)
# A house-number range: "72-152", "76 - 214" (hyphen, en dash, or em dash),
# each endpoint optionally carrying a toevoeging letter group ("72A-152B").
# Only the digits are captured; the toevoeging is discarded, because BAG
# selection is by huisnummer and the query's pand is found from the numeric
# value alone.
_RANGE_RE = re.compile(r"(\d+)[a-zA-Z]{0,3}\s*[-–—]\s*(\d+)[a-zA-Z]{0,3}")
# A single house number, optionally with a toevoeging letter group ("12A",
# "12hs"). The trailing letters are part of the pivot, so "12A" is recognised
# as the house number rather than swallowed into the street name, but only the
# digits are kept.
_SINGLE_RE = re.compile(r"\b(\d+)[a-zA-Z]{0,3}\b")
# Multi-street separator: the Dutch "en" surrounded by whitespace.
_SPLIT_STREETS_RE = re.compile(r"\s+en\s+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class AddressQuery:
    """A parsed free-text address query.

    Attributes:
        raw: the original input string, kept verbatim for diagnostics.
        streets: one or more street names, in input order.
        place: best-effort woonplaats / gemeente text, or ``None`` when
            the input carried none. Treat as a hint only; the geocoder
            returns the authoritative name.
        number_low / number_high: inclusive house-number range. Both
            ``None`` for a "z.n." (no number) query, in which case every
            house number on the matched street(s) is in scope. For a
            single number both bounds are equal. The range is parity-blind:
            ``72-152`` covers both the even and the odd side of the street.
    """

    raw: str
    streets: tuple[str, ...]
    place: str | None
    number_low: int | None
    number_high: int | None

    @property
    def has_number_range(self) -> bool:
        """True when the query constrains house numbers (not a "z.n." query)."""
        return self.number_low is not None

    def contains_number(self, number: int) -> bool:
        """Return whether *number* falls within the requested range.

        Always ``True`` for a "z.n." query, which selects the whole
        street rather than a numeric span.
        """
        if self.number_low is None:
            return True
        high = self.number_high if self.number_high is not None else self.number_low
        return self.number_low <= number <= high


def parse_address_query(raw: str) -> AddressQuery:
    """Parse *raw* into an :class:`AddressQuery`.

    Raises :class:`ValueError` when the string is empty or no street name
    can be recovered.
    """
    text = raw.strip()
    if not text:
        raise ValueError("address query is empty")

    zn_match = _ZN_RE.search(text)
    range_match = _RANGE_RE.search(text)
    # Only look for a lone number when there is no range, so the digits
    # inside a range ("72-152") are not also picked up as a single number.
    # Skip a number at the very start of the string (nothing but the number
    # before it): Dutch streets routinely begin with an ordinal token ("1e
    # Binnenvestgracht", "2e Helmersstraat"), which must stay part of the
    # street name, with the real house number taken from later in the string.
    single_match = None
    if not range_match:
        for candidate in _SINGLE_RE.finditer(text):
            if text[: candidate.start()].strip(" ,"):
                single_match = candidate
                break

    number_low: int | None = None
    number_high: int | None = None
    place: str | None
    street_part: str

    pivots = [m for m in (zn_match, range_match, single_match) if m is not None]
    if pivots:
        pivot = min(pivots, key=lambda m: m.start())
        street_part = text[: pivot.start()].strip(" ,")
        place = text[pivot.end() :].strip(" ,.")
        if pivot is range_match:
            low, high = int(range_match.group(1)), int(range_match.group(2))
            number_low, number_high = (low, high) if low <= high else (high, low)
        elif pivot is single_match:
            number_low = number_high = int(single_match.group(1))
        # A "z.n." pivot leaves both bounds None: the whole street is in scope.
    else:
        # No number and no "z.n." marker: assume the last whitespace-separated
        # token is the place and the rest is the street. This is the weakest
        # case; the geocoder still confirms the place.
        head, _, tail = text.rpartition(" ")
        if head:
            street_part, place = head.strip(), tail.strip()
        else:
            street_part, place = text, None

    streets = tuple(part.strip() for part in _SPLIT_STREETS_RE.split(street_part) if part.strip())
    if not streets:
        raise ValueError(f"could not extract a street name from {raw!r}")

    return AddressQuery(
        raw=raw,
        streets=streets,
        place=place or None,
        number_low=number_low,
        number_high=number_high,
    )
