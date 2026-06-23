# LoD3 tree reconstructions (CFTree)

CityJSON 2.0 files holding `SolitaryVegetationObject` features. The Emmer-Compascuum files back the small-area city smoke test; the Leiden files are on-demand reconstructions for address extents (see [`../address/`](../address/)). An ad-hoc `create_address.py` run writes its merged tree file here under the address slug, and only the files a checked-in profile references are tracked in git.

Each file is the output of [`tools/merge_cftree_tiles.py`](../../tools/merge_cftree_tiles.py): per-tile [CFTree](https://github.com/NoahAlting/CFTree) reconstructions are merged, clipped to a boundary polygon, and re-numbered with sequential `T_<n>` ids so the runtime no longer needs to carry tile metadata or resolve cross-tile collisions. CFTree assigns each physical tree to the single tile whose non-overlapping core cell contains its centroid, so the per-tile inputs hold no cross-tile duplicates and the merge does not deduplicate. The original CFTree gtid is preserved in each tree's `original_gtid` attribute for traceability.

## Files

| File | AHN version | Trees | AOI | Source CFTree case |
|---|---|---|---|---|
| `emmer-compascuum_small-area_AHN4.city.json` | AHN4 (2020 flight, CC0) | 614 | [`../boundaries/emmer-compascuum_small-area.geojson`](../boundaries/emmer-compascuum_small-area.geojson) | `CFTree/data/emmer-compascuum_small-area` (3 sub-tiles) |
| `emmer-compascuum_small-area_AHN6.city.json` | AHN6 (2025 flight, CC-BY-4.0) | 702 | [`../boundaries/emmer-compascuum_small-area.geojson`](../boundaries/emmer-compascuum_small-area.geojson) | `CFTree/data/emmer_compascuum_grid2` (3 tiles) |
| `annie-romeinsingel-72-152-leiden_400m.city.json` | AHN5 (geometry-only) | 346 | Annie Romeinsingel 72-152, Leiden (400 m address extent) | on-demand (`vegetation.generate`) |

## Regenerating

Re-run the merge whenever the upstream CFTree case is updated:

```bash
# AHN4
python tools/merge_cftree_tiles.py \
    --case-dir ../CFTree/data/emmer-compascuum_small-area \
    --boundary inputs/boundaries/emmer-compascuum_small-area.geojson \
    --output inputs/vegetation/emmer-compascuum_small-area_AHN4.city.json

# AHN6
python tools/merge_cftree_tiles.py \
    --case-dir ../CFTree/data/emmer_compascuum_grid2 \
    --boundary inputs/boundaries/emmer-compascuum_small-area.geojson \
    --output inputs/vegetation/emmer-compascuum_small-area_AHN6.city.json
```

Cross-tile duplicates are removed inside CFTree, not here: each tree is assigned to the single tile whose core cell contains its centroid, so two overlapping tiles never both emit the same tree. The merge concatenates the per-tile trees and clips them to the boundary. It relies on the CFTree case being built with this tile-ownership pipeline; a case from an older CFTree that still emits overlapping-tile reconstructions would carry those duplicates straight through, since the merge no longer deduplicates.

## Schema notes

The merged file is a single CityJSON 2.0 document with:

- `transform.scale = [0.001, 0.001, 0.001]` (millimetre quantization)
- `transform.translate = [min_x, min_y, min_z]` over every kept vertex
- `metadata.referenceSystem` is the OGC CRS URL `https://www.opengis.net/def/crs/EPSG/0/28992` (EPSG:28992, RD New)
- `metadata.geographicalExtent` = absolute RD New / NAP bbox of the kept trees
- `metadata.extensions.merge_provenance` records the source CFTree case + boundary file used

The runtime parser [`citygml_energy.city_builder.cityjson_trees_parse`](../../citygml_energy/city_builder/cityjson_trees_parse.py) reads this file directly, dequantizing vertices into absolute RD-New metres before the city builder consumes them.
