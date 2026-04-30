# Inputs

All inputs to the two pipelines live here, grouped by purpose.

| Folder | Contents | Pipeline |
|---|---|---|
| [`buildings/`](buildings/) | Per-building feature-collection JSONs (`schema_version: 2`) | Per-building ([`examples/create_building.py`](../examples/create_building.py)) |
| [`stp/`](stp/) | STEP geometry files referenced by the building JSONs | Per-building |
| [`cities/`](cities/) | City-scale configs (`schema_version: "city-1"`) | City-scale ([`examples/create_city.py`](../examples/create_city.py)) |
| [`boundaries/`](boundaries/) | GeoJSON AOI polygons used as `boundary` inputs by city configs | City-scale |
| [`pv_panels/`](pv_panels/) | PV-panel polygon dataset for Emmer-Compascuum | City-scale (optional `pv_panels` block) |

Each subfolder has its own `README.md` describing the files in detail.

## Quick start

Per-building (default reads [`buildings/owner_occupier_building.json`](buildings/owner_occupier_building.json)):

```powershell
python examples/create_building.py
```

City-scale (default reads [`cities/emmer-compascuum_small-area.json`](cities/emmer-compascuum_small-area.json)):

```powershell
python examples/create_city.py
```

Override either default with `--input <path-to-json>`.

## Path conventions

- Relative paths in a JSON config are resolved against the **config file's own directory**. So a city config in `cities/foo.json` reaches the boundaries folder via `../boundaries/...`, the PV panels folder via `../pv_panels/...`, and the repo root via `../../`.
- All geographic data uses EPSG:28992 (Amersfoort / RD New).
