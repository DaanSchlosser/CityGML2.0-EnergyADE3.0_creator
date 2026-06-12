"""Top-level city-build orchestrator.

:func:`build_city_model` wires the fetchers, CityJSON parser, address
matcher, and xsdata builders into a single :class:`CityModel` ready for
serialization. :func:`build_city_gml_file` is a convenience that writes
the result to :attr:`CityBuildConfig.output_path`.

Network calls are delegated to :class:`CachedSession` through the
fetchers; tests inject a pre-populated cache dir or monkeypatch
``session.session`` so they never hit the wire.

Progress messages are emitted through the stdlib ``logging`` module
(logger name ``citygml_energy.city_builder.pipeline``) at INFO level.
CLIs configure a handler; library callers can silence with standard
``logging.getLogger("citygml_energy").setLevel(WARNING)``.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._step import Coord3D
from ..core import CityModel
from ..gml_builders import build_envelope
from . import pand_executor
from . import postcode6 as postcode6_step
from . import solar_panels as solar_panels_module
from . import vegetation as vegetation_module
from .address_match import LabelFilter, ResolvedAddress, match_addresses, wanted_label_filter
from .appearance import (
    append_energy_label_appearance,
    append_solar_panel_appearance,
    append_vegetation_appearance,
)
from .boundary import load_boundary_polygon
from .cityjson_parse import ParsedBuilding, SemanticPolygon
from .config import CityBuildConfig, CityBuildError, load_city_config
from .fetchers import bag as bag_fetchers
from .fetchers import eponline as eponline_fetchers
from .fetchers import municipality as muni_fetchers
from .fetchers import threedbag
from .http import CachedSession
from .postcode6 import Postcode6Area
from .solar_panels import ProjectedPanel
from .vegetation import TreeBundle

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry


_LOG = logging.getLogger(__name__)

PathLike = str | Path


def build_city_gml_file(config_path: PathLike) -> CityModel:
    """Load *config_path*, build the CityModel, and write the GML."""
    config = load_city_config(config_path)
    model = build_city_model(config)
    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(output_path)
    return model


def build_city_model(
    config: CityBuildConfig,
    *,
    session: CachedSession | None = None,
) -> CityModel:
    """Build a :class:`CityModel` from *config*.

    When *session* is omitted a fresh :class:`CachedSession` rooted at
    ``config.cache_dir`` is used. Tests inject a pre-built session (or
    one with ``use_cache=False``) to control HTTP behaviour.
    """
    if session is None:
        session = CachedSession(cache_dir=config.cache_dir)

    boundary_geom = _maybe_load_boundary(config)

    _LOG.info("Fetching municipality outline: %s", config.municipality)
    outline = muni_fetchers.fetch_municipality_outline(session, name=config.municipality)
    bbox = _resolve_bbox(config, outline=outline, boundary_geom=boundary_geom)
    cbs_code = outline.cbs_code or None
    _LOG.info("CBS code: %r  bbox: %s", cbs_code, bbox)

    # BAG panden, BAG VBOs (optional), 3DBAG tiles, and CBS Postcode6
    # statistics (optional) are all I/O-bound network fetches that
    # depend only on bbox. Running them concurrently converts N serial
    # waits into one, cutting cold-cache wall time by roughly the
    # duration of the slowest fetches. The shared CachedSession is
    # safe here: its underlying urllib3 connection pool is thread-safe
    # for read-only GETs, and each fetcher's cache writes land under a
    # disjoint cache-key prefix so there is no shared-file race.
    _LOG.info("Fetching BAG panden, VBOs, 3DBAG tiles, and CBS Postcode6 concurrently …")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fut_panden = pool.submit(bag_fetchers.fetch_panden, session, bbox=bbox, cbs_code=cbs_code)
        fut_vbos = (
            pool.submit(bag_fetchers.fetch_verblijfsobjecten, session, bbox=bbox, cbs_code=cbs_code)
            if config.include_addresses
            else None
        )
        fut_3dbag = pool.submit(_fetch_parsed_buildings, session, outline=outline, bbox=bbox)
        fut_cbs = (
            pool.submit(
                postcode6_step.safely_fetch_postcode6_areas,
                session,
                source=config.cbs_postcode6_source,
                bbox=bbox,
            )
            if config.cbs_postcode6_source is not None
            else None
        )

    # The ThreadPoolExecutor's __exit__ already waited for every submitted
    # future, so each .result() either returns immediately or re-raises
    # the worker's exception. Calling .result() outside the with block
    # (rather than inline among the submits) keeps the submission and
    # collection phases visually distinct.
    panden = fut_panden.result()
    vbos = fut_vbos.result() if fut_vbos is not None else []
    parsed_buildings = fut_3dbag.result()
    postcode6_areas = fut_cbs.result() if fut_cbs is not None else []

    known_pand_ids = {pand.identificatie for pand in panden}
    _LOG.info("%d panden", len(panden))

    resolved_per_pand: dict[str, list[ResolvedAddress]] = {}
    if config.include_addresses:
        _LOG.info("%d verblijfsobjecten", len(vbos))

        energy_labels = _maybe_fetch_energy_labels(session, config, vbos=vbos)
        if energy_labels is not None:
            _LOG.info("%d EP-online labels matched", len(energy_labels))

        resolved_per_pand = match_addresses(
            vbos=vbos,
            energy_labels=energy_labels,
        )
        matched_vbos = sum(len(v) for v in resolved_per_pand.values())
        _LOG.info("%d VBOs matched to %d panden", matched_vbos, len(resolved_per_pand))

    parsed_by_id = {pb.pand_id: pb for pb in parsed_buildings if pb.pand_id in known_pand_ids}
    _LOG.info(
        "%d buildings from 3DBAG tiles; %d match known BAG panden",
        len(parsed_buildings),
        len(parsed_by_id),
    )
    skipped = len(panden) - len(parsed_by_id)
    if skipped:
        _LOG.info("%d panden have no 3DBAG geometry (skipped)", skipped)

    if boundary_geom is not None:
        before = len(parsed_by_id)
        parsed_by_id = filter_buildings_by_boundary(parsed_by_id, boundary_geom)
        dropped = before - len(parsed_by_id)
        kept_ids = set(parsed_by_id)
        panden = [p for p in panden if p.identificatie in kept_ids]
        _LOG.info(
            "Boundary polygon kept %d / %d buildings (%d outside)",
            len(parsed_by_id),
            before,
            dropped,
        )

    solar_matches_per_pand = _maybe_match_solar_panels(
        config=config,
        bbox=bbox,
        parsed_by_id=parsed_by_id,
    )

    tree_bundle = vegetation_module.fetch_and_match_trees(
        session,
        source=config.vegetation_source,
        bbox=bbox,
        boundary_geom=boundary_geom,
    )

    _LOG.info("Assembling CityModel …")
    model = _assemble_city_model(
        config=config,
        panden=panden,
        parsed_by_id=parsed_by_id,
        resolved_per_pand=resolved_per_pand,
        solar_matches_per_pand=solar_matches_per_pand,
        tree_bundle=tree_bundle,
        postcode6_areas=postcode6_areas,
        boundary_geom=boundary_geom,
    )
    building_count = sum(1 for m in model.xsd.city_object_member if m.building is not None)
    vegetation_count = sum(
        1 for m in model.xsd.city_object_member if m.solitary_vegetation_object is not None
    )
    postcode_count = sum(
        1 for m in model.xsd.city_object_member if m.urban_function_area is not None
    )
    _LOG.info(
        "Done: %d buildings + %d trees + %d postcode areas in model",
        building_count,
        vegetation_count,
        postcode_count,
    )
    return model


def _maybe_match_solar_panels(
    *,
    config: CityBuildConfig,
    bbox: tuple[float, float, float, float],
    parsed_by_id: dict[str, ParsedBuilding],
) -> dict[str, list[ProjectedPanel]]:
    """Load + match + project solar panels once in the main process.

    Empty dict when no solar-panel source is configured, when LoD 2 is disabled
    (there is nothing to attach to), or when no panels fall inside the
    bbox.
    """
    source = config.solar_panels_source
    if source is None:
        return {}
    if 2 not in config.lods:
        _LOG.warning("solar_panels configured but LoD 2 is disabled; skipping solar attach")
        return {}

    _LOG.info("Loading solar panels: %s (%s)", source.path.name, source.layer)
    panels = solar_panels_module.load_panels_in_bbox(source, bbox)
    if not panels:
        _LOG.info("Solar panels: 0 polygons inside bbox; skipping")
        return {}

    matches, skipped = solar_panels_module.match_and_project_panels(
        panels=panels,
        parsed_buildings=parsed_by_id.values(),
        z_offset_m=source.z_offset_m,
    )
    total = sum(len(v) for v in matches.values())
    _LOG.info(
        "Solar panels: %d projected onto %d buildings (%d skipped, no LoD 2 roof overlap)",
        total,
        len(matches),
        skipped,
    )
    return matches


# ---------------------------------------------------------------------------
# Sub-step helpers
# ---------------------------------------------------------------------------


def _maybe_load_boundary(config: CityBuildConfig) -> BaseGeometry | None:
    """Load the configured boundary polygon once, or return ``None``."""
    source = config.boundary_source
    if source is None:
        return None
    _LOG.info("Loading boundary polygon: %s", source.path.name)
    return load_boundary_polygon(source)


def _resolve_bbox(
    config: CityBuildConfig,
    *,
    outline: muni_fetchers.MunicipalityOutline,
    boundary_geom: BaseGeometry | None,
) -> tuple[float, float, float, float]:
    """Return the fetch bbox, preferring the boundary polygon when set.

    Resolution order, in plain words:

    * If a boundary polygon is set, take its 2D bounds. The pipeline
      later clips builds to the (concave) polygon itself, so this bbox
      is just the rectangular fetch envelope.
    * Else, fall back to the user-supplied ``bbox`` from the config.
    * Else, use the municipality outline's own bbox.
    """
    if boundary_geom is not None:
        minx, miny, maxx, maxy = boundary_geom.bounds
        return (float(minx), float(miny), float(maxx), float(maxy))
    if config.bbox is not None:
        return config.bbox
    return outline.bbox


def filter_buildings_by_boundary(
    parsed_by_id: dict[str, ParsedBuilding],
    boundary_geom: BaseGeometry,
) -> dict[str, ParsedBuilding]:
    """Keep only buildings whose 2D LoD 0 footprint intersects *boundary_geom*.

    Rule: "any overlap": a building is kept if any part of its LoD 0
    footprint polygon intersects the (possibly concave) boundary. This
    matches the user's intent of drawing a cut-line: buildings straddling
    the edge land on whichever side hosts most of their footprint, and
    we prefer keeping them over cutting them in half.

    Buildings without a LoD 0 polygon (shouldn't happen for 3DBAG, but
    defensively handled) are silently dropped, as are buildings whose
    LoD 0 rings collapse to a degenerate footprint.
    """
    try:
        from shapely import prepare
        from shapely.geometry import Polygon as ShapelyPolygon
        from shapely.ops import unary_union
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "Boundary filtering needs shapely; install with: pip install -e .[city]"
        ) from exc

    # ``prepare`` builds a cached PIP/intersects acceleration structure
    # for the boundary. The polygon is touched once per building, so the
    # prep cost amortises over even a modest run.
    prepare(boundary_geom)

    kept: dict[str, ParsedBuilding] = {}
    for pand_id, pb in parsed_by_id.items():
        lod0 = pb.geometries.get("0") or []
        # Union all LoD0 polygons: a multi-part building (e.g. two
        # detached units sharing one BAG pand_id) can have more than
        # one LoD0 footprint polygon. Checking only ``lod0[0]`` would
        # drop any building whose first polygon lies outside the
        # boundary but whose second polygon crosses it.
        parts = [poly for sp in lod0 if (poly := _footprint_xy(sp, ShapelyPolygon)) is not None]
        if not parts:
            continue
        footprint = parts[0] if len(parts) == 1 else unary_union(parts)
        if boundary_geom.intersects(footprint):
            kept[pand_id] = pb
    return kept


def _footprint_xy(sp: SemanticPolygon, polygon_cls: Any) -> Any:
    """Return a 2D shapely Polygon for *sp*, healing rings with ``buffer(0)``.

    3DBAG LoD 0 is a single-polygon MultiSurface, so using the first
    SemanticPolygon is sufficient. Returns ``None`` for degenerate rings
    (< 3 vertices) or geometry that ``buffer(0)`` couldn't rescue: in
    either case the building is dropped from the boundary-filter result.
    """
    ring = sp.polygon.exterior
    if len(ring) < 3:
        return None
    from shapely.errors import ShapelyError

    exterior = [(x, y) for (x, y, _z) in ring]
    interiors = [[(x, y) for (x, y, _z) in hole] for hole in sp.polygon.interiors]
    try:
        poly = polygon_cls(exterior, interiors)
        if not poly.is_valid:
            poly = poly.buffer(0)
    except (ShapelyError, ValueError, TypeError, IndexError) as exc:
        _LOG.debug("skipping malformed footprint ring: %s", exc)
        return None
    if poly.is_empty or poly.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    return poly


def _maybe_fetch_energy_labels(
    session: CachedSession,
    config: CityBuildConfig,
    *,
    vbos: list[bag_fetchers.Verblijfsobject],
) -> list[eponline_fetchers.EnergyLabel] | None:
    """Fetch only the EP-online labels that could possibly match *vbos*.

    The 5 M-row EP-online mutation file dwarfs the ~10³ addresses inside
    a typical city-builder BBOX. The :func:`wanted_label_filter` derived
    from the matchable VBOs lets the CSV parser drop non-matching rows
    immediately, so the pipeline sees only the subset the address join
    can use. The filter is built by :mod:`.address_match` (never here)
    so the fetch filter and the join cannot drift apart.

    A second caching layer persists the *filtered* label list to disk
    keyed by ``(filter, ep-online-ZIP-vintage)``. Cache entries
    invalidate automatically when EP-online publishes a new mutation
    ZIP because the ZIP's on-disk size/mtime participate in the cache
    key.
    """
    if not config.include_energy_labels:
        return None
    api_key = config.ep_online_api_key
    if api_key is None:
        raise CityBuildError(
            "include_energy_labels=true but ep_online_api_key_file did not yield a token"
        )

    wanted = wanted_label_filter(vbos)

    wanted_digest = _wanted_sets_digest(wanted)
    cache_path = _filtered_labels_cache_path(session, wanted_digest)
    if cache_path is not None and cache_path.exists():
        labels = _try_load_filtered_labels(cache_path)
        if labels is not None:
            _LOG.info("EP-online labels loaded from filter cache (%s)", cache_path.name)
            return labels

    labels = eponline_fetchers.fetch_energy_labels(
        session,
        api_key=api_key,
        wanted_ids=wanted.ids,
        wanted_keys=wanted.keys,
    )

    # Re-resolve the cache path. On first run the ZIP didn't exist yet
    # when we computed the digest above; now it does, so we can store the
    # filtered result under a vintage-aware key.
    cache_path = _filtered_labels_cache_path(session, wanted_digest)
    if cache_path is not None:
        _try_save_filtered_labels(cache_path, labels)

    return labels


_EP_ONLINE_ZIP_GLOB = "ep_online_bundle.*.bin"


def _wanted_sets_digest(wanted: LabelFilter) -> str:
    """Stable SHA-256 digest of the label filter (order-independent)."""
    h = hashlib.sha256()
    for vbo_id in sorted(wanted.ids):
        h.update(vbo_id.encode("utf-8"))
        h.update(b"\x00")
    h.update(b"\x01")  # boundary marker between the two sets
    for key in sorted(wanted.keys, key=lambda k: (k[0], k[1], k[2] or "", k[3] or "")):
        h.update(f"{key[0]}|{key[1]}|{key[2] or ''}|{key[3] or ''}".encode())
        h.update(b"\x00")
    return h.hexdigest()[:24]


def _energy_label_shape_fingerprint() -> str:
    """Stable short hash of :class:`EnergyLabel`'s field names **and types**.

    Folded into the filtered-labels cache key so that adding, removing,
    renaming, or retyping a field on the dataclass automatically invalidates
    every pre-existing pickle. Hashing only names (the previous behaviour)
    would miss a field whose type changed from ``str`` to ``str | None``:
    the pickle unpickles silently but builder code that assumed a non-None
    value would then fail at runtime on cached data.
    """
    fields: dict = getattr(eponline_fetchers.EnergyLabel, "__dataclass_fields__", {})
    parts = sorted(f"{name}:{fld.type}" for name, fld in fields.items())
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:8]


def _filtered_labels_cache_path(
    session: CachedSession,
    wanted_digest: str,
) -> Path | None:
    """Return the on-disk pickle path for the filtered label set, or ``None``.

    Composes the EP-online ZIP's on-disk size+mtime into the cache key so
    a newly-downloaded mutation ZIP invalidates stale filtered caches
    automatically. Returns ``None`` when on-disk caching is off or the
    ZIP hasn't been fetched yet (first run): in that case the caller
    parses the CSV normally and the cache gets populated after fetch.
    """
    if not session.use_cache:
        return None
    candidates = list(session.cache_dir.glob(_EP_ONLINE_ZIP_GLOB))
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime_ns)
    stat = latest.stat()
    vintage = f"{latest.name}|{stat.st_size}|{stat.st_mtime_ns}"
    h = hashlib.sha256()
    h.update(vintage.encode("utf-8"))
    h.update(b"\x02")
    h.update(wanted_digest.encode("ascii"))
    digest = h.hexdigest()[:24]
    shape = _energy_label_shape_fingerprint()
    return session.cache_dir / f"ep_online_filtered.{digest}.v{shape}.pkl"


def _try_load_filtered_labels(
    cache_path: Path,
) -> list[eponline_fetchers.EnergyLabel] | None:
    """Load a pickled filtered-label list, returning ``None`` on any failure.

    A corrupt or incompatible pickle just falls through to a full parse.
    We never raise: cache corruption is always recoverable and should
    not fail a run.
    """
    try:
        with cache_path.open("rb") as handle:
            return pickle.load(handle)
    except (pickle.UnpicklingError, EOFError, ValueError, OSError, AttributeError) as exc:
        logging.getLogger(__name__).warning(
            "EP-online filter cache %s unreadable (%s); re-parsing",
            cache_path.name,
            exc,
        )
        return None


def _try_save_filtered_labels(
    cache_path: Path,
    labels: list[eponline_fetchers.EnergyLabel],
) -> None:
    """Persist *labels* to *cache_path*. Swallow IO errors; caching is best-effort."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            pickle.dump(labels, handle, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(cache_path)
    except OSError as exc:
        logging.getLogger(__name__).warning(
            "EP-online filter cache write to %s failed (%s); continuing without cache",
            cache_path.name,
            exc,
        )


