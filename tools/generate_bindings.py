"""Generate xsdata Python bindings from every XSD tree shipped in the repo.

Stages all XSDs found on disk, rewrites their ``schemaLocation`` URLs to
local relative paths via namespace-based auto-discovery, then invokes
xsdata code generation with the discovered ADE entry points.

Usage::

    python tools/generate_bindings.py

Adding a new ADE (``ScenarioADE``, updated ``EnergyADE`` release, …):

1. Drop the ADE's XSD tree under the repo (``<AdeName>/xsd/...`` beside the
   existing ``Energy_ADE-3.0beta8/``, or inline under ``xsd/``). The tool
   discovers every ``*.xsd`` under :data:`_STAGED_ROOTS` automatically;
   no registration needed.
2. Rerun this tool. Any schemaLocation URL it cannot map to a local file
   is reported with the offending file and URL, so drift fails loudly
   instead of triggering a silent network fetch from xsdata.
3. If the new ADE defines a fresh XML namespace, add a prefix entry in
   ``schemas/namespace_prefixes.json``: the ``NSMAP`` discovery in
   :mod:`citygml_energy.namespaces` warns at import time until that is
   done.

No hand-maintained URL → local-path table is needed; the mapping is
derived every run by indexing each local ``*.xsd`` file by its declared
``targetNamespace``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PACKAGE = "citygml_energy/bindings"

# ── XSD trees staged for binding generation ─────────────────────────────────
# Every directory listed here is copied verbatim into the temp staging area.
# Add a line when a new ADE tree appears; the file-level auto-discovery
# takes care of the URL-rewriting.
_STAGED_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "xsd",
    REPO_ROOT / "Energy_ADE-3.0beta8",
)

# ── Entry points xsdata consumes ────────────────────────────────────────────
# Relative to the staging root. xsdata walks imports transitively from
# these files; every other staged XSD is reachable indirectly.
_ENTRY_XSDS: tuple[Path, ...] = (
    REPO_ROOT / "Energy_ADE-3.0beta8" / "xsd" / "Energy_ADE_3.0_beta8.xsd",
)

# ── Schema-location URL pattern ─────────────────────────────────────────────
# Absolute URIs (http(s)://..., urn:...) need remapping; relative values
# (``./foo.xsd``, ``../bar.xsd``) already work in-place and are left alone.
_ABSOLUTE_URI_RE = re.compile(r"^(?:https?://|urn:)")
_SCHEMA_LOCATION_RE = re.compile(r'schemaLocation="([^"]+)"')

# URLs that xsdata resolves internally without fetching. The W3C XML
# bootstrap schema (``xml:id``, ``xml:lang``, ``xml:space``) is special-
# cased by every XML toolchain, so leaving the ``<xs:import>`` pointing at
# the canonical URL is correct: xsdata's builtin resolver picks it up and
# no network call happens.
_BOOTSTRAP_URLS: frozenset[str] = frozenset({
    "http://www.w3.org/2001/xml.xsd",
})

# XML-Schema element names used when walking imports/includes.
_XS_NS = "http://www.w3.org/2001/XMLSchema"
_XS_IMPORT = f"{{{_XS_NS}}}import"
_XS_INCLUDE = f"{{{_XS_NS}}}include"


# ---------------------------------------------------------------------------
# Local XSD discovery
# ---------------------------------------------------------------------------


def _parse_staged_xsds(staging_dir: Path) -> dict[Path, etree._ElementTree]:
    """Parse every ``*.xsd`` under *staging_dir* exactly once.

    The resulting cache is reused for namespace indexing *and* for
    schemaLocation rewriting so each file is read and parsed only once
    even across the 50+ XSDs staged by a full CityGML + Energy-ADE run.
    """
    parsed: dict[Path, etree._ElementTree] = {}
    for xsd in staging_dir.rglob("*.xsd"):
        try:
            parsed[xsd] = etree.parse(str(xsd))
        except etree.XMLSyntaxError:
            continue
    return parsed


def _index_local_xsds(
    parsed: dict[Path, etree._ElementTree],
) -> dict[str, dict[str, Path]]:
    """Build ``{namespace: {basename: absolute_path}}`` for every parsed XSD.

    A basename-level index is kept so that XSDs sharing a namespace
    (e.g. every file under ``gml/3.1.1/base/``) can still be resolved
    unambiguously from the URL's basename.
    """
    index: dict[str, dict[str, Path]] = {}
    for xsd, tree in parsed.items():
        namespace = tree.getroot().get("targetNamespace")
        if namespace is None:
            continue
        index.setdefault(namespace, {})[xsd.name] = xsd
    return index


def _resolve_schema_location(
    index: dict[str, dict[str, Path]],
    namespace: str,
    url: str,
) -> Path | None:
    """Return the staged file *url* should point at, or ``None`` if unmappable.

    *namespace* is the ``namespace`` attribute on the enclosing
    ``<xs:import>`` (empty string when the reference is an
    ``<xs:include>``, a same-namespace reference inherited from the
    enclosing schema).
    """
    bucket = index.get(namespace)
    if not bucket:
        return None
    # URN schemes carry no path; rely on the namespace-scoped lookup.
    basename = url.rsplit("/", 1)[-1] if "/" in url else None
    if basename and basename in bucket:
        return bucket[basename]
    if len(bucket) == 1:
        return next(iter(bucket.values()))
    return None


# ---------------------------------------------------------------------------
# schemaLocation rewriting
# ---------------------------------------------------------------------------


def _rewrite_one_file(
    xsd_path: Path,
    tree: etree._ElementTree,
    index: dict[str, dict[str, Path]],
    unmapped: list[tuple[Path, str]],
) -> None:
    """Rewrite every absolute schemaLocation URL in *xsd_path* in place.

    Uses the pre-parsed *tree* to harvest each ``<xs:import>`` /
    ``<xs:include>``'s namespace attribute, resolves the target to a
    staged file via *index*, and performs a text-level substitution so
    whitespace/formatting survive unchanged.
    """
    root = tree.getroot()
    own_namespace = root.get("targetNamespace") or ""

    url_to_local: dict[str, Path] = {}
    for elem in root.iter(_XS_IMPORT, _XS_INCLUDE):
        url = elem.get("schemaLocation")
        if url is None or not _ABSOLUTE_URI_RE.match(url):
            continue
        if url in _BOOTSTRAP_URLS:
            continue
        # xs:include inherits the enclosing schema's namespace; xs:import
        # declares the foreign namespace it targets.
        ns = elem.get("namespace") if elem.tag == _XS_IMPORT else own_namespace
        target = _resolve_schema_location(index, ns or "", url)
        if target is None:
            unmapped.append((xsd_path, url))
            continue
        url_to_local[url] = target

    if not url_to_local:
        return

    xsd_dir = xsd_path.parent
    url_to_relative = {
        url: Path(os.path.relpath(target, xsd_dir)).as_posix()
        for url, target in url_to_local.items()
    }

    text = xsd_path.read_text(encoding="utf-8")
    rewritten = _SCHEMA_LOCATION_RE.sub(
        lambda m: f'schemaLocation="{url_to_relative.get(m.group(1), m.group(1))}"',
        text,
    )
    if rewritten != text:
        xsd_path.write_text(rewritten, encoding="utf-8")


def _stage_schemas(staging_dir: Path) -> list[Path]:
    """Copy every tree in :data:`_STAGED_ROOTS` into *staging_dir* and patch.

    Returns the list of staged entry-point XSDs (the paths xsdata should
    receive on its command line). Raises :class:`RuntimeError` if any
    schemaLocation URL cannot be resolved; the caller is expected to treat
    that as a fatal misconfiguration (missing local XSD, stale URL, or
    newly-added ADE whose imports were not dropped on disk yet).
    """
    for source_root in _STAGED_ROOTS:
        if not source_root.exists():
            raise RuntimeError(
                f"Configured XSD root does not exist: {source_root}. "
                "Check _STAGED_ROOTS in tools/generate_bindings.py."
            )
        destination = staging_dir / source_root.name
        shutil.copytree(source_root, destination)

    parsed = _parse_staged_xsds(staging_dir)
    index = _index_local_xsds(parsed)

    unmapped: list[tuple[Path, str]] = []
    for xsd, tree in parsed.items():
        _rewrite_one_file(xsd, tree, index, unmapped)

    if unmapped:
        lines = [f"  - {xsd.relative_to(staging_dir)}: {url}" for xsd, url in unmapped]
        raise RuntimeError(
            "Unresolved schemaLocation URLs in staged XSDs. xsdata would "
            "try to fetch these over the network, which the binding build "
            "forbids. Add a local copy under one of _STAGED_ROOTS in "
            "tools/generate_bindings.py and ensure its targetNamespace "
            "matches the import:\n" + "\n".join(lines)
        )

    print(f"Discovered {len(index)} namespace(s) across staged XSDs:")
    for namespace in sorted(index):
        print(f"  - {namespace} ({len(index[namespace])} file(s))")
    print()

    return [staging_dir / entry.relative_to(REPO_ROOT) for entry in _ENTRY_XSDS]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    # With ``--structure-style single-package`` and ``--package
    # citygml_energy.bindings`` xsdata writes a single file
    # ``citygml_energy/bindings.py``. Earlier layouts used a package
    # directory; clean both forms so stale output never lingers.
    output_file = REPO_ROOT / "citygml_energy" / "bindings.py"
    output_dir = REPO_ROOT / OUTPUT_PACKAGE

    if output_file.exists() and output_file.is_file():
        output_file.unlink()
    if output_dir.exists() and output_dir.is_dir():
        shutil.rmtree(output_dir)

    with tempfile.TemporaryDirectory(prefix="xsdata_staging_") as tmpdir:
        staging = Path(tmpdir)
        entry_xsds = _stage_schemas(staging)

        print(f"Staged XSD schemas in: {staging}")
        print(f"Entry XSDs: {[str(p) for p in entry_xsds]}")
        print(f"Output package: {OUTPUT_PACKAGE}")
        print()

        cmd = [
            sys.executable,
            "-m",
            "xsdata",
            "generate",
            *[str(p) for p in entry_xsds],
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
