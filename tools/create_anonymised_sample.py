"""Produce a shareable, anonymised, geometry-free sample GML based on the owner-occupier reference building.

Pipeline:
  1. Generate a CityGML 2.0 + EnergyADE 3.0 file from
     ``inputs/owner_occupier_building_sample.json`` (a structural clone of the real
     per-building input file where every data value is a placeholder).
  2. Drop every LOD geometry subtree so the output carries no coordinates.

The resulting ``generated/owner_occupier_building_sample.gml`` is safe to attach to
SDM_KITModelViewer issues #24, #25, and #26 — it preserves the element
structure that triggers the inconsistent rendering, but the sample has no
real addresses, owners, register identifiers, product models, measurements,
or time-series data.

Semantic boundary surfaces (``bldg:boundedBy`` wrapping
WallSurface/RoofSurface/GroundSurface/Window/Door) are preserved so the
``nrg3:CityObjectRelation`` xlinks from the PV panel (issue #24) still
resolve to valid ids within the document.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lxml import etree

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from citygml_energy import generate_gml_file

DEFAULT_INPUT = REPO_ROOT / "inputs" / "owner_occupier_building_sample.json"
DEFAULT_OUTPUT = REPO_ROOT / "generated" / "owner_occupier_building_sample.gml"

NS = {
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "gml": "http://www.opengis.net/gml",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
}

GEOMETRY_TAGS = {
    f"{{{NS['gml']}}}boundedBy",          # root-level envelope
    f"{{{NS['bldg']}}}lod0FootPrint",
    f"{{{NS['bldg']}}}lod1Solid",
    f"{{{NS['bldg']}}}lod2MultiSurface",
    f"{{{NS['bldg']}}}lod3MultiSurface",
    f"{{{NS['nrg3']}}}lod2MultiSurface",
    f"{{{NS['nrg3']}}}lod3MultiSurface",
    f"{{{NS['nrg3']}}}lod3Solid",
}


def strip_geometry(root: etree._Element) -> int:
    removed = 0
    for parent in root.iter():
        for child in list(parent):
            if child.tag in GEOMETRY_TAGS:
                parent.remove(child)
                removed += 1
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    # 1. Full generation from the anonymous input JSON.
    generate_gml_file(input_path=args.input, output_path=args.output)

    # 2. Strip geometry subtrees in place.
    xml_parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(args.output), xml_parser)
    root = tree.getroot()
    removed = strip_geometry(root)
    tree.write(
        str(args.output),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

    print(f"Wrote {args.output}")
    print(f"Removed {removed} geometry subtree(s)")


if __name__ == "__main__":
    main()
