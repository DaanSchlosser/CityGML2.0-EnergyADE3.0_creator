"""Merge a CFTree case directory's per-tile CityJSONs into a single file.

CFTree writes one ``trees_lod3.city.json`` per AHN sub-tile under
``data/<case>/tiles/<tile_id>/``. CFTree assigns each physical tree to
exactly one tile (the tile whose non-overlapping core cell contains the
tree's centroid), so a tree that two overlapping tiles both reconstruct is
emitted by only one of them. The per-tile outputs therefore carry no
cross-tile duplicates and this tool does not deduplicate; it concatenates.

This tool consolidates a CFTree case ahead of time:

1. Walk ``<case>/tiles/*/trees_lod3.city.json`` and parse every tree.
2. Drop trees whose centroid falls outside an AOI boundary polygon. A tile
   reconstructs a halo past its core cell, so some trees land in the buffer
   ring outside the requested AOI; this clip removes them.
3. Re-number the trees with sequential ``T_<n>`` ids and write a single
   CityJSON 2.0 file that the city-build vegetation loader can ingest
   directly.

Run it once per (CFTree case, AOI, AHN version) tuple; the output is
checked into the repo so the CFTree directory itself can be detached
from the build.

Example:

    python tools/merge_cftree_tiles.py \\
        --case-dir ../CFTree/data/emmer_compascuum_grid2 \\
        --boundary inputs/boundaries/emmer-compascuum_small-area.geojson \\
        --output inputs/vegetation/emmer-compascuum_small-area_AHN6.city.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Make ``citygml_energy`` importable when the script is launched as
# ``python tools/merge_cftree_tiles.py`` without ``-e`` install or a
# manual PYTHONPATH (matches the bench/generate-* tools convention).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Pull the existing parser so the merge step uses the exact same
# dequantization rules the runtime loader does, and the pipeline's own
# boundary loader so the tool accepts exactly the boundary files the
# city build does (a private copy here once drifted and rejected every
# checked-in single-feature FeatureCollection).
from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.boundary import BoundarySource, load_boundary_polygon
from citygml_energy.city_builder.cityjson_trees_parse import (
    ParsedTree,
    parse_cftree_tile_file,
)

_LOG = logging.getLogger("merge_cftree_tiles")


# ---------------------------------------------------------------------------
# Clip
# ---------------------------------------------------------------------------


def _clip_to_boundary(trees: list[ParsedTree], boundary: Any) -> list[ParsedTree]:
    """Keep trees whose 2D centroid falls inside *boundary*."""
    from shapely import prepare
    from shapely.geometry import Point

    prepare(boundary)
    return [tree for tree in trees if boundary.contains(Point(tree.centroid[0], tree.centroid[1]))]


# ---------------------------------------------------------------------------
# CityJSON writer
# ---------------------------------------------------------------------------


_QUANT_SCALE: float = 0.001  # millimetre quantization, same as CFTree


def _flatten_vertices(polygons: list[GeometryPolygon]) -> list[tuple[float, float, float]]:
    """All vertices across exterior + interior rings (without closing dup)."""
    out: list[tuple[float, float, float]] = []
    for poly in polygons:
        # GeometryPolygon stores rings with first==last (GML convention);
        # drop the closing duplicate before re-encoding to CityJSON.
        ext = (
            poly.exterior[:-1]
            if len(poly.exterior) >= 2 and poly.exterior[0] == poly.exterior[-1]
            else list(poly.exterior)
        )
        out.extend(ext)
        for ring in poly.interiors:
            ints = ring[:-1] if len(ring) >= 2 and ring[0] == ring[-1] else list(ring)
            out.extend(ints)
    return out


def _write_merged_cityjson(
    trees: list[ParsedTree],
    output_path: Path,
    *,
    case_label: str,
    boundary_label: str,
) -> None:
    if not trees:
        # Even an empty case still gets a parseable file so a downstream
        # config pointing at it doesn't crash with FileNotFoundError.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "type": "CityJSON",
                    "version": "2.0",
                    "transform": {
                        "scale": [_QUANT_SCALE] * 3,
                        "translate": [0.0, 0.0, 0.0],
                    },
                    "metadata": {
                        "referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/28992",
                        "presentLoDs": [3.0],
                    },
                    "CityObjects": {},
                    "vertices": [],
                },
            ),
            encoding="utf-8",
        )
        return

    # Shared origin = component-wise min over every kept vertex. This is
    # the same convention CFTree uses per-tile, just applied across the
    # whole merged set.
    all_pts: list[tuple[float, float, float]] = []
    for tree in trees:
        all_pts.extend(_flatten_vertices(tree.polygons))
    tx = min(p[0] for p in all_pts)
    ty = min(p[1] for p in all_pts)
    tz = min(p[2] for p in all_pts)

    vertices: list[list[int]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}

    def add_vertex(pt: tuple[float, float, float]) -> int:
        qx = round((pt[0] - tx) / _QUANT_SCALE)
        qy = round((pt[1] - ty) / _QUANT_SCALE)
        qz = round((pt[2] - tz) / _QUANT_SCALE)
        key = (qx, qy, qz)
        idx = vertex_index.get(key)
        if idx is None:
            idx = len(vertices)
            vertices.append([qx, qy, qz])
            vertex_index[key] = idx
        return idx

    city_objects: dict[str, dict[str, Any]] = {}
    for new_idx, tree in enumerate(trees, start=1):
        # CityJSON 2.0 Solid: boundaries = [shell], shell = [surface],
        # surface = [exterior_ring, *interior_rings].
        shell: list[list[list[int]]] = []
        for poly in tree.polygons:
            ext_pts = (
                poly.exterior[:-1]
                if len(poly.exterior) >= 2 and poly.exterior[0] == poly.exterior[-1]
                else list(poly.exterior)
            )
            ext_indices = [add_vertex(pt) for pt in ext_pts]
            surface: list[list[int]] = [ext_indices]
            for ring in poly.interiors:
                int_pts = ring[:-1] if len(ring) >= 2 and ring[0] == ring[-1] else list(ring)
                surface.append([add_vertex(pt) for pt in int_pts])
            shell.append(surface)

        attrs: dict[str, Any] = dict(tree.attributes)
        # Trace back to the source so a curious user can grep the
        # original CFTree case for a given gml:id.
        attrs["original_gtid"] = tree.gtid
        # tile_id no longer makes sense in a merged file — drop it so a
        # future builder doesn't accidentally namespace by it again.
        attrs.pop("tile_id", None)
        # Overwrite the CFTree gtid attribute with the new sequential one
        # so it stays in sync with the CityObject id.
        attrs["gtid"] = new_idx

        city_objects[f"T_{new_idx}"] = {
            "type": "SolitaryVegetationObject",
            "geometry": [
                {
                    "type": "Solid",
                    "lod": 3.0,
                    "boundaries": [shell],
                },
            ],
            "attributes": attrs,
        }

    abs_xs = [p[0] for p in all_pts]
    abs_ys = [p[1] for p in all_pts]
    abs_zs = [p[2] for p in all_pts]

    payload = {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {
            "scale": [_QUANT_SCALE] * 3,
            "translate": [tx, ty, tz],
        },
        "metadata": {
            "referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/28992",
            "geographicalExtent": [
                min(abs_xs),
                min(abs_ys),
                min(abs_zs),
                max(abs_xs),
                max(abs_ys),
                max(abs_zs),
            ],
            "presentLoDs": [3.0],
            "title": f"CFTree merged + clipped ({case_label})",
            "identifier": case_label,
            "extensions": {
                "merge_provenance": {
                    "case": case_label,
                    "boundary": boundary_label,
                },
            },
        },
        "CityObjects": city_objects,
        "vertices": vertices,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


# Default per-tile output filename CFTree writes; the single source of
# truth for both the CLI's ``--tree-filename`` default and the on-demand
# runner's tile glob (citygml_energy.city_builder.cftree_runner imports
# this so the two never drift out of sync).
TILE_FILENAME = "trees_lod3.city.json"


def _gather_tile_files(case_dir: Path, filename: str) -> list[Path]:
    """Find every ``tiles/*/<filename>`` under *case_dir*."""
    tiles_dir = case_dir / "tiles"
    if not tiles_dir.is_dir():
        raise FileNotFoundError(f"{case_dir} has no 'tiles' subdirectory; is this a CFTree case?")
    return sorted(tiles_dir.glob(f"*/{filename}"))


