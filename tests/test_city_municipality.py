"""Tests for :mod:`citygml_energy.city_builder.fetchers.municipality`.

Exercises the post-fetch transform via a monkeypatched ``CachedSession``
without hitting PDOK's WFS. The handful of edge cases that matter:
case-insensitive name matching, pagination across the layer's 1000-row
page size, the CBS-code normalisation (``"GM0503"`` vs ``"0503"`` vs
``""``), and the bbox calculation walking nested coordinate arrays.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from citygml_energy.city_builder.fetchers.municipality import (
    MUNICIPALITY_PAGE_SIZE,
    MunicipalityOutline,
    fetch_municipality_outline,
)
from citygml_energy.city_builder.http import CachedSession

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _municipality_feature(
    name: str,
    *,
    code: str = "GM0503",
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """Build a minimal PDOK-shaped municipality feature for testing."""
    if bbox is None:
        bbox = (84000.0, 446000.0, 86000.0, 448000.0)
    minx, miny, maxx, maxy = bbox
    return {
        "type": "Feature",
        "id": f"Gemeentegebied.{code}",
        "properties": {"naam": name, "code": code},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [minx, miny],
                    [maxx, miny],
                    [maxx, maxy],
                    [minx, maxy],
                    [minx, miny],
                ]
            ],
        },
    }


def _make_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pages: list[dict[str, Any]],
) -> CachedSession:
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=False)
    calls = iter(pages)

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]):
            self.status_code = 200
            self._payload = payload

        @property
        def content(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    class _FakeSession:
        headers: ClassVar[dict[str, str]] = {}

        def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(next(calls))

    monkeypatch.setattr(session, "_session", _FakeSession())
    return session


# ---------------------------------------------------------------------------
# fetch_municipality_outline
# ---------------------------------------------------------------------------


def test_fetch_municipality_outline_matches_case_insensitively(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _make_session(
        tmp_path,
        monkeypatch,
        pages=[{"features": [_municipality_feature("Delft")]}],
    )
    outline = fetch_municipality_outline(session, name="DELFT")
    assert isinstance(outline, MunicipalityOutline)
    assert outline.name == "Delft"
    assert outline.cbs_code == "0503"
    # bbox is computed from the polygon's vertices, so a flat [[…]] ring
    # round-trips without coordinate-stripping bugs.
    assert outline.bbox == (84000.0, 446000.0, 86000.0, 448000.0)


def test_fetch_municipality_outline_walks_pages_until_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-leading municipality name shouldn't fail just because it
    happens to live past the first 1000-row page."""
    full_page = {
        "features": [_municipality_feature(f"Gemeente_{i}") for i in range(MUNICIPALITY_PAGE_SIZE)],
    }
    target_page = {"features": [_municipality_feature("Emmen", code="GM0114")]}
    session = _make_session(tmp_path, monkeypatch, pages=[full_page, target_page])

    outline = fetch_municipality_outline(session, name="Emmen")
    assert outline.name == "Emmen"
    assert outline.cbs_code == "0114"


def test_fetch_municipality_outline_matches_official_name_spelling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user typing the official spelling ("'s-Gravenhage") must match a
    feature whose common name differs ("Den Haag"). The official field is
    an *alternative* spelling, not just a fallback for an absent ``naam``
    (which is all the original ``naam or naam_officieel`` expressed)."""
    feature = _municipality_feature("Den Haag", code="GM0518")
    feature["properties"]["naam_officieel"] = "'s-Gravenhage"

    session = _make_session(tmp_path, monkeypatch, pages=[{"features": [feature]}])
    outline = fetch_municipality_outline(session, name="'s-GRAVENHAGE")
    assert outline.name == "Den Haag"  # display prefers the common name
    assert outline.cbs_code == "0518"

    # The common spelling keeps working when both fields are present.
    session = _make_session(tmp_path, monkeypatch, pages=[{"features": [feature]}])
    outline = fetch_municipality_outline(session, name="den haag")
    assert outline.name == "Den Haag"


def test_fetch_municipality_outline_raises_when_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The caller cannot proceed without an outline; a missing name
    must surface as a :class:`ValueError`, not an empty result."""
    session = _make_session(
        tmp_path,
        monkeypatch,
        pages=[{"features": [_municipality_feature("Delft")]}],
    )
    with pytest.raises(ValueError, match="not found"):
        fetch_municipality_outline(session, name="Atlantis")


def test_fetch_municipality_outline_raises_on_empty_first_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty WFS response is treated as a hard miss, same as a
    non-matching populated response."""
    session = _make_session(tmp_path, monkeypatch, pages=[{"features": []}])
    with pytest.raises(ValueError, match="not found"):
        fetch_municipality_outline(session, name="Delft")


def test_fetch_municipality_outline_normalises_cbs_code_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDOK has shipped both ``"GM0503"`` and bare ``"0503"`` as the
    code field across vintages; both should reduce to ``"0503"``."""
    for raw_code, expected in (("GM0503", "0503"), ("0503", "0503")):
        session = _make_session(
            tmp_path,
            monkeypatch,
            pages=[{"features": [_municipality_feature("Delft", code=raw_code)]}],
        )
        outline = fetch_municipality_outline(session, name="Delft")
        assert outline.cbs_code == expected
