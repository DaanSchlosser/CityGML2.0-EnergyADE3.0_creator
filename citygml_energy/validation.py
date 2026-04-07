"""Structural comparison of generated GML against a reference file."""
from __future__ import annotations

from typing import Dict, List, Tuple

from lxml import etree


def compare_with_reference(
    generated_xml: str,
    reference_path: str,
) -> Dict:
    """Structurally compare generated XML against a reference file.

    Returns a dict with:
    - ``match`` (bool): True if structurally equivalent.
    - ``differences`` (list[str]): human-readable difference descriptions.
    """
    gen_tree = etree.fromstring(generated_xml.encode("utf-8"))
    with open(reference_path, "r", encoding="utf-8") as f:
        ref_tree = etree.fromstring(f.read().encode("utf-8"))

    diffs: List[str] = []
    _compare_elements(gen_tree, ref_tree, "/", diffs)
    return {"match": len(diffs) == 0, "differences": diffs}


def _compare_elements(
    gen: etree._Element,
    ref: etree._Element,
    path: str,
    diffs: List[str],
) -> None:
    """Recursively compare two element trees."""
    # Tag
    if gen.tag != ref.tag:
        diffs.append(f"{path}: tag mismatch: generated={gen.tag} vs reference={ref.tag}")
        return  # no point comparing children if the tag differs

    current_path = f"{path}{_short_tag(gen.tag)}/"

    # Attributes
    gen_attrs = dict(gen.attrib)
    ref_attrs = dict(ref.attrib)
    for attr in sorted(set(gen_attrs) | set(ref_attrs)):
        gv = gen_attrs.get(attr)
        rv = ref_attrs.get(attr)
        if gv != rv:
            diffs.append(
                f"{current_path}@{_short_tag(attr)}: "
                f"generated={gv!r} vs reference={rv!r}"
            )

    # Text content (stripped)
    gen_text = (gen.text or "").strip()
    ref_text = (ref.text or "").strip()
    if gen_text != ref_text:
        diffs.append(
            f"{current_path}text: "
            f"generated={gen_text!r} vs reference={ref_text!r}"
        )

    # Children count
    gen_children = list(gen)
    ref_children = list(ref)
    if len(gen_children) != len(ref_children):
        diffs.append(
            f"{current_path}: child count mismatch: "
            f"generated={len(gen_children)} vs reference={len(ref_children)}"
        )
        # Compare as far as possible
        min_len = min(len(gen_children), len(ref_children))
        for i in range(min_len):
            _compare_elements(gen_children[i], ref_children[i], current_path, diffs)
        return

    for i, (gc, rc) in enumerate(zip(gen_children, ref_children)):
        _compare_elements(gc, rc, current_path, diffs)


def _short_tag(tag: str) -> str:
    """Shorten ``{uri}local`` to ``prefix:local`` for readability."""
    from .namespaces import _URI_TO_PREFIX

    if tag.startswith("{"):
        uri, local = tag[1:].split("}", 1)
        prefix = _URI_TO_PREFIX.get(uri, uri)
        return f"{prefix}:{local}"
    return tag
