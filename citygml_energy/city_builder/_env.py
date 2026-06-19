"""Shared best-effort ``.env`` loading for the city builder.

Both :mod:`citygml_energy.city_builder.config` (for the EP-Online key
resolved relative to a config file) and
:mod:`citygml_energy.city_builder.cftree_runner` (for the ``CFTREE_*``
launch settings resolved relative to the repo root) need to populate
``os.environ`` from a ``.env`` before reading it. The helper lives here,
in a leaf module that imports nothing else from the package, so neither
of those two modules has to reach across the other's private surface and
the import does not create a cycle.
"""

from __future__ import annotations

from pathlib import Path

# Each resolved start directory is searched at most once per process, so
# repeated config loads / runner resolutions do not re-walk the tree.
_DOTENV_LOADED_FROM: set[Path] = set()


def maybe_load_dotenv(start_dir: Path) -> None:
    """Best-effort load of the nearest ``.env`` into ``os.environ``.

    Walks *start_dir* and its ancestors looking for the first ``.env``
    file, mirroring how ``python-dotenv``'s ``find_dotenv()`` behaves.
    Silent no-op when ``python-dotenv`` is not installed. Each resolved
    directory chain is searched at most once per process. Existing
    environment variables are never overwritten (``override=False``), so
    a real shell export always wins over a ``.env`` entry.
    """
    start_dir = start_dir.resolve()
    if start_dir in _DOTENV_LOADED_FROM:
        return
    _DOTENV_LOADED_FROM.add(start_dir)
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in [start_dir, *start_dir.parents]:
        env_file = candidate / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            return
