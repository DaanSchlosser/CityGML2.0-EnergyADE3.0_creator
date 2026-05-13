"""Model-walking seam for ADE-extension property emitters.

The CityGML 2.0 + Energy ADE 3.0 XSDs share one pattern for grafting derived
information onto an already-built feature tree: declare an element with
``substitutionGroup="..._GenericApplicationPropertyOf..."`` and let xsdata
turn it into a list field on every subclass of the target type. The
``bdgBdrySurf*`` family, ``bdgOpn*`` family, ``layeredConstruction``, and
``relatedTo`` all follow that pattern (see Energy_ADE_3.0_beta8.xsd
elements at lines 1339, 1359, 1996-2097). A future ADE (Scenario ADE,
Noise ADE, ...) will extend the same way.

This module is the one seam that walks the model once and stamps such
properties. ADE-specific knowledge lives in **emitters**: small records
that name a target list field and a pure compute function. The seam
itself is XSD-agnostic; it discovers list fields by name via xsdata's
generated dataclass introspection, applies emitters in registration
order per object, and stays idempotent (already-populated lists are
left untouched).

What stays out of this module:

* The Energy ADE 3.0 emitters themselves (geometry math, material
  reduction, construction xlink construction) — those live in
  :mod:`citygml_energy.boundary_attributes` and
  :mod:`citygml_energy.construction_mapping`, which export ``EMITTERS``
  and ``SETUPS`` lists. Adding a new ADE means dropping a sibling module
  with its own ``EMITTERS`` / ``SETUPS`` and appending them at the call
  site; no edit here.
* The config-iteration shape used by
  :func:`citygml_energy.device_relations.apply_device_relations`. That
  driver walks a JSON ``{device_id: [targets]}`` dict and raises on
  unresolved keys; a model-walk seam cannot detect a config entry whose
  device is missing. The two patterns are intentionally separate.

Verification: :func:`verify_emitters_against_bindings` resolves every
emitter's ``field_name`` against the loaded bindings and raises when no
dataclass declares that list field. Call it at startup (or let
:func:`apply_derived_attributes` call it the first time per process) so
an XSD rename surfaces as a loud error instead of a silently-empty
output attribute.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .core import CityModel
from .mapping import iter_instances
from .namespaces import iter_binding_classes

__all__ = [
    "DerivedAttribute",
    "DerivedContext",
    "Setup",
    "apply_derived_attributes",
    "verify_emitters_against_bindings",
]


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class DerivedContext:
    """Open attribute bag passed to setups and compute functions.

    An open ``__dict__`` is the contract: a setup hook stashes any
    pre-computed index it needs on the context, downstream compute
    functions read it via attribute access, the seam itself treats every
    attribute as opaque payload. Slots are deliberately *not* used here
    — they would block ``setattr`` for keys the seam learns about only
    at call time (kwargs to :func:`apply_derived_attributes`, or names
    introduced by a future emitter).
    """

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"DerivedContext({items})"


Setup = Callable[[CityModel, DerivedContext], None]
"""Hook run once at the start of :func:`apply_derived_attributes`.

