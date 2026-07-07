# Address pipeline: setup and usage

This guide sets up the address-driven extract pipeline ([README §4.5](../README.md#45-address-driven-extract)) on a machine that starts with nothing installed. The pipeline takes a free-text Dutch address and builds a CityGML 2.0 + Energy ADE 3.0 extract of a square area centred on it, with the queried buildings highlighted against their surroundings and, optionally, energy labels, LoD3 trees, and semantic landcover.

The setup is staged so the first result comes fast. Each stage adds one prerequisite:

| Stage | Adds | Needs |
| --- | --- | --- |
| 1. Basic extract | Buildings, addresses, highlight colours | Python 3.12 and this repo |
| 2. Energy labels | EP-Online label per dwelling | A free EP-Online API key |
| 3. Trees | LoD3 tree reconstructions from AHN LiDAR | Docker Desktop |

Landcover (roads, water, plant cover as draped ground surfaces) rides along with stage 1 whenever the profile asks for it; the PDOK services behind it are public and need no setup.

## Stage 1: basic extract

Clone the repository and install the environment. With [uv](https://docs.astral.sh/uv/) (recommended, pins Python 3.12 and the whole dependency graph):

```powershell
git clone https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator.git
cd CityGML2.0-EnergyADE3.0_creator
uv sync --all-extras
```

Or with a plain venv (Python 3.12+):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,city,city-fast]"
```

Then run an address. `--no-energy-labels` skips the EP-Online step so no API key is needed yet:

```powershell
uv run python examples/create_address.py --address "Langegracht 76 Leiden" --no-energy-labels
```

(Drop the `uv run` prefix in an activated venv; that holds for every command below.)

The run resolves the address through PDOK Locatieserver and the BAG, downloads the covering 3DBAG tiles, and writes `generated/langegracht-76-leiden_500m.gml`. The first run downloads tens to hundreds of megabytes depending on the extent; later runs serve the same downloads from the cache in `.cache/citygml_energy_city`.

The address may be a single house (`"Langegracht 76 Leiden"`), a house-number range (`"Annie Romeinsingel 72-152 Leiden"`), or several streets (`"Etta Palmstraat en Joke Smitstraat z.n. Leiden"`). Include the place name; without one, the query logs a warning and takes the geocoder's best hit, which may be a same-named street in another town.

Settings other than the address come from a profile JSON, default [inputs/address/leiden_example.json](../inputs/address/leiden_example.json). Useful flags on top of it:

- `--extent 250` sets the square's side length in metres (default from the profile, 500 in the example profile).
- `--output path\to\file.gml` names the output file yourself; otherwise it derives from the address and extent.
- `--profile inputs/address/annie-romeinsingel-72-152-leiden_400m.json` picks another profile, for example the tree-enabled one below.
- `--refresh` re-downloads instead of serving the cache (see "Caching and reuse").
- `-v` turns on debug logging.

Overridden values pass through the same validation as the profile file, so a bad `--extent` gets the same error message a hand-edited profile would.

## Stage 2: energy labels

The EP-Online step needs a personal API key. Request one for free from RVO at [ep-online.nl](https://www.ep-online.nl/) (choose the file-based delivery, "EP-Online bestanden opvragen"). Then put it in a `.env` file in the repository root:

```ini
EP_ONLINE_API_KEY=your_key_here
```

[.env.example](../.env.example) is a template with all recognised variables. With the key in place, drop `--no-energy-labels` and the extract paints each dwelling's registered energy label into the model. The label bundle is a one-time download of roughly 300 MB that is cached afterwards, so only the first labelled run is slow.

A rejected or expired key fails the run with a message naming the problem (`EP-online rejected the API key (HTTP 401)`); the run never silently continues without the labels it was asked for. `--no-energy-labels` is always available as the escape hatch.

## Stage 3: trees

Tree generation runs [CFTree](https://github.com/DaanSchlosser/CFTree), a LiDAR reconstruction pipeline with a compiled C++ core. You do not build or clone it: CFTree's CI publishes a ready-made Docker image, and the creator launches it on demand.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it. The default settings work; no WSL distro or Linux knowledge is needed.
2. Add one line to `.env`:

   ```ini
   CFTREE_IMAGE=ghcr.io/daanschlosser/cftree:latest
   ```

3. Run the tree-enabled profile:

   ```powershell
   uv run python examples/create_address.py --profile inputs/address/annie-romeinsingel-72-152-leiden_400m.json --no-energy-labels
   ```

The first run pulls the image (a one-time download, about 7 GB unpacked), downloads the AHN LiDAR for the area, and reconstructs the trees; for the 400 m example this takes a few minutes. The reconstruction is cached (see below), so rerunning the same area is fast. CFTree's working files live under `.cache/cftree` in this repo; set `CFTREE_WORKDIR` in `.env` to relocate them.

The docker runner is the default on Windows. On Linux or macOS, set `CFTREE_RUNNER=docker` in `.env` to opt in; the other runners (`wsl`, `native`) run CFTree from a local checkout and exist for CFTree development, see [.env.example](../.env.example).

To add trees to your own address, copy the 400 m profile, or add its `vegetation` block to another profile; running a profile with `--address` derives fresh output and tree files from that address, so profiles never clobber each other's results.

## Caching and reuse

Two caches make reruns fast, and both tell you when they are stale:

- **HTTP cache** (`.cache/citygml_energy_city`). Every BAG, 3DBAG, EP-Online, and PDOK download is kept and served forever; entries never expire. Each run logs one line with the cache's file count and oldest entry date. Pass `--refresh` to bypass it for one run; fresh downloads still land in the cache for the runs after.
- **CFTree reuse manifest** (`.cache/cftree/data/<case>/.cftree_manifest.json`). A completed tree run records its AOI, buffer, AHN version, geometry-only mode, and the image's content digest. A later build for the same case reuses the result only when all of those match; an interrupted run, a changed AOI, or a re-pulled image regenerates instead of serving stale trees.

Cached HTTP bodies are checked before use. A response that does not parse (an HTML maintenance page cached during an outage, a truncated download) is evicted and refetched once instead of crashing every later run.

## When the build stops instead of continuing

Setup problems fail the build with a message naming the missing piece; the build never quietly degrades because a machine is misconfigured. Runtime problems in optional inputs (a CFTree crash mid-run, a PDOK landcover outage) log a warning and continue without that input.

| Message | Fix |
| --- | --- |
| `The city_builder workflow requires the optional 'city' extras` | `pip install -e .[city]`, or `uv sync --all-extras` |
| `could not geocode any anchor for ...` | Check the address spelling and include the place name |
| `0 buildings in the assembled model` (warning) | The extent covers no built-up area, or the address resolved somewhere unintended; check the query |
| `EP-online rejected the API key (HTTP 401)` | Check the key on ep-online.nl, or pass `--no-energy-labels` |
| `Tree generation with CFTREE_RUNNER=docker needs CFTREE_IMAGE` | Add the `CFTREE_IMAGE` line from stage 3 to `.env` |
| `The docker daemon is not reachable` | Start Docker Desktop and rerun |
| `'docker pull ...' failed` | Check the image reference for typos and your network; the image is public, no registry login is needed |
| `UNC path ... is not supported by the docker runner` | Work from a drive-letter path (`C:\...`), not a network share |
| `request to <host> failed` | A PDOK / 3DBAG / EP-Online hiccup; these are usually brief, retry |

## Known limitations

- **One build at a time per area.** Two concurrent builds that share a CFTree case or an output path race on the same work directories. Run them sequentially.
- **Street names containing numbers** (`Plein 1940-45`) can parse as a house-number range. Quote an explicit house number (`"Plein 1940-45 12 Rotterdam"`) or use a profile with the exact query when a name like this misresolves.
- **Hand-supplied vegetation files are trusted as-is.** A `vegetation.path` file without a generate manifest is assumed to cover the AOI; nothing verifies it matches the extract's square.
- **A cut building keeps its 3DBAG attributes.** Area and volume attributes of a building cut at the box edge describe the whole building, not the cut part (see [ADR-0004](adr/0004-viewport-aois-clip-to-box.md)).
