"""Tests for :mod:`citygml_energy.city_builder.http`.

:class:`CachedSession`'s disk cache is shared by every fetcher, so its
session-wide behaviours are covered here directly rather than once per
fetcher: the refresh mode (bypass cache reads, still write fresh
entries), the construction-time vintage log, and the JSON self-heal
(parse before caching; evict and refetch a poisoned cached body once).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

import pytest

from citygml_energy.city_builder.http import CachedSession

_HTTP_LOGGER = "citygml_energy.city_builder.http"


def _session_with_bodies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bodies: list[bytes],
    *,
    refresh: bool = False,
) -> tuple[CachedSession, list[bytes]]:
    """A caching session whose fake transport serves *bodies* in order.

    Returns the session plus the list of bodies actually served, so a
    test can assert whether the network was touched at all.
    """
    session = CachedSession(cache_dir=tmp_path / "cache", refresh=refresh)
    calls = iter(bodies)
    served: list[bytes] = []

    class _FakeResponse:
        def __init__(self, body: bytes) -> None:
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
            body = next(calls)
            served.append(body)
            return _FakeResponse(body)

    monkeypatch.setattr(session, "_session", _FakeSession())
    return session, served


# ---------------------------------------------------------------------------
# refresh mode
# ---------------------------------------------------------------------------


def test_refresh_bypasses_cache_read_but_rewrites_the_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded, _ = _session_with_bodies(tmp_path, monkeypatch, [b'{"v": 1}'])
    assert seeded.get_json("https://example.invalid/x", cache_key="k") == {"v": 1}

    refreshing, served = _session_with_bodies(tmp_path, monkeypatch, [b'{"v": 2}'], refresh=True)
    assert refreshing.get_json("https://example.invalid/x", cache_key="k") == {"v": 2}
    assert served == [b'{"v": 2}']  # the warm entry was ignored

    # The fresh body replaced the entry for later non-refresh runs; the
    # plain session below has no transport, so a hit proves the cache read.
    warm = CachedSession(cache_dir=tmp_path / "cache")
    assert warm.get_json("https://example.invalid/x", cache_key="k") == {"v": 2}


def test_cached_bytes_reports_cold_under_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded, _ = _session_with_bodies(tmp_path, monkeypatch, [b"zip-bytes"])
    seeded.get_bytes("https://example.invalid/bundle", cache_key="bundle")

    refreshing = CachedSession(cache_dir=tmp_path / "cache", refresh=True)
    assert refreshing.cached_bytes("bundle") is None

    warm = CachedSession(cache_dir=tmp_path / "cache")
    assert warm.cached_bytes("bundle") == b"zip-bytes"


# ---------------------------------------------------------------------------
# construction-time vintage log
# ---------------------------------------------------------------------------


def test_construction_logs_cache_vintage_and_mentions_refresh(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "a.bin").write_bytes(b"x")
    (cache / "b.bin").write_bytes(b"y")

    with caplog.at_level(logging.INFO, logger=_HTTP_LOGGER):
        CachedSession(cache_dir=cache)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "2 file(s)" in message and "dated" in message and "--refresh" in message
        for message in messages
    )


def test_construction_stays_quiet_on_an_empty_or_disabled_cache(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=_HTTP_LOGGER):
        CachedSession(cache_dir=tmp_path / "cache")
        CachedSession(cache_dir=tmp_path / "other", use_cache=False)
    assert not caplog.records


# ---------------------------------------------------------------------------
# JSON self-heal: parse before caching, evict-and-refetch-once
# ---------------------------------------------------------------------------


def test_get_json_does_not_cache_an_unparseable_fresh_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTP-200 maintenance page must raise without being memoised;
    caching it would crash every later run on the same garbage."""
    session, _ = _session_with_bodies(tmp_path, monkeypatch, [b"<html>maintenance</html>"])
    with pytest.raises(ValueError):
        session.get_json("https://example.invalid/x", cache_key="k")
    assert not list((tmp_path / "cache").glob("*.bin"))


def test_get_json_evicts_and_refetches_a_poisoned_cache_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cached body written before the parse-before-cache guard existed
    (or corrupted on disk) heals itself: one eviction, one refetch."""
    session, served = _session_with_bodies(tmp_path, monkeypatch, [b'{"ok": true}'])
    cache_path = session._cache_path("GET", "https://example.invalid/x", None, "k")
    assert cache_path is not None
    cache_path.write_bytes(b"<html>maintenance</html>")

    with caplog.at_level(logging.WARNING, logger=_HTTP_LOGGER):
        assert session.get_json("https://example.invalid/x", cache_key="k") == {"ok": True}

    assert served == [b'{"ok": true}']
    assert cache_path.read_bytes() == b'{"ok": true}'  # entry healed on disk
    assert any("evicting" in record.getMessage() for record in caplog.records)


def test_get_json_refetch_failure_propagates_without_looping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, served = _session_with_bodies(tmp_path, monkeypatch, [b"<html>still down</html>"])
    cache_path = session._cache_path("GET", "https://example.invalid/x", None, "k")
    assert cache_path is not None
    cache_path.write_bytes(b"<html>poison</html>")

    with pytest.raises(ValueError):
        session.get_json("https://example.invalid/x", cache_key="k")
    assert served == [b"<html>still down</html>"]  # exactly one refetch


def test_get_json_runs_the_caller_validate_hook_before_caching(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller-supplied validate hook (the 3DBV / ArcGIS pattern) still
    rejects a body that parses as JSON but is an application error."""
    session, _ = _session_with_bodies(tmp_path, monkeypatch, [b'{"error": "quota"}'])

    def reject_error_body(body: bytes) -> None:
        if b'"error"' in body:
            raise ValueError("application error body")

    with pytest.raises(ValueError, match="application error body"):
        session.get_json("https://example.invalid/x", cache_key="k", validate=reject_error_body)
    assert not list((tmp_path / "cache").glob("*.bin"))
