"""Construct CityGML 2.0 landcover features from 3D Basisvoorziening objects.

Each :class:`citygml_energy.city_builder.cityjson_landcover_parse.ParsedLandcover`
carries a
:class:`citygml_energy.city_builder.landcover_class.LandcoverDisposition`,
decided once by :func:`citygml_energy.city_builder.landcover_class.classify_landcover`,
that names the target CityGML 2.0 feature:

==================  ==========================
3DBV CityObject     CityGML 2.0 feature
==================  ==========================
``LandUse``         ``luse:LandUse``
``Road``            ``tran:Road``
``WaterBody``       ``wtr:WaterBody``
``PlantCover``      ``veg:PlantCover``
``Bridge``          ``brid:Bridge``
*anything else*     ``gen:GenericCityObject``
==================  ==========================

This module only turns that decision into xsdata. The draped LoD 1.2 surfaces
attach as ``lod1MultiSurface`` (or ``lod1Geometry`` for the generic fallback,
whose geometry slot is an open ``gml:GeometryPropertyType``). The disposition's
cleaned classification labels ride into the open ``gml:CodeType`` slots with a
codeSpace naming the vocabulary (``class`` under the coarse 3DBV class list,
``function`` / ``usage`` under the IMGeo BGT handbook); the source object's
ULID and a little provenance attach as a ``core:externalReference`` plus
``gen:stringAttribute`` siblings. Building / BuildingPart objects never reach
here (:func:`classify_landcover` drops them, since the 3DBAG path already
supplies richer buildings).
"""

from __future__ import annotations

from typing import Any

from ...bindings import (
    CodeType,
    ExternalObjectReferenceType,
    ExternalReferenceType,
    GeometryPropertyType,
    StringAttribute,
)
from ...gml_builders import build_multi_surface
from ...mapping import resolve_class
from ...namespaces import CS_3DBV_CLASS, CS_IMGEO_BGT
from ...schema_types import GENERIC_CITY_OBJECT
from .._helpers import safe_gml_id
from ..cityjson_landcover_parse import ParsedLandcover
from ..config import BuildContext
from ..fetchers.threedbv import THREEDBV_INFORMATION_SYSTEM_URL
from ..landcover_class import LandcoverDisposition, clean_label

__all__ = ["build_landcover_object"]

# Provenance attributes worth keeping as generic string attributes (everything
# else in the 3DBV attribute dict is either classification, already resolved
# into the disposition, or noise such as empty registration dates).
_PROVENANCE_KEYS: tuple[tuple[str, str], ...] = (
    ("bronhouder", "bronhouder"),
    ("bgt_status", "bgtStatus"),
)


def build_landcover_object(
    parsed: ParsedLandcover,
    build_context: BuildContext = BuildContext(),
) -> Any:
    """Build the CityGML 2.0 landcover feature for one parsed 3DBV object.

    Resolves the feature named by ``parsed.disposition`` (a
    ``gen:GenericCityObject`` for an unmapped type), attaches the draped
    surfaces as ``lod1MultiSurface`` / ``lod1Geometry``, fills the open
    classification slots from the disposition's labels, and links the source
    object through a ``core:externalReference``. Binding-resolution failures
    still raise (a missing class is a schema error that should surface loudly).
    """
    disposition = parsed.disposition
    cls = resolve_class(disposition.feature_qname)
    gml_id = safe_gml_id(build_context.gml_id_prefix, disposition.id_kind, parsed.object_id)
    obj = cls(id=gml_id)

    ms_prop = build_multi_surface(
        f"{gml_id}_lod1ms",
        parsed.polygons,
        srs_name=build_context.srs_name,
        srs_dimension=build_context.srs_dimension,
    )
    if disposition.feature_qname == GENERIC_CITY_OBJECT:
        # gen:GenericCityObject.lod1Geometry is a generic gml:GeometryProperty,
        # so the MultiSurface is re-wrapped (a single-level rewrap, not a copy
        # of the polygon data), mirroring the vegetation lod3Geometry path.
        obj.lod1_geometry = GeometryPropertyType(multi_surface=ms_prop.multi_surface)
    else:
        obj.lod1_multi_surface = ms_prop

    _apply_classification(obj, disposition)
    _apply_provenance(obj, parsed)
    return obj


def _apply_classification(obj: Any, disposition: LandcoverDisposition) -> None:
    """Fill the ``class`` / ``function`` / ``usage`` CodeType slots.

    The labels arrive already cleaned on the disposition, so this only wraps
    each present value in a ``gml:CodeType`` under the codeSpace naming its
    vocabulary: the coarse 3DBV class list for ``class``, the IMGeo BGT
    handbook for ``function`` and ``usage``.
    """
    if disposition.class_value is not None:
        obj.class_value = CodeType(value=disposition.class_value, code_space=CS_3DBV_CLASS)

    for value in disposition.function_values:
        obj.function.append(CodeType(value=value, code_space=CS_IMGEO_BGT))

    if disposition.usage_value is not None:
        obj.usage.append(CodeType(value=disposition.usage_value, code_space=CS_IMGEO_BGT))


def _apply_provenance(obj: Any, parsed: ParsedLandcover) -> None:
    """Link the source 3DBV object and keep a little provenance.

    ``ExternalObjectReferenceType`` is a choice of ``name`` or ``uri``; the
    3DBV object id is an opaque ULID, not a dereferenceable URL, so it lands
    in ``name`` (the raw-handle branch) under the 3DBV information system.
    """
    obj.external_reference.append(
        ExternalReferenceType(
            information_system=THREEDBV_INFORMATION_SYSTEM_URL,
            external_object=ExternalObjectReferenceType(name=parsed.object_id),
        )
    )
    for key, attr_name in _PROVENANCE_KEYS:
        value = clean_label(parsed.attributes.get(key))
        if value is not None:
            obj.string_attribute.append(StringAttribute(name=attr_name, value=value))
