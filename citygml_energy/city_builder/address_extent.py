"""Resolve a free-text address into a centred fetch extent and targets.

This is the core of the address-driven input method. Given a string like
``"Annie Romeinsingel 72-152 Leiden"`` it produces:

* a square fetch ``bbox`` in EPSG:28992, ``extent_m`` on a side, centred
  on the middle of the matched buildings;
* the set of BAG pand identifiers the query addresses, so the appearance
  step can paint them distinctly from their surroundings;
* the authoritative gemeente / woonplaats name from the geocoder.

The resolution splits the work between two services by what each does
well. PDOK Locatieserver (fuzzy, relevance-ranked) supplies only a coarse
anchor coordinate and the place name. The authoritative BAG WFS then
decides exactly which addresses, and therefore which panden, the query
covers: VBOs are fetched in a small seed bbox around the anchor and
selected by normalised street name and house-number range. This avoids
trusting the fuzzy geocoder for the membership decision while still
letting it handle the messy free-text parsing of the place.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass

from .address_query import AddressQuery, parse_address_query
from .fetchers import locatieserver
from .fetchers.bag import Verblijfsobject, fetch_verblijfsobjecten
from .http import CachedSession

_LOG = logging.getLogger(__name__)

# Padding added around the geocoded anchor point(s) to form the seed bbox
# in which BAG VBOs are fetched for address selection. Large enough to
# absorb the offset between Locatieserver's address point and the BAG
# verblijfsobjectpunt, and to span a short terrace, without pulling in a
# whole neighbourhood.
DEFAULT_SEED_BUFFER_M = 80.0

# Default side length of the final square extent, in metres.
DEFAULT_EXTENT_M = 500.0


class AddressResolutionError(RuntimeError):
    """Raised when an address query cannot be resolved to any building."""


@dataclass(frozen=True, slots=True)
class AddressResolution:
    """The outcome of resolving an address query to a fetch extent.

    Attributes:
        bbox: ``(minx, miny, maxx, maxy)`` in EPSG:28992, square and
            centred on :attr:`center`.
        center: ``(x, y)`` the box is centred on, the mean of the matched
            buildings' centroids (each building's own VBO points are
            averaged first, so a multi-unit building does not bias the
            centre). Falls back to the geocode anchor points when no
            matched VBO carried a geometry.
        target_pand_ids: BAG pand identifiers the query addresses.
        municipality: gemeente name from the geocoder, or ``None``.
        woonplaats: woonplaats name from the geocoder, or ``None``.
        matched_addresses: how many VBOs were selected (diagnostics).
        query: the parsed query, retained for logging and tests.
    """

    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    target_pand_ids: frozenset[str]
    municipality: str | None
    woonplaats: str | None
    matched_addresses: int
    query: AddressQuery


def normalise_street(name: str) -> str:
    """Return a comparison key for a street name.

    Lower-cases, strips diacritics, and removes every non-alphanumeric
    character, so a user's "Lange gracht" matches BAG's "Langegracht" and
    casing or punctuation differences never split a match.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(ch for ch in stripped.lower() if ch.isalnum())


# Colloquial place names whose official BAG woonplaats differs. The geocoder
# returns the official name, so a user's everyday spelling has to be mapped
# before comparison or a perfectly valid address is rejected: "Den Haag" is the
# woonplaats "'s-Gravenhage", "Den Bosch" is "'s-Hertogenbosch". The place is
# only a hint, so this never accepts a genuinely different town (a Delft hit for
# a Leiden query still fails), it only bridges the alias spellings of one place.
_PLACE_ALIASES: dict[str, str] = {
    normalise_street("Den Haag"): normalise_street("'s-Gravenhage"),
    normalise_street("Den Bosch"): normalise_street("'s-Hertogenbosch"),
}


def _acceptable_place_keys(normalised_place: str) -> set[str]:
    """Normalised place keys that satisfy *normalised_place*: itself + any alias."""
    keys = {normalised_place}
    alias = _PLACE_ALIASES.get(normalised_place)
    if alias:
        keys.add(alias)
    return keys


