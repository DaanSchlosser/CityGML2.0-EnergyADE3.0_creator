# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Each tagged
release is archived on Zenodo (see [CITATION.cff](CITATION.cff) and the DOI
badge in the [README](README.md)).

## [1.1.0] - 2026-06-23

### Added

- **Address-driven extract.** A free-text Dutch address resolves, through PDOK
  Locatieserver geocoding and authoritative BAG, to a centred square AOI and the
  set of target Panden it named (`examples/create_address.py`, `address_extent`,
  `address_query`). It is an extent adapter on the existing city-scale pipeline,
  not a third pipeline (ADR-0003).
- **On-demand CFTree tree generation.** A `vegetation.generate` block
  reconstructs the merged tree file for the AOI when it is missing, running
  CFTree as a subprocess at the requested AHN version and merging the per-tile
  output (`cftree_runner`). It soft-fails to a treeless build, like the other
  optional inputs.
- **Semantic landcover from the 3D Basisvoorziening.** The optional `landcover`
  block emits the Dutch ground as classified, draped CityGML 2.0 features
  (`luse:LandUse`, `tran:Road`, `wtr:WaterBody`, `veg:PlantCover`, `brid:Bridge`,
  and `gen:GenericCityObject` for anything else), parsed from the 3DBV CityJSON
  product. Documented in `docs/mapping_city.md` § 13.
- **Multi-theme Appearance layer.** A `landcover` theme paints the ground by
  feature class from a natural map palette, a `buildingHighlight` theme contrasts
  an address extract's target Panden with their surroundings, and the
  `vegetation` theme now renders trees slightly transparent so a canopy does not
  fully occlude what is behind it.
- **`BuildExtent.clip_to_box`.** One flag that both the building clip and the
  3DBV ground clip read, so a rectangular viewport cuts both layers at the same
  edge and they cannot drift apart.
- Per-building and city-scale render images in the README.

### Changed

- A `gemeente` + `bbox` small-area build now clips its buildings to the box,
  matching the ground (previously the ground was cut to the box while the
  buildings stayed whole). A whole-gemeente run and a boundary-polygon AOI keep
  both layers un-cut; the boundary AOI takes its building edge from the polygon.
- Cross-tile tree de-duplication moved into CFTree (tile ownership plus a halo);
  the merge tool only clips and renumbers.
- The landcover feature taxonomy lives in one ordered registry in
  `landcover_class`; the appearance palette and the landcover count derive their
  class set from it, so a new ground class is one registry row.

### Fixed

- An opt-in landcover build no longer crashes on a 3DBV tile that is valid JSON
  but not a usable CityJSON document (a sidecar member, a truncated tile, or a
  future format change). The sheet is skipped, the build degrades to landcover-free
  with a warning, and the poisoned cache entry is evicted so the next run
  re-fetches a good one.
- `_unzip_cityjson` prefers a `*.city.json` member over a bare `*.json`, so a
  sidecar `metadata.json` is never handed to the parser.

### Known limitations

- A clipped extract is visual context, not an analysis-grade dataset: a building
  cut at the AOI box keeps its original 3DBAG volume, area, and height
  attributes, which then describe the uncut geometry.
- 3DBV tile discovery takes the latest-vintage covering sheets without following
  OGC index pagination (cap 100). This is ample for an address or small-area
  AOI, but would truncate a whole-municipality landcover fetch.

## [1.0.1] - 2026-06-12

### Added

- Minted Zenodo DOIs recorded in the citation metadata.

### Changed

- Hardened the HTTP cache and the city fetchers against partial failures; serve
  a warm EP-Online cache offline and read the real postcode column; coerce JSON
  booleans strictly rather than by truthiness.
- Declared every `uom` token once in `citygml_energy.units`; built the EP-Online
  label filter in `address_match` rather than the pipeline; moved the BAG usable
  area from the Building to its BuildingUnit; screened near-vertical facets out
  of solar-panel roof fitting; emitted CFTree generic attributes in sorted
  order; reused the pipeline boundary loader in the CFTree merge tool.

## [1.0.0] - 2026-06-09

- Initial public release: a per-building pipeline and a city-scale pipeline that
  both emit CityGML 2.0 extended with Energy ADE 3.0 (beta 8) from flat JSON
  input plus STEP or CityJSON geometry, with offline XSD validation.

[1.1.0]: https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator/releases/tag/v1.1.0
[1.0.1]: https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator/releases/tag/v1.0.1
[1.0.0]: https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator/releases/tag/v1.0.0
