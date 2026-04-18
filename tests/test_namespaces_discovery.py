"""NSMAP auto-derivation from bindings.

The pipeline's XSD-agnosticism rests on two claims:

1. Every namespace URI referenced by the xsdata bindings has a registered
   prefix in ``schemas/namespace_prefixes.json``. Without a prefix the
   URI silently vanishes from xmlns declarations and the resulting GML
   cannot be serialised correctly.

2. Adding a new ADE's XSD surfaces an *unregistered* URI as a loud warning
   (not a silent drop), so drift is visible.

Narrow, behaviour-focused tests: we don't guard the internals of the
prefix dict or the implementation of ``qn`` — those are either tautologies
or tests of stdlib behaviour.
"""

from __future__ import annotations

import warnings
from unittest.mock import patch

import pytest

from citygml_energy import namespaces


def test_nsmap_covers_every_binding_namespace():
    """Every URI declared by the xsdata bindings must have a registered prefix.

    Regressions in the prefix config show up here as the set of URIs
    that need to be added to schemas/namespace_prefixes.json.
    """
    binding_uris = namespaces._discover_binding_namespaces()
    mapped = set(namespaces.NSMAP.values())
    missing = binding_uris - mapped
    assert not missing, (
        "xsdata bindings contain namespace URIs with no prefix in "
        "schemas/namespace_prefixes.json (so they will not be declared "
        f"in xmlns): {sorted(missing)}"
    )


def test_unregistered_binding_namespace_emits_warning():
    """An unregistered URI from the bindings must fire a loud warning.

    This is the drift-detection mechanism: when a new ADE is added and a
    binding URI has no prefix yet, the import-time warning tells the
    operator exactly what URI needs to land in the config. The test
    bypasses the real bindings and asserts the warning *does* fire when
    the discovery returns a URI absent from the config.
    """
    fake_ns = "http://example.invalid/new-ade/1.0"
    with (
        patch.object(
            namespaces,
            "_discover_binding_namespaces",
            return_value={fake_ns},
        ),
        warnings.catch_warnings(record=True) as caught,
    ):
        warnings.simplefilter("always")
        namespaces._build_nsmap()

    drift_warnings = [w for w in caught if fake_ns in str(w.message)]
    assert drift_warnings, (
        "Expected a warning citing the unregistered URI, got: "
        f"{[str(w.message) for w in caught]}"
    )


def test_prefix_config_pins_canonical_prefixes():
    """A handful of prefixes are conventional in the CityGML ecosystem.

    An accidental JSON edit that renamed e.g. ``bldg`` to ``building``
    would still pass XSD validation but break every downstream consumer
    that expects the standard prefix. Pin the canonical mapping.
    """
    assert namespaces.NSMAP["core"] == "http://www.opengis.net/citygml/2.0"
    assert namespaces.NSMAP["bldg"] == "http://www.opengis.net/citygml/building/2.0"
    assert namespaces.NSMAP["gml"] == "http://www.opengis.net/gml"
    assert namespaces.NSMAP["nrg3"] == (
        "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0"
    )


def test_extra_uris_are_declared_even_without_binding_coverage():
    """Wire-only namespaces listed in ``extra_uris`` (xsi, schematron,
    tex, pbase) must appear in the NSMAP even though no binding class
    references them. Without their xmlns declaration on the root element
    downstream validators reject the document.
    """
    assert "xsi" in namespaces.NSMAP
    assert "sch" in namespaces.NSMAP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
