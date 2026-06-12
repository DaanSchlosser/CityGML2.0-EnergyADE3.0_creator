"""Canonical normalisation for Dutch address keys.

The matching pipeline joins BAG verblijfsobjecten to EP-online labels on
two keys:

* ``bag_verblijfsobject_id``: the BAG identificatie, used when EP-online
  (v5+) enriches labels with it. Plain string equality.
* ``(postcode, huisnummer, huisletter, toevoeging)``: the address-tuple
  fallback for labels that predate the BAG-id enrichment.

Three places compute or compare these keys: the EP-online CSV parser, the
pipeline's fetcher-filter set, and the in-memory address matcher. All
three route through this module so the BAG and EP-online spellings cannot
drift; slightly-different ``_strip_upper`` copies would silently cause
joins to miss, which is exactly the failure mode we want designed out.

Hot-path note: :func:`normalise_postcode` is called once per CSV row
(~5 M calls on the production EP-online file). Both normalisers
short-circuit the already-clean case (alphanumeric and already
upper-cased, checked with one C-level ``isalnum`` pass) before falling
through to the generic strip-all-whitespace path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fetchers.bag import Verblijfsobject


AddressKey = tuple[str, int, str | None, str | None]


def normalise_postcode(raw: Any) -> str:
    """Return *raw* upper-cased with all whitespace stripped.

    Empty / falsy input returns ``""``. Accepts any stringifiable value so
    the EP-online parser can feed CSV cells directly.
    """
    if not raw:
        return ""
    if isinstance(raw, str):
        # ``isalnum`` is one C-level pass and excludes *all* whitespace
        # (space, tab, CR, …), so the fast path can never disagree with
        # the strip-everything slow path below — the literal ``" " not
        # in raw`` check it replaces let a stray tab/CR ride through.
        if raw.isalnum():
            return raw if raw.isupper() else raw.upper()
        return "".join(raw.split()).upper()
    return "".join(str(raw).split()).upper()


def normalise_letter(raw: str | None) -> str | None:
    """Upper-case *raw* and trim whitespace; empty/``None`` returns ``None``.

    Shared between ``huisletter`` and ``huisnummertoevoeging``: both follow
    the same "single upper token or nothing" rule.
    """
    if raw is None:
        return None
    # Fast path mirrors :func:`normalise_postcode`: alphanumeric (so no
    # whitespace anywhere, not just no literal space at the ends) and
    # already upper-cased.
    if raw and raw.isalnum() and raw.isupper():
        return raw
    trimmed = raw.strip().upper()
    return trimmed or None


def address_key(
    postcode: Any,
    huisnummer: int,
    huisletter: str | None,
    toevoeging: str | None,
) -> AddressKey:
    """Return the canonical :data:`AddressKey` tuple.

    Every field is pushed through the appropriate normaliser so callers
    can pass raw BAG / EP-online values directly.
    """
    return (
        normalise_postcode(postcode),
        huisnummer,
        normalise_letter(huisletter),
        normalise_letter(toevoeging),
    )


def address_key_from_vbo(vbo: Verblijfsobject) -> AddressKey:
    """Return the :data:`AddressKey` for a BAG :class:`Verblijfsobject`.

    ``vbo.huisnummer`` being ``None`` is tolerated (defaults to ``0``) so
    this function is safe to call on un-filtered VBO lists; the resulting
    key will not match any EP-online label, which is the desired
    behaviour for an unaddressable VBO.
    """
    return address_key(
        vbo.postcode or "",
        vbo.huisnummer or 0,
        vbo.huisletter,
        vbo.toevoeging,
    )
