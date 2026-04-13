"""XmlSerializer wrapper with project-specific defaults."""

from __future__ import annotations

from pathlib import Path

from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from .namespaces import NSMAP

# Namespace prefix map for xsdata's serializer (prefix → URI).
NS_MAP: dict[str, str] = dict(NSMAP)

_TAB_CONFIG = SerializerConfig(
    xml_declaration=True,
    encoding="UTF-8",
    indent="\t",
)

_TAB_SERIALIZER = XmlSerializer(config=_TAB_CONFIG)


def _make_serializer(indent: str) -> XmlSerializer:
    config = SerializerConfig(
        xml_declaration=True,
        encoding="UTF-8",
        indent=indent,
    )
    return XmlSerializer(config=config)


def serialize_to_string(obj: object, *, indent: str = "\t") -> str:
    """Serialize an xsdata dataclass to an XML string."""
    ser = _TAB_SERIALIZER if indent == "\t" else _make_serializer(indent)
    return ser.render(obj, ns_map=NS_MAP)


def serialize_to_file(obj: object, path: str | Path, *, indent: str = "\t") -> None:
    """Serialize an xsdata dataclass to a GML/XML file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialize_to_string(obj, indent=indent), encoding="utf-8")
