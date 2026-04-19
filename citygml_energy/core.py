"""CityModel convenience wrapper around xsdata-generated bindings."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from .bindings import (
    BoundedBy,
    CityObjectMember,
    Description,
    Envelope,
    Name,
)
from .bindings import (
    CityModel as XsdCityModel,
)
from .mapping import attach_child, get_fields
from .serialization import serialize_to_file, serialize_to_string

# The CityGML 2.0 CityModel exposes four inherited feature-member wrappers
# (city_object_member, feature_member, feature_members, appearance_member)
# all of which can technically hold a Building via property-type indirection.
# The *semantic* CityGML convention is to use city:cityObjectMember; this
# hint keeps :func:`mapping.attach_child` unambiguous without needing a
# hand-maintained type-to-field map on this module.
_MEMBER_FIELD_HINT = "city_object_member"


class CityModel:
    """Convenience wrapper around the xsdata-generated ``CityModelType``.

    Provides a builder-style :meth:`add` API and :meth:`write` /
    :meth:`to_string` for serialization. The bounding envelope is written
    by :func:`citygml_energy.geometry.apply_geometry_sources`, so this
    wrapper does not accept bbox arguments: any value set at construction
    would be overwritten as soon as STEP geometry is applied.
    """

    def __init__(
        self,
        *,
        gml_id: str | None = None,
        gml_description: str | None = None,
        gml_name: str | None = None,
    ) -> None:
        self._model = XsdCityModel(
            id=gml_id,
            description=Description(value=gml_description) if gml_description else None,
            name=[Name(value=gml_name)] if gml_name else [],
        )
        # STEP layer name → gml:id of every attached boundary surface.
        # Populated by the geometry pipeline; consumed by any step that
        # resolves JSON-declared relations (``installed_on``, …) to their
        # concrete CityObject targets.
        self.surface_name_index: dict[str, str] = {}

    @property
    def xsd(self) -> XsdCityModel:
        """Access the underlying xsdata-generated CityModel object."""
        return self._model

    @property
    def gml_name(self) -> str | None:
        if self._model.name:
            return self._model.name[0].value
        return None

    @gml_name.setter
    def gml_name(self, value: str | None) -> None:
        if value is None:
            self._model.name = []
        elif self._model.name:
            self._model.name[0].value = value
        else:
            self._model.name = [Name(value=value)]

    @property
    def gml_description(self) -> str | None:
        if self._model.description:
            return self._model.description.value
        return None

    @gml_description.setter
    def gml_description(self, value: str | None) -> None:
        if value is None:
            self._model.description = None
        elif self._model.description:
            self._model.description.value = value
        else:
            self._model.description = Description(value=value)

    def add_member(self, member: CityObjectMember) -> CityModel:
        """Add a pre-built ``CityObjectMember``."""
        self._model.city_object_member.append(member)
        return self

    def add(self, city_object: Any, *, field_name: str | None = None) -> CityModel:
        """Add a city object (Building, etc.) as a ``cityObjectMember``.

        *field_name* is the attribute name on ``CityObjectMember`` that
        should hold this object (e.g. ``"building"``). When omitted,
        :func:`mapping.attach_child` resolves it by matching the object's
        class against the CityObjectMember wrapper's field types.
        """
        if field_name is None:
            attach_child(self._model, city_object, field_hint=_MEMBER_FIELD_HINT)
        else:
            self._model.city_object_member.append(
                CityObjectMember(**{field_name: city_object})
            )
        return self

    def set_envelope(self, envelope: Envelope) -> None:
        """Attach *envelope* as the model's ``gml:boundedBy``.

        The xsdata-generated field name that carries this wrapper is a
        disambiguation artifact of how xsdata resolves repeated element
        names across GML's inheritance chain (not an XSD element name),
        so we resolve it by type-matching ``BoundedBy`` against the
        CityModel's fields instead of hardcoding the field name.
        Regenerating the bindings with different xsdata options therefore
        cannot silently break the envelope write.
        """
        field = _resolve_bounded_by_field()
        setattr(self._model, field, BoundedBy(envelope=envelope))

    def to_string(self, *, indent: str = "\t") -> str:
        """Serialize to an XML string."""
        return serialize_to_string(self._model, indent=indent)

    def write(self, filepath: str | Path, *, indent: str = "\t") -> None:
        """Write the CityModel to a GML/XML file."""
        serialize_to_file(self._model, filepath, indent=indent)


@cache
def _resolve_bounded_by_field() -> str:
    """Return the CityModel Python attribute that holds ``gml:boundedBy``.

    Discovered once per process by scanning CityModel's fields for the
    unique non-list field whose inner type is :class:`BoundedBy`.
    """
    matches = [
        info.name
        for info in get_fields(XsdCityModel).values()
        if info.inner_type is BoundedBy and not info.is_list
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one non-list BoundedBy field on CityModel, "
            f"found {len(matches)}: {matches}. "
            "The bindings may have been regenerated against a CityGML revision "
            "that reshaped AbstractFeatureType; review core.set_envelope."
        )
    return matches[0]


