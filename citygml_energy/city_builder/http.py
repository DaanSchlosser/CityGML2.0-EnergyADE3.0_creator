"""Shared HTTP client + disk cache + retry policy.

The fetchers are all read-only bulk downloads from public PDOK / 3DBAG
/ EP-online endpoints, so the same session settings (timeouts,
User-Agent, retry on transient 5xx) apply everywhere. Keeping the
wiring in one place also makes the fetchers trivially unit-testable:
tests construct a :class:`CachedSession` with a temp cache directory
and monkeypatch ``requests.Session.request`` for deterministic
responses.

``requests`` is only imported inside the class body so this module can
be imported without the optional ``[city]`` extras installed; missing
deps raise a clear error at construction time, not at import time.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import requests

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "citygml-energy-city-builder/0.5"
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 1.5
# Connection pool sizing. A single ``CachedSession`` drives all fetchers
# in the city pipeline; 10 simultaneous hosts / 20 keepalive sockets is
# plenty for PDOK + 3DBAG + EP-online without wasting FDs.
_HTTP_POOL_CONNECTIONS = 10
_HTTP_POOL_MAXSIZE = 20


# Prefer orjson when available: multi-MB CityJSON tile parses go from
# ~55 ms per tile (stdlib json) to ~15 ms with orjson. Graceful fallback
# keeps the base install small for users who never touch the city extras.
try:
    import orjson as _orjson

    def loads_json(data: bytes | str) -> Any:
        """Parse a JSON payload using orjson when available, else stdlib."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return _orjson.loads(data)

