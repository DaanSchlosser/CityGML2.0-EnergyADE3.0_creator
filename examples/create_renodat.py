"""Recreate the RenoDAT_GML_V1.gml file using the citygml_energy API.

This script demonstrates the full API for creating a CityGML 2.0 file
with Energy ADE 3.0 extensions.
"""
import os
import sys

# Allow running from repo root
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


def create_renodat() -> GMLDocument:
    """Build the RenoDAT example city model."""
    doc = GMLDocument(
        description="This is a description",
        name="RenoDAT City",
    )

    # --- PV collector ---
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

    # --- Building ---
    building = Building(
        gml_id="id_building_1",
        gml_name="Han solo's house",
        creation_date="2026-04-04",
        # Energy ADE CityObject extensions
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
        # CityGML building properties
        bldg_class=CodeValue("1000", CS_BUILDING_CLASS),
        bldg_function=CodeValue("1000", CS_BUILDING_FUNCTION),
        bldg_usage=CodeValue("1000", CS_BUILDING_USAGE),
        year_of_construction=2020,
        roof_type=CodeValue("1030", CS_BUILDING_ROOFTYPE),
        storeys_above_ground=3,
        storeys_below_ground=0,
        # Energy ADE building extensions
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
    doc = create_renodat()
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output_renodat.gml",
    )
    doc.write(out_path)
    print(f"Written to {out_path}")

    # Quick preview
    print("\n--- Generated GML (first 60 lines) ---")
    text = doc.to_string()
    for i, line in enumerate(text.split("\n")[:60], 1):
        print(f"  {line}")
