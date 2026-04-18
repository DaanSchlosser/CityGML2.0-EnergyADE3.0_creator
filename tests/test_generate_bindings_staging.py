"""Namespace-based auto-staging for ``tools/generate_bindings.py``.

Two claims matter:

* Staging the shipped XSD trees leaves no absolute ``schemaLocation``
  URL unresolved (other than the documented ``xml.xsd`` bootstrap).
  This is the end-to-end integration check — if the claim fails, binding
  generation would trigger a network fetch that the offline build forbids.

* ``_resolve_schema_location`` disambiguates correctly inside a
  multi-file namespace bucket (``gml`` has 29 siblings, matched by URL
  basename) and returns ``None`` for namespaces that nobody ships —
  fail-loud rather than silently resolving to a wrong file.

Staging runs once per module via fixture — it walks 50+ XSDs and
rewrites schemaLocations for each, so repeating it per test was wasteful.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools import generate_bindings as gb

_ABSOLUTE_URI_RE = re.compile(r"^(?:https?://|urn:)")


@pytest.fixture(scope="module")
def staged() -> Iterator[Path]:
    """Stage the XSD trees once for the whole module."""
    with tempfile.TemporaryDirectory(prefix="xsdata_staging_test_") as tmp:
        staging = Path(tmp)
        gb._stage_schemas(staging)
        yield staging


@pytest.fixture(scope="module")
def ns_index(staged: Path) -> dict[str, dict[str, Path]]:
    return gb._index_local_xsds(gb._parse_staged_xsds(staged))


def test_staged_xsds_have_no_unresolved_absolute_urls(staged: Path):
    """Every absolute URL in a staged XSD either resolves to a local
    path or is in the documented bootstrap allowlist.
    """
    unresolved: list[tuple[Path, str]] = []
    for xsd in staged.rglob("*.xsd"):
        text = xsd.read_text(encoding="utf-8")
        for match in re.finditer(r'schemaLocation="([^"]+)"', text):
            url = match.group(1)
            if not _ABSOLUTE_URI_RE.match(url):
                continue
            if url in gb._BOOTSTRAP_URLS:
                continue
            unresolved.append((xsd.relative_to(staged), url))
    assert not unresolved, (
        "Staged XSDs still reference absolute URLs that were not "
        f"rewritten to local paths:\n{unresolved}"
    )


def test_resolve_disambiguates_inside_a_multi_file_namespace(
    ns_index: dict[str, dict[str, Path]],
):
    """The GML 3.1.1 base tree contains 29 XSDs sharing one namespace.

    Resolution must use the URL's basename to pick the right sibling;
    returning "any file" (e.g. the first one) would misroute imports.
    This is the test that motivated the basename lookup in
    ``_resolve_schema_location``.
    """
    gml_ns = "http://www.opengis.net/gml"
    assert len(ns_index.get(gml_ns, {})) > 1, (
        "Test premise: GML 3.1.1 base must have multiple files per namespace"
    )

    for filename in ("gml.xsd", "feature.xsd", "basicTypes.xsd", "measures.xsd"):
        url = f"http://schemas.opengis.net/gml/3.1.1/base/{filename}"
        resolved = gb._resolve_schema_location(ns_index, gml_ns, url)
        assert resolved is not None, f"Failed to resolve {url}"
        assert resolved.name == filename, (
            f"Expected {filename}, resolved to {resolved.name} — basename "
            "disambiguation is broken"
        )


def test_resolve_handles_urn_without_basename(
    ns_index: dict[str, dict[str, Path]],
):
    """Bare URNs (``urn:oasis:names:tc:ciq:xsdschema:xAL:2.0``) carry no
    slash-separated basename, so resolution falls back to the
    single-file-per-namespace branch.
    """
    resolved = gb._resolve_schema_location(
        ns_index,
        "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0",
        "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0",
    )
    assert resolved is not None and resolved.name == "xAL.xsd"


def test_resolve_returns_none_for_unknown_namespace(
    ns_index: dict[str, dict[str, Path]],
):
    """Unknown namespace must surface as ``None`` so staging fails loudly.

    Silently resolving against a random file would produce broken
    bindings; the RuntimeError path in ``_stage_schemas`` is what tells
    the operator they forgot to drop an ADE's XSDs on disk.
    """
    assert (
        gb._resolve_schema_location(
            ns_index,
            "http://example.invalid/not-an-ade/1.0",
            "http://example.invalid/not-an-ade/1.0/schema.xsd",
        )
        is None
    )
