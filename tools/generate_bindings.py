"""Generate xsdata Python bindings from the CityGML 2.0 + Energy ADE 3.0 XSD schemas.

Creates a temporary copy of all XSD files with remote schemaLocation URLs rewritten
to local relative paths, then runs xsdata code generation.

Usage:
    python tools/generate_bindings.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PACKAGE = "citygml_energy/bindings"

# ── Source XSD locations ─────────────────────────────────────────────────────
_XSD_ROOT = REPO_ROOT / "xsd"
_ENERGY_XSD = REPO_ROOT / "Energy_ADE-3.0beta8" / "xsd" / "Energy_ADE_3.0_beta8.xsd"

# ── URL → local relative path mapping ───────────────────────────────────────
# Keys: URLs that appear in schemaLocation attributes.
# Values: path relative to the temp staging directory root.
_URL_TO_RELATIVE: dict[str, str] = {
    # GML 3.1.1
    "http://schemas.opengis.net/gml/3.1.1/base/gml.xsd": "gml/3.1.1/base/gml.xsd",
    # GML SMIL
    "http://schemas.opengis.net/gml/3.1.1/smil/smil20.xsd": "gml/3.1.1/smil/smil20.xsd",
    "http://schemas.opengis.net/gml/3.1.1/smil/smil20-language.xsd": "gml/3.1.1/smil/smil20-language.xsd",
    # xlink
    "http://www.w3.org/1999/xlink.xsd": "xlink/xlink.xsd",
    # CityGML 2.0
    "http://schemas.opengis.net/citygml/2.0/cityGMLBase.xsd": "citygml/2.0/cityGMLBase.xsd",
    "http://schemas.opengis.net/citygml/appearance/2.0/appearance.xsd": "citygml/2.0/appearance.xsd",
    "http://schemas.opengis.net/citygml/bridge/2.0/bridge.xsd": "citygml/2.0/bridge.xsd",
    "http://schemas.opengis.net/citygml/building/2.0/building.xsd": "citygml/2.0/building.xsd",
    "http://schemas.opengis.net/citygml/cityfurniture/2.0/cityFurniture.xsd": "citygml/2.0/cityFurniture.xsd",
    "http://schemas.opengis.net/citygml/cityobjectgroup/2.0/cityObjectGroup.xsd": "citygml/2.0/cityObjectGroup.xsd",
    "http://schemas.opengis.net/citygml/generics/2.0/generics.xsd": "citygml/2.0/generics.xsd",
    "http://schemas.opengis.net/citygml/landuse/2.0/landUse.xsd": "citygml/2.0/landUse.xsd",
    "http://schemas.opengis.net/citygml/relief/2.0/relief.xsd": "citygml/2.0/relief.xsd",
    "http://schemas.opengis.net/citygml/transportation/2.0/transportation.xsd": "citygml/2.0/transportation.xsd",
    "http://schemas.opengis.net/citygml/tunnel/2.0/tunnel.xsd": "citygml/2.0/tunnel.xsd",
    "http://schemas.opengis.net/citygml/vegetation/2.0/vegetation.xsd": "citygml/2.0/vegetation.xsd",
    "http://schemas.opengis.net/citygml/waterbody/2.0/waterBody.xsd": "citygml/2.0/waterBody.xsd",
    "http://schemas.opengis.net/citygml/texturedsurface/2.0/texturedSurface.xsd": "citygml/2.0/texturedSurface.xsd",
    # xAL (OASIS)
    "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0": "xAL.xsd",
}


def _rewrite_schema_locations(content: str, xsd_dir_relative: str) -> str:
    """Rewrite schemaLocation URLs to local relative paths.

    *xsd_dir_relative* is the path from the XSD file's location to the
    staging root (e.g. ``"../"`` for a file one level deep).
    """

    def _replacer(match: re.Match[str]) -> str:
        url = match.group(1)
        local = _URL_TO_RELATIVE.get(url)
        if local is not None:
            return f'schemaLocation="{xsd_dir_relative}{local}"'
        return match.group(0)

    return re.sub(r'schemaLocation="([^"]+)"', _replacer, content)


def _stage_schemas(staging_dir: Path) -> Path:
    """Copy all XSD files to *staging_dir* with URLs rewritten to local paths.

    Returns the path to the patched Energy ADE XSD (the entry point).
    """
    # Copy XSD files into staging root (flat structure matching _URL_TO_RELATIVE paths)
    shutil.copytree(_XSD_ROOT / "gml", staging_dir / "gml")
    shutil.copytree(_XSD_ROOT / "citygml", staging_dir / "citygml")
    shutil.copytree(_XSD_ROOT / "xlink", staging_dir / "xlink")
    shutil.copy2(_XSD_ROOT / "xAL.xsd", staging_dir / "xAL.xsd")
    (staging_dir / "energy").mkdir()
    shutil.copy2(_ENERGY_XSD, staging_dir / "energy" / _ENERGY_XSD.name)

    # Rewrite all XSD files under staging_dir
    for xsd_file in staging_dir.rglob("*.xsd"):
        rel_to_staging = xsd_file.parent.relative_to(staging_dir)
        # How many levels deep is this file? We need "../" for each level.
        depth = len(rel_to_staging.parts)
        prefix = "../" * depth

        content = xsd_file.read_text(encoding="utf-8")
        rewritten = _rewrite_schema_locations(content, prefix)
        if rewritten != content:
            xsd_file.write_text(rewritten, encoding="utf-8")

    return staging_dir / "energy" / _ENERGY_XSD.name


def main() -> int:
    import tempfile

    output_dir = REPO_ROOT / OUTPUT_PACKAGE

    # Clean previous output
    if output_dir.exists():
        shutil.rmtree(output_dir)

    with tempfile.TemporaryDirectory(prefix="xsdata_staging_") as tmpdir:
        staging = Path(tmpdir)
        entry_xsd = _stage_schemas(staging)

        print(f"Staged XSD schemas in: {staging}")
        print(f"Entry XSD: {entry_xsd}")
        print(f"Output package: {OUTPUT_PACKAGE}")
        print()

        cmd = [
            sys.executable,
            "-m",
            "xsdata",
            "generate",
            str(entry_xsd),
            "--package",
            OUTPUT_PACKAGE.replace("/", "."),
            "--structure-style",
            "single-package",
            "--docstring-style",
            "Google",
            "--relative-imports",
            "--slots",
            "--no-unnest-classes",
            "--max-line-length",
            "100",
            "--recursive",
        ]

        print(f"Running: {' '.join(cmd)}")
        print()

        result = subprocess.run(cmd, cwd=str(REPO_ROOT))

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