def _probe_addresses(query: AddressQuery) -> list[tuple[str, int | None]]:
    """Pick the (street, number) probes used to anchor the seed bbox.

    For a numbered query the range endpoints anchor both ends of a
    terrace; for a "z.n." query each street is probed without a number.
    """
    probes: list[tuple[str, int | None]] = []
    for street in query.streets:
        if query.number_low is None:
            probes.append((street, None))
        else:
            probes.append((street, query.number_low))
            if query.number_high is not None and query.number_high != query.number_low:
                probes.append((street, query.number_high))
    return probes


def _street_variants(street: str) -> list[str]:
    """Return search spellings to try for *street*.

    Dutch street names are routinely written either spaced or
    concatenated ("Lange gracht" vs the official "Langegracht"). The
    fuzzy ``free`` search ranks by token, so a stray space can bury the
    real street under unrelated same-token streets ("Lange Mare"). Trying
    a space-collapsed variant recovers those without affecting names that
    are legitimately spaced (for example "Annie Romeinsingel"), because
    the verified-match check below accepts either spelling.
    """
    variants = [street]
    despaced = street.replace(" ", "")
    if despaced and despaced != street:
        variants.append(despaced)
    return variants


def _place_matches(hit: locatieserver.GeocodeHit, wanted_place: str | None) -> bool:
    """Whether *hit* sits in the requested place (woonplaats or gemeente).

    Comparison is alias-aware, so a colloquial place hint ("Den Haag") matches
    the geocoder's official woonplaats ("'s-Gravenhage"); see
    :data:`_PLACE_ALIASES`.
    """
    if not wanted_place:
        return True
    acceptable = _acceptable_place_keys(wanted_place)
    for name in (hit.woonplaatsnaam, hit.gemeentenaam):
        if name and normalise_street(name) in acceptable:
            return True
    # When the hit carries no place at all we cannot contradict the
    # request, so we do not reject it on that basis.
    return not (hit.woonplaatsnaam or hit.gemeentenaam)


def _best_hit(
    session: CachedSession,
    street: str,
    number: int | None,
    place: str | None,
) -> locatieserver.GeocodeHit | None:
    """Geocode one probe and return a hit whose street verifies, or ``None``.

    The ``free`` endpoint is fuzzy, so a returned document is accepted
    only when its street (and place, when known) matches the request.
    Several search spellings are tried (see :func:`_street_variants`). No
    unverified top-ranked fallback is used: a wrong anchor would seed the
    wrong area, and BAG, not the geocoder, is the source of truth for
    membership, so an unresolvable probe is better reported than guessed.
    """
    wanted_street = normalise_street(street)
    wanted_place = normalise_street(place) if place else None
    type_filters: tuple[str, ...] = ("adres",) if number is not None else ("weg", "adres")

    for variant in _street_variants(street):
        parts = [variant, str(number) if number is not None else "", place or ""]
        text = " ".join(part for part in parts if part).strip()
        for type_filter in type_filters:
            hits = locatieserver.geocode_free(session, text, type_filter=type_filter, rows=15)
            for hit in hits:
                if not hit.straatnaam or normalise_street(hit.straatnaam) != wanted_street:
                    continue
                if not _place_matches(hit, wanted_place):
                    continue
                return hit
    _LOG.warning("No verified geocode match for street %r in %r", street, place)
    return None