def _fetch_parsed_buildings(
    session: CachedSession,
    *,
    outline: muni_fetchers.MunicipalityOutline,
    bbox: tuple[float, float, float, float] | None,
) -> list[ParsedBuilding]:
    """Pull intersecting 3DBAG tiles and parse per-pand geometry.

    When *bbox* is provided, the municipality outline is clipped to it
    before the tile query so only tiles that overlap the requested area
    are downloaded; critical for sub-municipality smoke tests.

    The clipped geometry is used only when the intersection is non-empty
    and geometrically valid. A degenerate bbox (zero-area, entirely
    outside the municipality, …) yields an empty or invalid result; we
    fall back to the full outline in that case so the caller never sees
    an empty geometry. Real shapely exceptions (invalid input geometry,
    missing dependency, …) are deliberately **not** suppressed.
    """
    geom = _outline_to_shapely(outline.feature.get("geometry") or {})
    if bbox is not None:
        from shapely.geometry import box as shapely_box

        clipped = geom.intersection(shapely_box(*bbox))
        if not clipped.is_empty and clipped.is_valid:
            geom = clipped
    return threedbag.fetch_buildings_for_outline(session, outline=geom)


def _outline_to_shapely(geometry: dict[str, Any]) -> BaseGeometry:
    try:
        from shapely.geometry import shape
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "City build needs shapely; install with: pip install -e .[city]"
        ) from exc
    return shape(geometry)


