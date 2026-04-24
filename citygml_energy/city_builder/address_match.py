"""Join BAG VBO addresses to EP-online labels.

All matching is local, keyed by the normalised
``(postcode, huisnummer, huisletter, toevoeging)`` tuple. BAG is the
source of truth for addresses; EP-online is joined **into** the VBO
set and missing labels simply leave the VBO without an EPC record.

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
    def point(self) -> tuple[float, float] | None:
        return self.vbo.point


def match_addresses(
    *,
    vbos: list[Verblijfsobject],
    energy_labels: list[EnergyLabel] | None = None,
) -> dict[str, list[ResolvedAddress]]:
    """Return ``{pand_id: [ResolvedAddress, ...]}``: VBOs grouped by Pand.

    Matching strategy (in priority order):

    1. ``BAGVerblijfsobjectID``: direct BAG VBO id match. Available in
       EP-online v5+ CSV, far more reliable than address-key matching and
       covers institutions/university buildings that have irregular addresses.
    2. ``(postcode, huisnummer, huisletter, toevoeging)``: address-key
       fallback for labels that predate the BAG-id enrichment.

    VBOs that lack a postcode or huisnummer are silently dropped: they
    cannot produce a valid CityGML ``bldg:address``.
    """
    # Only the VBOs that can match are addressable; dropping the rest up
    # front means we can build a *tight* wanted-key set for the label
    # filter. With 5M+ labels and ~500 VBOs, that filter turns the label
    # scan from "index everything" to "keep ~0.01% of rows".
    matchable = [v for v in vbos if v.postcode is not None and v.huisnummer is not None]
    wanted_ids = {v.identificatie for v in matchable}
    wanted_keys = {address_key_from_vbo(v) for v in matchable}

    labels_by_vbo_id, labels_by_key = _index_labels(
        energy_labels or [],
        wanted_ids=wanted_ids,
        wanted_keys=wanted_keys,
    )

    grouped: dict[str, list[ResolvedAddress]] = {}
    for vbo in matchable:
        label = (
            labels_by_vbo_id.get(vbo.identificatie)
            or labels_by_key.get(address_key_from_vbo(vbo))
        )
        grouped.setdefault(vbo.pand_identificatie, []).append(
            ResolvedAddress(vbo=vbo, energy_label=label)
        )
    return grouped


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _index_labels(
    labels: list[EnergyLabel],
    *,
    wanted_ids: set[str],
    wanted_keys: set[AddressKey],
) -> tuple[dict[str, EnergyLabel], dict[AddressKey, EnergyLabel]]:
    """Return ``(by_vbo_id, by_address_key)``: most recent label per key.

    EP-online can ship multiple labels for one address (re-registration,
    corrections). We keep the one with the newest ``registratiedatum``,
    falling back to ``opnamedatum``.

    Only labels whose ``bag_verblijfsobject_id`` matches *wanted_ids* or
    whose address-key matches *wanted_keys* are retained. This membership
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
        hit_id = vbo_id is not None and vbo_id in wanted_ids
        key = label.address_key()
        hit_key = key in wanted_keys
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


def _label_timestamp(label: EnergyLabel) -> tuple[int, int, int]:
    """Ordering key: ``(registratiedatum, opnamedatum, reg != None)``."""
    reg = label.registratiedatum
    opname = label.opnamedatum
    return (
        reg.toordinal() if reg else 0,
        opname.toordinal() if opname else 0,
        1 if reg else 0,
    )