def _seed_bbox(
    points: list[tuple[float, float]],
    buffer_m: float,
) -> tuple[float, float, float, float]:
    """Return the bounds of *points* padded by *buffer_m* on every side."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) - buffer_m, min(ys) - buffer_m, max(xs) + buffer_m, max(ys) + buffer_m)


def _select_targets(
    vbos: list[Verblijfsobject],
    query: AddressQuery,
) -> tuple[set[str], dict[str, list[tuple[float, float]]], int]:
    """Select the VBOs matching the query.

    Returns the matched pand identifiers, the matched VBO geometry points
    grouped by pand (so the box can be centred per building rather than per
    VBO, see :func:`resolve_address_extent`), and the count of matched VBOs.
    A pand with no geometry on any of its VBOs is still in the id set but
    absent from the points dict.
    """
    wanted_streets = {normalise_street(s) for s in query.streets}
    target_pand_ids: set[str] = set()
    points_by_pand: dict[str, list[tuple[float, float]]] = {}
    matched_count = 0
    for vbo in vbos:
        if not vbo.openbare_ruimte_naam:
            continue
        if normalise_street(vbo.openbare_ruimte_naam) not in wanted_streets:
            continue
        if vbo.huisnummer is None:
            # A numbered query needs a number to compare against; skip
            # numberless VBOs. A "z.n." query keeps them.
            if query.has_number_range:
                continue
        elif not query.contains_number(vbo.huisnummer):
            continue
        target_pand_ids.add(vbo.pand_identificatie)
        matched_count += 1
        if vbo.point is not None:
            points_by_pand.setdefault(vbo.pand_identificatie, []).append(vbo.point)
    return target_pand_ids, points_by_pand, matched_count


def resolve_address_extent(
    session: CachedSession,
    raw_query: str,
    *,
    extent_m: float = DEFAULT_EXTENT_M,
    seed_buffer_m: float = DEFAULT_SEED_BUFFER_M,
) -> AddressResolution:
    """Resolve *raw_query* into a centred :class:`AddressResolution`.

    Raises :class:`AddressResolutionError` when no anchor can be geocoded
    or no matching building is found in BAG.
    """
    query = parse_address_query(raw_query)
    _LOG.info(
        "Resolving address query: streets=%s numbers=%s place=%r",
        list(query.streets),
        (query.number_low, query.number_high) if query.has_number_range else "z.n.",
        query.place,
    )

    anchor_points: list[tuple[float, float]] = []
    municipality: str | None = None
    woonplaats: str | None = None
    for street, number in _probe_addresses(query):
        hit = _best_hit(session, street, number, query.place)
        if hit is None:
            continue
        anchor_points.append(hit.point_rd)
        municipality = municipality or hit.gemeentenaam
        woonplaats = woonplaats or hit.woonplaatsnaam
    if not anchor_points:
        raise AddressResolutionError(f"could not geocode any anchor for {raw_query!r}")
    if not query.place:
        _LOG.warning(
            "Address query %r names no place; the geocoder's best hit in "
            "gemeente %s was taken. Add a place name (woonplaats or gemeente) "
            "to the query to disambiguate same-named streets elsewhere.",
            raw_query,
            municipality or woonplaats or "unknown",
        )

    # A range normally anchors both endpoints, so their span sets the seed
    # extent. When only one endpoint of a *true* range geocoded (the other house
    # number does not exist), widen the buffer so the rest of the run is still
    # covered. A single-house query (low == high) is not a range and must keep
    # the default buffer, not fetch a needlessly large seed bbox.
    is_true_range = query.number_high is not None and query.number_high != query.number_low
    buffer = seed_buffer_m
    if is_true_range and len(anchor_points) < 2:
        buffer = max(buffer, 250.0)
    seed = _seed_bbox(anchor_points, buffer)
    _LOG.info("Seed bbox for BAG address selection: %s", seed)
    vbos = fetch_verblijfsobjecten(session, bbox=seed)
    target_pand_ids, points_by_pand, matched_count = _select_targets(vbos, query)

    if not target_pand_ids:
        raise AddressResolutionError(
            f"geocoded {raw_query!r} but found no BAG address matching "
            f"street(s) {list(query.streets)} in the resolved area"
        )

    # Centre on the matched buildings' middle: average each pand's VBO
    # points into a per-pand centroid first, then average those, so a pand
    # with many units (an apartment block) does not pull the box toward
    # itself the way a per-VBO mean would. Fall back to the anchor points
    # only when no matched VBO carried a geometry.
    pand_centroids = [
        (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
        for pts in points_by_pand.values()
    ]
    centre_points = pand_centroids or anchor_points
    cx = sum(p[0] for p in centre_points) / len(centre_points)
    cy = sum(p[1] for p in centre_points) / len(centre_points)
    half = extent_m / 2.0
    bbox = (cx - half, cy - half, cx + half, cy + half)
    _LOG.info(
        "Matched %d address(es) across %d pand(en); centre=(%.2f, %.2f)",
        matched_count,
        len(target_pand_ids),
        cx,
        cy,
    )

    return AddressResolution(
        bbox=bbox,
        center=(cx, cy),
        target_pand_ids=frozenset(target_pand_ids),
        municipality=municipality,
        woonplaats=woonplaats,
        matched_addresses=matched_count,
        query=query,
    )
