"""Abstract base builder with XSD-ordered serialization to lxml Elements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from lxml import etree

from .namespaces import NS_GML, NSMAP
from .types import CodeValue, MeasureValue, ScaleValue
from .xml_support import RawXmlElement, append_xml_content


@dataclass
class BaseBuilder:
    """Base class for all CityGML / Energy ADE element builders.

    Subclasses must define:
    * ``ELEMENT_TAG``  -- ``(namespace_uri, local_name)`` of the XML element
    * ``ELEMENT_ORDER`` -- tuple of ``(namespace_uri, local_name)`` defining
      the child-element sequence mandated by the XSD
    * ``FIELD_MAP`` -- dict mapping Python field names to
      ``(namespace_uri, local_name)`` pairs

    The :meth:`to_xml` method iterates *ELEMENT_ORDER* and emits children
    for every field that has been set, guaranteeing schema-compliant order.
    """

    # Subclasses override these
    ELEMENT_TAG: ClassVar[tuple[str, str]] = ("", "")
    ELEMENT_ORDER: ClassVar[tuple[tuple[str, str], ...]] = ()
    FIELD_MAP: ClassVar[dict[str, tuple[str, str]]] = {}

    gml_id: str | None = None

    # ------------------------------------------------------------------
    # Internal: reverse lookup (ns, local) -> field name
    # ------------------------------------------------------------------
    @classmethod
    def _reverse_map(cls) -> dict[tuple[str, str], str]:
        return {v: k for k, v in cls.FIELD_MAP.items()}

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_xml(self, parent: etree._Element | None = None) -> etree._Element:
        """Serialize this builder to an lxml Element.

        If *parent* is provided the element is appended as a sub-element of
        *parent*; otherwise a detached element is returned.
        """
        ns, local = self.ELEMENT_TAG
        tag = f"{{{ns}}}{local}"

        if parent is not None:
            elem = etree.SubElement(parent, tag)
        else:
            elem = etree.Element(tag, nsmap=NSMAP)

        if self.gml_id:
            elem.set(f"{{{NS_GML}}}id", self.gml_id)

        reverse = self._reverse_map()

        for ns_uri, local_name in self.ELEMENT_ORDER:
            key = (ns_uri, local_name)
            field_name = reverse.get(key)
            if field_name is None:
                continue
            value = getattr(self, field_name, None)
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    self._emit_child(elem, ns_uri, local_name, item)
            else:
                self._emit_child(elem, ns_uri, local_name, value)

        return elem

    # ------------------------------------------------------------------
    def _emit_child(
        self,
        parent: etree._Element,
        ns: str,
        local: str,
        value: Any,
    ) -> None:
        """Emit a single child element under *parent*."""
        child_tag = f"{{{ns}}}{local}"

        if isinstance(value, (BaseBuilder, RawXmlElement, etree._Element)):
            append_xml_content(parent, child_tag, value)

        elif isinstance(value, (MeasureValue, ScaleValue)):
            child = etree.SubElement(parent, child_tag)
            child.set("uom", value.uom)
            child.text = value.text

        elif isinstance(value, CodeValue):
            child = etree.SubElement(parent, child_tag)
            if value.code_space:
                child.set("codeSpace", value.code_space)
            child.text = str(value.value)

        elif isinstance(value, bool):
            child = etree.SubElement(parent, child_tag)
            child.text = "true" if value else "false"

        elif isinstance(value, int):
            child = etree.SubElement(parent, child_tag)
            child.text = str(value)

        elif isinstance(value, float):
            child = etree.SubElement(parent, child_tag)
            child.text = _format_number(value)

        else:
            # Plain string / date
            child = etree.SubElement(parent, child_tag)
            child.text = str(value)


def _format_number(v: float) -> str:
    """Format a float value; Python's repr already preserves trailing decimals."""
    return str(v)
