"""Energy ADE 3.0 emitter: ``nrg3:layeredConstruction`` xlink references.

Plug-in module for the :mod:`citygml_energy.derived_attributes` seam.
Exports one :class:`DerivedAttribute` that, on every dataclass carrying
a ``layered_construction`` list field, appends an xlink:href pointing at
a LayeredConstruction library entry. The construction is resolved per
object via:

* ``construction_mapping["by_id"]``, keyed on the object's ``gml:id``.
* ``construction_mapping["by_type"]``, keyed on the object's XSD element
  name (``WallSurface``, ``RoofSurface``, ...). Fallback when the gml:id
  is not in the by-id map.

The compute function reads its config from the
:class:`citygml_energy.derived_attributes.DerivedContext` under
``construction_mapping`` (set by the call site).

The traversal is binding-driven: every dataclass the XSD declares
``layered_construction`` on participates automatically. Regenerating the
bindings with new surface / opening / zone-boundary classes therefore
picks up matching mappings without code changes.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from .bindings import TypeType
from .derived_attributes import DerivedAttribute, DerivedContext
from .mapping import get_fields, resolve_class
from .schema_types import LAYERED_CONSTRUCTION

__all__ = ["EMITTERS"]


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------


def _compute_layered_construction(
    obj: Any, ctx: DerivedContext,
) -> list[Any] | None:
    """Return ``[xlink-wrapper]`` when *obj* maps to a construction, else None.

    The seam handles idempotence (only called when ``layered_construction``
    is empty) and field-presence (only called when the dataclass declares
    the field as a list). The check on element-type matching is kept
    locally: an unrelated xsdata class could in principle reuse the name
    ``layered_construction``, and instantiating the wrong wrapper would
    serialise to wrong XML rather than fail.
    """
    info = get_fields(type(obj)).get("layered_construction")
    if info is None or not info.is_list:
        return None
    if info.inner_type is not _layered_construction_ref_cls():
        return None

    mapping_cfg: dict[str, Any] = getattr(ctx, "construction_mapping", None) or {}
    by_id: dict[str, str] = mapping_cfg.get("by_id", {})
    by_type: dict[str, str] = mapping_cfg.get("by_type", {})

    constr_id = _resolve_construction_id(obj, by_id, by_type)
    if constr_id is None:
        return None
    return [_make_construction_ref(constr_id)]


EMITTERS: tuple[DerivedAttribute, ...] = (
    DerivedAttribute(
        field_name="layered_construction",
        compute=_compute_layered_construction,
    ),
)


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
