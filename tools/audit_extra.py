"""Throwaway audit for issues audit_silent_bugs.py doesn't check.

Run: python tools/audit_extra.py generated/*.gml
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import lxml.etree as ET  # noqa: N812

NRG3 = "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0"
GML = "http://www.opengis.net/gml"
BLDG = "http://www.opengis.net/citygml/building/2.0"
CORE = "http://www.opengis.net/citygml/2.0"
XLINK = "http://www.w3.org/1999/xlink"

# nrg3 elements that substitute core:_GenericApplicationPropertyOfCityObject.
# Derived from Energy_ADE_3.0_beta8.xsd by enumerating every <xs:element>
# with substitutionGroup="core:_GenericApplicationPropertyOfCityObject".
NRG3_CITYOBJECT_HOOKS = {
    "device",
    "identifier",
    "indicator",
    "intervention",
    "layeredConstruction",
    "metadata",
    "referencePoint",
    "relatedTo",
    "resource",
    "sensorData",
    "status",
    "utilityNetworkConnection",
    "validFrom",
    "validTo",
}
# nrg3 elements that substitute bldg:_GenericApplicationPropertyOfAbstractBuilding.
# Same derivation. ``zone``, ``buildingUnit`` and ``energyPerformanceCertificate``
# live here (not under the CityObject hook) because the XSD attaches them to
# AbstractBuildingType, not AbstractCityObjectType.
NRG3_BUILDING_HOOKS = {
    "bdgArea",
    "bdgAtticThermalStatus",
    "bdgBasementThermalStatus",
    "bdgConstructionWeight",
    "bdgHeight",
    "bdgIsProtected",
    "bdgNumberOfBuildingUnits",
    "bdgOwnerName",
    "bdgOwnershipType",
    "bdgType",
    "bdgVolume",
    "buildingUnit",
    "energyPerformanceCertificate",
    "zone",
}
# nrg3 elements that substitute bldg:_GenericApplicationPropertyOfBoundarySurface
NRG3_BNDSURF_HOOKS = {
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
}
# nrg3 elements that substitute bldg:_GenericApplicationPropertyOfOpening
NRG3_OPENING_HOOKS = {
    "bdgOpnArea",
    "bdgOpnInclination",
    "bdgOpnAzimuth",
    "bdgOpnGroundViewFactor",
    "bdgOpnSkyViewFactor",
}

POSITIVE_QUANTITIES = {
    "bdgBdrySurfTotalSurfaceArea",
    "bdgBdrySurfOpaqueSurfaceArea",
    "bdgBdrySurfThickness",
    "bdgBdrySurfHeatCapacity",
    "bdgOpnArea",
    "moduleArea",
    "apertureArea",
    "installedPower",
    "numberOfDevices",
    "storeysAboveGround",
    "storeysBelowGround",
    "bdgArea",
    "bdgVolume",
    "bdgHeight",
}

ANGLE_360 = {"bdgBdrySurfAzimuth", "bdgOpnAzimuth", "azimuth"}
ANGLE_180 = {"bdgBdrySurfInclination", "bdgOpnInclination", "inclination"}


def audit(path: Path) -> dict:
    print(f"\n===== {path.name} =====")
    tree = ET.parse(str(path))
    root = tree.getroot()

    findings: dict[str, list] = defaultdict(list)

    # 1. Polygon order: ADE-hook substituting CityObject hook must appear
    #    before BoundarySurface lod*MultiSurface in a BoundarySurface.
    for bs_tag in (
        "GroundSurface",
        "WallSurface",
        "RoofSurface",
        "ClosureSurface",
        "OuterCeilingSurface",
        "OuterFloorSurface",
    ):
        for bs in root.iter(f"{{{BLDG}}}{bs_tag}"):
            saw_lod = False
            for child in bs:
                ln = ET.QName(child.tag).localname
                ns = ET.QName(child.tag).namespace
                if ln in ("lod2MultiSurface", "lod3MultiSurface", "lod4MultiSurface"):
                    saw_lod = True
                elif ln == "opening":
                    if not saw_lod:
                        # opening BEFORE lod*MultiSurface is invalid per XSD
                        findings["opening_before_lod"].append(
                            (path.name, bs.get(f"{{{GML}}}id"), child.sourceline)
                        )
                elif ns == NRG3:
                    if ln in NRG3_CITYOBJECT_HOOKS:
                        # CityObject hook MUST precede lod* (which is BoundarySurface seq)
                        if saw_lod:
                            findings["cityobj_hook_after_boundary"].append(
                                (path.name, bs.get(f"{{{GML}}}id"), ln, child.sourceline)
                            )
                    # BoundarySurface hook MUST follow lod*MultiSurface and opening
                    elif ln in NRG3_BNDSURF_HOOKS and not saw_lod:
                        findings["bndsurf_hook_before_lod"].append(
                            (path.name, bs.get(f"{{{GML}}}id"), ln, child.sourceline)
                        )

    # 2. Check Building ADE-hook ordering: bdg* (building hooks) must be in
    #    bldg:AbstractBuildingType's hook slot, which is AFTER consistsOfBuildingPart
    for b in root.iter(f"{{{BLDG}}}Building"):
        saw_bldg_specific = False  # bldg:class, function, usage, etc.
        for child in b:
            ln = ET.QName(child.tag).localname
            ns = ET.QName(child.tag).namespace
            if ns == BLDG and ln in (
                "class",
                "function",
                "usage",
                "yearOfConstruction",
                "yearOfDemolition",
                "roofType",
                "measuredHeight",
                "storeysAboveGround",
                "storeysBelowGround",
                "storeyHeightsAboveGround",
                "storeyHeightsBelowGround",
                "lod0FootPrint",
                "lod0RoofEdge",
                "lod1Solid",
                "lod1MultiSurface",
                "lod2Solid",
                "lod2MultiSurface",
                "lod3Solid",
                "lod3MultiSurface",
                "lod4Solid",
                "lod4MultiSurface",
                "lod1TerrainIntersection",
                "lod2TerrainIntersection",
                "lod3TerrainIntersection",
                "lod4TerrainIntersection",
                "lod2MultiCurve",
                "lod3MultiCurve",
                "lod4MultiCurve",
                "outerBuildingInstallation",
                "interiorBuildingInstallation",
                "boundedBy",
                "interiorRoom",
                "consistsOfBuildingPart",
                "address",
            ):
                saw_bldg_specific = True
            elif ns == NRG3 and ln in NRG3_CITYOBJECT_HOOKS and saw_bldg_specific:
                findings["cityobj_hook_after_bldg_field"].append(
                    (path.name, b.get(f"{{{GML}}}id"), ln, child.sourceline)
                )

    # 3. Positive-quantity sanity
    for el in root.iter():
        ln = ET.QName(el.tag).localname
        if ln in POSITIVE_QUANTITIES and el.text:
            try:
                v = float(el.text.strip())
                if v < 0:
                    findings["negative_quantity"].append((path.name, ln, v, el.sourceline))
                if v == 0 and ln not in ("storeysBelowGround",):
                    findings["zero_quantity"].append((path.name, ln, v, el.sourceline))
            except ValueError:
                pass

    # 4. Angle ranges
    for el in root.iter():
        ln = ET.QName(el.tag).localname
        if not el.text:
            continue
        try:
            v = float(el.text.strip())
        except ValueError:
            continue
        if ln in ANGLE_360:
            if v < 0 or v >= 360:
                findings["azimuth_out_of_range"].append((path.name, ln, v, el.sourceline))
        elif ln in ANGLE_180 and (v < 0 or v > 180):
            findings["inclination_out_of_range"].append((path.name, ln, v, el.sourceline))

    # 5. Empty elements (whitespace-only text, no children, no xlink)
    for el in root.iter():
        if (
            (el.text is None or not el.text.strip())
            and len(el) == 0
            and not el.get(f"{{{XLINK}}}href")
            and not el.attrib
        ):
            ln = ET.QName(el.tag).localname
            if ln in ("CityModel",):
                continue
            findings["empty_element"].append((path.name, ln, el.sourceline))

    # 6. xlink:href + text content together
    for el in root.iter():
        if el.get(f"{{{XLINK}}}href") and el.text and el.text.strip():
            findings["xlink_plus_text"].append(
                (path.name, ET.QName(el.tag).localname, el.sourceline)
            )

    # 7. Polygon orientation check (CCW for exterior in projected coords): hard, skip for now

    # 8. Sequence sanity within bdgBdrySurf hooks: there's a UML order but no XSD order;
    #    we just count distinct elements per parent and flag suspiciously rare values

    # 9. Boundary surface heat-capacity dimensional uom check
    # SI-conformant areal heat capacity token (``k`` = kilo prefix, ``K``
    # = kelvin per BIPM SI Brochure §3.1; ISO 13786 convention). Single
    # accepted form: anything else on bdgBdrySurfHeatCapacity is drift.
    expected_hc_uom = {"kJ/(K*m2)"}
    for el in root.iter(f"{{{NRG3}}}bdgBdrySurfHeatCapacity"):
        u = el.get("uom") or ""
        if u not in expected_hc_uom:
            findings["heatcap_uom_drift"].append((path.name, u, el.sourceline))

    # 10. EPC type/status uom: the EPC values are codes, not uoms; check the codeSpace
    #    has /energy/3.0/<Name>Value.xml (flat) not /codelists/
    bad_codespace = []
    for el in root.iter():
        cs = el.get("codeSpace")
        if cs and "3dcities" in cs and "/codelists/" in cs:
            bad_codespace.append((ET.QName(el.tag).localname, cs, el.sourceline))
    if bad_codespace:
        findings["nrg3_codelist_path_404"].extend(bad_codespace)

    # 11. Print finding summary
    for k, lst in findings.items():
        if not lst:
            continue
        print(f"  {k}: {len(lst)}")
        for item in lst[:3]:
            print(f"     {item}")
        if len(lst) > 3:
            print(f"     ... and {len(lst) - 3} more")

    if not findings:
        print("  (clean)")
    return findings


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    total = 0
    for p in sys.argv[1:]:
        f = audit(Path(p))
        total += sum(len(v) for v in f.values())
    print(f"\n===== EXTRA TOTAL: {total} findings =====")
    sys.exit(0 if total == 0 else 1)
