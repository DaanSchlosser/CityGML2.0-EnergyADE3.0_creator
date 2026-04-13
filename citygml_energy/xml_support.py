"""Helpers for working with raw XML fragments alongside typed builders."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import lxml.etree as etree

from .namespaces import NS_GML, qn


@dataclass
class RawXmlElement:
    """Wrapper for an existing XML element that should be preserved as-is."""

    element: etree._Element

    @classmethod
    def from_element(cls, element: etree._Element) -> RawXmlElement:
        return cls(deepcopy(element))

    @classmethod
    def from_string(
        cls,
        xml_text: str,
        *,
        remove_blank_text: bool = True,
    ) -> RawXmlElement:
        parser = etree.XMLParser(remove_blank_text=remove_blank_text)
        element = etree.fromstring(xml_text.encode("utf-8"), parser=parser)
        return cls(element)

    def clone(self) -> etree._Element:
        return deepcopy(self.element)

    def to_xml(self, parent: etree._Element | None = None) -> etree._Element:
        element = self.clone()
        if parent is not None:
            parent.append(element)
        return element

    def get_gml_id(self) -> str | None:
        return self.element.get(f"{{{NS_GML}}}id")

    def find_child(self, prefix: str, local: str) -> etree._Element | None:
        return self.element.find(qn(prefix, local))

    def set_child_text(self, prefix: str, local: str, text: str | None) -> None:
        child = self.find_child(prefix, local)
        if child is None:
            raise KeyError(f"Child element {prefix}:{local} not found")
        child.text = text

    def xpath(self, expression: str, **kwargs: Any) -> Any:
        return self.element.xpath(expression, **kwargs)


def append_xml_content(
    parent: etree._Element,
    wrapper_tag: str,
    value: object,
) -> etree._Element:
    """Append a wrapped XML child to *parent*.

    The *value* can be a typed builder with ``to_xml(parent)``, a raw
    ``lxml`` element, or :class:`RawXmlElement`.
    """
    wrapper = etree.SubElement(parent, wrapper_tag)

    if isinstance(value, etree._Element):
        wrapper.append(deepcopy(value))
        return wrapper

    to_xml = getattr(value, "to_xml", None)
    if callable(to_xml):
        to_xml(wrapper)
        return wrapper

    raise TypeError(f"Unsupported XML child value: {type(value)!r}")
