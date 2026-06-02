"""Cross-domain helpers shared between the builder sub-modules.

Lives inside ``builders/`` (not in ``city_builder/_helpers.py``) because
it imports xsdata-binding-aware code (:mod:`citygml_energy.mapping`),
and the layering rule for the wider package keeps fetchers free of
xsdata. Only the builder modules import from here.

UOM tokens are pinned as constants so they match the KITModelViewer
``Data/UOMList.xml`` ids exactly, the same convention
used in :mod:`citygml_energy.city_builder.solar_panels`. Mismatched UOM
strings render fine but the viewer's Properties panel then displays the
raw token instead of a translated unit name. The energy-domain tokens
introduced for EP-online (``kWh/m2/a``, ``kg/m2/a``, ``MJ/a``, ``kg/a``)
live in :mod:`citygml_energy.city_builder.energy_resources` because that
is where the regime semantics that motivate them are documented;
``UOM_KWH_PER_M2_PER_A`` and ``UOM_MJ_PER_A`` are exported publicly
from there because the EPC builder also reuses them on
``EnergyPerformanceCertificate.value``. ``percent`` is shared between
the renewable-share emission (BuildingUnit) and any future percentage
attribute, so it lives here.
"""

from __future__ import annotations

from functools import cache

from ...mapping import get_fields

__all__ = [
    "UOM_AREA_M2",
    "UOM_DEGREES",
    "UOM_METRES",
    "UOM_PERCENT",
    "UOM_VOLUME_M3",
    "inner_type",
]


UOM_METRES: str = "m"  # METRE primary id
UOM_AREA_M2: str = "m2"  # SQUARE_METRE primary id
UOM_VOLUME_M3: str = "m3"  # CUBIC_METRE primary id
UOM_PERCENT: str = "percent"  # PERCENTAGE primary id (NOT "%", which is a sign-glyph)
# DEGREE altId in UOMList.xml (primary id is "grad"; "deg" is the more
# common ASCII synonym and is what the viewer's Properties panel
# accepts as input for filters. Both PV-collector orientations and the
# Energy ADE 3.0 ``bdgBdrySurf{Azimuth,Inclination}`` use this token.
UOM_DEGREES: str = "deg"


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
