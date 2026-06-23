# 0004. Rectangular viewports clip both buildings and ground to the box

## Status

accepted

## Decision

A city build carries one `clip_to_box` flag on `BuildExtent` (`citygml_energy/city_builder/extent.py`). Both the building clip and the 3D Basisvoorziening landcover clip read that one flag, so a build either cuts both layers at the box or cuts neither, and the two layers cannot disagree at the boundary. The flag is `True` for the two rectangular-viewport extents, an address extract (`_resolve_address_extent`) and a `gemeente` with an explicit `bbox` (`_resolve_municipality_extent`, where `clip_to_box = config.bbox is not None and boundary_geom is None`), and `False` for the two area extents, a whole gemeente and a boundary-polygon AOI. When the flag is set, `box_clip.clip_building_to_box` cuts each straddling solid plane by plane and rebuilds the exposed cross-section as a cap so the shell stays closed, and `box_clip.clip_landcover_polygons` cuts each draped ground facet to the same box. When the flag is clear, a straddling building is kept whole. A boundary-polygon AOI still removes a building whose LoD0 footprint does not intersect the polygon, but it removes it whole rather than cutting it, so its edge comes from the polygon, not from a box.

## Considered Options

**Keep both layers whole and drop straddlers whole, for viewports too.** Rejected. A viewport is meant to be a clean square cut-out centred on a subject. Keeping whole buildings and ground that trail far past the corner leaves a ragged frame around the subject and defeats the point of the centred box.

**Clip only the ground and keep buildings whole.** Rejected. The ground would stop at the box while edge buildings overhang it, so the two layers would disagree at the boundary. The single shared flag exists precisely so they cannot.

**Drop a straddling building whole instead of cutting it.** Rejected for viewports. A building half inside the box would either vanish or overhang, and both read worse than a clean cut. `box_clip.clip_building_to_box` therefore cuts the solid and caps the exposed cross-section so the result still reads as a closed solid, feeding each plane's cap into the next so a corner building cut by two planes is capped on both.

**Cut buildings to the boundary polygon edge as well.** Rejected. A boundary polygon is an area of interest, not a viewport, and cutting concave polygon edges through closed solids is heavier and was not wanted. The boundary path selects whole buildings by intersection, so its edge buildings stay whole on purpose.

**Recompute the 3DBAG attributes for the cut subset.** Rejected. The city pipeline passes the 3DBAG-published volume, area, and height values through rather than deriving them from geometry. Recomputing only the clipped buildings would mix two provenances under the same attribute names with no marker, which is worse than a uniform, documented staleness.

## Consequences

A box-clipped building keeps the 3DBAG volume, area, and height attributes it had before the cut, so on a straddling building those numbers describe the uncut geometry. A clipped extract is therefore visual context, not an analysis-grade dataset, and a consumer must not measure off a cut building. This is recorded as a user-facing limitation in the README (§ 4.5), which is why the trade was accepted rather than treated as a defect.

The one shared flag is also a small seam: a future extent kind (a postcode, a cadastral parcel) declares its clip behaviour with one boolean and inherits both clips, rather than wiring the building clip and the ground clip independently and risking a boundary mismatch.

A reader who meets a cut building whose size attributes do not match its geometry, or a boundary AOI whose edge buildings are whole rather than trimmed, should not "fix" either. Both follow from this decision.

## References

`citygml_energy/city_builder/extent.py` (`BuildExtent.clip_to_box` and the two adapters), `citygml_energy/city_builder/box_clip.py` (`clip_building_to_box`, `clip_landcover_polygons`), README § 4.5 (address extract) and § 4.7 (semantic landcover), and the "Build extent (AOI)" entry in `CONTEXT.md`.