def merge_case(
    case_dir: Path,
    boundary_path: Path,
    output_path: Path,
    *,
    tree_filename: str = TILE_FILENAME,
) -> int:
    """Merge one CFTree case's per-tile CityJSONs into a single file.

    Walks ``<case_dir>/tiles/*/<tree_filename>``, clips to the AOI in
    *boundary_path*, and writes the merged CityJSON 2.0 to *output_path*.
    Returns the number of trees written. The tiles carry no cross-tile
    duplicates (CFTree assigns each tree to one owning tile), so there is no
    dedup step here; the clip only removes trees in the halo ring outside the
    requested AOI.

    This is the importable core the CLI :func:`main` wraps and the
    on-demand runner
    (:func:`citygml_energy.city_builder.cftree_runner.ensure_tree_file`)
    calls in-process, so the clip / re-numbering rules live in one place.
    Raises :class:`FileNotFoundError` when the case has no tiles to merge
    (no ``tiles`` directory, or no matching per-tile files).
    """
    tile_paths = _gather_tile_files(case_dir, tree_filename)
    if not tile_paths:
        raise FileNotFoundError(f"No {tree_filename} files found under {case_dir}/tiles/")
    _LOG.info("Found %d tile file(s) under %s", len(tile_paths), case_dir)

    boundary = load_boundary_polygon(BoundarySource(path=boundary_path))

    all_trees: list[ParsedTree] = []
    for tile_path in tile_paths:
        parsed = parse_cftree_tile_file(tile_path)
        all_trees.extend(parsed)
        _LOG.info("  %s: %d trees", tile_path.parent.name, len(parsed))
    _LOG.info("Parsed %d trees across %d tile(s)", len(all_trees), len(tile_paths))

    clipped = _clip_to_boundary(all_trees, boundary)
    _LOG.info("Inside-AOI: %d / %d trees", len(clipped), len(all_trees))

    _write_merged_cityjson(
        clipped,
        output_path,
        case_label=case_dir.name,
        boundary_label=boundary_path.name,
    )
    _LOG.info("Wrote %s (%d trees)", output_path, len(clipped))
    return len(clipped)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--case-dir",
        required=True,
        type=Path,
        help="CFTree case directory (contains tiles/<tile_id>/...)",
    )
    parser.add_argument(
        "--boundary",
        required=True,
        type=Path,
        help=(
            "GeoJSON (Multi)Polygon in EPSG:28992: a Feature or a "
            "single-feature FeatureCollection (QGIS default export)"
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination .city.json path",
    )
    parser.add_argument(
        "--tree-filename",
        default=TILE_FILENAME,
        help="Filename to read in each tile dir (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    try:
        merge_case(
            args.case_dir,
            args.boundary,
            args.output,
            tree_filename=args.tree_filename,
        )
    except FileNotFoundError as exc:
        _LOG.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
