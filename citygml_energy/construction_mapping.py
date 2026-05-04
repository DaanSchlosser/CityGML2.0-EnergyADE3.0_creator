"""Post-processor: attach ``nrg3:layeredConstruction`` xlink refs.

Split out of :mod:`citygml_energy.geometry` so the mapping concern has
its own place. This module's only public surface is
:func:`apply_construction_mapping`; every helper below it is private
support for that one operation.

The traversal is XSD-agnostic: we walk the whole model via
:func:`citygml_energy.mapping.iter_instances` and for every dataclass
that declares a ``layered_construction`` list field in its bindings, we
append an xlink:href based on ``by_id`` (keyed by ``gml:id``) or
``by_type`` (keyed by the class's XSD element name). Regenerating the
bindings with new surface / opening / zone-boundary classes therefore
picks up matching mappings without code changes.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from .bindings import TypeType
from .core import CityModel
from .mapping import get_fields, iter_instances, resolve_class
from .schema_types import LAYERED_CONSTRUCTION

__all__ = ["apply_construction_mapping"]


def apply_construction_mapping(
    model: CityModel,
    mapping: dict[str, Any],
) -> None:
    """Append ``nrg3:layeredConstruction`` references wherever the XSD permits them.

    Traverses the entire ``CityModel`` and, for each dataclass instance
    that carries a ``layered_construction`` *list* field (per the generated
    bindings), resolves a construction ID via ``by_id`` (keyed by
    ``gml:id``) or falls back to ``by_type`` (keyed by the class's XSD
    element name). A ``LayeredConstruction2`` xlink:href is appended when
    a mapping is found.

    Scope is therefore determined by the bindings, not by hand-maintained
    taxonomy: boundary surfaces, openings, zone boundaries, and any other
    class the XSD gives ``layered_construction`` receive matching mappings
    without code changes. The caller is responsible for keeping the mapping
    keys semantically appropriate for its domain.
    """
    by_type: dict[str, str] = mapping.get("by_type", {})
    by_id: dict[str, str] = mapping.get("by_id", {})

    for obj in iter_instances(model.xsd):
        construction_list = _layered_construction_list(obj)
        if construction_list is None:
            continue
        constr_id = _resolve_construction_id(obj, by_id, by_type)
        if constr_id is not None:
            construction_list.append(_make_construction_ref(constr_id))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


@cache
def _layered_construction_ref_cls() -> type:
    """Resolve the ``nrg3:layeredConstruction`` property-type wrapper once."""
    return resolve_class(LAYERED_CONSTRUCTION)


def _make_construction_ref(construction_id: str) -> Any:
    """Build an xlink:href wrapper pointing at a LayeredConstruction library entry."""
    ref = _layered_construction_ref_cls()(href=f"#{construction_id}")
    ref.type_value = TypeType.SIMPLE
    return ref


def _layered_construction_list(obj: Any) -> list[Any] | None:
    """Return the ``layered_construction`` list on *obj* if present.

    Also verifies the list's element type matches the
    ``nrg3:layeredConstruction`` wrapper. The field name alone isn't
    enough because unrelated xsdata classes could theoretically reuse it.
    """
    # mypy's stub for ``_lru_cache_wrapper.__call__`` wants ``Hashable``;
    # ``type[Any]`` is Hashable at runtime but the stub chain doesn't
    # prove it. Safe to ignore until mypy ships a correct stub.
    info = get_fields(type(obj)).get("layered_construction")  # type: ignore[arg-type]
    if info is None or not info.is_list:
        return None
    if info.inner_type is not _layered_construction_ref_cls():
        return None
    value = getattr(obj, "layered_construction", None)
    return value if isinstance(value, list) else None


def _resolve_construction_id(
    obj: Any,
    by_id: dict[str, str],
    by_type: dict[str, str],
) -> str | None:
    gml_id = getattr(obj, "id", None)
    if isinstance(gml_id, str) and gml_id in by_id:
        return by_id[gml_id]
    type_name = _xsd_type_name(type(obj))
    if type_name and type_name in by_type:
        return by_type[type_name]
    return None


def _xsd_type_name(cls: type) -> str | None:
    """Return the class's XSD element name (``Meta.name`` or class name)."""
    meta = getattr(cls, "Meta", None)
    if meta is None:
        return None
    return getattr(meta, "name", None) or cls.__name__
