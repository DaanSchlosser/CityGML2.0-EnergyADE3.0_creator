"""CityModel root element and Address."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from lxml import etree

from .namespaces import NS_GML, NS_XAL, NSMAP, qn
from .xml_support import append_xml_content


@dataclass
class Envelope:
    """``gml:Envelope`` with SRS and corner coordinates."""

    srs_name: str
    srs_dimension: int = 3
    lower_corner: str = ""
    upper_corner: str = ""

    def to_xml(self, parent: etree._Element) -> etree._Element:
        bounded = etree.SubElement(parent, qn("gml", "boundedBy"))
        env = etree.SubElement(bounded, qn("gml", "Envelope"))
        env.set("srsName", self.srs_name)
        env.set("srsDimension", str(self.srs_dimension))
        lc = etree.SubElement(env, qn("gml", "lowerCorner"))
        lc.text = self.lower_corner
        uc = etree.SubElement(env, qn("gml", "upperCorner"))
        uc.text = self.upper_corner
        return bounded


@dataclass
class Address:
    """``core:Address`` containing ``xAL:AddressDetails``."""

    country: Optional[str] = None
    locality: Optional[str] = None
    thoroughfare: Optional[str] = None
    thoroughfare_number: Optional[str] = None
    postal_code: Optional[str] = None
    gml_id: Optional[str] = None

    def to_xml(self, parent: etree._Element) -> etree._Element:
        addr = etree.SubElement(parent, qn("core", "Address"))
        if self.gml_id:
            addr.set(f"{{{NS_GML}}}id", self.gml_id)
        xal = etree.SubElement(addr, qn("core", "xalAddress"))
        details = etree.SubElement(xal, f"{{{NS_XAL}}}AddressDetails")
        if self.country:
            c = etree.SubElement(details, f"{{{NS_XAL}}}Country")
            cn = etree.SubElement(c, f"{{{NS_XAL}}}CountryName")
            cn.text = self.country
            if self.locality:
                loc = etree.SubElement(c, f"{{{NS_XAL}}}Locality")
                loc.set("Type", "Town")
                ln = etree.SubElement(loc, f"{{{NS_XAL}}}LocalityName")
                ln.text = self.locality
                if self.thoroughfare:
                    th = etree.SubElement(loc, f"{{{NS_XAL}}}Thoroughfare")
                    th.set("Type", "Street")
                    tn = etree.SubElement(th, f"{{{NS_XAL}}}ThoroughfareName")
                    tn.text = self.thoroughfare
                    if self.thoroughfare_number:
                        tnum = etree.SubElement(th, f"{{{NS_XAL}}}ThoroughfareNumber")
                        tnum.text = self.thoroughfare_number
                if self.postal_code:
                    pc = etree.SubElement(loc, f"{{{NS_XAL}}}PostalCode")
                    pcn = etree.SubElement(pc, f"{{{NS_XAL}}}PostalCodeNumber")
                    pcn.text = self.postal_code
        return addr


@dataclass
class CityModel:
    """Top-level ``core:CityModel`` container."""

    gml_description: Optional[str] = None
    gml_name: Optional[str] = None
    envelope: Optional[Envelope] = None
    city_object_members: List[Any] = field(default_factory=list)
    appearance_members: List[Any] = field(default_factory=list)

    def add(self, city_object: Any) -> "CityModel":
        """Add a city object (Building, etc.) as a cityObjectMember."""
        self.city_object_members.append(city_object)
        return self

    def add_appearance(self, appearance: Any) -> "CityModel":
        """Add an appearance object as an ``app:appearanceMember``."""
        self.appearance_members.append(appearance)
        return self

    def to_xml(self) -> etree._Element:
        root = etree.Element(qn("core", "CityModel"), nsmap=NSMAP)

        if self.gml_description is not None:
            desc = etree.SubElement(root, qn("gml", "description"))
            desc.text = self.gml_description

        if self.gml_name is not None:
            name = etree.SubElement(root, qn("gml", "name"))
            name.text = self.gml_name

        if self.envelope is not None:
            self.envelope.to_xml(root)

        for member in self.city_object_members:
            append_xml_content(root, qn("core", "cityObjectMember"), member)

        for appearance in self.appearance_members:
            append_xml_content(root, qn("app", "appearanceMember"), appearance)

        return root

    def to_string(
        self,
        xml_declaration: bool = True,
        pretty_print: bool = True,
    ) -> str:
        root = self.to_xml()
        raw = etree.tostring(
            root,
            xml_declaration=xml_declaration,
            encoding="UTF-8",
            pretty_print=pretty_print,
        ).decode("utf-8")
        # Convert 2-space indentation to tab indentation to match references
        lines = raw.split("\n")
        result = []
        for line in lines:
            stripped = line.lstrip(" ")
            n_spaces = len(line) - len(stripped)
            n_tabs = n_spaces // 2
            result.append("\t" * n_tabs + stripped)
        return "\n".join(result)

    def write(self, filepath: str, **kwargs: Any) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_string(**kwargs))
