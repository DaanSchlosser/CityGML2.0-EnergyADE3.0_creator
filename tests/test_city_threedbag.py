"""Tests for :mod:`citygml_energy.city_builder.fetchers.threedbag`.

The :func:`fetch_tile_index` path needs the optional ``flatgeobuf``
dependency and live HTTP range requests to data.3dbag.nl, which makes
it inappropriate for unit testing. These tests therefore focus on the
post-download path that actually transforms bytes into the project's
``ParsedBuilding`` representation: gzip sniffing, the JSON parse, the
parsed-tile pickle cache, and the cache-key shape.

The :func:`_decompress_if_gzipped` helper is exercised directly because
its 2-byte magic-number sniff is the contract the rest of the pipeline
relies on; getting it wrong silently delivers gzip-as-JSON to
:func:`citygml_energy.city_builder.cityjson_parse.parse_buildings`.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest  # noqa: TC002 (load-bearing at runtime: fixture types are runtime markers)

from citygml_energy.city_builder.fetchers.threedbag import (
    Tile,
    _decompress_if_gzipped,
    fetch_tile_cityjson,
)
from citygml_energy.city_builder.http import CachedSession

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_CITYJSON = {
    "type": "CityJSON",
    "version": "2.0",
    "transform": {"scale": [0.001, 0.001, 0.001], "translate": [0.0, 0.0, 0.0]},
    "CityObjects": {},
    "vertices": [],
}


def _make_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> CachedSession:
    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=False)

    class _FakeResponse:
        def __init__(self, body: bytes):
            self.status_code = 200
            self._body = body

        @property
        def content(self) -> bytes:
            return self._body

        def raise_for_status(self) -> None:
            return None

    class _FakeSession:
        headers: ClassVar[dict[str, str]] = {}

        def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(payload)

    monkeypatch.setattr(session, "_session", _FakeSession())
    return session


# ---------------------------------------------------------------------------
# _decompress_if_gzipped
# ---------------------------------------------------------------------------


def test_decompress_if_gzipped_passes_plain_bytes_through() -> None:
    """A non-gzip body must round-trip unchanged so a plain-JSON tile
    skips the gzip code path."""
    plain = b'{"type": "CityJSON"}'
    assert _decompress_if_gzipped(plain) == plain


def test_decompress_if_gzipped_handles_real_gzip_payload() -> None:
    """3DBAG serves tiles as gzipped CityJSON; the sniff must catch the
    1f 8b magic number and decompress."""
    payload = json.dumps(_MINIMAL_CITYJSON).encode("utf-8")
    compressed = gzip.compress(payload)
    assert compressed[:2] == b"\x1f\x8b"  # sanity: it's actually gzipped
    assert _decompress_if_gzipped(compressed) == payload


def test_decompress_if_gzipped_does_not_misinterpret_short_payload() -> None:
    """A pathologically short body must not raise; the sniff is a strict
    prefix check, not a length-sensitive parse."""
    assert _decompress_if_gzipped(b"") == b""
    assert _decompress_if_gzipped(b"x") == b"x"


# ---------------------------------------------------------------------------
# fetch_tile_cityjson
# ---------------------------------------------------------------------------


def test_fetch_tile_cityjson_returns_parsed_dict_for_plain_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(_MINIMAL_CITYJSON).encode("utf-8")
    session = _make_session(tmp_path, monkeypatch, payload)
    tile = Tile(
        tile_id="9-200-300",
        download_url="https://example.invalid/tile.json",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
    )
    result = fetch_tile_cityjson(session, tile)
    assert result["type"] == "CityJSON"
    assert result["version"] == "2.0"


def test_fetch_tile_cityjson_decompresses_gzipped_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(_MINIMAL_CITYJSON).encode("utf-8")
    session = _make_session(tmp_path, monkeypatch, gzip.compress(payload))
    tile = Tile(
        tile_id="9-200-300",
        download_url="https://example.invalid/tile.json.gz",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
    )
    result = fetch_tile_cityjson(session, tile)
    assert result["type"] == "CityJSON"


# ---------------------------------------------------------------------------
# Cache-key shape
# ---------------------------------------------------------------------------


def test_tile_cache_key_replaces_slashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3DBAG tile ids contain forward slashes (``"9/200/300"``); naive
    use as a filename component breaks on Windows. The fetcher
    replaces them with underscores so the cache key works on every
    supported OS.
    """
    payload = json.dumps(_MINIMAL_CITYJSON).encode("utf-8")
    captured: dict[str, str | None] = {}

    session = CachedSession(cache_dir=tmp_path / "cache", use_cache=True)

    class _FakeResponse:
        status_code: ClassVar[int] = 200
        content: ClassVar[bytes] = payload

        def raise_for_status(self) -> None:
            return None

    class _FakeSession:
        headers: ClassVar[dict[str, str]] = {}

        def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(session, "_session", _FakeSession())

    real_get_bytes = session.get_bytes

    def _spy(url: str, **kwargs: Any) -> bytes:
        captured["cache_key"] = kwargs.get("cache_key")
        return real_get_bytes(url, **kwargs)

    monkeypatch.setattr(session, "get_bytes", _spy)

    tile = Tile(
        tile_id="9/200/300",
        download_url="https://example.invalid/tile.json",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
    )
    fetch_tile_cityjson(session, tile)
    assert captured["cache_key"] == "3dbag_9_200_300"
