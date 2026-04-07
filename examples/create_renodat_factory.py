"""Recreate RenoDAT_GML_V1.gml using the FME-style FeatureFactory API.

This script demonstrates the flat-dict / ``gml_parent_id`` approach:
each feature type is described by an attribute dictionary, and the
factory assembles the hierarchy automatically.

Compare with ``create_renodat.py`` which uses the structured dataclass API
directly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citygml_energy import (
    FeatureFactory,
    CS_BUILDING_CLASS,
    CS_BUILDING_FUNCTION,
    CS_BUILDING_ROOFTYPE,
    CS_BUILDING_USAGE,
    CS_NRG3_BUILDING_TYPE,
    CS_NRG3_OWNERSHIP_TYPE,
    CS_NRG3_VOLUME_TYPE,
)


def create_renodat_via_factory():
    """Build the RenoDAT example city model using the FeatureFactory."""
    factory = FeatureFactory(
        description="This is a description",
        name="RenoDAT City",
    )

    # --- Building ---
    factory.add("bldg_Building", {
        "gml_id":                               "id_building_1",
        "gml_name":                             "Han solo's house",
        "core_creationDate":                    "2026-04-04",
        # Energy ADE CityObject extensions
        "nrg3_identifier":                      "0503100000032914",
        "nrg3_identifier_codeSpace":            "https://bagviewer.kadaster.nl/?objectId=0503100000032914",
        "nrg3_metadata_author":                 "Daan Schlosser",
        "nrg3_metadata_acquisitionMethod":      "measurement",
        "nrg3_metadata_owner":                  "Han Solo",
        # CityGML building properties
        "bldg_class":                           "1000",
        "bldg_class_codeSpace":                 CS_BUILDING_CLASS,
        "bldg_function":                        "1000",
        "bldg_function_codeSpace":              CS_BUILDING_FUNCTION,
        "bldg_usage":                           "1000",
        "bldg_usage_codeSpace":                 CS_BUILDING_USAGE,
        "bldg_yearOfConstruction":              "2020",
        "bldg_roofType":                        "1030",
        "bldg_roofType_codeSpace":              CS_BUILDING_ROOFTYPE,
        "bldg_storeysAboveGround":              "3",
        "bldg_storeysBelowGround":              "0",
        # Energy ADE building extensions
        "nrg3_bdgIsProtected":                  "false",
        "nrg3_bdgNumberOfBuildingUnits":        "1",
        "nrg3_bdgOwnerName":                    "Han Solo",
        "nrg3_bdgOwnershipType":                "occupantPrivateOwner",
        "nrg3_bdgOwnershipType_codeSpace":      CS_NRG3_OWNERSHIP_TYPE,
        "nrg3_bdgType":                         "singleFamilyHouse",
        "nrg3_bdgType_codeSpace":               CS_NRG3_BUILDING_TYPE,
        "nrg3_bdgVolume_description":           "Building's gross volume of 3D model",
        "nrg3_bdgVolume_source":                "3D model",
        "nrg3_bdgVolume_value":                 "823.30",
        "nrg3_bdgVolume_uom":                   "m3",
        "nrg3_bdgVolume_type":                  "grossVolume",
        "nrg3_bdgVolume_type_codeSpace":        CS_NRG3_VOLUME_TYPE,
    })

    # --- PV collector (linked to building via gml_parent_id) ---
    factory.add("nrg3_PhotovoltaicCollector", {
        "gml_id":                   "pv_panel_1",
        "gml_parent_id":            "id_building_1",   # ← attach to the building
        "gml_name":                 "PV collector (36x270 Wp)",
        "core_creationDate":        "2026-04-04",
        "nrg3_model":               "PV-16-270 PW",
        "nrg3_yearOfInstallation":  "2020",
        "nrg3_numberOfDevices":     "36",
        "nrg3_installedPower":      "9720",
        "nrg3_installedPower_uom":  "W",
        "nrg3_azimuth":             "235.65",
        "nrg3_azimuth_uom":         "deg",
        "nrg3_inclination":         "44.51",
        "nrg3_inclination_uom":     "deg",
        "nrg3_cellType":            "unknown",
    })

    return factory.build()


if __name__ == "__main__":
    model = create_renodat_via_factory()
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output_renodat_factory.gml",
    )
    model.write(out_path)
    print(f"Written to {out_path}")

    print("\n--- Generated GML (first 60 lines) ---")
    text = model.to_string()
    for i, line in enumerate(text.split("\n")[:60], 1):
        print(f"  {line}")
