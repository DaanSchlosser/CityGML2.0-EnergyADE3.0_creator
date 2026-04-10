"""Load CityGML documents as editable XML-backed city models."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from .core import CityModel, Envelope
from .namespaces import NS_NRG3, qn
from .xml_support import RawXmlElement

PathLike = str | Path

_REMOVE_NRG3_CHILDREN = {
    "connectionStatus",
    "creationDate",
    "dataAcquisitionMethod",
    "libraryLayeredConstruction",
    "refurbishmentMeasure",
    "suitability",
    "terminationDate",
}

_RENAME_NRG3_CHILDREN = {
    "accessType": "access",
}


def load_city_model_template(path: PathLike) -> CityModel:
    """Load a CityGML file into a :class:`CityModel` backed by raw XML nodes.

    This is useful for large reference datasets like Alderaan that use more
    CityGML / Energy ADE classes than the typed Python API currently exposes.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.parse(str(path), parser=parser).getroot()

    model = CityModel(
        gml_description=_text(root.find(qn("gml", "description"))),
        gml_name=_text(root.find(qn("gml", "name"))),
        envelope=_parse_envelope(root.find(qn("gml", "boundedBy"))),
    )

    for member in root.findall(qn("core", "cityObjectMember")):
        child = _first_element_child(member)
        if child is not None:
            model.add(RawXmlElement.from_element(child))

    for member in root.findall(qn("app", "appearanceMember")):
        child = _first_element_child(member)
        if child is not None:
            model.add_appearance(RawXmlElement.from_element(child))

    return model


def find_city_object_by_gml_id(
    model: CityModel,
    gml_id: str,
) -> RawXmlElement | None:
    """Return a top-level city object member by its ``gml:id`` if present."""
    for member in model.city_object_members:
        raw_member = _as_raw_member(member)
        if raw_member is not None and raw_member.get_gml_id() == gml_id:
            return raw_member
    return None


def normalize_city_model_for_beta8(model: CityModel) -> CityModel:
    """Normalize an XML-backed city model to the checked-in beta8 XSD.

    The current Alderaan template only requires a minimal compatibility fix for
    EV charging access elements to validate against the bundled beta8 XSD.
    This pass intentionally keeps the rest of the XML untouched.
    """
    for collection in (model.city_object_members, model.appearance_members):
        for member in collection:
            raw_member = _as_raw_member(member)
            if raw_member is not None:
                _normalize_element(raw_member.element)
    return model


def _as_raw_member(member: object) -> RawXmlElement | None:
    if isinstance(member, RawXmlElement):
        return member
    if isinstance(member, etree._Element):
        return RawXmlElement.from_element(member)
    return None


def _first_element_child(parent: etree._Element) -> etree._Element | None:
    for child in parent:
        if isinstance(child.tag, str):
            return child
    return None


def _parse_envelope(bounded_by: etree._Element | None) -> Envelope | None:
    if bounded_by is None:
        return None

    envelope = bounded_by.find(qn("gml", "Envelope"))
    if envelope is None:
        return None

    return Envelope(
        srs_name=envelope.get("srsName", ""),
        srs_dimension=int(envelope.get("srsDimension", "3")),
        lower_corner=_text(envelope.find(qn("gml", "lowerCorner"))) or "",
        upper_corner=_text(envelope.find(qn("gml", "upperCorner"))) or "",
    )


def _text(element: etree._Element | None) -> str | None:
    if element is None:
        return None
    return element.text


def _normalize_element(element: etree._Element) -> None:
    for child in list(element):
        if not isinstance(child.tag, str):
            element.remove(child)
            continue
        _normalize_element(child)

    for child in list(element):
        if not isinstance(child.tag, str):
            continue
        qname = etree.QName(child)
        if qname.namespace != NS_NRG3:
            continue

        new_local = _RENAME_NRG3_CHILDREN.get(qname.localname)
        if new_local is not None:
            child.tag = f"{{{NS_NRG3}}}{new_local}"
            qname = etree.QName(child)

