"""XmlSerializer wrapper with project-specific defaults.

xsdata's :class:`XmlSerializer` is stateless across calls but carries a
lazily-initialised model-builder cache on its internal ``XmlContext``.
Reusing a single serializer instance across runs keeps that cache warm,
saving a handful of milliseconds each time and paying the reflection
cost once per process rather than once per :func:`serialize_to_string`
call. A small ``lru_cache`` on the indent variant covers the occasional
test that asks for a non-default indent.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig
from xsdata.formats.dataclass.serializers.writers.native import XmlEventWriter

from . import _xsdata_patches
from .namespaces import NSMAP

# Apply xsdata hot-path patches at import time. Idempotent; see the module
# docstring for the two surgical caches we install.
_xsdata_patches.apply()


@lru_cache(maxsize=8)
def _get_serializer(indent: str) -> XmlSerializer:
    """Return a process-wide :class:`XmlSerializer` for *indent*.

    Cached per-indent so a caller mixing tab and space indentation (tests,
    diagnostics) still gets a warm model-builder cache on the dominant
    path. Passing ``""`` disables pretty-printing and is the fastest mode
    (xsdata skips the indent walk entirely).

    Uses the stdlib (``xml.sax.saxutils.XMLGenerator``) writer rather
    than the lxml-backed one: both produce XSD-valid output against
    Energy ADE 3.0 + CityGML 2.0, but the native writer is ~10 % faster
    on our city-scale model because it emits events directly to a
    string buffer without lxml's intermediate tree construction. The
    lxml writer is still used by :mod:`tools.validate_xsd` for
    *reading* GML; it is only the *writing* path we accelerate here.
    """
    config = SerializerConfig(xml_declaration=True, encoding="UTF-8", indent=indent)
    return XmlSerializer(config=config, writer=XmlEventWriter)


def serialize_to_string(obj: object, *, indent: str = "\t", header: str | None = None) -> str:
    """Serialize an xsdata dataclass to an XML string.

    When *header* is given, it is emitted as an XML comment placed between
    the XML declaration and the root element (the conventional spot for a
    file banner: copyright, provenance, read-me). The comment is invisible
    to schema validation, so it never affects XSD validity.
    """
    # NSMAP is a read-only mapping; xsdata does not mutate it. Passing the
    # module-level dict directly (rather than a copy) saves ~10 µs per call
    # and, more importantly, keeps the serializer's namespace context from
    # diverging from the repo-wide source of truth.
    xml = _get_serializer(indent).render(obj, ns_map=NSMAP)
    if header is not None:
        xml = _inject_header_comment(xml, header)
    return xml


def serialize_to_file(
    obj: object, path: str | Path, *, indent: str = "\t", header: str | None = None
) -> None:
    """Serialize an xsdata dataclass to a GML/XML file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialize_to_string(obj, indent=indent, header=header), encoding="utf-8")


def _inject_header_comment(xml: str, header: str) -> str:
    """Insert *header* as an XML comment after the XML declaration.

    XML 1.0 forbids the ``--`` sequence inside a comment, so a header
    carrying one would produce malformed output. We reject it loudly here
    rather than silently emit an unparseable file. Validation upstream
    (``input_loader``) catches this at load time; this guard covers any
    other caller.
    """
    if "--" in header:
        raise ValueError(
            "file header may not contain the sequence '--' (forbidden inside an XML comment)"
        )
    comment = f"<!--\n{header}\n-->"
    marker = "?>"
    idx = xml.find(marker)
    if xml.startswith("<?xml") and idx != -1:
        cut = idx + len(marker)
        return f"{xml[:cut]}\n{comment}{xml[cut:]}"
    # No XML declaration (e.g. xml_declaration disabled): prepend the banner.
    return f"{comment}\n{xml}"
