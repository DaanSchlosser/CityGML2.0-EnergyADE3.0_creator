# Address-driven extract profiles

Profiles for the city-scale pipeline's address extent ([`examples/create_address.py`](../../examples/create_address.py)). Each is a city config whose extent comes from a free-text Dutch address rather than a `municipality` (+ `bbox` / `boundary`): the address is geocoded through PDOK Locatieserver for a coarse anchor and resolved against authoritative BAG for the exact building match, a square `extent_m` box is centred on the matched buildings, and those buildings are painted distinctly from their surroundings. See [§4.5 of the root README](../../README.md#45-address-driven-extract).

## Files

| File | Address | Extent | Vegetation |
|---|---|---|---|
| `leiden_example.json` | Annie Romeinsingel 72-152, Leiden | 500 m square | none |
| `leiden_250.json` | Annie Romeinsingel 72-152, Leiden | 250 m square | on-demand CFTree (AHN5, geometry-only) |

`leiden_example.json` is the default profile. `leiden_250.json` adds a `vegetation.generate` block, so LoD3 trees are reconstructed on demand by CFTree when the merged file is missing (see [§4.6 of the root README](../../README.md#46-on-demand-tree-generation)); it points at [`../vegetation/leiden_250.city.json`](../vegetation/leiden_250.city.json), which is checked in, so a normal run reuses it without launching CFTree.

## The `address` block

| Key | Required | Default | Meaning |
|---|---|---|---|
| `query` | yes | - | Free-text Dutch address. A single house, a house-number range (`72-152`), or several streets joined by `en`, optionally `z.n.` (*zonder nummer*) for a whole street. |
| `extent_m` | no | 500 | Side length of the square fetch extent in metres (50-5000), centred on the matched buildings. |
| `target_color` | no | `[0.98, 0.78, 0.42]` | RGB in `[0, 1]` for the matched buildings (light yellow-orange). |
| `surroundings_color` | no | `[1.0, 1.0, 1.0]` | RGB in `[0, 1]` for everything around them (white). |

The `address` block is mutually exclusive with `bbox` and `boundary`, and makes `municipality` optional (the gemeente is derived from the geocode). The `--address`, `--extent`, and `--output` command-line flags override the profile, so one profile serves any address.

## Path conventions

Relative paths in a profile are resolved against the profile's own directory, as for the [city configs](../cities/README.md): `../vegetation/...`, `../../generated/<name>.gml`, `../../.cache/...`. All geographic data uses EPSG:28992 (Amersfoort / RD New).
