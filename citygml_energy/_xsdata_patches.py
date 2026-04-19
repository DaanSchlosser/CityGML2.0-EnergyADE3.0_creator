"""Surgical monkey-patches to xsdata's hot serialization internals.

xsdata ships a correct but reflection-heavy serializer: for every value
it emits it re-resolves the converter for that value's type, and for
every field it re-checks whether the value is a list via a chain of
``isinstance`` probes. Both answers are **pure functions of the
argument's type**, so they trivially memoise.

Two patches, applied idempotently at import time:

1. :func:`xsdata.formats.converter.ConverterFactory.type_converter`
   gets a per-class dict cache keyed on the input class. xsdata's own
   ``registry`` is already O(1) on cache hits, but on misses it walks
   ``data_type.__mro__`` every call; the second layer of caching
   short-circuits that.

2. :func:`xsdata.utils.collections.is_array` is replaced by a fast
   path that returns immediately for the dominant ``type(value) is
   list`` case before falling back to the original implementation for
   tuples/sets/generators.

The patches are additive-only and stateless: they don't change
xsdata's observable behaviour, only its performance. Applying them
twice is a no-op.
"""

from __future__ import annotations

from typing import Any

_PATCHED_SENTINEL = "_citygml_energy_patched"


def apply() -> None:
    """Install the patches. Safe to call repeatedly (guarded by a sentinel)."""
    _patch_type_converter()
    _patch_is_array()


# ---------------------------------------------------------------------------
# ConverterFactory.type_converter: per-type cache over the singleton
# ---------------------------------------------------------------------------


def _patch_type_converter() -> None:
    """Add a ``{type: Converter}`` cache in front of ``ConverterFactory.type_converter``.

    Patched at the **class** level because ``ConverterFactory`` uses
    ``__slots__`` (per-instance attribute assignment is forbidden).
    The original implementation stays as the slow-path delegate; on
    the fixed xsdata schema the cache fills with a few hundred
    entries and stays tiny for the rest of the process.
    """
    from xsdata.formats.converter import ConverterFactory

    if getattr(ConverterFactory, _PATCHED_SENTINEL, False):
        return

    original = ConverterFactory.type_converter
    cache: dict[type, Any] = {}

    def cached_type_converter(self: ConverterFactory, data_type: type) -> Any:
        try:
            return cache[data_type]
        except KeyError:
            resolved = original(self, data_type)
            cache[data_type] = resolved
            return resolved

    ConverterFactory.type_converter = cached_type_converter  # type: ignore[method-assign]
    setattr(ConverterFactory, _PATCHED_SENTINEL, True)


# ---------------------------------------------------------------------------
# is_array: fast path for ``list`` (the dominant case) + original fallback
# ---------------------------------------------------------------------------


def _patch_is_array() -> None:
    """Wrap :func:`xsdata.utils.collections.is_array` with a fast-path check.

    Serializer hot loop: virtually every value passed in is a Python
    ``list`` from an xsdata-generated dataclass field. We front the call
    with ``type(value) is list`` (a single C-level pointer equality)
    and only fall through for the rare tuple/set/frozenset/Generator.
    """
    from xsdata.utils import collections as _collections

    if getattr(_collections, _PATCHED_SENTINEL, False):
        return

    original = _collections.is_array

    def fast_is_array(value: Any) -> bool:
        # ``type(x) is list`` skips the abstract-base-class slow path in
        # ``__instancecheck__``. Correctness is preserved: a ``list``
        # subclass with its own ``_fields`` attribute still reaches the
        # fallback, which handles tuple-with-_fields (namedtuples).
        if type(value) is list:
            return True
        return original(value)

    _collections.is_array = fast_is_array
    setattr(_collections, _PATCHED_SENTINEL, True)
