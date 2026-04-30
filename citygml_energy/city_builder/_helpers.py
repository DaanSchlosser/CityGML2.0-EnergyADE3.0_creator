"""Pure-Python helpers shared across the city-builder pipeline.

Lives at the package root rather than inside ``builders/`` because the
fetchers also need them: type coercion for raw API payloads, a
deterministic on-disk cache-key generator for paged downloads, and a
``gml:id``-safe identifier helper that the builders share with anything
else writing XML.

Kept free of xsdata imports so a fetcher importing ``_helpers`` does
not transitively pull in the generated bindings. The xsdata-aware
binding-introspection helper lives in ``builders/_common.py``
(:func:`citygml_energy.city_builder.builders._common.inner_type`).
"""

from __future__ import annotations

import logging
import math
from typing import Any

__all__ = [
    "bbox_cache_key",
    "safe_gml_id",
    "to_clean_str",
    "to_finite_float",
    "to_float",
    "to_int",
]


def safe_gml_id(user_prefix: str, kind: str, source_id: str) -> str:
    """Return a valid XML ``xs:ID`` string.

    BAG identificaties are purely numeric, which is invalid as ``xs:ID``
    (it requires the first character to be a letter or underscore). We
    always prepend a semantic prefix (``pand``, ``bu``, ``addr``,
    ``epc``) so the final id is both valid and self-describing. The
    optional caller prefix is layered on top for multi-city merges
    where two BAG ids could otherwise collide.
    """
    core = f"{kind}_{source_id}"
    if user_prefix:
        return f"{user_prefix}_{core}"
    return core


def to_int(
    value: Any,
    *,
    logger: logging.Logger | None = None,
    label: str = "",
) -> int | None:
    """Return *value* as ``int``, or ``None`` for empty / non-numeric.

    ArcGIS sometimes serialises integer fields as floats (``1960.0``);
    cast through ``float`` first so both ``"1960"`` and ``1960.0``
    round-trip. When *logger* is given, a non-coercible non-empty value
    emits a warning tagged with *label* (e.g. ``"BAG bouwjaar"``) so
    the noise survives to the test log instead of being swallowed.
    """
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        if logger is not None:
            logger.warning(
                "%s integer field not coercible (%r): %s",
                label or "value", value, exc,
            )
        return None


def to_float(
    value: Any,
    *,
    logger: logging.Logger | None = None,
    label: str = "",
) -> float | None:
    """Return *value* as ``float``, or ``None`` for empty / non-numeric.

    Treats ``None``, ``""``, and any value that ``float()`` rejects as
    "absent". *logger* + *label* behave like :func:`to_int`.
    """
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        if logger is not None:
            logger.warning(
                "%s float field not coercible (%r): %s",
                label or "value", value, exc,
            )
        return None


def to_finite_float(value: Any) -> float | None:
    """Return *value* as a finite ``float`` or ``None``.

    NaN-aware variant of :func:`to_float`: NaN, +/-Inf, ``None``, and
    empty strings all collapse to "absent" so they never make it into
    the GML. CFTree writes ``NaN`` for metrics it could not compute
    (missing DTM pixel, degenerate crown), and ``math.isfinite`` avoids
    the float-``==``-NaN trap that ``value != value`` would dance
    around.
    """
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def to_clean_str(value: Any, *, drop_literal_none: bool = False) -> str | None:
    """Return *value* as a non-empty stripped ``str`` or ``None``.

    With *drop_literal_none* set, the literal placeholder strings
    ``"None"`` (any case) and ``"null"`` are also treated as absent.
    Some Dutch GIS layers (notably Emmen's ArcGIS Online tenant) ship
    these as sentinel values for unpopulated cells, and turning them
    into Python ``None`` keeps the resulting GML free of bogus
    "<gen:value>None</gen:value>" elements.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if drop_literal_none and text.lower() in {"none", "null"}:
        return None
    return text


def bbox_cache_key(
    prefix: str,
    bbox: tuple[float, float, float, float],
    *,
    page: int | None = None,
) -> str:
    """Return a deterministic on-disk cache key for a bbox-paged fetch.

    Coordinates are clipped to two decimal places so a sub-centimetre
    rounding drift on the caller's side (e.g. shapely re-projecting a
    boundary polygon) does not invalidate an otherwise-fresh cache
    entry. *page* is appended as ``.p<N>`` when present, matching the
    historical convention used by the BGT and Emmen-BOR fetchers.
    """
    xmin, ymin, xmax, ymax = bbox
    base = f"{prefix}.{xmin:.2f}_{ymin:.2f}_{xmax:.2f}_{ymax:.2f}"
    return f"{base}.p{page}" if page is not None else base
