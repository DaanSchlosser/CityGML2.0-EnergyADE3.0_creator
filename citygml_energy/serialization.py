"""XmlSerializer wrapper with project-specific defaults."""

from __future__ import annotations

from pathlib import Path

from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from .namespaces import NSMAP

# Namespace prefix map for xsdata's serializer (prefix → URI).
_NS_MAP: dict[str, str] = dict(NSMAP)


def serialize_to_string(obj: object, *, indent: str = "\t") -> str:
    """Serialize an xsdata dataclass to an XML string."""
    config = SerializerConfig(xml_declaration=True, encoding="UTF-8", indent=indent)
    return XmlSerializer(config=config).render(obj, ns_map=_NS_MAP)


def serialize_to_file(obj: object, path: str | Path, *, indent: str = "\t") -> None:
    """Serialize an xsdata dataclass to a GML/XML file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialize_to_string(obj, indent=indent), encoding="utf-8")
