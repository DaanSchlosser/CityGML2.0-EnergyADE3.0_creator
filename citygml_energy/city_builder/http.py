"""Shared HTTP client + disk cache + retry policy.

The fetchers are all read-only bulk downloads from public PDOK / 3DBAG
/ EP-online endpoints, so the same session settings (timeouts,
User-Agent, retry on transient 5xx) apply everywhere. Keeping the
wiring in one place also makes the fetchers trivially unit-testable —
tests construct a :class:`CachedSession` with a temp cache directory
and monkeypatch ``requests.Session.request`` for deterministic
responses.

``requests`` is only imported inside the class body so this module can
be imported without the optional ``[city]`` extras installed; missing
deps raise a clear error at construction time, not at import time.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import requests

USER_AGENT = "citygml-energy-city-builder/0.5"
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 1.5


@dataclass
class CachedSession:
    """HTTP session with on-disk caching keyed by (method, url, params).

    Responses are stored as raw bytes next to a small JSON metadata file
    so cached downloads survive restarts. Set ``use_cache=False`` to
    bypass — useful for tests that monkeypatch the underlying session.
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
        unit tests that never hit the wire do not need the dep.
        """
        if self._session is None:
            try:
                import requests
            except ImportError as exc:
                raise RuntimeError(
                    "The city_builder workflow requires the optional 'city' "
                    "extras. Install with: pip install -e .[city]"
                ) from exc
            self._session = requests.Session()
            self._session.headers["User-Agent"] = USER_AGENT
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
    ) -> bytes:
        """GET *url* and return the response body as bytes.

        If *cache_key* is given and :attr:`use_cache` is True the
        response is memoised to disk; subsequent calls with the same
        cache key skip the network entirely.
        """
        return self._request("GET", url, params=params, headers=headers, cache_key=cache_key)

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
    ) -> Any:
        """GET *url* and parse the response as JSON."""
        raw = self.get_bytes(url, params=params, headers=headers, cache_key=cache_key)
        return json.loads(raw.decode("utf-8"))

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
    ) -> bytes:
        cache_path = self._cache_path(method, url, params, cache_key)
        if cache_path is not None and cache_path.exists():
            return cache_path.read_bytes()

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method, url, params=params, headers=headers, timeout=self.timeout
                )
            except Exception as exc:
                last_exc = exc
                time.sleep(self.backoff_seconds * attempt)
                continue
            if response.status_code >= 500 and attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)
                continue
            response.raise_for_status()
            body = response.content
            if cache_path is not None:
                cache_path.write_bytes(body)
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
        if not self.use_cache or cache_key is None:
            return None
        # Key files with a human-readable prefix for easier debugging, plus a
        # hash of the full request so two similar URLs don't collide.
        digest = hashlib.sha256(
            json.dumps(
                {"method": method, "url": url, "params": params or {}, "key": cache_key},
                sort_keys=True,
                default=str,
            ).encode("utf-8"),
        ).hexdigest()[:16]
        safe_key = "".join(c if c.isalnum() or c in "._-" else "_" for c in cache_key)[:60]
        return self.cache_dir / f"{safe_key}.{digest}.bin"