Setups own preparation work that emitters share, e.g. building a
material-by-id index that every boundary-surface emitter consumes.
"""


_Compute = Callable[[Any, DerivedContext], "Iterable[Any] | None"]


@dataclass(frozen=True, slots=True)
class DerivedAttribute:
    """One emitter: a list field name + a compute function.

    ``field_name`` is the Python attribute name on the bindings dataclass
    (e.g. ``"bdg_bdry_surf_thickness"``). The seam reads
    ``getattr(obj, field_name)`` and only acts when the value is a list.

    ``compute`` returns the dataclass instances to append, or ``None`` to
    skip this object. The compute function owns construction of the
    typed measure / wrapper / nested feature; the seam never
    instantiates bindings classes itself. This keeps each ADE's
    schema coupling localised to its compute functions instead of
    leaking into a shared factory.
    """

    field_name: str
    compute: _Compute


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def apply_derived_attributes(
    model: CityModel,
    *,
    emitters: Sequence[DerivedAttribute],
    setups: Sequence[Setup] = (),
    verify: bool = True,
    **context_kwargs: Any,
) -> None:
    """Walk *model* once and append derived attributes from *emitters*.

    Per object, emitters are visited in registration order; per emitter,
    the seam:

    1. Reads ``getattr(obj, emitter.field_name)``. Skips when absent or
       not a list.
    2. Skips when the list is already non-empty (idempotent: re-running
       does not duplicate entries).
    3. Calls ``emitter.compute(obj, ctx)`` and extends the list with
       whatever it returns.

    Ordering matters when emitter B reads what emitter A wrote on the
    same object (the canonical case is boundary thickness reading
    ``layered_construction``). Order emitters at the call site so the
    writer precedes the reader.

    *verify* runs :func:`verify_emitters_against_bindings` once at entry
    when ``True`` (the default). Disable in tests that supply a stub
    emitter for a not-yet-bound field.

    Extra keyword arguments populate the :class:`DerivedContext` passed
    to setups and compute functions, so any per-run config the emitters
    need (the construction mapping dict, an external resolver, …) is
    visible to them without globals.
    """
    if verify and emitters:
        verify_emitters_against_bindings(emitters)

    ctx = DerivedContext(**context_kwargs)

    for setup in setups:
        setup(model, ctx)

    for obj in iter_instances(model.xsd):
        for emitter in emitters:
            target_list = getattr(obj, emitter.field_name, None)
            if not isinstance(target_list, list):
                continue
            if target_list:
                # Idempotent: another path (city-builder geometry-only
                # attacher, a prior apply call) already populated this
                # list. Trust the prior write.
                continue
            values = emitter.compute(obj, ctx)
            if not values:
                continue
            target_list.extend(values)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_emitters_against_bindings(emitters: Sequence[DerivedAttribute]) -> None:
    """Raise when an emitter names a field no bindings dataclass declares.

    Detects the silent failure mode that motivates this seam: an XSD
    rename (or an ADE that drops a property) leaves an emitter pointing
    at a Python field name that no longer exists. Without this check,
    ``apply_derived_attributes`` would walk the model, find that
    ``getattr(obj, field_name, None)`` returns ``None`` on every object,
    and emit nothing. The resulting GML would validate but be missing
    the derived attribute; the regression only surfaces downstream.

    The check is precise per emitter: each ``field_name`` must appear on
    at least one dataclass in the bindings as a ``list[...]`` field.
    Non-list fields are rejected even when the name matches, because
    every supported ADE-property emission appends to a list.

    Raises :class:`ValueError` listing every offending emitter; one call
    surfaces every problem at once rather than failing field-by-field.
    """
    known = _list_field_names()
    missing = [e.field_name for e in emitters if e.field_name not in known]
    if missing:
        raise ValueError(
            "Derived-attribute emitter(s) reference field name(s) not declared "
            "as list fields on any bindings dataclass: "
            f"{sorted(set(missing))}. "
            "This usually means the XSD was renamed: update the emitter's "
            "DerivedAttribute(field_name=...) to match the regenerated bindings."
        )


@lru_cache(maxsize=1)
def _list_field_names() -> frozenset[str]:
    """Every Python field name that appears as a ``list[...]`` on any bindings dataclass.

    Cached because the bindings module is immutable per process and the
    walk is non-trivial: it visits every generated dataclass once. The
    cache is keyed on nothing because the bindings module never changes
    after import; tests that swap bindings will have to clear it
    explicitly.
    """
    out: set[str] = set()
    import typing

    for info in iter_binding_classes():
        cls = info.cls
        if not dataclasses.is_dataclass(cls):
            continue
        try:
            hints = typing.get_type_hints(cls)
        except (NameError, AttributeError):
            # Defensive: some xsdata-generated classes have forward
            # refs to types in other modules. ``get_type_hints`` can
            # fail on them; we skip rather than fail the whole walk
            # since one unresolvable class doesn't invalidate the rest.
            continue
        for f in dataclasses.fields(cls):
            hint = hints.get(f.name)
            if hint is None:
                continue
            if getattr(hint, "__origin__", None) is list:
                out.add(f.name)
    return frozenset(out)
