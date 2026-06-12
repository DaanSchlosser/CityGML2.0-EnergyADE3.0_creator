"""Merge a CFTree case directory's per-tile CityJSONs into a single deduped file.

CFTree writes one ``trees_lod3.city.json`` per AHN sub-tile under
``data/<case>/tiles/<tile_id>/``. Two adjacent tiles can each reconstruct
the same physical tree from their own (overlapping) point cloud chunks,
so the city-build pipeline used to ingest tiles individually and then
namespace each tree's ``gml:id`` by ``tile_id`` to dodge xs:ID collisions.

This tool consolidates a CFTree case ahead of time:

1. Walk ``<case>/tiles/*/trees_lod3.city.json`` and parse every tree.
2. Drop trees whose centroid falls outside an AOI boundary polygon.
3. Cluster trees by 2D centroid proximity and keep one representative
   per cluster (the one with the most polygon faces, i.e. the most
   complete reconstruction).
4. Re-number the survivors with sequential ``T_<n>`` ids and write a
   single CityJSON 2.0 file that the city-build vegetation loader can
   ingest without further dedup.

Run it once per (CFTree case, AOI, AHN version) tuple — the output is
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
# Clip + dedupe
# ---------------------------------------------------------------------------


def _clip_to_boundary(trees: list[ParsedTree], boundary: Any) -> list[ParsedTree]:
    """Keep trees whose 2D centroid falls inside *boundary*."""
    from shapely import prepare
    from shapely.geometry import Point

    prepare(boundary)
    return [tree for tree in trees if boundary.contains(Point(tree.centroid[0], tree.centroid[1]))]


def _dedupe_by_centroid(
    trees: list[ParsedTree],
    threshold_m: float,
) -> list[ParsedTree]:
    """Greedy spatial dedup: cluster by centroid, keep most-detailed tree.

    "Most detailed" = highest polygon-face count, ties broken by lower
    gtid. Order-independent thanks to the upfront sort.

    O(n*k) where k is the number of already-kept trees in a square
    bucket; with a default bucket size = ``threshold_m`` the lookup is
    effectively O(1) per insertion.
    """
    if not trees:
        return []
    sorted_trees = sorted(
        trees, key=lambda t: (-len(t.polygons), int(t.gtid) if t.gtid.isdigit() else t.gtid)
    )

    bucket_size = max(threshold_m, 0.001)
    threshold_sq = threshold_m * threshold_m
    buckets: dict[tuple[int, int], list[ParsedTree]] = {}
    kept: list[ParsedTree] = []

    for tree in sorted_trees:
        cx, cy, _ = tree.centroid
        bx, by = int(cx // bucket_size), int(cy // bucket_size)
        is_dup = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in buckets.get((bx + dx, by + dy), ()):
                    ox, oy, _ = other.centroid
                    if (cx - ox) ** 2 + (cy - oy) ** 2 < threshold_sq:
                        is_dup = True
                        break
                if is_dup:
                    break
            if is_dup:
                break
        if not is_dup:
            kept.append(tree)
            buckets.setdefault((bx, by), []).append(tree)
    return kept


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
            "title": f"CFTree merged + clipped + deduped ({case_label})",
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


def _gather_tile_files(case_dir: Path, filename: str) -> list[Path]:
    """Find every ``tiles/*/<filename>`` under *case_dir*."""
    tiles_dir = case_dir / "tiles"
    if not tiles_dir.is_dir():
        raise FileNotFoundError(f"{case_dir} has no 'tiles' subdirectory; is this a CFTree case?")
    return sorted(tiles_dir.glob(f"*/{filename}"))


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
        default="trees_lod3.city.json",
        help="Filename to read in each tile dir (default: %(default)s)",
    )
    parser.add_argument(
        "--dedup-threshold-m",
        type=float,
        default=1.0,
        help="2D centroid distance below which two trees are duplicates (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    tile_paths = _gather_tile_files(args.case_dir, args.tree_filename)
    if not tile_paths:
        _LOG.error("No %s files found under %s/tiles/", args.tree_filename, args.case_dir)
        return 1
    _LOG.info("Found %d tile file(s) under %s", len(tile_paths), args.case_dir)

    boundary = load_boundary_polygon(BoundarySource(path=args.boundary))

    all_trees: list[ParsedTree] = []
    for tile_path in tile_paths:
        parsed = parse_cftree_tile_file(tile_path)
        all_trees.extend(parsed)
        _LOG.info("  %s: %d trees", tile_path.parent.name, len(parsed))
    _LOG.info("Parsed %d trees across %d tile(s)", len(all_trees), len(tile_paths))

    clipped = _clip_to_boundary(all_trees, boundary)
    _LOG.info("Inside-AOI: %d / %d trees", len(clipped), len(all_trees))

    deduped = _dedupe_by_centroid(clipped, threshold_m=args.dedup_threshold_m)
    _LOG.info(
        "After dedup (threshold=%.2f m): %d / %d trees",
        args.dedup_threshold_m,
        len(deduped),
        len(clipped),
    )

    _write_merged_cityjson(
        deduped,
        args.output,
        case_label=args.case_dir.name,
        boundary_label=args.boundary.name,
    )
    _LOG.info("Wrote %s (%d trees)", args.output, len(deduped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