def _assemble_city_model(
    *,
    config: CityBuildConfig,
    panden: list[bag_fetchers.Pand],
    parsed_by_id: dict[str, ParsedBuilding],
    resolved_per_pand: dict[str, list[ResolvedAddress]],
    solar_matches_per_pand: dict[str, list[ProjectedPanel]] | None = None,
    tree_bundle: TreeBundle | None = None,
    postcode6_areas: list[Postcode6Area] | None = None,
    boundary_geom: BaseGeometry | None = None,
) -> CityModel:
    """Assemble a :class:`CityModel` from parsed BAG/3DBAG/EP-online inputs.

    The per-pand build (xsdata Building + BuildingUnit + Address +
    EnergyPerformanceCertificate construction + coordinate collection) is
    pure-Python CPU work and is embarrassingly parallel across pand. Setting
    ``CITYGML_ENERGY_ASSEMBLY_WORKERS=<N>`` spreads it across ``N`` worker
    processes (``multiprocessing.Pool``) rather than running sequentially.
    Process parallelism is off by default because it only pays off past
    a few thousand buildings; below that, worker startup + pickle cost
    exceeds the pure-CPU gain. For full-municipality runs (10k+ panden)
    the gain scales near-linearly with available cores.
    """
    model = CityModel(
        gml_description=config.city_model_description,
        gml_name=config.city_model_name,
    )
    # Optional file-banner comment (copyright / provenance / read-me),
    # emitted on write between the XML declaration and the root element.
    model.file_header = config.file_header

    inputs_per_pand = pand_executor.bundle_per_pand_inputs(
        panden=panden,
        resolved_per_pand=resolved_per_pand,
        solar_matches_per_pand=solar_matches_per_pand or {},
    )
    workers = pand_executor.assembly_worker_count(len(panden))
    build_results = pand_executor.run_per_pand_build(
        config=config,
        panden=panden,
        parsed_by_id=parsed_by_id,
        inputs_per_pand=inputs_per_pand,
        workers=workers,
    )

    all_coords: list[Coord3D] = []
    building_label_pairs: list[tuple[Any, list[ResolvedAddress]]] = []
    # Capture colorable surface ids as each building is built so the
    # appearance step doesn't need a second ``iter_instances`` tree walk.
    targets_by_gml_id: dict[str, list[str]] = {}
    for art in build_results:
        model.add(art.building)
        building_label_pairs.append((art.building, art.resolved))
        targets_by_gml_id[art.building.id] = art.targets
        all_coords.extend(art.coords)

    append_energy_label_appearance(
        model,
        building_label_pairs,
        targets_by_gml_id=targets_by_gml_id,
    )
    append_solar_panel_appearance(model)

    build_context = config.build_context()
    tree_targets = vegetation_module.attach_trees_to_model(
        model,
        tree_bundle if tree_bundle is not None else vegetation_module.EMPTY_BUNDLE,
        build_context,
        coords_sink=all_coords,
    )
    if tree_targets:
        append_vegetation_appearance(model, targets=tree_targets)

    postcode6_step.attach_postcode6_areas_to_model(
        model,
        build_context,
        areas=postcode6_areas or [],
        parsed_by_id=parsed_by_id,
        boundary_geom=boundary_geom,
        coords_sink=all_coords,
    )

    if all_coords:
        model.set_envelope(
            build_envelope(
                all_coords,
                srs_name=config.srs_name,
                srs_dimension=config.srs_dimension,
            )
        )
    return model


# Per-Pand build execution (sequential vs multiprocessing pool) lives
# in ``pand_executor`` so this module stays a recipe-style orchestrator.
# The CBS Postcode6 step lives in ``postcode6.py`` and the CFTree +
# BGT + Emmen-BOR vegetation step lives in ``vegetation.py``, each
# owning fetch + filter + build + attach for one data type behind one
# seam.
