"""Join BAG VBO addresses to EP-online labels.

All matching is local, keyed by the normalised
``(postcode, huisnummer, huisletter, toevoeging)`` tuple. BAG is the
source of truth for addresses; EP-online is joined **into** the VBO
set and missing labels simply leave the VBO without an EPC record.

Address data (street, postcode, huisnummer) is embedded directly in the
PDOK BAG WFS VBO response — no separate Nummeraanduiding or
OpenbareRuimte fetches are needed.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def match_addresses(
    *,
    vbos: list[Verblijfsobject],
    energy_labels: list[EnergyLabel] | None = None,
) -> dict[str, list[ResolvedAddress]]:
    """Return ``{pand_id: [ResolvedAddress, ...]}`` — VBOs grouped by Pand.

    Matching strategy (in priority order):

    1. ``BAGVerblijfsobjectID`` — direct BAG VBO id match. Available in
       EP-online v5+ CSV; far more reliable than address-key matching and
       covers institutions/university buildings that have irregular addresses.
    2. ``(postcode, huisnummer, huisletter, toevoeging)`` — address-key
       fallback for labels that predate the BAG-id enrichment.

    VBOs that lack a postcode or huisnummer are silently dropped — they
    cannot produce a valid CityGML ``bldg:address``.
    """
    labels_by_vbo_id, labels_by_key = _index_labels(energy_labels or [])

    grouped: dict[str, list[ResolvedAddress]] = {}
    for vbo in vbos:
        if vbo.postcode is None or vbo.huisnummer is None:
            continue
        label = (
            labels_by_vbo_id.get(vbo.identificatie)
            or labels_by_key.get(_address_key_from_vbo(vbo))
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
) -> tuple[
    dict[str, EnergyLabel],
    dict[tuple[str, int, str | None, str | None], EnergyLabel],
]:
    """Return ``(by_vbo_id, by_address_key)`` — most recent label per key.

    EP-online can ship multiple labels for one address (re-registration,
    corrections). We keep the one with the newest ``registratiedatum``,
    falling back to ``opnamedatum``.

    ``by_vbo_id`` is keyed by ``BAGVerblijfsobjectID`` (EP-online v5+).
    ``by_address_key`` is the ``(postcode, huisnummer, huisletter,
    toevoeging)`` fallback for older labels without a BAG id.
    """
    by_vbo_id: dict[str, EnergyLabel] = {}
    by_address_key: dict[tuple[str, int, str | None, str | None], EnergyLabel] = {}
    for label in labels:
        ts = _label_timestamp(label)
        if label.bag_verblijfsobject_id:
            incumbent = by_vbo_id.get(label.bag_verblijfsobject_id)
            if incumbent is None or ts >= _label_timestamp(incumbent):
                by_vbo_id[label.bag_verblijfsobject_id] = label
        key = label.address_key()
        incumbent_key = by_address_key.get(key)
        if incumbent_key is None or ts >= _label_timestamp(incumbent_key):
            by_address_key[key] = label
    return by_vbo_id, by_address_key


def _label_timestamp(label: EnergyLabel) -> tuple[int, int, int]:
    """Ordering key — ``(registratiedatum, opnamedatum, reg != None)``."""
    reg = label.registratiedatum
    opname = label.opnamedatum
    return (
        reg.toordinal() if reg else 0,
        opname.toordinal() if opname else 0,
        1 if reg else 0,
    )


def _address_key_from_vbo(
    vbo: Verblijfsobject,
) -> tuple[str, int, str | None, str | None]:
    postcode = (vbo.postcode or "").replace(" ", "").upper()
    huisnummer = vbo.huisnummer or 0
    huisletter = _strip_upper(vbo.huisletter)
    toevoeging = _strip_upper(vbo.toevoeging)
    return (postcode, huisnummer, huisletter, toevoeging)


def _strip_upper(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip().upper()
    return trimmed or None
