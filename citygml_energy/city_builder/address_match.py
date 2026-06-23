"""Join BAG VBO addresses to EP-online labels.

All matching is local. Every VBO is matched primarily on its BAG
``verblijfsobject_id`` (the EP-online v5+ ``BAGVerblijfsobjectID``), with
the normalised ``(postcode, huisnummer, huisletter, toevoeging)`` tuple
as the fallback for labels that predate that enrichment. BAG is the
source of truth for addresses; EP-online is joined **into** the VBO set
and missing labels simply leave the VBO without an EPC record. Every VBO
is emitted as a BuildingUnit regardless of its address (ADR-0005); the
matcher never drops one.

Address data (street, postcode, huisnummer) is embedded directly in the
PDOK BAG WFS VBO response, so no separate Nummeraanduiding or
OpenbareRuimte fetches are needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .address_key import AddressKey, address_key_from_vbo
from .fetchers.bag import Verblijfsobject
from .fetchers.eponline import EnergyLabel


@dataclass(frozen=True)
class ResolvedAddress:
    """A VBO with its matched EP-online energy label (when found)."""

    vbo: Verblijfsobject
    energy_label: EnergyLabel | None

    @property
    def street(self) -> str:
        return self.vbo.openbare_ruimte_naam or ""

    @property
    def postcode(self) -> str:
        return self.vbo.postcode or ""

    @property
    def huisnummer(self) -> int | None:
        return self.vbo.huisnummer

    @property
    def huisletter(self) -> str | None:
        return self.vbo.huisletter

    @property
    def toevoeging(self) -> str | None:
        return self.vbo.toevoeging

    @property
    def woonplaats(self) -> str | None:
        """BAG locality (``woonplaats``); may differ from gemeente."""
        return self.vbo.woonplaats

    @property
    def point(self) -> tuple[float, float] | None:
        return self.vbo.point


@dataclass(frozen=True)
class LabelFilter:
    """The EP-online row filter for a VBO set.

    ``ids`` holds the BAG VBO id of *every* VBO (the EP-online v5+
    ``BAGVerblijfsobjectID`` match): every VBO carries one and the id
    match is primary, so a label can be fetched for any unit the register
    holds one for. ``keys`` holds the normalised address-key fallback,
    built only from the *address-key VBOs* (those with both a postcode and
    a huisnummer), since a partial address cannot form a usable key. A
    label survives the CSV filter when it matches either set, mirroring
    the two-key join in :func:`match_addresses`. Frozensets keep the
    filter hashable and order-independent; the pipeline's filtered-labels
    cache digest relies on that.
    """

    ids: frozenset[str]
    keys: frozenset[AddressKey]


def wanted_label_filter(vbos: list[Verblijfsobject]) -> LabelFilter:
    """Return the :class:`LabelFilter` for *vbos*.

    The ``ids`` set covers every VBO, because every VBO has a BAG id and
    the id match is primary, so a label can be fetched for any unit the
    register holds one for. The ``keys`` set covers only the address-key
    VBOs, because a VBO without a postcode or huisnummer cannot form a
    usable address key. This is the only place the wanted sets are built;
    the fetch filter and the join sharing one definition is the point of
    this function.
    """
    return LabelFilter(
        ids=frozenset(v.identificatie for v in vbos),
        keys=frozenset(address_key_from_vbo(v) for v in _address_key_vbos(vbos)),
    )


def match_addresses(
    *,
    vbos: list[Verblijfsobject],
    energy_labels: list[EnergyLabel] | None = None,
) -> dict[str, list[ResolvedAddress]]:
    """Return ``{pand_id: [ResolvedAddress, ...]}``: every VBO grouped by Pand.

    Every VBO becomes one :class:`ResolvedAddress`, keyed by its BAG
    ``verblijfsobject_id``; none is dropped for a missing or partial
    address (ADR-0005). A VBO such as a garage or storage box that carries
    no postcode is still emitted, simply with no energy label unless it
    matches by BAG id.

    Matching strategy (in priority order):

    1. ``BAGVerblijfsobjectID``: direct BAG VBO id match. Available in
       EP-online v5+ CSV, far more reliable than address-key matching, and
       covers every VBO, including institutions and address-incomplete
       units that have no usable address key.
    2. ``(postcode, huisnummer, huisletter, toevoeging)``: address-key
       fallback for labels that predate the BAG-id enrichment. Only the
       address-key VBOs take part; an address-incomplete VBO is never
       given a label by a partial-address guess.
    """
    # The id set covers every VBO, the key set only the address-key ones.
    # With 5M+ labels and ~500 VBOs, that filter still turns the label
    # scan from "index everything" to "keep ~0.01% of rows".
    labels_by_vbo_id, labels_by_key = _index_labels(
        energy_labels or [],
        wanted=wanted_label_filter(vbos),
    )

    grouped: dict[str, list[ResolvedAddress]] = {}
    for vbo in vbos:
        label = labels_by_vbo_id.get(vbo.identificatie)
        if label is None and _is_address_key_vbo(vbo):
            label = labels_by_key.get(address_key_from_vbo(vbo))
        grouped.setdefault(vbo.pand_identificatie, []).append(
            ResolvedAddress(vbo=vbo, energy_label=label)
        )
    return grouped


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _is_address_key_vbo(vbo: Verblijfsobject) -> bool:
    """True when *vbo* has both a postcode and a huisnummer.

    Only such a VBO can form a usable ``(postcode, huisnummer, ...)``
    address key, so only it takes part in the EP-online address-key
    fallback. The predicate gates that fallback alone, never whether the
    VBO is emitted as a BuildingUnit (see ADR-0005 and the "Address-key
    VBO" entry in ``CONTEXT.md``).
    """
    return vbo.postcode is not None and vbo.huisnummer is not None


def _address_key_vbos(vbos: list[Verblijfsobject]) -> list[Verblijfsobject]:
    """The VBOs that can take part in the address-key fallback."""
    return [v for v in vbos if _is_address_key_vbo(v)]


def _index_labels(
    labels: list[EnergyLabel],
    *,
    wanted: LabelFilter,
) -> tuple[dict[str, EnergyLabel], dict[AddressKey, EnergyLabel]]:
    """Return ``(by_vbo_id, by_address_key)``: most recent label per key.

    EP-online can ship multiple labels for one address (re-registration,
    corrections). We keep the one with the newest ``registratiedatum``,
    falling back to ``opnamedatum``.

    Only labels whose ``bag_verblijfsobject_id`` matches ``wanted.ids`` or
    whose address-key matches ``wanted.keys`` are retained. This membership
    test turns what was a full 5M-row indexing pass into a filter, which
    is critical for the city-pipeline case where the BBOX covers a few
    hundred VBOs out of the national mutation file.

    ``by_vbo_id`` is keyed by ``BAGVerblijfsobjectID`` (EP-online v5+).
    ``by_address_key`` is the ``(postcode, huisnummer, huisletter,
    toevoeging)`` fallback for older labels without a BAG id.
    """
    by_vbo_id: dict[str, EnergyLabel] = {}
    by_address_key: dict[AddressKey, EnergyLabel] = {}
    for label in labels:
        vbo_id = label.bag_verblijfsobject_id
        hit_id = vbo_id is not None and vbo_id in wanted.ids
        key = label.address_key()
        hit_key = key in wanted.keys
        if not hit_id and not hit_key:
            continue

        # A label can be relevant via both indices, e.g. one VBO matches
        # by BAG id and a different VBO with the same address-key matches
        # by key. Mirror the original behaviour and update both indices
        # independently.
        ts = _label_timestamp(label)
        if hit_id:
            # ``hit_id`` is only True when ``vbo_id is not None``; reassert
            # for the type checker so the dict access below narrows cleanly.
            assert vbo_id is not None
            incumbent = by_vbo_id.get(vbo_id)
            if incumbent is None or ts >= _label_timestamp(incumbent):
                by_vbo_id[vbo_id] = label
        if hit_key:
            incumbent_key = by_address_key.get(key)
            if incumbent_key is None or ts >= _label_timestamp(incumbent_key):
                by_address_key[key] = label
    return by_vbo_id, by_address_key


def _label_timestamp(label: EnergyLabel) -> tuple[int, int]:
    """Ordering key: ``(registratiedatum, opnamedatum)``.

    Changing this ordering can silently flip which calculation regime
    gets emitted on the BuildingUnit (NTA 8800 vs legacy NEN-7120).
    Label selection (here) is kept separate from regime-aware resource
    emission (in :mod:`energy_resources`); the cross-module invariant
    is captured by tests in ``tests/test_city_address_match.py``.

    Missing dates collapse to ``0``, which is below every real
    ``date.toordinal()`` (minimum is 1), so a label with reg set always
    outranks one without on the first axis without needing a third
    "has_reg" element.
    """
    reg = label.registratiedatum
    opname = label.opnamedatum
    return (
        reg.toordinal() if reg else 0,
        opname.toordinal() if opname else 0,
    )
