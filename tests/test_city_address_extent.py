"""Tests for the address-to-extent resolver.

The resolver splits work between a fuzzy geocoder (coarse anchor only)
and authoritative BAG (exact address-to-building membership). These tests
mock both seams so they run offline, and check the three behaviours that
matter: street verification (including the spaced/concatenated spelling
trap), the BAG target selection by street and number range, and the
centred square-extent maths.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from citygml_energy.city_builder import address_extent
from citygml_energy.city_builder.address_extent import (
    AddressResolutionError,
    normalise_street,
    resolve_address_extent,
)
from citygml_energy.city_builder.fetchers.locatieserver import GeocodeHit
from citygml_energy.city_builder.http import CachedSession
from tests._factories import make_vbo


def _session(tmp_path: Path) -> CachedSession:
    return CachedSession(cache_dir=tmp_path / "cache", use_cache=False)


def _hit(point: tuple[float, float], street: str = "Annie Romeinsingel") -> GeocodeHit:
    return GeocodeHit(
        type="adres",
        weergavenaam=f"{street} 1, Leiden",
        point_rd=point,
        straatnaam=street,
        huisnummer=1,
        woonplaatsnaam="Leiden",
        gemeentenaam="Leiden",
    )


# ---------------------------------------------------------------------------
# normalise_street
# ---------------------------------------------------------------------------


def test_normalise_street_ignores_spaces_case_and_diacritics() -> None:
    assert normalise_street("Lange gracht") == normalise_street("Langegracht")
    assert normalise_street("Etta Palmstraat") == "ettapalmstraat"
    assert normalise_street("Sint-Jorissteeg") == "sintjorissteeg"


# ---------------------------------------------------------------------------
# _best_hit street verification (geocoder is fuzzy)
# ---------------------------------------------------------------------------


def test_best_hit_recovers_concatenated_street_via_despaced_variant(monkeypatch, tmp_path) -> None:
    """A spaced street ("Lange gracht") must still find BAG's "Langegracht".

    The fuzzy search buries the real street when the space is present, so
    the resolver retries with the space removed; only the despaced spelling
    surfaces the correct hit here.
    """

    def fake_geocode(session, text, *, type_filter="adres", rows=10):
        if "Langegracht" in text:  # despaced variant
            return [_hit((94092.0, 464267.0), street="Langegracht")]
        return [_hit((0.0, 0.0), street="Lange Mare")]  # wrong, fuzzy noise

    monkeypatch.setattr(address_extent.locatieserver, "geocode_free", fake_geocode)
    hit = address_extent._best_hit(_session(tmp_path), "Lange gracht", 76, "Leiden")
    assert hit is not None
    assert hit.straatnaam == "Langegracht"


def test_best_hit_returns_none_when_no_variant_verifies(monkeypatch, tmp_path) -> None:
    def fake_geocode(session, text, *, type_filter="adres", rows=10):
        return [_hit((0.0, 0.0), street="Totally Different Street")]

    monkeypatch.setattr(address_extent.locatieserver, "geocode_free", fake_geocode)
    assert address_extent._best_hit(_session(tmp_path), "Annie Romeinsingel", 72, "Leiden") is None


# ---------------------------------------------------------------------------
# resolve_address_extent end to end (geocoder + BAG mocked)
# ---------------------------------------------------------------------------


def test_resolve_centres_box_on_matched_buildings(monkeypatch, tmp_path) -> None:
    # Anchor every probe at one point; BAG selection drives the real result.
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))

    vbos = [
        # In range, two distinct panden -> both are targets.
        make_vbo(
            identificatie="v72",
            pand_identificatie="pandA",
            huisnummer=72,
            street="Annie Romeinsingel",
            point=(900.0, 2000.0),
        ),
        make_vbo(
            identificatie="v152",
            pand_identificatie="pandB",
            huisnummer=152,
            street="Annie Romeinsingel",
            point=(1100.0, 2000.0),
        ),
        # Right street but number out of range -> excluded.
        make_vbo(
            identificatie="v200",
            pand_identificatie="pandC",
            huisnummer=200,
            street="Annie Romeinsingel",
            point=(5000.0, 5000.0),
        ),
        # In-range number but a different street -> excluded.
        make_vbo(
            identificatie="vx",
            pand_identificatie="pandD",
            huisnummer=80,
            street="Andere Straat",
            point=(5000.0, 5000.0),
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    res = resolve_address_extent(
        _session(tmp_path), "Annie Romeinsingel 72-152 Leiden", extent_m=500.0
    )

    assert res.target_pand_ids == frozenset({"pandA", "pandB"})
    assert res.matched_addresses == 2
    # Centre is the mean of the two matched VBO points.
    assert res.center == pytest.approx((1000.0, 2000.0))
    assert res.bbox == pytest.approx((750.0, 1750.0, 1250.0, 2250.0))
    # The box is exactly extent_m on a side.
    minx, miny, maxx, maxy = res.bbox
    assert (maxx - minx, maxy - miny) == pytest.approx((500.0, 500.0))
    assert res.municipality == "Leiden"


def test_resolve_raises_when_no_anchor(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: None)
    with pytest.raises(AddressResolutionError):
        resolve_address_extent(_session(tmp_path), "Nowhere 1 Atlantis", extent_m=500.0)


def test_resolve_raises_when_no_bag_match(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))
    # Geocode anchors fine, but BAG has no VBO on the requested street.
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: [])
    with pytest.raises(AddressResolutionError):
        resolve_address_extent(
            _session(tmp_path), "Annie Romeinsingel 72-152 Leiden", extent_m=500.0
        )


def test_resolve_zonder_nummer_selects_whole_street(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))
    vbos = [
        make_vbo(
            identificatie="a",
            pand_identificatie="pandA",
            huisnummer=1,
            street="Etta Palmstraat",
            point=(990.0, 2000.0),
        ),
        make_vbo(
            identificatie="b",
            pand_identificatie="pandB",
            huisnummer=999,
            street="Joke Smitstraat",
            point=(1010.0, 2000.0),
        ),
        make_vbo(
            identificatie="c",
            pand_identificatie="pandC",
            huisnummer=5,
            street="Andere Straat",
            point=(5000.0, 5000.0),
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    res = resolve_address_extent(
        _session(tmp_path), "Etta Palmstraat en Joke Smitstraat z.n. Leiden", extent_m=500.0
    )
    assert res.target_pand_ids == frozenset({"pandA", "pandB"})


def test_resolve_centres_per_pand_not_per_vbo(monkeypatch, tmp_path) -> None:
    """A multi-unit pand must not bias the centre: each pand counts once."""
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((0.0, 0.0)))
    vbos = [
        # pandA: three tightly-clustered VBOs at x=100 (an apartment block).
        make_vbo(
            identificatie="a1",
            pand_identificatie="pandA",
            huisnummer=72,
            street="Annie Romeinsingel",
            point=(100.0, 0.0),
        ),
        make_vbo(
            identificatie="a2",
            pand_identificatie="pandA",
            huisnummer=74,
            street="Annie Romeinsingel",
            point=(100.0, 0.0),
        ),
        make_vbo(
            identificatie="a3",
            pand_identificatie="pandA",
            huisnummer=76,
            street="Annie Romeinsingel",
            point=(100.0, 0.0),
        ),
        # pandB: one house far away at x=300.
        make_vbo(
            identificatie="b1",
            pand_identificatie="pandB",
            huisnummer=152,
            street="Annie Romeinsingel",
            point=(300.0, 0.0),
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    res = resolve_address_extent(
        _session(tmp_path), "Annie Romeinsingel 72-152 Leiden", extent_m=500.0
    )
    # Per-pand centroids are (100,0) and (300,0); their mean is x=200. A
    # per-VBO mean would be (100*3+300)/4 = 150, biased toward pandA.
    assert res.center == pytest.approx((200.0, 0.0))
    assert res.matched_addresses == 4  # every matched VBO is still counted


def test_resolve_widens_seed_when_only_one_endpoint_geocodes(monkeypatch, tmp_path) -> None:
    """A range with only one endpoint geocoded widens the seed buffer past the default."""

    def fake_best_hit(session, street, number, place):
        return _hit((1000.0, 2000.0)) if number == 72 else None

    monkeypatch.setattr(address_extent, "_best_hit", fake_best_hit)

    seen: dict[str, Any] = {}

    def fake_fetch(session, *, bbox):
        seen["bbox"] = bbox
        return [
            make_vbo(
                identificatie="v",
                pand_identificatie="pandA",
                huisnummer=72,
                street="Annie Romeinsingel",
                point=(1000.0, 2000.0),
            )
        ]

    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", fake_fetch)

    resolve_address_extent(
        _session(tmp_path), "Annie Romeinsingel 72-152 Leiden", extent_m=500.0, seed_buffer_m=80.0
    )
    minx, _miny, maxx, _maxy = seen["bbox"]
    # One anchor at x=1000 widened by >=250 m a side (not the 80 m default),
    # so the far end of the terrace is still fetched.
    assert (minx, maxx) == pytest.approx((750.0, 1250.0))


def test_resolve_does_not_widen_for_single_number(monkeypatch, tmp_path) -> None:
    """A single-house query keeps the default seed buffer, not the range widening.

    has_number_range is true for any number, so the widening (meant for a range
    with one endpoint missing) used to fire for every single-house lookup and
    fetch a needlessly large seed bbox.
    """
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))

    seen: dict[str, Any] = {}

    def fake_fetch(session, *, bbox):
        seen["bbox"] = bbox
        return [
            make_vbo(
                identificatie="v",
                pand_identificatie="pandA",
                huisnummer=12,
                street="Annie Romeinsingel",
                point=(1000.0, 2000.0),
            )
        ]

    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", fake_fetch)

    resolve_address_extent(
        _session(tmp_path), "Annie Romeinsingel 12 Leiden", extent_m=500.0, seed_buffer_m=80.0
    )
    minx, _miny, maxx, _maxy = seen["bbox"]
    # One anchor at x=1000 padded by the 80 m default (160 m wide), not 250 m.
    assert (minx, maxx) == pytest.approx((920.0, 1080.0))


def test_best_hit_rejects_street_match_in_wrong_place(monkeypatch, tmp_path) -> None:
    """A same-named street in another gemeente is not accepted as the anchor."""

    def fake_geocode(session, text, *, type_filter="adres", rows=10):
        return [
            GeocodeHit(
                type="adres",
                weergavenaam="Kerkstraat 1, Delft",
                point_rd=(0.0, 0.0),
                straatnaam="Kerkstraat",
                huisnummer=1,
                woonplaatsnaam="Delft",
                gemeentenaam="Delft",
            )
        ]

    monkeypatch.setattr(address_extent.locatieserver, "geocode_free", fake_geocode)
    assert address_extent._best_hit(_session(tmp_path), "Kerkstraat", 1, "Leiden") is None


def test_best_hit_accepts_colloquial_place_alias(monkeypatch, tmp_path) -> None:
    """A colloquial place hint ("Den Haag") matches the official woonplaats.

    PDOK returns "'s-Gravenhage", which never equals the normalised "Den Haag",
    so a strict place check rejected every hit for a valid The Hague address.
    """

    def fake_geocode(session, text, *, type_filter="adres", rows=10):
        return [
            GeocodeHit(
                type="adres",
                weergavenaam="Lange Voorhout 1, 's-Gravenhage",
                point_rd=(80000.0, 455000.0),
                straatnaam="Lange Voorhout",
                huisnummer=1,
                woonplaatsnaam="'s-Gravenhage",
                gemeentenaam="'s-Gravenhage",
            )
        ]

    monkeypatch.setattr(address_extent.locatieserver, "geocode_free", fake_geocode)
    hit = address_extent._best_hit(_session(tmp_path), "Lange Voorhout", 1, "Den Haag")
    assert hit is not None
    assert hit.woonplaatsnaam == "'s-Gravenhage"


def test_best_hit_accepts_place_less_hit(monkeypatch, tmp_path) -> None:
    """A street-matching hit with no place fields cannot contradict the request."""

    def fake_geocode(session, text, *, type_filter="adres", rows=10):
        return [
            GeocodeHit(
                type="weg",
                weergavenaam="Kerkstraat",
                point_rd=(5.0, 6.0),
                straatnaam="Kerkstraat",
                huisnummer=None,
                woonplaatsnaam=None,
                gemeentenaam=None,
            )
        ]

    monkeypatch.setattr(address_extent.locatieserver, "geocode_free", fake_geocode)
    hit = address_extent._best_hit(_session(tmp_path), "Kerkstraat", None, "Leiden")
    assert hit is not None
    assert hit.point_rd == (5.0, 6.0)


def test_resolve_zonder_nummer_keeps_numberless_vbo(monkeypatch, tmp_path) -> None:
    """A "z.n." query keeps a VBO that carries no house number."""
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))
    vbos = [
        make_vbo(
            identificatie="a",
            pand_identificatie="pandA",
            huisnummer=None,
            street="Etta Palmstraat",
            point=(1000.0, 2000.0),
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    res = resolve_address_extent(_session(tmp_path), "Etta Palmstraat z.n. Leiden", extent_m=500.0)
    assert res.target_pand_ids == frozenset({"pandA"})


def test_resolve_numbered_query_skips_numberless_vbo(monkeypatch, tmp_path) -> None:
    """A numbered query skips a numberless VBO (no number to compare against)."""
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))
    vbos = [
        make_vbo(
            identificatie="a",
            pand_identificatie="pandA",
            huisnummer=None,
            street="Annie Romeinsingel",
            point=(1000.0, 2000.0),
        ),
        make_vbo(
            identificatie="b",
            pand_identificatie="pandB",
            huisnummer=72,
            street="Annie Romeinsingel",
            point=(1000.0, 2000.0),
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    res = resolve_address_extent(
        _session(tmp_path), "Annie Romeinsingel 72-152 Leiden", extent_m=500.0
    )
    assert res.target_pand_ids == frozenset({"pandB"})  # pandA's numberless VBO skipped


def test_resolve_warns_when_query_names_no_place(monkeypatch, tmp_path, caplog) -> None:
    """A place-less query proceeds on the geocoder's best hit, but the
    chosen gemeente is named in a warning so a same-named street in the
    wrong town is noticeable."""
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))
    vbos = [
        make_vbo(
            identificatie="v",
            pand_identificatie="pandA",
            huisnummer=72,
            street="Annie Romeinsingel",
            point=(1000.0, 2000.0),
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    with caplog.at_level(logging.WARNING, logger="citygml_energy.city_builder.address_extent"):
        resolve_address_extent(_session(tmp_path), "Annie Romeinsingel 72", extent_m=500.0)

    messages = [r.getMessage() for r in caplog.records]
    assert any("names no place" in m and "Leiden" in m for m in messages)


def test_resolve_does_not_warn_when_place_is_given(monkeypatch, tmp_path, caplog) -> None:
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1000.0, 2000.0)))
    vbos = [
        make_vbo(
            identificatie="v",
            pand_identificatie="pandA",
            huisnummer=72,
            street="Annie Romeinsingel",
            point=(1000.0, 2000.0),
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    with caplog.at_level(logging.WARNING, logger="citygml_energy.city_builder.address_extent"):
        resolve_address_extent(_session(tmp_path), "Annie Romeinsingel 72 Leiden", extent_m=500.0)

    assert not any("names no place" in r.getMessage() for r in caplog.records)


def test_resolve_falls_back_to_anchor_when_no_vbo_geometry(monkeypatch, tmp_path) -> None:
    """With matched VBOs but no geometry, the box centres on the anchor, not NaN."""
    monkeypatch.setattr(address_extent, "_best_hit", lambda *a, **k: _hit((1234.0, 5678.0)))
    vbos = [
        make_vbo(
            identificatie="a",
            pand_identificatie="pandA",
            huisnummer=72,
            street="Annie Romeinsingel",
            point=None,
        ),
    ]
    monkeypatch.setattr(address_extent, "fetch_verblijfsobjecten", lambda *a, **k: vbos)

    res = resolve_address_extent(
        _session(tmp_path), "Annie Romeinsingel 72-152 Leiden", extent_m=500.0
    )
    assert res.target_pand_ids == frozenset({"pandA"})
    assert res.center == pytest.approx((1234.0, 5678.0))
    assert res.matched_addresses == 1  # the geometry-less VBO is still counted
