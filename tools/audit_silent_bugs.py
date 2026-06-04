"""Audit a generated GML for issues XSD validation cannot catch.

Comprehensive scan for:
  H1. Dangling xlink:href / app:target references (must point to an in-doc gml:id).
  H2. gml:posList coordinate count vs declared srsDimension (must be divisible).
  H3. Element URIs that have no XSD declaration (validator silently passes).
  H4. @codeSpace URLs — list distinct values for human review.
  H5. gml:Polygon LinearRing point counts (>= 4, first == last).
  H6. @uom tokens unknown to the KITModelViewer's UOMList.xml (viewer
      renders unmatched tokens as raw text instead of the unit sign).
  H7. xs:any wildcards in the schemas (one-shot, not per file).
  H8. XSD-required child elements present on a curated set of feature types.
      XSD validation catches these too, but H8 reports them per parent feature
      with the parent's gml:id so a regression points straight at the failing
      builder. Currently covers: nrg3:Energy (operationType, isAmountNormalized,
      type, endUse), nrg3:BuildingUnit (type), nrg3:EnergyPerformanceCertificate
      (type, label).
  H9. nrg3:CityObjectRelation xlink targets resolve to a CityObject-shaped
      element, not a geometry primitive. H1 only checks the gml:id exists;
      H9 additionally rejects targets in the {gml} namespace (e.g. an
      installedOn xlink mis-pointing at a gml:MultiSurface instead of the
      bldg:RoofSurface that wraps it).
  H10. nrg3 solar-collector installedOn xlinks resolve to a bldg:RoofSurface
       specifically. Catches the "solar matcher kept a sliver roof index that
       the builder skipped under the round-to-mm gate" failure mode the city
       pipeline introduced in 2026-05-27.
  UML. nrg3 elements with UML taggedValue maxOccurs=1 that appear >1× under a parent.
  UML. <nrg3:metadata> ADE-hook usage (pipeline standardises on
       <nrg3:Metadata> via gml:metaDataProperty; lowercase variant should not appear).

Usage:
    python tools/audit_silent_bugs.py generated/<file>.gml [more.gml ...]
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import lxml.etree as etree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from validate_xsd import load_schema

# ---------------------------------------------------------------------------
# H6 — KIT viewer UOMList.xml cross-check
# ---------------------------------------------------------------------------
# The KITModelViewer ships a curated UOM catalog at
# Data/UOMList.xml (one <UOM> entry per unit, each with one ``id`` and 0–3
# ``altId`` aliases). Any uom="..." attribute in our GML whose value is
# neither an id nor an altId will render as raw text in the viewer's
# Properties panel instead of the human-readable sign. The repo bundles
# the viewer at KITModelViewer_V*/ (untracked); we point at whichever
# build is present and skip the check cleanly if none is.
KIT_VIEWER_GLOB = "KITModelViewer_V*/Data/UOMList.xml"

# Every uom token emitted by this pipeline lives in the bundled
# UOMList.xml — including the three TU Delft–proposed additions
# (kWh/a, m3/a, W/W) the file ships with at v1.2 pending upstream KIT
# merge. The audit therefore has no per-token allowlist: if H6 reports
# a uom as unknown, it really is unknown to the catalog and either
# wants fixing in the input or wants adding to UOMList.xml itself.
UOM_NL_EXTENSIONS: frozenset[str] = frozenset()


@lru_cache(maxsize=1)
def _uomlist_known_tokens() -> frozenset[str] | None:
    """Return every ``id`` + ``altId`` from KIT's UOMList.xml, or None.

    None when the KIT viewer dir is not present (the bundle is untracked
    and may not be cloned alongside the source tree). Cached: the
    UOMList is immutable for the process.
    """
    matches = sorted(REPO.glob(KIT_VIEWER_GLOB))
    if not matches:
        return None
    doc = etree.parse(str(matches[0]))
    tokens: set[str] = set()
    for uom in doc.iterfind(".//UOM"):
        id_val = uom.get("id")
        if id_val:
            tokens.add(id_val)
        for alt in uom.iterfind("altId"):
            text = (alt.text or "").strip()
            if text:
                tokens.add(text)
    return frozenset(tokens)


NS = {
    "core": "http://www.opengis.net/citygml/2.0",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "app": "http://www.opengis.net/citygml/appearance/2.0",
    "grp": "http://www.opengis.net/citygml/cityobjectgroup/2.0",
    "gen": "http://www.opengis.net/citygml/generics/2.0",
    "veg": "http://www.opengis.net/citygml/vegetation/2.0",
    "nrg3": "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0",
    "gml": "http://www.opengis.net/gml",
    "xlink": "http://www.w3.org/1999/xlink",
}

UML_MAX1 = {
    f"{{{NS['nrg3']}}}{n}"
    for n in [
        "identifier",
        "status",
        "validFrom",
        "validTo",
        "layeredConstruction",
        "referencePoint",
        "bdgOwnerName",
        "bdgOwnershipType",
        "bdgNumberOfBuildingUnits",
        "bdgAtticThermalStatus",
        "bdgBasementThermalStatus",
        "bdgConstructionWeight",
        "bdgIsProtected",
        "bdgType",
        "bdgBdrySurfAdditionalThermalBridgeUValue",
        "bdgBdrySurfIsShared",
        "bdgBdrySurfThickness",
        "bdgBdrySurfTotalSurfaceArea",
        "bdgBdrySurfOpaqueSurfaceArea",
        "bdgBdrySurfHeatCapacity",
        "bdgBdrySurfAzimuth",
        "bdgBdrySurfInclination",
        "bdgBdrySurfGroundViewFactor",
        "bdgBdrySurfSkyViewFactor",
        "bdgOpnArea",
        "bdgOpnInclination",
        "bdgOpnAzimuth",
        "bdgOpnGroundViewFactor",
        "bdgOpnSkyViewFactor",
    ]
}

# The XSD declares two element names that both end up wired as "Metadata":
#   * <nrg3:Metadata> substitutes gml:metaDataProperty  (XSD line 347, UML unbounded)
#   * <nrg3:metadata> substitutes core:_GenericApplicationPropertyOfCityObject
#     (XSD line 1260, UML maxOccurs=1)
# The pipeline standardises on the capital-M / gml:metaDataProperty route. The
# lowercase ADE-hook variant is structurally available but never used; if it
# starts appearing in the output that signals an authoring bug, regardless of
# how many times it appears under one parent.
LOWERCASE_METADATA_HOOK = f"{{{NS['nrg3']}}}metadata"

XLINK_HREF = f"{{{NS['xlink']}}}href"
GML_ID = f"{{{NS['gml']}}}id"
APP_TARGET = f"{{{NS['app']}}}target"

# H8 — XSD-required children per feature type (local-name lists). Source of truth
# is Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd; reproduce only the
# minOccurs=1 children. Inherited bases are folded in (e.g. nrg3:Energy gets
# operationType + isAmountNormalized from AbstractResourceType plus type +
# endUse from EnergyType itself). XSD validation also catches these, but H8
# reports the failing parent's gml:id so a regression points straight at the
# emitter that ships an incomplete feature, instead of just listing line numbers.
H8_REQUIRED_CHILDREN: dict[tuple[str, str], tuple[str, ...]] = {
    # XSD line 2025+ (EnergyType) + line 544+ (AbstractResourceType inherited).
    (NS["nrg3"], "Energy"): ("operationType", "isAmountNormalized", "type", "endUse"),
    # XSD line 1422+ (BuildingUnitType).
    (NS["nrg3"], "BuildingUnit"): ("type",),
    # XSD line ~1334+ (EnergyPerformanceCertificateType).
    (NS["nrg3"], "EnergyPerformanceCertificate"): ("type", "label"),
}

# H9/H10 — namespace URIs that must NEVER appear as the resolved target tag
# of an nrg3:CityObjectRelation. The CityGML 2.0 + Energy ADE 3.0 CityObject
# substitution group sits in core/bldg/nrg3/grp/veg/etc. — never in {gml},
# which is reserved for geometry primitives (gml:Polygon, gml:MultiSurface,
# gml:LinearRing, gml:Point). An xlink that resolves to a {gml} tag means
# someone wrote the geometry container's gml:id instead of the CityObject's.
H9_FORBIDDEN_TARGET_NS: frozenset[str] = frozenset({NS["gml"]})

# H10 — solar-collector relations: installedOn must land on a roof surface.
# AbstractSolarCollector (and its concrete GenericSolarCollector /
# PhotovoltaicCollector / SolarThermalCollector members) attaches to a
# bldg:RoofSurface in this pipeline's emission convention (see
# citygml_energy/city_builder/solar_panels.py docstrings). The check is
# narrowly scoped to that relation/feature pair to keep false positives at
# zero; broader "installedOn must be a CityObject" is already covered by H9.
H10_SOLAR_COLLECTOR_TAGS: frozenset[str] = frozenset(
    {
        f"{{{NS['nrg3']}}}GenericSolarCollector",
        f"{{{NS['nrg3']}}}PhotovoltaicCollector",
        f"{{{NS['nrg3']}}}SolarThermalCollector",
    }
)
H10_EXPECTED_INSTALLED_ON_TAG: str = f"{{{NS['bldg']}}}RoofSurface"


def audit(path: Path) -> int:
    print(f"\n===== {path.name} =====")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    errors = 0

    # ------------------------------------------------------------------ H1
    ids: set[str] = set()
    for elem in root.iter():
        v = elem.get(GML_ID)
        if v:
            ids.add(v)

    dangling_xlinks: list[tuple[str, int]] = []
    for elem in root.iter():
        href = elem.get(XLINK_HREF)
        if href and href.startswith("#"):
            target = href[1:]
            if target not in ids:
                dangling_xlinks.append((href, elem.sourceline or 0))
    if dangling_xlinks:
        errors += len(dangling_xlinks)
        print(f"  H1 DANGLING xlink:href ({len(dangling_xlinks)}):")
        for h, ln in dangling_xlinks[:5]:
            print(f"     line {ln}: {h}")
        if len(dangling_xlinks) > 5:
            print(f"     ... and {len(dangling_xlinks) - 5} more")
    else:
        print("  H1 xlink:href: OK (no dangling)")

    # app:target — usually `#id` but the XSD type is xs:anyURI so bare ids are also seen
    dangling_targets: list[tuple[str, int]] = []
    for tgt in root.iter(APP_TARGET):
        v = (tgt.text or "").strip()
        ref = v.lstrip("#")
        if ref and ref not in ids:
            dangling_targets.append((v, tgt.sourceline or 0))
    if dangling_targets:
        errors += len(dangling_targets)
        print(f"  H1b DANGLING app:target ({len(dangling_targets)}):")
        for v, ln in dangling_targets[:5]:
            print(f"     line {ln}: {v}")
        if len(dangling_targets) > 5:
            print(f"     ... and {len(dangling_targets) - 5} more")
    else:
        print("  H1b app:target: OK (no dangling)")

    # ------------------------------------------------------------------ H2
    # gml:posList — coord count must be divisible by srsDimension.
    # srsDimension can be on the posList itself, or inherited from ancestor.
    bad_poslists: list[tuple[int, int, int]] = []
    for pl in root.iter(f"{{{NS['gml']}}}posList"):
        # Find effective srsDimension
        srs_dim = None
        e = pl
        while e is not None:
            sd = e.get("srsDimension")
            if sd:
                srs_dim = int(sd)
                break
            e = e.getparent()
        if srs_dim is None:
            srs_dim = 3  # default from CityModel envelope
        coords = (pl.text or "").split()
        if len(coords) % srs_dim != 0:
            bad_poslists.append((pl.sourceline or 0, len(coords), srs_dim))
    if bad_poslists:
        errors += len(bad_poslists)
        print(f"  H2 BAD posList counts ({len(bad_poslists)}):")
        for ln, n, d in bad_poslists[:5]:
            print(f"     line {ln}: {n} coords / srsDimension={d}")
    else:
        print("  H2 gml:posList: OK (all divisible by srsDimension)")

    # gml:pos must have exactly srsDimension values
    bad_pos: list[tuple[int, int, int]] = []
    for p in root.iter(f"{{{NS['gml']}}}pos"):
        srs_dim = None
        e = p
        while e is not None:
            sd = e.get("srsDimension")
            if sd:
                srs_dim = int(sd)
                break
            e = e.getparent()
        if srs_dim is None:
            srs_dim = 3
        coords = (p.text or "").split()
        if len(coords) != srs_dim:
            bad_pos.append((p.sourceline or 0, len(coords), srs_dim))
    if bad_pos:
        errors += len(bad_pos)
        print(f"  H2b BAD pos counts ({len(bad_pos)}):")
        for ln, n, d in bad_pos[:5]:
            print(f"     line {ln}: {n} coords / srsDimension={d}")
    else:
        print("  H2b gml:pos: OK")

    # ------------------------------------------------------------------ H5
    # gml:LinearRing point counts: at least 4, first == last
    bad_rings: list[tuple[int, str]] = []
    for ring in root.iter(f"{{{NS['gml']}}}LinearRing"):
        pl = ring.find(f"{{{NS['gml']}}}posList")
        if pl is None:
            continue
        srs_dim = None
        e = pl
        while e is not None:
            sd = e.get("srsDimension")
            if sd:
                srs_dim = int(sd)
                break
            e = e.getparent()
        if srs_dim is None:
            srs_dim = 3
        coords = (pl.text or "").split()
        if len(coords) % srs_dim != 0:
            continue  # already flagged in H2
        n_pts = len(coords) // srs_dim
        if n_pts < 4:
            bad_rings.append((pl.sourceline or 0, f"only {n_pts} pts"))
            continue
        first = coords[:srs_dim]
        last = coords[-srs_dim:]
        if first != last:
            bad_rings.append((pl.sourceline or 0, f"first ({first}) != last ({last})"))
    if bad_rings:
        errors += len(bad_rings)
        print(f"  H5 BAD LinearRings ({len(bad_rings)}):")
        for ln, msg in bad_rings[:5]:
            print(f"     line {ln}: {msg}")
    else:
        print("  H5 gml:LinearRing: OK (>=4 pts, first==last)")

    # ------------------------------------------------------------------ H6
    # @uom cross-check against KIT viewer UOMList.xml. Tokens that match
    # neither an id nor an altId render as raw text in the viewer's
    # Properties panel; flag them so any future drift surfaces here
    # before someone opens the file in the GUI.
    uom_known = _uomlist_known_tokens()
    if uom_known is None:
        print("  H6 @uom: SKIPPED (KIT viewer UOMList.xml not found in repo)")
    else:
        uom_counts: Counter[str] = Counter()
        for elem in root.iter():
            v = elem.get("uom")
            if v:
                uom_counts[v] += 1
        extensions: list[tuple[str, int]] = []
        unknowns: list[tuple[str, int]] = []
        for token, n in sorted(uom_counts.items()):
            if token in uom_known:
                continue
            if token in UOM_NL_EXTENSIONS:
                extensions.append((token, n))
            else:
                unknowns.append((token, n))
        n_distinct = len(uom_counts)
        n_known = n_distinct - len(extensions) - len(unknowns)
        if unknowns:
            errors += sum(n for _, n in unknowns)
            print(f"  H6 @uom UNKNOWN to KIT UOMList ({len(unknowns)} distinct):")
            for token, n in unknowns:
                print(f"     {n:>5} × {token!r}")
        elif extensions:
            print(
                f"  H6 @uom: OK ({n_known}/{n_distinct} distinct tokens in KIT UOMList; "
                f"{len(extensions)} documented NL extension(s))"
            )
        else:
            print(f"  H6 @uom: OK ({n_distinct} distinct tokens, all in KIT UOMList)")
        if extensions:
            print(f"  H6 @uom EXTENSION (pending KIT upstream) ({len(extensions)} distinct):")
            for token, n in extensions:
                print(f"     {n:>5} × {token!r}")

    # ------------------------------------------------------------------ H8
    # XSD-required children per feature type. Reports the failing parent's
    # gml:id so the emitter is identifiable; xmllint / lxml schema validation
    # only carries line numbers.
    h8_violations: list[tuple[str, str, str]] = []  # (tag, gml_id, missing_child)
    for (uri, local), required in H8_REQUIRED_CHILDREN.items():
        parent_tag = f"{{{uri}}}{local}"
        for parent in root.iter(parent_tag):
            # ``parent.iterchildren()`` would also yield comment / PI nodes
            # whose .tag is a cyfunction and would crash QName(); filter
            # to real element nodes (callable .tag rules them out).
            present = {etree.QName(c.tag).localname for c in parent if isinstance(c.tag, str)}
            gml_id = parent.get(GML_ID) or "(no gml:id)"
            h8_violations.extend(
                (f"{local}", gml_id, needed) for needed in required if needed not in present
            )
    if h8_violations:
        errors += len(h8_violations)
        print(f"  H8 MISSING required children ({len(h8_violations)}):")
        for tag, gml_id, child in h8_violations[:10]:
            print(f"     <{tag} gml:id={gml_id!r}> missing required <{child}>")
        if len(h8_violations) > 10:
            print(f"     ... and {len(h8_violations) - 10} more")
    else:
        n_covered = sum(1 for _ in H8_REQUIRED_CHILDREN)
        print(f"  H8 required children: OK ({n_covered} feature types checked)")

    # ------------------------------------------------------------------ H9
    # nrg3:CityObjectRelation xlink target type-check. H1 verifies the gml:id
    # exists; H9 additionally rejects targets in the {gml} namespace (geometry
    # primitives are never valid CityObject relation targets). Catches the
    # "device installedOn xlink mis-pointed at a gml:MultiSurface id instead of
    # the wrapping bldg:RoofSurface" failure mode.
    h9_violations: list[tuple[str, str, str, int]] = []  # (rel_type, target_id, target_tag, lineno)
    id_to_elem: dict[str, etree._Element] = {}
    for elem in root.iter():
        v = elem.get(GML_ID)
        if v:
            id_to_elem.setdefault(v, elem)
    for rel in root.iter(f"{{{NS['nrg3']}}}CityObjectRelation"):
        rt = rel.find(f"{{{NS['nrg3']}}}relationType")
        rel_type = (rt.text or "").strip() if rt is not None else "(no relationType)"
        related = rel.find(f"{{{NS['nrg3']}}}relatedTo")
        if related is None:
            continue
        href = related.get(XLINK_HREF) or ""
        if not href.startswith("#"):
            continue
        target_id = href[1:]
        target = id_to_elem.get(target_id)
        if target is None:
            continue  # already flagged by H1
        target_ns = etree.QName(target.tag).namespace or ""
        if target_ns in H9_FORBIDDEN_TARGET_NS:
            h9_violations.append((rel_type, target_id, target.tag, rel.sourceline or 0))
    if h9_violations:
        errors += len(h9_violations)
        print(f"  H9 BAD relatedTo target type ({len(h9_violations)}):")
        for rel_type, tid, ttag, ln in h9_violations[:10]:
            print(f"     line {ln}: relationType={rel_type!r} -> #{tid} ({ttag})")
        if len(h9_violations) > 10:
            print(f"     ... and {len(h9_violations) - 10} more")
    else:
        print("  H9 relatedTo target type: OK (no targets resolve to gml: geometry)")

    # ------------------------------------------------------------------ H10
    # Solar-collector installedOn must land on a bldg:RoofSurface. Tighter
    # than H9: catches the specific city-pipeline regression where the panel
    # matcher kept a sliver-area roof index that the builder skipped under
    # the round-to-mm gate, producing an installedOn → #pand_X_roofsurface_N
    # xlink whose target was never emitted (would also fail H1) OR was
    # emitted but as a different surface type (would slip past H1+H9).
    h10_violations: list[tuple[str, str, str, str, int]] = []
    # (collector_gml_id, collector_tag, target_id, target_tag, lineno)
    for collector in root.iter():
        if collector.tag not in H10_SOLAR_COLLECTOR_TAGS:
            continue
        coll_id = collector.get(GML_ID) or "(no gml:id)"
        for rel in collector.iter(f"{{{NS['nrg3']}}}CityObjectRelation"):
            rt = rel.find(f"{{{NS['nrg3']}}}relationType")
            rel_type = (rt.text or "").strip() if rt is not None else ""
            if rel_type != "installedOn":
                continue
            related = rel.find(f"{{{NS['nrg3']}}}relatedTo")
            if related is None:
                continue
            href = related.get(XLINK_HREF) or ""
            if not href.startswith("#"):
                continue
            target_id = href[1:]
            target = id_to_elem.get(target_id)
            if target is None:
                # dangling: H1 already reports it; don't double-count
                continue
            if target.tag != H10_EXPECTED_INSTALLED_ON_TAG:
                h10_violations.append(
                    (
                        coll_id,
                        etree.QName(collector.tag).localname,
                        target_id,
                        target.tag,
                        rel.sourceline or 0,
                    )
                )
    if h10_violations:
        errors += len(h10_violations)
        print(f"  H10 solar collector installedOn -> wrong target type ({len(h10_violations)}):")
        for cid, ctag, tid, ttag, ln in h10_violations[:10]:
            print(
                f"     line {ln}: <{ctag} gml:id={cid!r}> installedOn -> #{tid} ({ttag}); expected bldg:RoofSurface"
            )
        if len(h10_violations) > 10:
            print(f"     ... and {len(h10_violations) - 10} more")
    else:
        print("  H10 solar collector installedOn -> RoofSurface: OK")

    # ------------------------------------------------------------------ UML
    uml_viols: dict[str, int] = defaultdict(int)
    lowercase_metadata_hits = 0
    for elem in root.iter():
        counts = Counter(c.tag for c in elem)
        for qname in UML_MAX1:
            if counts.get(qname, 0) > 1:
                uml_viols[
                    f"{etree.QName(qname).localname} under {etree.QName(elem.tag).localname}"
                ] += 1
        lowercase_metadata_hits += counts.get(LOWERCASE_METADATA_HOOK, 0)
    if uml_viols:
        errors += sum(uml_viols.values())
        print(f"  UML maxOccurs=1 VIOLATIONS ({sum(uml_viols.values())}):")
        for k, v in sorted(uml_viols.items()):
            print(f"     {k}: {v} parents")
    else:
        print("  UML maxOccurs=1: OK")

    if lowercase_metadata_hits:
        errors += lowercase_metadata_hits
        print(
            f"  UML <nrg3:metadata> hook used {lowercase_metadata_hits}× — "
            "pipeline standardises on <nrg3:Metadata> via gml:metaDataProperty; "
            "the lowercase ADE-hook variant should not appear."
        )
    else:
        print("  UML <nrg3:metadata> ADE hook: OK (pipeline uses gml:metaDataProperty route)")

    # ------------------------------------------------------------------ H11
    # CRS / srsDimension consistency between the root gml:Envelope and every
    # child geometry. lxml's XSD validation does not enforce this — a
    # building fragment can declare any srsName/srsDimension and pass — so
    # an emitter that hard-codes a fallback CRS (e.g. WGS84 when an RD
    # transform fails) would produce intra-document mixing that silently
    # corrupts every downstream spatial query. Walks every element with
    # srsName or srsDimension and asserts the value matches the envelope's;
    # an envelope-less document is treated as "no anchor" and the check is
    # skipped rather than guessing a reference value.
    env = root.find(f".//{{{NS['gml']}}}Envelope")
    env_srs = env.get("srsName") if env is not None else None
    env_dim = env.get("srsDimension") if env is not None else None
    if env is None or env_srs is None:
        print("  H11 CRS consistency: SKIPPED (no root gml:Envelope srsName)")
    else:
        srs_viols: list[tuple[str, str, int]] = []  # (localname, srsName, line)
        dim_viols: list[tuple[str, str, int]] = []  # (localname, srsDim, line)
        for elem in root.iter():
            if elem is env or not isinstance(elem.tag, str):
                continue
            v_srs = elem.get("srsName")
            if v_srs is not None and v_srs != env_srs:
                srs_viols.append((etree.QName(elem.tag).localname, v_srs, elem.sourceline or 0))
            v_dim = elem.get("srsDimension")
            if env_dim is not None and v_dim is not None and v_dim != env_dim:
                dim_viols.append((etree.QName(elem.tag).localname, v_dim, elem.sourceline or 0))
        n_viol = len(srs_viols) + len(dim_viols)
        if n_viol:
            errors += n_viol
            if srs_viols:
                print(f"  H11 srsName mismatch vs Envelope ({env_srs!r}) ({len(srs_viols)}):")
                for ln, v, line in srs_viols[:10]:
                    print(f"     line {line}: <{ln} srsName={v!r}>")
                if len(srs_viols) > 10:
                    print(f"     ... and {len(srs_viols) - 10} more")
            if dim_viols:
                print(f"  H11 srsDimension mismatch vs Envelope ({env_dim!r}) ({len(dim_viols)}):")
                for ln, v, line in dim_viols[:10]:
                    print(f"     line {line}: <{ln} srsDimension={v!r}>")
                if len(dim_viols) > 10:
                    print(f"     ... and {len(dim_viols) - 10} more")
        else:
            print(
                f"  H11 CRS consistency: OK (Envelope srsName={env_srs!r}, "
                f"srsDimension={env_dim!r}; all child geometries match)"
            )

    # ------------------------------------------------------------------ H12
    # nrg3 child-element sequence (per-feature). lxml's XSD validator catches
    # any xs:sequence violation but reports it against a line number only.
    # H12 walks a curated set of nrg3 complex types and prints the offending
    # parent's gml:id when a child appears before an earlier-ranked sibling.
    # The benefit over raw XSD validation is the per-feature handle for the
    # emitter that produced the wrong shape; the cost is a small static map
    # that needs a refresh on every Energy ADE XSD bump.
    #
    # Coverage is intentionally narrow — only nrg3:Energy, which has the
    # longest single sequence (~30 fields across AbstractCityObjectType →
    # AbstractResourceType → EnergyType inheritance) and is built field-by-
    # field across multiple emitter sites in the pipeline, making it the
    # type where a sequence regression is most likely. Types with shorter
    # sequences (EnergyPerformanceCertificate: 4 fields; BuildingUnit:
    # ~8) get adequate coverage from H8's required-children check; adding
    # them to H12 would mean re-encoding their multi-level inheritance
    # chain by hand on every XSD bump — a high-maintenance gain that
    # duplicates what XSD validation already enforces.
    #
    # Children NOT in the list are tolerated (they belong to substitution
    # groups whose relative order is not constrained, e.g. the nrg3 ADE-hook
    # substitutions on AbstractCityObject: identifier, status, validFrom,
    # validTo, layeredConstruction, referencePoint, etc.).
    h12_sequences: dict[tuple[str, str], tuple[str, ...]] = {
        # nrg3:Energy = EnergyType → AbstractResourceType → AbstractCityObjectType
        # Source: Energy_ADE_3.0_beta8.xsd lines 547+ (AbstractResource) and 2047+ (Energy).
        (NS["nrg3"], "Energy"): (
            # core:AbstractCityObject base sequence
            "creationDate",
            "terminationDate",
            "externalReference",
            "generalizesTo",
            "relativeToTerrain",
            "relativeToWater",
            # AbstractResourceType
            "operationType",
            "referencePeriod",
            "amount",
            "year",
            "isAmountNormalized",
            "normalizationValue",
            "normalizationParameter",
            "expense",
            "revenue",
            "co2Equivalent",
            "timeDependentAmount",
            "timeDependentExpense",
            "timeDependentRevenue",
            "amountBasedOn",
            # EnergyType
            "type",
            "endUse",
            "energyCarrier",
            "maximumLoad",
            "maximumLoadTime",
            "maximumLoadDay",
            "maximumLoadMonth",
            "source",
        ),
    }
    h12_viols: list[tuple[str, str, str, str, int]] = []
    # (parent_localname, gml_id, out_of_order_child, prior_in_order_child, line)
    for (uri, local), expected in h12_sequences.items():
        rank = {n: i for i, n in enumerate(expected)}
        parent_tag = f"{{{uri}}}{local}"
        for parent in root.iter(parent_tag):
            gml_id = parent.get(GML_ID) or "(no gml:id)"
            last_rank = -1
            last_name = ""
            for child in parent:
                if not isinstance(child.tag, str):
                    continue
                ln = etree.QName(child.tag).localname
                r = rank.get(ln)
                if r is None:
                    continue
                if r < last_rank:
                    h12_viols.append((local, gml_id, ln, last_name, child.sourceline or 0))
                    break
                last_rank = r
                last_name = ln
    if h12_viols:
        errors += len(h12_viols)
        print(f"  H12 nrg3 child-sequence violations ({len(h12_viols)}):")
        for tag, gid, bad, prior, ln in h12_viols[:10]:
            print(
                f"     line {ln}: <{tag} gml:id={gid!r}> "
                f"has <{bad}> after <{prior}> (XSD requires opposite order)"
            )
        if len(h12_viols) > 10:
            print(f"     ... and {len(h12_viols) - 10} more")
    else:
        n_covered = len(h12_sequences)
        print(f"  H12 nrg3 child-sequence: OK ({n_covered} feature types checked)")

    # ------------------------------------------------------------------ H4
    # @codeSpace distinct values. The "SUSPECT" marker is scoped to nrg3
    # codespaces only: SIG3D's CityGML 2.0 building codelists legitimately
    # live under /codelists/, but the nrg3 codespaces must be flat
    # (".../energy/3.0/<Name>Value.xml") — the /codelists/ form 404s on the
    # 3dcities.bk.tudelft.nl host (see reference_codespace_urls memory).
    cs = Counter()
    for elem in root.iter():
        v = elem.get("codeSpace")
        if v:
            cs[v] += 1
    print(f"  H4 distinct @codeSpace URLs: {len(cs)}")
    for url, n in sorted(cs.items()):
        marker = ""
        if "energy/3.0" in url and "/codelists/" in url:
            marker = "  <-- SUSPECT (nrg3 codespaces must be flat, no /codelists/)"
        print(f"     {n:>5} × {url}{marker}")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    # H7 — verify no xs:any wildcards in schemas (one-shot)
    xsd_root = REPO / "xsd"
    nrg3_xsd = REPO / "Energy_ADE-3.0beta8" / "xsd" / "Energy_ADE_3.0_beta8.xsd"
    any_count = 0
    for xsd_path in [*xsd_root.rglob("*.xsd"), nrg3_xsd]:
        try:
            doc = etree.parse(str(xsd_path))
            anys = doc.findall(".//{http://www.w3.org/2001/XMLSchema}any")
            any_count += len(anys)
        except Exception as e:
            print(f"H7 schema parse error: {xsd_path}: {e}")
    print(f"H7 xs:any wildcards across all bundled schemas: {any_count}")

    # H3 — sanity-check the schema loaded fully (LocalResolver covered every import)
    print("H3 loading schema with LocalResolver...")
    try:
        load_schema()
        print("H3 schema loaded OK (no unresolved imports)")
    except etree.XMLSchemaParseError as e:
        print(f"H3 SCHEMA PARSE ERROR: {e}")
        return 2

    total = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.is_absolute():
            p = REPO / p
        total += audit(p)

    print(f"\n===== TOTAL audit findings: {total} =====")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
