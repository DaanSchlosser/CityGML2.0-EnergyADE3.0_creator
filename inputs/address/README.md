# Address-driven extract profiles

Profiles for the city-scale pipeline's address extent ([`examples/create_address.py`](../../examples/create_address.py)). Each is a city config whose extent comes from a free-text Dutch address rather than a `municipality` (+ `bbox` / `boundary`): the address is geocoded through PDOK Locatieserver for a coarse anchor and resolved against authoritative BAG for the exact building match, a square `extent_m` box is centred on the matched buildings, and those buildings are coloured differently from their surroundings. See [§4.5 of the root README](../../README.md#45-address-driven-extract).

## Files

| File | Address | Extent | Vegetation |
|---|---|---|---|
| `delft_example.json` | Julianalaan 134, Delft (TU Delft Faculty of Architecture) | 500 m square | none |
| `annie-romeinsingel-72-152-leiden_400m.json` | Annie Romeinsingel 72-152, Leiden | 400 m square | on-demand CFTree (AHN5, geometry-only) |

`delft_example.json` is the default profile. `annie-romeinsingel-72-152-leiden_400m.json` adds a `vegetation.generate` block, so LoD3 trees are reconstructed on demand by CFTree when the merged file is missing (see [§4.6 of the root README](../../README.md#46-on-demand-tree-generation)); it points at [`../vegetation/annie-romeinsingel-72-152-leiden_400m.city.json`](../vegetation/annie-romeinsingel-72-152-leiden_400m.city.json), which is checked in, so a normal run reuses it without launching CFTree. Running it with `--address "<other address>"` derives a fresh output file and tree file from that address, so one profile serves several squares (the slug is the address lower-cased, with every run of characters other than letters and digits replaced by a hyphen, plus the square size). Unlike `delft_example.json` (which builds LoD0, LoD1, and LoD2), this 400 m profile builds LoD2 only and enables the `landcover` block (which takes no further settings), so the 3D Basisvoorziening semantic ground is emitted alongside the buildings.

## The `address` block

| Key | Required | Default | Meaning |
|---|---|---|---|
| `query` | yes | - | Free-text Dutch address. A single house, a house-number range (`72-152`), or several streets joined by `en`, optionally `z.n.` (*zonder nummer*) for a whole street. |
| `extent_m` | no | 500 | Side length of the square fetch extent in metres (50-5000), centred on the matched buildings. |
| `target_color` | no | `[0.98, 0.78, 0.42]` | RGB in `[0, 1]` for the matched buildings (light yellow-orange). |
| `surroundings_color` | no | `[1.0, 1.0, 1.0]` | RGB in `[0, 1]` for everything around them (white). |

The `address` block is mutually exclusive with `bbox` and `boundary`, and makes `municipality` optional (the gemeente is derived from the geocode). The `--address`, `--extent`, and `--output` command-line flags override the profile, so one profile serves any address; overridden values pass through the same validation as the profile file.

Both profiles request EP-Online energy labels (`include_energy_labels: true`), which needs an API key in `.env`. Pass `--no-energy-labels` to run them without one, and `--refresh` to re-download instead of serving the HTTP cache. [docs/address-pipeline.md](../../docs/address-pipeline.md) is the full setup guide, including the Docker-based tree generation.

## Path conventions

Relative paths in a profile are resolved against the profile's own directory, as for the [city configs](../cities/README.md): `../vegetation/...`, `../../generated/<name>.gml`, `../../.cache/...`. All geographic data uses EPSG:28992 (Amersfoort / RD New).
