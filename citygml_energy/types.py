"""Small reusable value types that map to XSD simple/complex types."""

from dataclasses import dataclass


@dataclass
class CodeValue:
    """Represents ``gml:CodeType`` -- a string value with an optional
    ``codeSpace`` attribute.

    Usage::

        CodeValue("1000", code_space="http://.../_class.xml")
        CodeValue("unknown")           # no codeSpace emitted
    """

    value: str
    code_space: str | None = None


@dataclass
class MeasureValue:
    """Represents ``gml:MeasureType`` (and ``gml:LengthType``,
    ``gml:AreaType``, ``gml:VolumeType``, ``gml:AngleType``, etc.)
    -- a numeric value with a required ``uom`` attribute.

    The *value* can be a number or a string.  Use a string when you need
    exact decimal formatting (e.g. ``"823.30"`` to keep the trailing zero).

    Usage::

        MeasureValue(9720, "W")
        MeasureValue("823.30", "m3")
    """

    value: int | float | str
    uom: str

    @property
    def text(self) -> str:
        """Return the string representation used in XML text content."""
        return str(self.value)


@dataclass
class ScaleValue:
    """Represents ``gml:ScaleType`` -- same structure as MeasureType,
    typically used for fractions (0..1).

    Usage::

        ScaleValue(0.3, "unit interval")
    """

    value: int | float | str = 0.0
    uom: str = "unit interval"

    @property
    def text(self) -> str:
        return str(self.value)
