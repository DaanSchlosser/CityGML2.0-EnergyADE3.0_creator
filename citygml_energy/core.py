"""CityModel convenience wrapper around xsdata-generated bindings."""

from __future__ import annotations

import dataclasses
from functools import lru_cache
from pathlib import Path
from typing import Any

from .bindings import (
    BoundedBy,
    CityModel as XsdCityModel,
    CityObjectMember,
    Description,
    DirectPositionType,
    Envelope,
    Name,
)
from .serialization import serialize_to_file, serialize_to_string


class CityModel:
    """Convenience wrapper around the xsdata-generated ``CityModelType``.

    Provides a builder-style ``add()`` API and ``write()`` / ``to_string()``
    for easy serialization.
    """

    def __init__(
        self,
        *,
        gml_id: str | None = None,
        gml_description: str | None = None,
        gml_name: str | None = None,
        srs_name: str | None = None,
        srs_dimension: int = 3,
        lower_corner: list[float] | None = None,
        upper_corner: list[float] | None = None,
    ) -> None:
        self._model = XsdCityModel(
            id=gml_id,
            description=Description(value=gml_description) if gml_description else None,
            name=[Name(value=gml_name)] if gml_name else [],
        )
        if srs_name and lower_corner and upper_corner:
            self._model.opengis_net_gml_bounded_by = BoundedBy(
                envelope=Envelope(
                    lower_corner=DirectPositionType(
                        value=lower_corner, srs_dimension=srs_dimension
                    ),
                    upper_corner=DirectPositionType(
                        value=upper_corner, srs_dimension=srs_dimension
                    ),
                    srs_name=srs_name,
                    srs_dimension=srs_dimension,
                ),
            )

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

        The *field_name* is the attribute name on ``CityObjectMember`` that
        should hold this object (e.g. ``"building"``).  If omitted, it is
        resolved by matching the object's type against ``CityObjectMember``
        field type annotations.
        """
        if field_name is None:
            field_name = _resolve_member_field(type(city_object))

        member = CityObjectMember(**{field_name: city_object})
        self._model.city_object_member.append(member)
        return self

    def to_string(self, *, indent: str = "\t") -> str:
        """Serialize to an XML string."""
        return serialize_to_string(self._model, indent=indent)

    def write(self, filepath: str | Path, *, indent: str = "\t") -> None:
        """Write the CityModel to a GML/XML file."""
        serialize_to_file(self._model, filepath, indent=indent)


@lru_cache(maxsize=None)
def _build_member_type_map() -> dict[type, str]:
    """Build a mapping from concrete types to CityObjectMember field names."""
    import typing

    result: dict[type, str] = {}
    for f in dataclasses.fields(CityObjectMember):
        hints = typing.get_type_hints(CityObjectMember)
        hint = hints.get(f.name)
        if hint is None:
            continue
        # Extract the concrete type from ``None | SomeType``
        args = getattr(hint, "__args__", None)
        if args:
            for arg in args:
                if arg is not type(None):
                    result[arg] = f.name
        elif isinstance(hint, type):
            result[hint] = f.name
    return result


def _resolve_member_field(cls: type) -> str:
    """Find the CityObjectMember field name for an xsdata binding class."""
    type_map = _build_member_type_map()
    # Check exact match first, then walk MRO for base classes
    if cls in type_map:
        return type_map[cls]
    for base in cls.__mro__[1:]:
        if base in type_map:
            return type_map[base]
    raise TypeError(
        f"Cannot find a CityObjectMember field for {cls.__name__}. "
        f"Pass field_name= explicitly."
    )
