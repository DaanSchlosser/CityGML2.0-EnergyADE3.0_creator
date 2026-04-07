"""High-level document builder for CityGML 2.0 + Energy ADE 3.0 files."""
from __future__ import annotations

from typing import Any, Optional

from .core import CityModel, Envelope


class GMLDocument:
    """Convenience wrapper around :class:`CityModel`.

    Usage::

        doc = GMLDocument(description="My city", name="Example City")
        doc.add_building(building)
        doc.write("output.gml")
    """

    def __init__(
        self,
        description: Optional[str] = None,
        name: Optional[str] = None,
        envelope: Optional[Envelope] = None,
    ) -> None:
        self.model = CityModel(
            gml_description=description,
            gml_name=name,
            envelope=envelope,
        )

    def add_building(self, building: Any) -> "GMLDocument":
        self.model.add(building)
        return self

    def add(self, city_object: Any) -> "GMLDocument":
        self.model.add(city_object)
        return self

    def to_string(self, **kwargs: Any) -> str:
        return self.model.to_string(**kwargs)

    def write(self, filepath: str, **kwargs: Any) -> None:
        self.model.write(filepath, **kwargs)
