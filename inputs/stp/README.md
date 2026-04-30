# STEP geometry

ISO-10303-21 STEP files referenced by the per-building feature-collection JSONs in [`../buildings/`](../buildings/). The per-building pipeline parses these into polygon / solid objects via [`citygml_energy/_step.py`](../../citygml_energy/_step.py) and attaches them as LoD 0/1/2/3 geometry on the target `bldg:Building` (or LoD 3 on a thermal zone part).

## Files

The six files here all describe the **owner-occupier reference building** (single-family residence in Delft) at successive levels of detail:

| File | Content |
|---|---|
| `Owner-Occupier1_LOD0_STEP.stp` | LoD 0 footprint (single MultiSurface). |
| `Owner-Occupier1_LOD1_STEP.stp` | LoD 1 generic extrusion (one Solid). |
| `Owner-Occupier1_LOD2_STEP.stp` | LoD 2 faceted exterior with thematic surfaces (Wall / Roof / Ground). |
| `Owner-Occupier1_LOD3_STEP.stp` | LoD 3 detailed exterior with windows and doors. |
| `Owner-Occupier1_ZonePart1_STEP.stp` | LoD 3 geometry for thermal zone part 1. |
| `Owner-Occupier1_ZonePart2_STEP.stp` | LoD 3 geometry for thermal zone part 2. |

Coordinates are in EPSG:28992 (Amersfoort / RD New) with metres as the unit. The reference building's `coordinate_origin` (in the JSON) is `[85182.085, 446868.675, 0.105]`; the STEP geometry is expressed relative to that origin. Note that this is a bogus origin, placed in Delft near the Architecture faculty for anonymisation reasons.

## Authoring

The STEP files were produced in Rhino. Adding a new building means adding a matching set of STEP files plus a feature-collection JSON in `../buildings/`.
