"""Landcover classification: what one 3D Basisvoorziening object becomes.

This module owns the single judgement the landcover path used to make in two
places. Given one 3DBV ``CityObject`` (its ``type`` and its raw attribute
dict) :func:`classify_landcover` returns either ``None`` (drop it) or a
:class:`LandcoverDisposition` that says which CityGML feature it becomes and
which classification labels it carries.

Keeping the judgement here, behind one small call, is what stops the parser
and the builder from disagreeing about a 3DBV object. The parser used to skip
buildings by CityObject ``type`` while the builder mapped ``type`` to a feature
and separately read ``3df_class``; a building filed under the ``LandUse`` type
and tagged ``3df_class`` ``Building`` slipped the type-only skip and rendered
as ground. Now the keep-or-drop test, the feature mapping, and the label
extraction read ``type``, ``3df_class``, and the ``bgt_*`` attributes in this
one function, so they cannot drift apart.

The module is pure standard library plus the ``schema_types`` qname constants
(plain strings), so it carries no xsdata binding and is trivial to unit-test:
one ``CityObject`` shape in, one :class:`LandcoverDisposition` (or ``None``)
out. Turning a disposition into an xsdata feature stays in the landcover
builder; choosing the codeSpace for each label stays there too. This function
decides only the semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..schema_types import (
    BRIDGE,
    GENERIC_CITY_OBJECT,
    LAND_USE,
    PLANT_COVER,
    ROAD,
    WATER_BODY,
)

__all__ = [
    "LANDCOVER_FEATURE_QNAMES",
    "LandcoverDisposition",
    "classify_landcover",
    "clean_label",
]


# CityObject types that are never landcover. 3DBV buildings duplicate the
# richer 3DBAG buildings the pipeline already emits, so they are dropped.
_SKIP_TYPES: frozenset[str] = frozenset({"Building", "BuildingPart"})

# 3DBV also files building geometry under ``LandUse`` objects tagged
# ``3df_class`` ``Building`` (in the Leiden 2 km tile two thirds of the
# ``LandUse`` objects are buildings, vertical, up to 25 m tall). The type skip
# alone misses them, so the semantic class is a second drop signal.
_CLASS_KEY = "3df_class"
_SKIP_CLASSES: frozenset[str] = frozenset({"Building"})

# The landcover taxonomy: the single ordered table mapping a 3DBV CityObject
# type to the CityGML feature it becomes and the prefix on its ``gml:id``. The
# generic fallback (``object_type`` ``None``) is last and catches any unmapped
# type (``OtherConstruction`` and any future type), so "convert everything in
# the tile" never silently drops an object. This is the one place the
# membership and order of the landcover feature set live: the appearance palette
# and the pipeline count both derive their class set from
# :data:`LANDCOVER_FEATURE_QNAMES` rather than re-listing it, so a new row here
# extends the classifier, the painter, and the counter together (mirroring the
# ``device_relations.RELATION_KINDS`` registry pattern).
_LANDCOVER_TAXONOMY: tuple[tuple[str | None, str, str], ...] = (
    ("LandUse", LAND_USE, "landuse"),
    ("Road", ROAD, "road"),
    ("WaterBody", WATER_BODY, "water"),
    ("PlantCover", PLANT_COVER, "plantcover"),
    ("Bridge", BRIDGE, "bridge"),
    (None, GENERIC_CITY_OBJECT, "landobject"),
)

# Kept 3DBV type -> (feature qname, gml:id prefix), projected from the taxonomy.
_TYPE_TO_FEATURE: dict[str, tuple[str, str]] = {
    object_type: (qname, id_kind)
    for object_type, qname, id_kind in _LANDCOVER_TAXONOMY
    if object_type is not None
}
# The generic fallback row (the unmapped-type catch-all), projected likewise.
_GENERIC_FEATURE: tuple[str, str] = next(
    (qname, id_kind) for object_type, qname, id_kind in _LANDCOVER_TAXONOMY if object_type is None
)

# The CityGML feature qnames the taxonomy produces, in paint order. The
# landcover appearance palette and the pipeline's landcover count both build
# their class set from this tuple, so the taxonomy stays single-sourced.
LANDCOVER_FEATURE_QNAMES: tuple[str, ...] = tuple(
    qname for _object_type, qname, _id_kind in _LANDCOVER_TAXONOMY
)

# Attribute keys that hold the classification labels. ``3df_class`` is the
# coarse 3DBV class, ``bgt_functie`` / ``bgt_type`` the BGT function, and
# ``bgt_fysiekvoorkomen`` the physical appearance. The builder ships each
# verbatim into an open ``gml:CodeType`` under the codeSpace that names its
# vocabulary.
_FUNCTION_KEYS: tuple[str, ...] = ("bgt_functie", "bgt_type")
_USAGE_KEY = "bgt_fysiekvoorkomen"


@dataclass(frozen=True, slots=True)
class LandcoverDisposition:
    """What one kept 3DBV object resolves to: its feature and its labels.

    Attributes:
        feature_qname: the CityGML feature the object becomes, e.g.
            ``"luse:LandUse"`` or ``"gen:GenericCityObject"`` for the fallback.
        id_kind: the semantic prefix on the feature's ``gml:id``.
        class_value: the coarse 3DBV class label, or ``None`` when absent.
        function_values: the BGT function labels, in source order, empty when
            none are present.
        usage_value: the physical-appearance label, or ``None`` when absent.

    The labels are the cleaned values, not the raw attribute keys, so the
    builder only wraps them in a ``CodeType`` with the right codeSpace.
    """

    feature_qname: str
    id_kind: str
    class_value: str | None = None
    function_values: tuple[str, ...] = field(default_factory=tuple)
    usage_value: str | None = None


def classify_landcover(
    object_type: str | None,
    attributes: dict[str, Any],
) -> LandcoverDisposition | None:
    """Return the disposition of one 3DBV object, or ``None`` to drop it.

    Drops the object when its CityObject *object_type* is a building type or
    its ``3df_class`` attribute marks it a building. Otherwise maps the type to
    its CityGML feature (a generic city object for an unmapped type) and reads
    the classification labels from ``3df_class`` and the ``bgt_*`` attributes.
    """
    if object_type in _SKIP_TYPES:
        return None
    if attributes.get(_CLASS_KEY) in _SKIP_CLASSES:
        return None

    qname, id_kind = _TYPE_TO_FEATURE.get(object_type or "", _GENERIC_FEATURE)
    function_values = tuple(
        value for key in _FUNCTION_KEYS if (value := clean_label(attributes.get(key))) is not None
    )
    return LandcoverDisposition(
        feature_qname=qname,
        id_kind=id_kind,
        class_value=clean_label(attributes.get(_CLASS_KEY)),
        function_values=function_values,
        usage_value=clean_label(attributes.get(_USAGE_KEY)),
    )


def clean_label(value: Any) -> str | None:
    """Return a stripped non-empty string, or ``None``; the landcover cleaner.

    The 3DBV attribute dict uses ``""`` for an absent value, so an empty or
    whitespace-only string is treated as missing rather than carried as a blank
    label. Shared with the landcover builder so the classifier and the builder
    clean labels and provenance identically.

    Stricter than :func:`citygml_energy.city_builder._helpers.to_clean_str` on
    purpose: a non-string value yields ``None`` (never a coerced ``str(value)``),
    because a classification label or provenance string must be a genuine
    string, not a stringified number or list.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
