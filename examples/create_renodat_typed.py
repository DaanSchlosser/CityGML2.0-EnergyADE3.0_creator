"""Recreate RenoDAT_GML_V1.gml using the typed builder API directly."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    Building,
    CodeValue,
    GMLDocument,
    MeasureValue,
    Metadata,
    PhotovoltaicCollector,
    QualifiedVolume,
    CS_BUILDING_CLASS,
    CS_BUILDING_FUNCTION,
    CS_BUILDING_ROOFTYPE,
    CS_BUILDING_USAGE,
    CS_NRG3_BUILDING_TYPE,
    CS_NRG3_OWNERSHIP_TYPE,
    CS_NRG3_VOLUME_TYPE,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "generated" / "renodat_typed.gml"


def create_renodat_typed() -> GMLDocument:
    """Build the RenoDAT example using the typed Python API."""
    doc = GMLDocument(
        description="This is a description",
        name="RenoDAT City",
    )

    pv = PhotovoltaicCollector(
        gml_id="pv_panel_1",
        gml_name="PV collector (36x270 Wp)",
        creation_date="2026-04-04",
        model="PV-16-270 PW",
        year_of_installation=2020,
        number_of_devices=36,
        installed_power=MeasureValue(9720, "W"),
        azimuth=MeasureValue(235.65, "deg"),
        inclination=MeasureValue(44.51, "deg"),
        cell_type=CodeValue("unknown"),
    )

    building = Building(
        gml_id="id_building_1",
        gml_name="Han solo's house",
        creation_date="2026-04-04",
        devices=[pv],
        nrg3_identifier=CodeValue(
            "0503100000032914",
            code_space="https://bagviewer.kadaster.nl/?objectId=0503100000032914",
        ),
        nrg3_metadata=Metadata(
            author="Daan Schlosser",
            acquisition_method="measurement",
            owner="Han Solo",
        ),
        bldg_class=CodeValue("1000", CS_BUILDING_CLASS),
        bldg_function=CodeValue("1000", CS_BUILDING_FUNCTION),
        bldg_usage=CodeValue("1000", CS_BUILDING_USAGE),
        year_of_construction=2020,
        roof_type=CodeValue("1030", CS_BUILDING_ROOFTYPE),
        storeys_above_ground=3,
        storeys_below_ground=0,
        bdg_is_protected=False,
        bdg_number_of_building_units=1,
        bdg_owner_name="Han Solo",
        bdg_ownership_type=CodeValue(
            "occupantPrivateOwner", CS_NRG3_OWNERSHIP_TYPE
        ),
        bdg_type=CodeValue("singleFamilyHouse", CS_NRG3_BUILDING_TYPE),
        bdg_volumes=[
            QualifiedVolume(
                description="Building's gross volume of 3D model",
                source="3D model",
                value=MeasureValue("823.30", "m3"),
                type=CodeValue("grossVolume", CS_NRG3_VOLUME_TYPE),
            )
        ],
    )

    doc.add_building(building)
    return doc


if __name__ == "__main__":
    doc = create_renodat_typed()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.write(str(OUTPUT))
    print(f"Written to {OUTPUT}")