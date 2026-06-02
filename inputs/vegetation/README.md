# LoD3 tree reconstructions (CFTree)

CityJSON 2.0 files holding `SolitaryVegetationObject` features for the small-area test AOI in Emmer-Compascuum.

Each file is the output of [`tools/merge_cftree_tiles.py`](../../tools/merge_cftree_tiles.py): per-tile [CFTree](https://github.com/NoahAlting/CFTree) reconstructions are merged, clipped to a boundary polygon, deduplicated by 2D centroid proximity, and re-numbered with sequential `T_<n>` ids so the runtime no longer needs to carry tile metadata or resolve cross-tile collisions. The original CFTree gtid is preserved in each tree's `original_gtid` attribute for traceability.

## Files

| File | AHN version | Trees | AOI | Source CFTree case |
|---|---|---|---|---|
| `emmer-compascuum_small-area_AHN4.city.json` | AHN4 (2020 flight, CC0) | 623 | [`../boundaries/emmer-compascuum_small-area.geojson`](../boundaries/emmer-compascuum_small-area.geojson) | `CFTree/data/emmer-compascuum_small-area` (3 sub-tiles) |
| `emmer-compascuum_small-area_AHN6.city.json` | AHN6 (2025 flight, CC-BY-4.0) | 702 | [`../boundaries/emmer-compascuum_small-area.geojson`](../boundaries/emmer-compascuum_small-area.geojson) | `CFTree/data/emmer_compascuum_grid2` (3 tiles) |

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

`--dedup-threshold-m` defaults to 1.0 m (centroid distance below which two reconstructions are treated as the same physical tree). The AHN4 small-area run drops 28 cross-tile duplicates at this threshold; AHN6 grid2 has zero duplicates at any threshold up to 2 m. Going wider than 1 m starts collapsing genuinely distinct neighbouring trees, so widen only if cross-tile overlap behaviour in CFTree changes meaningfully.

## Schema notes

The merged file is a single CityJSON 2.0 `Feature` with:

- `transform.scale = [0.001, 0.001, 0.001]` (millimetre quantization)
- `transform.translate = [min_x, min_y, min_z]` over every kept vertex
- `metadata.referenceSystem = EPSG:28992`
- `metadata.geographicalExtent` = absolute RD New / NAP bbox of the kept trees
- `metadata.extensions.merge_provenance` records the source CFTree case + boundary file used

The runtime parser [`citygml_energy.city_builder.cityjson_trees_parse`](../../citygml_energy/city_builder/cityjson_trees_parse.py) reads this file directly, dequantizing vertices into absolute RD-New metres before the city builder consumes them.
