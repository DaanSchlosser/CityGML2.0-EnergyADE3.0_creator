# Address pipeline: setup and usage

This guide sets up the address-driven extract pipeline ([README §4.5](../README.md#45-address-driven-extract)) on a machine that starts with nothing installed. The pipeline takes a free-text Dutch address and builds a CityGML 2.0 + Energy ADE 3.0 extract of a square area centred on it, with the queried buildings highlighted against their surroundings and, optionally, energy labels, LoD3 trees, and semantic landcover.

The setup is staged. Each stage adds one prerequisite, and stage 1 already produces a model:

| Stage | Adds | Needs |
| --- | --- | --- |
| 1. Basic extract | Buildings, addresses, highlight colours | Python 3.12 and this repo |
| 2. Energy labels | EP-Online label per dwelling | A free EP-Online API key |
| 3. Trees | LoD3 tree reconstructions from AHN LiDAR | Docker Desktop |

Landcover (roads, water, plant cover as draped ground surfaces) is part of stage 1 whenever the profile asks for it; the PDOK services behind it are public and need no setup.

## Stage 1: basic extract

Two tools are needed to start: git and [uv](https://docs.astral.sh/uv/). On Windows both install with winget (`winget install Git.Git`, then `winget install astral-sh.uv`); the uv site lists installers for other platforms. uv downloads the pinned Python 3.12 by itself, so no separate Python install is needed.

Clone the repository and install the environment:

```powershell
git clone https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator.git
cd CityGML2.0-EnergyADE3.0_creator
uv sync --all-extras
```

Or, with an existing Python 3.12+ install, use a plain venv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # PowerShell; on Linux or macOS: source .venv/bin/activate
python -m pip install -e ".[dev,city,city-fast]"
```

Then run an address. `--no-energy-labels` skips the EP-Online step so no API key is needed yet:

```powershell
uv run python examples/create_address.py --address "Langegracht 76 Leiden" --no-energy-labels
```

(Drop the `uv run` prefix in an activated venv; that holds for every command below.)

The run resolves the address through PDOK Locatieserver and the BAG, downloads the covering 3DBAG tiles, and writes `generated/langegracht-76-leiden_500m.gml`. The first run downloads tens to hundreds of megabytes depending on the extent; later runs read the same downloads from the cache in `.cache/citygml_energy_city`.

### Checking the result

The run ends with a line such as `Wrote <n> city objects to generated/langegracht-76-leiden_500m.gml`. Open that file in a CityGML viewer (for example the KITModelViewer) to see the square extract with the queried buildings in light yellow-orange against white surroundings. To check the file against the CityGML and Energy ADE schemas, run:

```powershell
uv run python tools/validate_xsd.py generated/langegracht-76-leiden_500m.gml
```

### Addresses and flags

The address may be a single house (`"Langegracht 76 Leiden"`), a house-number range (`"Annie Romeinsingel 72-152 Leiden"`), or several streets (`"Etta Palmstraat en Joke Smitstraat z.n. Leiden"`). Include the place name; without one, the query logs a warning and uses the geocoder's best match, which may be a same-named street in another town.

Settings other than the address come from a profile JSON, default [inputs/address/leiden_example.json](../inputs/address/leiden_example.json). Useful flags on top of it:

- `--extent 250` sets the square's side length in metres (50 to 5000; the example profile sets 500).
- `--output path\to\file.gml` names the output file yourself; otherwise it derives from the address and extent.
- `--profile inputs/address/annie-romeinsingel-72-152-leiden_400m.json` picks another profile, for example the tree-enabled one below.
- `--refresh` re-downloads instead of reading the cache (see "Caching and reuse").
- `-v` turns on debug logging.

Overridden values pass through the same validation as the profile file, so a bad `--extent` gets the same error message a hand-edited profile would.

## Stage 2: energy labels

The EP-Online step needs a personal API key. Request one for free from RVO at [ep-online.nl](https://www.ep-online.nl/) (choose the file-based delivery, "EP-Online bestanden opvragen"). Then put it in a `.env` file in the repository root:

```ini
EP_ONLINE_API_KEY=your_key_here
```

[.env.example](../.env.example) is a template with all recognised variables. With the key in place, drop `--no-energy-labels` and the extract adds each dwelling's registered energy label to the model. The label bundle is a one-time download of roughly 300 MB that is cached afterwards, so only the first labelled run is slow.

A rejected or expired key fails the run with a message naming the problem (`EP-online rejected the API key (HTTP 401)`); the run never silently continues without the labels it was asked for. `--no-energy-labels` remains available as the fallback.

## Stage 3: trees

Tree generation runs [CFTree](https://github.com/DaanSchlosser/CFTree), Noah Alting's LiDAR tree-reconstruction pipeline with a compiled C++ core (the linked fork publishes the prebuilt image). You do not build or clone it: CFTree's CI publishes a ready-made Docker image, and the creator launches it on demand.

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

To add trees to your own address, copy the 400 m profile, or add its `vegetation` block to another profile; running a profile with `--address` derives fresh output and tree files from that address, so runs for different addresses do not overwrite each other's results.

## Caching and reuse

Two caches make reruns fast, and both report their age:

- **HTTP cache** (`.cache/citygml_energy_city`). Every BAG, 3DBAG, EP-Online, and PDOK download is stored and reused; entries never expire. Each run logs one line with the cache's file count and oldest entry date. Pass `--refresh` to bypass it for one run; fresh downloads still fill the cache for later runs.
- **CFTree reuse manifest** (`.cache/cftree/data/<case>/.cftree_manifest.json`). A completed tree run records the area it covered, the buffer, the AHN version, the geometry-only mode, and the image's content digest. A later build for the same case reuses the result only when all of those match; an interrupted run, a changed area, or a re-pulled image regenerates instead of reusing stale trees.

Cached HTTP bodies are checked before use. A response that does not parse (an HTML maintenance page cached during an outage, a truncated download) is removed and downloaded again once, instead of failing every later run.

## When the build stops instead of continuing

Setup problems fail the build with a message naming the missing piece, so a misconfigured machine cannot quietly produce a reduced model. Runtime problems in optional inputs (a CFTree crash mid-run, a PDOK landcover outage) log a warning, and the build continues without that input.

| Message | Fix |
| --- | --- |
| `The city_builder workflow requires the optional 'city' extras` | `pip install -e .[city]`, or `uv sync --all-extras` |
| `could not geocode any anchor for ...` | Check the address spelling and include the place name |
| `0 buildings in the assembled model` (warning) | The extent covers no built-up area, or the address resolved somewhere unintended; check the query |
| `EP-online rejected the API key (HTTP 401)` | Check the key on ep-online.nl, or pass `--no-energy-labels` |
| `Tree generation with CFTREE_RUNNER=docker needs CFTREE_IMAGE` | Add the `CFTREE_IMAGE` line from stage 3 to `.env` |
| `Cannot run the docker CLI` | Install Docker Desktop (stage 3, step 1) |
| `The docker daemon is not reachable` | Start Docker Desktop and rerun |
| `'docker pull ...' failed` | Check the image reference for typos and your network; the image is public, no registry login is needed |
| `UNC path ... is not supported by the docker runner` | Work from a drive-letter path (`C:\...`), not a network share |
| `request to <host> failed` | A short outage at PDOK, 3DBAG, or EP-Online; retry after a moment |

## Known limitations

- **One build at a time per area.** Two concurrent builds that share a CFTree case or an output path interfere in the same work directories. Run them sequentially.
- **Street names containing numbers** (`Plein 1940-45`) can parse as a house-number range. Quote an explicit house number (`"Plein 1940-45 12 Rotterdam"`) or use a profile with the exact query when a name like this resolves wrongly.
- **Hand-supplied vegetation files are not checked.** A `vegetation.path` file without a generate manifest is assumed to cover the area of interest; nothing verifies it matches the extract's square.
- **A cut building keeps its 3DBAG attributes.** Area and volume attributes of a building cut at the box edge describe the whole building, not the cut part (see [ADR-0004](adr/0004-viewport-aois-clip-to-box.md)).
