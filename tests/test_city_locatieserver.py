"""Tests for the PDOK Locatieserver geocoder client.

The fuzzy ``free`` endpoint is mocked; these check the field/CRS parsing
the resolver relies on, including dropping documents without a usable RD
coordinate.
"""

from __future__ import annotations

from citygml_energy.city_builder.fetchers.locatieserver import (
    _parse_point_rd,
    geocode_free,
)
from tests._factories import make_session_with_pages


def test_parse_point_rd() -> None:
    assert _parse_point_rd("POINT(94092.17 464267.343)") == (94092.17, 464267.343)
    assert _parse_point_rd("") is None
    assert _parse_point_rd(None) is None
    assert _parse_point_rd("not a point") is None


def test_geocode_free_parses_documents(tmp_path, monkeypatch) -> None:
    payload = {
        "response": {
            "numFound": 2,
            "docs": [
                {
                    "type": "adres",
                    "weergavenaam": "Langegracht 76, 2312NH Leiden",
                    "centroide_rd": "POINT(94092.17 464267.343)",
                    "straatnaam": "Langegracht",
                    "huisnummer": 76,
                    "woonplaatsnaam": "Leiden",
                    "gemeentenaam": "Leiden",
                },
                # No RD coordinate -> dropped.
                {"type": "adres", "weergavenaam": "broken", "straatnaam": "X"},
            ],
        }
    }
    session = make_session_with_pages(tmp_path, monkeypatch, [payload])
    hits = geocode_free(session, "Langegracht 76 Leiden")

    assert len(hits) == 1
    hit = hits[0]
    assert hit.point_rd == (94092.17, 464267.343)
    assert hit.straatnaam == "Langegracht"
    assert hit.huisnummer == 76
    assert hit.woonplaatsnaam == "Leiden"
    assert hit.gemeentenaam == "Leiden"