except ImportError:  # pragma: no cover, exercised when orjson is absent.

    def loads_json(data: bytes | str) -> Any:
        """Parse a JSON payload using stdlib json (orjson not installed)."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)


@dataclass
class CachedSession:
    """HTTP session with on-disk caching keyed by an explicit cache key.

    Responses are stored as raw bytes so cached downloads survive
    restarts; writes go through a temp file + :func:`os.replace` so an
    interrupted run can never leave a truncated entry behind. Set
    ``use_cache=False`` to bypass; useful for tests that monkeypatch
    the underlying session.

    **Mutability model.** ``CachedSession`` is a service object, not a
    value object. The configured fields (``cache_dir``, ``use_cache``,
    ``timeout``, ``max_retries``, ``backoff_seconds``) are effectively
    immutable after construction -- nothing in this module writes to
    them -- while ``_session`` is populated lazily on first network use
    and is deliberately monkey-patchable by tests (see
    ``tests/test_city_bgt.py`` for the pattern). ``@dataclass`` gives
    us a free ``__init__`` / ``__repr__`` for the config fields; it is
    **not** ``frozen`` because patching ``_session`` is part of the
    test contract.
    """

    cache_dir: Path
    use_cache: bool = True
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_seconds: float = DEFAULT_BACKOFF
    _session: requests.Session | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def session(self) -> requests.Session:
        """Return the lazily-created :class:`requests.Session`.

        Defers ``import requests`` until first real network use, so
        unit tests that never hit the wire do not need the dep. The
        session is configured with an :class:`HTTPAdapter` that enables
        connection pooling across repeated GETs (BAG WFS pagination,
        3DBAG tile downloads) and retries transient 5xx responses with
        exponential backoff, which is cheaper and more correct than
        our in-house retry loop for the 502/503 weather that PDOK
        occasionally has.
        """
        if self._session is None:
            try:
                import requests
                from requests.adapters import HTTPAdapter
            except ImportError as exc:
                raise RuntimeError(
                    "The city_builder workflow requires the optional 'city' "
                    "extras. Install with: pip install -e .[city]"
                ) from exc
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
            # Pool-only adapter: connection reuse across paginated BAG WFS
            # requests and the sizeable 3DBAG tile set, but no retry policy.
            # Retry behaviour stays in :meth:`_request` where tests and the
            # existing backoff curve already exercise it. Mixing HTTPAdapter
            # retries on top of the custom loop would silently multiply the
            # attempt count on a flaky endpoint.
            adapter = HTTPAdapter(
                pool_connections=_HTTP_POOL_CONNECTIONS,
                pool_maxsize=_HTTP_POOL_MAXSIZE,
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            self._session = session
        return self._session

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def get_bytes(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
        validate: Callable[[bytes], None] | None = None,
    ) -> bytes:
        """GET *url* and return the response body as bytes.

        If *cache_key* is given and :attr:`use_cache` is True the
        response is memoised to disk; subsequent calls with the same
        cache key skip the network entirely.

        *validate*, when given, is called with the fresh response body
        **before** it is written to the cache; raising from it both
        propagates the error and keeps the bad payload out of the cache.
        Needed for APIs (ArcGIS REST) that ship application errors with
        HTTP 200, which ``raise_for_status`` cannot catch. Cached reads
        skip validation: entries are validated-at-write by construction.
        """
        return self._request(
            "GET", url, params=params, headers=headers, cache_key=cache_key, validate=validate
        )

    def cached_bytes(self, cache_key: str) -> bytes | None:
        """Return the cached body for *cache_key*, or ``None`` when cold.

        Never touches the network. Lets a fetcher whose cache identity
        does not depend on the request URL (the EP-online bundle, whose
        download URL rotates per vintage while the cache key is fixed)
        skip the URL-discovery round-trip entirely on a warm cache,
        which also removes the API-key and network requirement from
        fully cached runs. Respects ``use_cache=False`` by reporting
        cold.

        Fixed-key entries never expire, so a hit logs the entry's date
        and age; without that a months-old vintage would be served with
        no signal at all.
        """
        cache_path = self._cache_path("GET", "", None, cache_key)
        if cache_path is not None and cache_path.exists():
            mtime = cache_path.stat().st_mtime
            _LOGGER.info(
                "Serving %r from the disk cache (entry dated %s, %d day(s) old); "
                "delete %s to force a fresh download",
                cache_key,
                time.strftime("%Y-%m-%d", time.localtime(mtime)),
                int((time.time() - mtime) / 86400),
                cache_path,
            )
            return cache_path.read_bytes()
        return None

    def evict(self, cache_key: str) -> None:
        """Remove the cached entry for *cache_key* so the next call re-fetches.

        Self-heals a poisoned entry: a body that passed a lightweight
        validate hook (e.g. a TIFF magic sniff) but later proves
        undecodable should not be re-served verbatim on every subsequent
        run. A no-op when caching is off or the entry is already absent;
        a filesystem error while unlinking is swallowed (the goal is best-
        effort cleanup, not a hard guarantee).
        """
        cache_path = self._cache_path("GET", "", None, cache_key)
        if cache_path is None:
            return
        with contextlib.suppress(OSError):  # best-effort cleanup, not a guarantee
            cache_path.unlink(missing_ok=True)

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
        validate: Callable[[bytes], None] | None = None,
    ) -> Any:
        """GET *url* and parse the response as JSON."""
        raw = self.get_bytes(
            url, params=params, headers=headers, cache_key=cache_key, validate=validate
        )
        return loads_json(raw)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        cache_key: str | None,
        validate: Callable[[bytes], None] | None = None,
    ) -> bytes:
        cache_path = self._cache_path(method, url, params, cache_key)
        if cache_path is not None and cache_path.exists():
            return cache_path.read_bytes()

        # Only retry on transient network-layer failures. Broader catches
        # would also swallow KeyboardInterrupt / MemoryError / programming
        # mistakes, masking bugs as mysterious retry-exhaustion failures.
        # ``RequestException`` is the root of every requests-raised error
        # (connection reset, SSL error, timeout, read error, ...); ``OSError``
        # covers DNS / low-level socket issues that surface before requests
        # wraps them. The ``self.session`` property call ensures ``requests``
        # is imported before we reach the ``except`` clause.
        session = self.session
        import requests as _requests  # already imported by ``session`` above

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = session.request(
                    method, url, params=params, headers=headers, timeout=self.timeout
                )
            except (_requests.RequestException, OSError) as exc:
                last_exc = exc
                time.sleep(self.backoff_seconds * attempt)
                continue
            if response.status_code >= 500 and attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)
                continue
            response.raise_for_status()
            body = response.content
            if validate is not None:
                validate(body)
            if cache_path is not None:
                # Atomic publish: write to a pid-suffixed temp file in the
                # same directory, then ``os.replace``. A crash mid-write
                # leaves at worst an orphaned temp file, never a truncated
                # cache entry that poisons every later run; the pid suffix
                # keeps the parallel pand workers off each other's temp
                # files (last replace wins, which is fine for identical
                # responses).
                tmp_path = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
                tmp_path.write_bytes(body)
                tmp_path.replace(cache_path)
            return body

        assert last_exc is not None
        raise last_exc

    def _cache_path(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        cache_key: str | None,
    ) -> Path | None:
        """Map a request to its on-disk cache path (or ``None`` to skip).

        The cache identity is the *cache_key* alone: method/url/params
        are deliberately excluded. All callers derive their cache_key
        from the stable facet of the request (``bag:pand``-per-bbox,
        ``3dbag_<tile>``, ``ep_online_bundle``, …) so that a rotating
        signed URL or a reordered query string does not defeat caching.
        The human-readable key serves as the filename prefix; a short
        digest of the key disambiguates on filesystems that are
        case-insensitive or that would clash on truncation.
        """
        if not self.use_cache or cache_key is None:
            return None
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:16]
        safe_key = "".join(c if c.isalnum() or c in "._-" else "_" for c in cache_key)[:60]
        return self.cache_dir / f"{safe_key}.{digest}.bin"
