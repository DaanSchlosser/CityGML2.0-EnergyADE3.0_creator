"""Cross-domain helpers shared between the builder sub-modules.

Lives inside ``builders/`` (not in ``city_builder/_helpers.py``) because
it imports xsdata-binding-aware code (:mod:`citygml_energy.mapping`),
and the layering rule for the wider package keeps fetchers free of
xsdata. Only the builder modules import from here.

UOM tokens used to be declared here; they now live in
:mod:`citygml_energy.units` (the package-wide vocabulary, one
declaration per token together with its KITModelViewer
``Data/UOMList.xml`` registration notes). Import them from there.
"""

from __future__ import annotations

from functools import cache

from ...mapping import get_fields

__all__ = [
    "inner_type",
]


@cache
def inner_type(parent_cls: type, field_name: str) -> type | None:
    """Return the unwrapped inner type of ``parent_cls.field_name`` or ``None``.

    Memoised by ``(parent_cls, field_name)``: the answer is a pure
    function of the binding class and never varies across runs. Used by
    the builders to resolve the wrapper class for a CityGML element
    without having to hard-code the xsdata-generated name (e.g.
    ``BuildingPropertyType`` or ``BuildingUnitPropertyType``), which
    can change across regenerated bindings.
    """
    info = get_fields(parent_cls).get(field_name)
    if info is None or not isinstance(info.inner_type, type):
        return None
    return info.inner_type
