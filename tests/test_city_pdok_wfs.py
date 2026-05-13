"""Unit tests for :mod:`citygml_energy.city_builder.pdok_wfs`.

The paginator is the one seam every PDOK WFS 2.0 fetcher in this
project goes through (BAG, CBS Postcode6, municipality). These tests
exercise the wire-protocol contract directly: page-walk termination,
the bbox-vs-no-bbox cache-key shape, the WFS query envelope, and the
``extra_params`` passthrough. Fetcher-specific transforms (dedup,
attribute extraction) are covered by the per-fetcher test files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import json
import pytest

from citygml_energy.city_builder.http import CachedSession
from citygml_energy.city_builder.pdok_wfs import (
    DEFAULT_PAGE_SIZE,
    paginate_features,
)


def _feature(idx: int) -> dict[str, Any]:
    return {"type": "Feature", "id": f"f{idx}", "properties": {"i": idx}}


def _capturing_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pages: list[dict[str, Any]],
) -> tuple[CachedSession, list[dict[str, Any]]]:
    """Like :func:`tests._factories.make_session_with_pages` but also
    captures the per-request kwargs so tests can assert on query params."""
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=False)
    calls = iter(pages)
    captured: list[dict[str, Any]] = []

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.status_code = 200
            self._payload = payload

        @property
        def content(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    class _FakeSession:
        headers: ClassVar[dict[str, str]] = {}

        def request(
            self, method: str, url: str, **kwargs: Any
        ) -> _FakeResponse:
            captured.append({"method": method, "url": url, **kwargs})
            return _FakeResponse(next(calls))

    monkeypatch.setattr(session, "_session", _FakeSession())
    return session, captured


def test_paginate_features_stops_on_short_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page shorter than ``page_size`` ends pagination — the WFS 2.0
    'no more rows' convention. Two pages of 2 + a page of 1 = three
    features, one stop."""
    session, captured = _capturing_session(
        tmp_path, monkeypatch,
        pages=[
            {"features": [_feature(1), _feature(2)]},
            {"features": [_feature(3)]},
        ],
    )
    features = paginate_features(
        session,
        "https://example/wfs",
        type_names="test:layer",
        cache_prefix="test_layer",
        bbox=(0.0, 0.0, 1.0, 1.0),
        page_size=2,
    )
    assert [f["id"] for f in features] == ["f1", "f2", "f3"]
    assert len(captured) == 2


def test_paginate_features_walks_multiple_full_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every page is exactly full, the loop keeps walking until
    the server returns a short page."""
    session, captured = _capturing_session(
        tmp_path, monkeypatch,
        pages=[
            {"features": [_feature(i) for i in (1, 2)]},
            {"features": [_feature(i) for i in (3, 4)]},
            {"features": []},  # empty terminates
        ],
    )
    features = paginate_features(
        session, "https://example/wfs",
        type_names="test:layer",
        cache_prefix="test_layer",
        bbox=(0.0, 0.0, 1.0, 1.0),
        page_size=2,
    )
    assert [f["id"] for f in features] == ["f1", "f2", "f3", "f4"]
    assert len(captured) == 3


def test_paginate_features_emits_wfs_query_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The query string carries the WFS 2.0 contract every PDOK
    endpoint expects: service, version, request, typeNames, GeoJSON
    output format, srsName, startIndex, count, and the bbox suffixed
    with the SRS name."""
    session, captured = _capturing_session(
        tmp_path, monkeypatch,
        pages=[{"features": []}],
    )
    paginate_features(
        session, "https://example/wfs",
        type_names="bag:pand",
        cache_prefix="bag_pand",
        bbox=(1.0, 2.0, 3.0, 4.0),
        page_size=10,
    )
    [call] = captured
    params = call["params"]
    assert params["service"] == "WFS"
    assert params["version"] == "2.0.0"
    assert params["request"] == "GetFeature"
    assert params["typeNames"] == "bag:pand"
    assert params["outputFormat"] == "application/json"
    assert params["srsName"] == "EPSG:28992"
    assert params["count"] == 10
    assert params["startIndex"] == 0
    assert params["bbox"] == "1.0,2.0,3.0,4.0,EPSG:28992"


def test_paginate_features_omits_bbox_when_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The municipality fetcher walks the whole Gemeentegebied layer
    with no bbox filter. Without *bbox*, the WFS request must not
    carry a ``bbox`` key (which would otherwise be interpreted as an
    empty filter by some WFS implementations)."""
    session, captured = _capturing_session(
        tmp_path, monkeypatch,
        pages=[{"features": []}],
    )
    paginate_features(
        session, "https://example/wfs",
        type_names="bestuurlijkegebieden:Gemeentegebied",
        cache_prefix="pdok_gemeentegebied",
    )
    [call] = captured
    assert "bbox" not in call["params"]


def test_paginate_features_cache_key_depends_on_bbox_and_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With *bbox* set, the cache key is derived from
    :func:`bbox_cache_key` so a re-run with the same bbox hits cache;
    consecutive pages get distinct keys so concurrent in-flight pages
    do not clobber each other on disk."""
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=True)
    pages = iter([
        {"features": [_feature(i) for i in range(2)]},
        {"features": []},
    ])

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
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
            return _FakeResponse(next(pages))

    monkeypatch.setattr(session, "_session", _FakeSession())

    paginate_features(
        session, "https://example/wfs",
        type_names="test:layer",
        cache_prefix="bag:pand",
        bbox=(1.0, 2.0, 3.0, 4.0),
        page_size=2,
    )
    cached_files = sorted(p.name for p in (tmp_path / "cache").glob("*.bin"))
    # Two pages → two distinct cache files, both keyed on the bbox prefix.
    assert len(cached_files) == 2
    assert all(name.startswith("bag_pand.1.00_2.00_3.00_4.00.p") for name in cached_files)


def test_paginate_features_cache_key_when_no_bbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without *bbox*, the cache key collapses to
    ``f"{cache_prefix}.p{page}"`` so a layer that is the same across
    runs (e.g. the national Gemeentegebied layer) shares one cache
    entry per page regardless of what the caller is searching for."""
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=True)
    pages = iter([{"features": []}])

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
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
            return _FakeResponse(next(pages))

    monkeypatch.setattr(session, "_session", _FakeSession())

    paginate_features(
        session, "https://example/wfs",
        type_names="bestuurlijkegebieden:Gemeentegebied",
        cache_prefix="pdok_gemeentegebied",
    )
    [cached] = list((tmp_path / "cache").glob("*.bin"))
    assert cached.name.startswith("pdok_gemeentegebied.p0")


def test_paginate_features_default_page_size_matches_pdok_cap() -> None:
    """1000 is PDOK's server-side WFS 2.0 page cap; smaller defaults
    just mean more round trips for the same data."""
    assert DEFAULT_PAGE_SIZE == 1000


def test_paginate_features_passes_extra_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``extra_params`` is folded into the request after the standard
    WFS keys so callers can attach CQL filters / vendor extensions
    without touching this module."""
    session, captured = _capturing_session(
        tmp_path, monkeypatch,
        pages=[{"features": []}],
    )
    paginate_features(
        session, "https://example/wfs",
        type_names="bag:pand",
        cache_prefix="bag_pand",
        bbox=(1.0, 2.0, 3.0, 4.0),
        extra_params={"cql_filter": "status='Pand in gebruik'"},
    )
    [call] = captured
    assert call["params"]["cql_filter"] == "status='Pand in gebruik'"
