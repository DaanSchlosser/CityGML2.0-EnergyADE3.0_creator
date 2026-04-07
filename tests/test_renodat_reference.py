"""Golden-file test: recreate RenoDAT_GML_V1.gml and compare."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import compare_with_reference

# Import the example builder
from examples.create_renodat import create_renodat

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE = os.path.join(REPO_ROOT, "RenoDAT_GML_V1.gml")


def test_renodat_matches_reference():
    """Generated GML structurally matches the hand-crafted reference file."""
    doc = create_renodat()
    generated = doc.to_string()
    result = compare_with_reference(generated, REFERENCE)
    if not result["match"]:
        for d in result["differences"]:
            print(f"  DIFF: {d}")
    assert result["match"], (
        f"Found {len(result['differences'])} difference(s):\n"
        + "\n".join(f"  - {d}" for d in result["differences"])
    )


def test_generated_is_well_formed_xml():
    """The generated GML is well-formed XML."""
    from lxml import etree

    doc = create_renodat()
    generated = doc.to_string()
    # This will raise if not well-formed
    etree.fromstring(generated.encode("utf-8"))


if __name__ == "__main__":
    test_renodat_matches_reference()
    print("All tests passed!")
