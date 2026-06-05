"""Validate a GML file against the CityGML 2.0 + Energy ADE 3.0 beta8 XSD schemas.

Uses lxml's XMLSchema with a custom resolver that redirects all schema imports
to local files, so no network access is required.

Usage:
    python tools/validate_xsd.py generated/owner_occupier_building.gml
    python tools/validate_xsd.py Energy_ADE-3.0beta8/test_data/Alderaan_Energy_ADE_All.gml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import lxml.etree as etree

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Schema locations ──────────────────────────────────────────────────────────
ENERGY_XSD = REPO_ROOT / "Energy_ADE-3.0beta8" / "xsd" / "Energy_ADE_3.0_beta8.xsd"

_XSD_ROOT = REPO_ROOT / "xsd"
_CITYGML_DIR = _XSD_ROOT / "citygml" / "2.0"
_GML_BASE_DIR = _XSD_ROOT / "gml" / "3.1.1" / "base"
_SMIL_DIR = _XSD_ROOT / "gml" / "3.1.1" / "smil"
_XAL_XSD = _XSD_ROOT / "xAL.xsd"
_XLINK_XSD = _XSD_ROOT / "xlink" / "xlink.xsd"

# ── URL → local file mapping ─────────────────────────────────────────────────
_URL_MAP: dict[str, Path] = {
    # GML 3.1.1
    "http://schemas.opengis.net/gml/3.1.1/base/gml.xsd": _GML_BASE_DIR / "gml.xsd",
    # GML SMIL
    "http://schemas.opengis.net/gml/3.1.1/smil/smil20.xsd": _SMIL_DIR / "smil20.xsd",
    "http://schemas.opengis.net/gml/3.1.1/smil/smil20-language.xsd": _SMIL_DIR
    / "smil20-language.xsd",
    # xlink
    "http://www.w3.org/1999/xlink.xsd": _XLINK_XSD,
    # CityGML 2.0 base
    "http://schemas.opengis.net/citygml/2.0/cityGMLBase.xsd": _CITYGML_DIR / "cityGMLBase.xsd",
    # CityGML 2.0 modules
    "http://schemas.opengis.net/citygml/appearance/2.0/appearance.xsd": _CITYGML_DIR
    / "appearance.xsd",
    "http://schemas.opengis.net/citygml/bridge/2.0/bridge.xsd": _CITYGML_DIR / "bridge.xsd",
    "http://schemas.opengis.net/citygml/building/2.0/building.xsd": _CITYGML_DIR / "building.xsd",
    "http://schemas.opengis.net/citygml/cityfurniture/2.0/cityFurniture.xsd": _CITYGML_DIR
    / "cityFurniture.xsd",
    "http://schemas.opengis.net/citygml/cityobjectgroup/2.0/cityObjectGroup.xsd": _CITYGML_DIR
    / "cityObjectGroup.xsd",
    "http://schemas.opengis.net/citygml/generics/2.0/generics.xsd": _CITYGML_DIR / "generics.xsd",
    "http://schemas.opengis.net/citygml/landuse/2.0/landUse.xsd": _CITYGML_DIR / "landUse.xsd",
    "http://schemas.opengis.net/citygml/relief/2.0/relief.xsd": _CITYGML_DIR / "relief.xsd",
    "http://schemas.opengis.net/citygml/transportation/2.0/transportation.xsd": _CITYGML_DIR
    / "transportation.xsd",
    "http://schemas.opengis.net/citygml/tunnel/2.0/tunnel.xsd": _CITYGML_DIR / "tunnel.xsd",
    "http://schemas.opengis.net/citygml/vegetation/2.0/vegetation.xsd": _CITYGML_DIR
    / "vegetation.xsd",
    "http://schemas.opengis.net/citygml/waterbody/2.0/waterBody.xsd": _CITYGML_DIR
    / "waterBody.xsd",
    "http://schemas.opengis.net/citygml/texturedsurface/2.0/texturedSurface.xsd": _CITYGML_DIR
    / "texturedSurface.xsd",
}

# xAL namespace may appear as a namespace URI, a URL, or a bare filename.
_XAL_HINTS = {
    "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0",
    "http://docs.oasis-open.org/election/external/xAL.xsd",
    "docs.oasis-open.org/election/external/xAL.xsd",
    "xAL.xsd",
}


class _LocalResolver(etree.Resolver):
    """Redirect all known schema URLs to local files."""

    def resolve(self, system_url: str, public_id, context):  # type: ignore[override]
        if not system_url:
            return None

        # Exact URL match (OGC schemas)
        local = _URL_MAP.get(system_url)
        if local is not None:
            return self.resolve_filename(str(local), context)  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]

        # xAL (namespace URI or OASIS URL)
        if any(hint in system_url for hint in _XAL_HINTS):
            return self.resolve_filename(str(_XAL_XSD), context)  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]

        return None  # fall through to lxml default (file-relative)


def load_schema() -> etree.XMLSchema:
    """Load the Energy ADE 3.0 beta8 XSD with all CityGML 2.0 imports resolved locally."""
    parser = etree.XMLParser()
    parser.resolvers.add(_LocalResolver())
    schema_doc = etree.parse(str(ENERGY_XSD), parser)
    return etree.XMLSchema(schema_doc)


def validate(gml_path: Path, schema: etree.XMLSchema) -> list[str]:
    """Validate a GML file. Returns a list of error strings (empty = valid)."""
    # Harden against XXE / billion-laughs / network-resolved entities when
    # parsing user-supplied GML input. Validation only needs the document tree.
    safe_parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
    )
    doc = etree.parse(str(gml_path), safe_parser)
    schema.validate(doc)
    # lxml-stubs types ``error_log`` as the empty ``_ErrorLog`` base; the runtime
    # object is an iterable ``_ListErrorLog``.
    return [str(e) for e in schema.error_log]  # type: ignore[attr-defined]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gml_file", type=Path, help="GML file to validate")
    args = ap.parse_args()

    gml_path = args.gml_file
    if not gml_path.is_absolute():
        gml_path = REPO_ROOT / gml_path

    if not gml_path.exists():
        print(f"ERROR: {gml_path} not found", file=sys.stderr)
        return 1

    print("Loading schemas (Energy ADE 3.0 beta8 + CityGML 2.0, all local) ...")
    try:
        schema = load_schema()
    except etree.XMLSchemaParseError as exc:
        print(f"SCHEMA LOAD ERROR:\n{exc}", file=sys.stderr)
        return 2

    print(f"Validating:  {gml_path.name} ...")
    errors = validate(gml_path, schema)

    if not errors:
        print("VALID - no XSD errors found.")
        return 0

    print(f"\nFOUND {len(errors)} VALIDATION ERROR(S):\n")
    for i, err in enumerate(errors, 1):
        print(f"  {i}. {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
