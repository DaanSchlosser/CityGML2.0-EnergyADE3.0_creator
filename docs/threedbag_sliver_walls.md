# 3DBAG LoD 2.2 sliver wall surfaces — observation and reproducer

Short report for the 3DBAG team on a roof-mesh reconstruction artefact
that survives into our CityGML 2.0 + Energy ADE 3.0 output. Not a
critique of 3DBAG quality, just a reproducible note in case the
reconstruction pipeline could filter these out at source.

## What we see

In every city-pipeline run that emits LoD 2.2 walls, a handful of
`bldg:WallSurface` features come out with a `<nrg3:bdgBdrySurfTotalSurfaceArea>`
of `0.0 m²` after rounding to mm². Inspecting the underlying
`gml:posList`, each one is a 4-point ring with:

* a 3D surface area in the **`0.000001–0.0005` m²** range
  (`1–500 mm²` — i.e. 1 mm² to ~5 cm²),
* a Z extent of **1 mm to 49 mm** between the lowest and highest vertex.

In other words: tall, paper-thin wall quads sitting between two
adjacent roof facets at slightly different heights. They behave like
mesh slivers from the roof reconstruction rather than real walls of
the building.

The pipeline already drops fully-collapsed rings (those whose vertex
indices resolve to fewer than three distinct points at 1 µm precision,
see [`cityjson_parse._ring_from_indices`](../citygml_energy/city_builder/cityjson_parse.py#L287)).
Slivers with three or four distinct points but area below 1000 mm²
are still geometrically valid, so they pass through and reach the
output unless the sliver-area filter described below removes them.

## Reproducer

Tile cache used: 3DBAG release fetched on **2026-05-27** through
`https://data.3dbag.nl/cityjson/v20240228/tiles/...` (the version
string our [`threedbag` fetcher](../citygml_energy/city_builder/fetchers/threedbag.py)
pins, persisted under `.cache/citygml_energy_city/3dbag_*.bin`).

```powershell
# 1. Drop the parsed-tile cache so the pre-filter slivers are re-evaluated
#    against the current MIN_FACE_AREA_M2 threshold, then rebuild the
#    small-area Emmer-Compascuum and Delft smoke runs.
Remove-Item -Force .cache/citygml_energy_city/3dbag_parsed_*.pkl
python -m citygml_energy.city_builder inputs/cities/emmer-compascuum_small-area.json
python -m citygml_energy.city_builder inputs/cities/delft_smoke.json

# 2. Audit the outputs for zero-area boundary surfaces.
python tools/audit_extra.py generated/emmer-compascuum_small-area.gml generated/delft_smoke.gml
# Post-fix expected: 0 findings (parse-time filter at MIN_FACE_AREA_M2=1e-3 m²
# drops every documented sliver below). Pre-fix (parse threshold 1e-4 m²)
# this was ~20 'zero_quantity' findings under bdgBdrySurfTotalSurfaceArea
# per file, all caused by the rows in the table below.
```

`tools/audit_extra.py` flags every `<nrg3:bdgBdrySurfTotalSurfaceArea>`
that rounds to 0.0; the geometry comes from the parent
`<bldg:WallSurface gml:id="pand_<pand_id>_wallsurface_<n>">`.

## Affected BAG Pand IDs (Emmer-Compascuum small-area run)

20 sliver walls across 18 BAG Pand IDs in the
[`inputs/cities/emmer-compascuum_small-area.json`](../inputs/cities/emmer-compascuum_small-area.json)
AOI. Numbers are reproducible from the cached 3DBAG tiles bundled
under `.cache/`.

| BAG Pand ID | WallSurface (suffix `_n`) | 3D area (m²) | Z extent (m) | Ring points |
|---|---|---|---|---|
| `0114100000205906` | 16 | 0.0004327 | 0.008 | 4 |
| `0114100000205572` | 23 | 0.0003802 | 0.025 | 4 |
| `0114100000214533` | 23 | 0.0001791 | 0.030 | 4 |
| `0114100000225724` | 12 | 0.0000204 | 0.010 | 4 |
| `0114100000225724` | 20 | 0.0000402 | 0.006 | 4 |
| `0114100000233208` | 9  | 0.0000382 | 0.049 | 4 |
| `0114100000233208` | 19 | 0.0002551 | 0.024 | 4 |
| `0114100000233354` | 27 | 0.0001346 | 0.027 | 4 |
| `0114100000233387` | 8  | 0.0002348 | 0.004 | 4 |
| `0114100000243023` | 25 | 0.0000011 | 0.002 | 4 |
| `0114100000242882` | 16 | 0.0001276 | 0.001 | 5 |
| `0114100000260545` | 36 | 0.0000010 | 0.001 | 4 |
| `0114100000260552` | 2  | 0.0000212 | 0.006 | 4 |
| `0114100000260560` | 21 | 0.0000014 | 0.003 | 4 |
| `0114100000257762` | 9  | 0.0000297 | 0.007 | 5 |
| `0114100000261137` | 19 | 0.0002738 | 0.041 | 4 |
| `0114100000260193` | 13 | 0.0000650 | 0.005 | 4 |
| `0114100000261186` | 30 | 0.0003522 | 0.035 | 4 |
| `0114100000269712` | 20 | 0.0000247 | 0.007 | 4 |
| `0114100000391307` | 114 | 0.0004809 | 0.016 | 4 |

The same pattern shows up at much larger volume in the Delft and
Groningen full-municipality runs.

The wall index `_n` is the 1-based position of the wall polygon in
the LoD 2.2 boundary list our parser emits, so a 3DBAG-side
inspection can address the same face by walking the
`Solid → Shell → Surface` boundary array in the order the CityJSON
tile presents.

## Why it matters downstream

The slivers are XSD-valid `gml:Polygon` instances, so they neither
fail validation nor break the viewer. Two consequences worth flagging:

1. **Wall counts and total wall area aggregates** computed from the
   output include these slivers as full walls. A simple "count of
   `bldg:WallSurface` per `bldg:Building`" overstates the wall count
   for any building whose roof mesh has slivers.
2. **Per-surface energy attributes**
   (`<nrg3:bdgBdrySurfTotalSurfaceArea>`, `<nrg3:bdgBdrySurfHeatCapacity>`,
   U-values once they are wired in) get attached to surfaces that
   carry almost no physical envelope area. A naive heat-loss roll-up
   gives them a real coefficient times an essentially zero area, which
   is mathematically fine but obscures the actual wall stock.

## What 3DBAG could check on its side

The slivers behave like the standard sliver-triangle artefact that
boundary-representation mesh reconstruction produces when two roof
facets meet at a near-horizontal edge: the wall between them is
emitted at the precision of the input point cloud rather than
collapsed when the height difference is below some tolerance.

Two upstream filters would each remove the class:

* drop any wall facet whose 3D area falls below a small threshold
  (~500 mm² covers every observed case in the table above; the
  largest sliver is 481 mm²), or
* collapse adjacent roof facets that meet within a Z tolerance
  (~50 mm covers the observed cases) before the wall between them is
  generated.

## What this repo does anyway

Independent of any upstream change, the parser at
[`cityjson_parse._parse_semantic_faces`](../citygml_energy/city_builder/cityjson_parse.py#L259)
drops sliver faces in addition to fully-degenerate rings. The
threshold is **10 cm² (`MIN_FACE_AREA_M2 = 1e-3` m²)** — about `2x`
above the largest observed sliver (`0.000481 m² ≈ 481 mm²`) and
`~500x` below the smallest plausible real LoD 2.2 wall facet (small
dormer side walls start around `0.5 m² = 5 000 cm²`; typical walls
`5-20 m²`). The chosen value sits at the conservative-against-
slivers end of the gap, so an unmeasured sliver up to ~1000 mm² is
still caught while the `500x` margin against real walls keeps false
positives off the table. The
constant is also re-used as the build-time gate inside
[`builders.building.thematic_surface_attrs`](../citygml_energy/city_builder/builders/building.py#L383),
so the parse-time filter and the boundedBy/solar-panel matcher gate
share a single source of truth and cannot drift apart.

The threshold was raised to its current value on 2026-05-27 after an
empirical sweep of cached 3DBAG tiles showed 26 documented slivers
sitting in the previous `[1e-4, 5e-4]` m² band — above the earlier
`1e-4` parse threshold and only caught by the build-time `round(area,
3) <= 0` guard. Unifying the two threshold magnitudes at `1e-3` m²
turns the parse-time filter into the load-bearing one and reduces the
build-time gate to defence-in-depth.

The report stays here as a record of the upstream artefact, in case
3DBAG ever closes the gap at source.
