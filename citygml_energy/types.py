"""Value types for CityGML / Energy ADE properties.

New code should use the xsdata-generated types directly::

    from citygml_energy.bindings import CodeType, MeasureType, ScaleType

The legacy types below (``CodeValue``, ``MeasureValue``, ``ScaleValue``,
``XlinkRef``) are kept for backward compatibility with modules that have
not yet been migrated to xsdata bindings.
"""

from dataclasses import dataclass

# Re-export xsdata-generated equivalents for convenience.
from .bindings import CodeType, MeasureType, ScaleType  # noqa: F401


# ---------------------------------------------------------------------------
# Legacy types (used by base.py, building.py, energy_ade.py, factory.py)
# ---------------------------------------------------------------------------


@dataclass
class CodeValue:
    """Represents ``gml:CodeType`` -- a string value with an optional
    ``codeSpace`` attribute.
    """

    value: str
    code_space: str | None = None


@dataclass
class MeasureValue:
    """Represents ``gml:MeasureType`` -- a numeric value with a required ``uom``."""

    value: int | float | str
    uom: str

    @property
    def text(self) -> str:
        return str(self.value)


@dataclass
class ScaleValue:
    """Represents ``gml:ScaleType`` -- same structure as MeasureType."""

    value: int | float | str = 0.0
    uom: str = "unit interval"

    @property
    def text(self) -> str:
        return str(self.value)


@dataclass
class XlinkRef:
    """An ``xlink:href`` reference to another object."""

    href: str
