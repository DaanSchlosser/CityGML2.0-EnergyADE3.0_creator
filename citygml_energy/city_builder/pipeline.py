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

import hashlib
import logging
import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._step import Coord3D
from ..core import CityModel
from ..gml_builders import build_envelope
from . import pand_executor
from . import pv_panels as pv_panels_module
from . import vegetation as vegetation_module
from .address_key import address_key_from_vbo
from .address_match import ResolvedAddress, match_addresses
from .appearance import (
    append_energy_label_appearance,
    append_pv_panel_appearance,
    append_vegetation_appearance,
)
from .bgt_match import match_trees_to_bgt
from .boundary import load_boundary_polygon
from .builders import build_solitary_vegetation_object
from .cityjson_parse import ParsedBuilding, SemanticPolygon
from .cityjson_trees_parse import ParsedTree
from .config import CityBuildConfig, CityBuildError, load_city_config
from .fetchers import bag as bag_fetchers
from .fetchers import eponline as eponline_fetchers
from .fetchers import municipality as muni_fetchers
from .fetchers import threedbag
from .fetchers.bgt import BgtTree, fetch_bgt_trees
from .fetchers.emmen_bor import BorTree, fetch_bor_trees
from .http import CachedSession
from .pv_panels import ProjectedPanel
from .tree_enrichment import match_trees_to_bor

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

    _LOG.info(f"Fetching municipality outline: {config.municipality}")
    outline = muni_fetchers.fetch_municipality_outline(
        session, name=config.municipality
    )
    bbox = _resolve_bbox(config, outline=outline, boundary_geom=boundary_geom)
    cbs_code = outline.cbs_code or None
    _LOG.info(f"CBS code: {cbs_code!r}  bbox: {bbox}")

    _LOG.info("Fetching BAG panden …")
    panden = bag_fetchers.fetch_panden(session, bbox=bbox, cbs_code=cbs_code)
    known_pand_ids = {pand.identificatie for pand in panden}
    _LOG.info(f"{len(panden)} panden")

    resolved_per_pand: dict[str, list[ResolvedAddress]] = {}
    if config.include_addresses:
        _LOG.info("Fetching BAG verblijfsobjecten …")
        vbos = bag_fetchers.fetch_verblijfsobjecten(
            session, bbox=bbox, cbs_code=cbs_code
        )
        _LOG.info(f"{len(vbos)} verblijfsobjecten")

        energy_labels = _maybe_fetch_energy_labels(session, config, vbos=vbos)
        if energy_labels is not None:
            _LOG.info(f"{len(energy_labels)} EP-online labels matched")

        resolved_per_pand = match_addresses(
            vbos=vbos,
            energy_labels=energy_labels,
        )
        matched_vbos = sum(len(v) for v in resolved_per_pand.values())
        _LOG.info(f"{matched_vbos} VBOs matched to {len(resolved_per_pand)} panden")

    _LOG.info("Fetching 3DBAG tiles …")
    parsed_buildings = _fetch_parsed_buildings(session, outline=outline, bbox=bbox)
    parsed_by_id = {pb.pand_id: pb for pb in parsed_buildings if pb.pand_id in known_pand_ids}
    _LOG.info(
        f"{len(parsed_buildings)} buildings from 3DBAG tiles; "
        f"{len(parsed_by_id)} match known BAG panden"
    )
    skipped = len(panden) - len(parsed_by_id)
    if skipped:
        _LOG.info(f"{skipped} panden have no 3DBAG geometry (skipped)")

    if boundary_geom is not None:
        before = len(parsed_by_id)
        parsed_by_id = _filter_by_boundary(parsed_by_id, boundary_geom)
        dropped = before - len(parsed_by_id)
        kept_ids = set(parsed_by_id)
        panden = [p for p in panden if p.identificatie in kept_ids]
        _LOG.info(
            f"Boundary polygon kept {len(parsed_by_id)} / {before} "
            f"buildings ({dropped} outside)"
        )

    pv_matches_per_pand = _maybe_match_pv_panels(
        config=config, bbox=bbox, parsed_by_id=parsed_by_id,
    )

    trees = _maybe_load_trees(
        config=config, bbox=bbox, boundary_geom=boundary_geom,
    )
    bgt_matches = _maybe_match_trees_to_bgt(
        session=session, trees=trees, bbox=bbox,
    )
    bor_matches = _maybe_match_trees_to_bor(
        session=session, trees=trees, bbox=bbox,
    )

    _LOG.info("Assembling CityModel …")
    model = _assemble_city_model(
        config=config,
        panden=panden,
        parsed_by_id=parsed_by_id,
        resolved_per_pand=resolved_per_pand,
        pv_matches_per_pand=pv_matches_per_pand,
        trees=trees,
        bgt_matches=bgt_matches,
        bor_matches=bor_matches,
    )
    building_count = sum(
        1 for m in model.xsd.city_object_member if m.building is not None
    )
    vegetation_count = sum(
        1 for m in model.xsd.city_object_member
        if m.solitary_vegetation_object is not None
    )
    _LOG.info(
        f"Done: {building_count} buildings + "
        f"{vegetation_count} trees in model"
    )
    return model


def _maybe_load_trees(
    *,
    config: CityBuildConfig,
    bbox: tuple[float, float, float, float],
    boundary_geom: BaseGeometry | None,
) -> list[ParsedTree]:
    """Load CFTree reconstructions from *config.vegetation_source*.

    Empty list when no vegetation source is configured. The bbox clip
    runs first (fast, avoids parsing tiles that are fully outside); the
    optional boundary polygon clip runs second, matching the building
    filter's ``boundary-wins-over-bbox`` semantics.
    """
    source = config.vegetation_source
    if source is None:
        return []

    _LOG.info(f"Loading CFTree vegetation: {source.path}")
    trees = vegetation_module.load_trees_in_bbox(source, bbox)
    if not trees:
        return []

    if boundary_geom is not None:
        before = len(trees)
        trees = vegetation_module.filter_trees_by_boundary(trees, boundary_geom)
        _LOG.info(
            f"Boundary polygon kept {len(trees)} / {before} trees"
        )
    else:
        _LOG.info(f"Loaded {len(trees)} trees inside bbox")

    return trees


def _maybe_match_trees_to_bgt(
    *,
    session: CachedSession,
    trees: list[ParsedTree],
    bbox: tuple[float, float, float, float],
) -> dict[str, BgtTree]:
    """Fetch BGT ``vegetatieobject_punt`` and nearest-join onto CFTree trees.

    Returns an empty dict when there are no CFTree trees or when BGT
    yields nothing for the bbox. Any HTTP / parse error is caught by
    :func:`fetch_bgt_trees`, which logs a warning and returns ``[]`` —
    the cross-reference is an authoritative-register link, not a hard
    dependency, so a PDOK outage degrades to plain geometry rather
    than failing the build.

    The match is logged with ``matched / total`` so users can judge
    coverage: low ratios (e.g. < 50 %) suggest either that the AOI is
    private garden land (unregistered in BGT) or that CFTree is
    over-reconstructing non-tree vegetation.
    """
    if not trees:
        return {}
    _LOG.info("Fetching BGT vegetatieobject_punt (boom) …")
    bgt_trees = fetch_bgt_trees(session, bbox)
    matches = match_trees_to_bgt(trees, bgt_trees)
    _LOG.info(
        f"BGT cross-reference: {len(matches)} of {len(trees)} "
        f"CFTree trees matched a BGT boom record ({len(bgt_trees)} BGT "
        f"features in bbox)"
    )
    return matches


def _maybe_match_trees_to_bor(
    *,
    session: CachedSession,
    trees: list[ParsedTree],
    bbox: tuple[float, float, float, float],
) -> dict[str, BorTree]:
    """Fetch Gemeente Emmen's BOR tree register and join it onto CFTree trees.

    Behaves identically to :func:`_maybe_match_trees_to_bgt`: empty
    dict on no trees / empty bbox response, soft-failed fetch on
    network or parse errors. Outside Emmen the bbox-restricted query
    returns zero features (silently logged), which is the desired
    no-op behaviour for the city pipeline's PoC scope.
    """
    if not trees:
        return {}
    _LOG.info("Fetching Gemeente Emmen BOR tree register …")
    bor_trees = fetch_bor_trees(session, bbox)
    matches = match_trees_to_bor(trees, bor_trees)
    _LOG.info(
        f"BOR enrichment: {len(matches)} of {len(trees)} "
        f"CFTree trees matched a BOR record ({len(bor_trees)} BOR "
        f"features in bbox)"
    )
    return matches


def _maybe_match_pv_panels(
    *,
    config: CityBuildConfig,
    bbox: tuple[float, float, float, float],
    parsed_by_id: dict[str, ParsedBuilding],
) -> dict[str, list[ProjectedPanel]]:
    """Load + match + project PV panels once in the main process.

    Empty dict when no PV source is configured, when LoD 2 is disabled
    (there is nothing to attach to), or when no panels fall inside the
    bbox.
    """
    source = config.pv_panels_source
    if source is None:
        return {}
    if 2 not in config.lods:
        _LOG.warning(
            "pv_panels configured but LoD 2 is disabled; skipping PV attach"
        )
        return {}

    _LOG.info(f"Loading PV panels: {source.path.name} ({source.layer})")
    panels = pv_panels_module.load_panels_in_bbox(source, bbox)
    if not panels:
        _LOG.info("PV panels: 0 polygons inside bbox; skipping")
        return {}

    matches, skipped = pv_panels_module.match_and_project_panels(
        panels=panels,
        parsed_buildings=parsed_by_id.values(),
        z_offset_m=source.z_offset_m,
    )
    total = sum(len(v) for v in matches.values())
    _LOG.info(
        f"PV panels: {total} projected onto {len(matches)} buildings "
        f"({skipped} skipped, no LoD 2 roof overlap)"
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
    _LOG.info(
        f"Loading boundary polygon: {source.path.name} "
        f"(layer={source.layer}, fid={source.fid})"
    )
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


def _filter_by_boundary(
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
    defensively handled) are dropped with a log line so a silent data
    gap is easy to spot.
    """
    try:
        from shapely import prepare
        from shapely.geometry import Polygon as ShapelyPolygon
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
        if not lod0:
            continue
        footprint = _footprint_xy(lod0[0], ShapelyPolygon)
        if footprint is None:
            continue
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
    interiors = [
        [(x, y) for (x, y, _z) in hole] for hole in sp.polygon.interiors
    ]
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
    a typical city-builder BBOX. Passing the VBO-derived id / address-key
    sets into the fetcher lets the CSV parser drop non-matching rows
    immediately, so the pipeline sees only the matching subset.

    A second caching layer persists the *filtered* label list to disk
    keyed by ``(wanted_keys, wanted_ids, ep-online-ZIP-vintage)``. Cache
    entries invalidate automatically when EP-online publishes a new
    mutation ZIP because the ZIP's on-disk size/mtime participate in
    the cache key.
    """
    if not config.include_energy_labels:
        return None
    api_key = config.ep_online_api_key
    if api_key is None:
        raise CityBuildError(
            "include_energy_labels=true but ep_online_api_key_file did not yield a token"
        )

    wanted_ids = {v.identificatie for v in vbos}
    wanted_keys = {
        address_key_from_vbo(v)
        for v in vbos
        if v.postcode is not None and v.huisnummer is not None
    }

    wanted_digest = _wanted_sets_digest(wanted_ids, wanted_keys)
    cache_path = _filtered_labels_cache_path(session, wanted_digest)
    if cache_path is not None and cache_path.exists():
        labels = _try_load_filtered_labels(cache_path)
        if labels is not None:
            _LOG.info(f"EP-online labels loaded from filter cache ({cache_path.name})")
            return labels

    labels = eponline_fetchers.fetch_energy_labels(
        session,
        api_key=api_key,
        wanted_ids=wanted_ids,
        wanted_keys=wanted_keys,
    )

    # Re-resolve the cache path. On first run the ZIP didn't exist yet
    # when we computed the digest above; now it does, so we can store the
    # filtered result under a vintage-aware key.
    cache_path = _filtered_labels_cache_path(session, wanted_digest)
    if cache_path is not None:
        _try_save_filtered_labels(cache_path, labels)

    return labels


_EP_ONLINE_ZIP_GLOB = "ep_online_bundle.*.bin"


def _wanted_sets_digest(
    wanted_ids: set[str],
    wanted_keys: set[tuple[str, int, str | None, str | None]],
) -> str:
    """Stable SHA-256 digest of the two filter sets (order-independent)."""
    h = hashlib.sha256()
    for vbo_id in sorted(wanted_ids):
        h.update(vbo_id.encode("utf-8"))
        h.update(b"\x00")
    h.update(b"\x01")  # boundary marker between the two sets
    for key in sorted(wanted_keys, key=lambda k: (k[0], k[1], k[2] or "", k[3] or "")):
        h.update(f"{key[0]}|{key[1]}|{key[2] or ''}|{key[3] or ''}".encode())
        h.update(b"\x00")
    return h.hexdigest()[:24]


def _energy_label_shape_fingerprint() -> str:
    """Stable short hash of :class:`EnergyLabel`'s field list.

    Folded into the filtered-labels cache key so that adding, removing,
    or renaming a field on the dataclass automatically invalidates every
    pre-existing pickle. Without this, a stale pickle produced before a
    new field was added would unpickle into a slotted instance whose
    new slot is never set, causing ``AttributeError`` the first time
    the builder accesses it.
    """
    fields = getattr(eponline_fetchers.EnergyLabel, "__dataclass_fields__", {})
    return hashlib.sha256("|".join(sorted(fields)).encode("utf-8")).hexdigest()[:8]


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
            "EP-online filter cache %s unreadable (%s); re-parsing", cache_path.name, exc,
        )
        return None


def _try_save_filtered_labels(
    cache_path: Path, labels: list[eponline_fetchers.EnergyLabel],
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
            cache_path.name, exc,
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
    pv_matches_per_pand: dict[str, list[ProjectedPanel]] | None = None,
    trees: list[ParsedTree] | None = None,
    bgt_matches: dict[str, BgtTree] | None = None,
    bor_matches: dict[str, BorTree] | None = None,
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

    inputs_per_pand = pand_executor.bundle_per_pand_inputs(
        panden=panden,
        resolved_per_pand=resolved_per_pand,
        pv_matches_per_pand=pv_matches_per_pand or {},
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
    for building, resolved, targets, coords in build_results:
        model.add(building)
        building_label_pairs.append((building, resolved))
        targets_by_gml_id[building.id] = targets
        all_coords.extend(coords)

    append_energy_label_appearance(
        model,
        building_label_pairs,
        targets_by_gml_id=targets_by_gml_id,
    )
    append_pv_panel_appearance(model)

    if trees:
        tree_appearance_targets = _attach_trees_to_model(
            model,
            trees,
            gml_id_prefix=config.gml_id_prefix,
            srs_name=config.srs_name,
            srs_dimension=config.srs_dimension,
            coords_sink=all_coords,
            bgt_matches=bgt_matches or {},
            bor_matches=bor_matches or {},
        )
        append_vegetation_appearance(model, targets=tree_appearance_targets)

    if all_coords:
        model.set_envelope(
            build_envelope(
                all_coords,
                srs_name=config.srs_name,
                srs_dimension=config.srs_dimension,
            )
        )
    return model


def _attach_trees_to_model(
    model: CityModel,
    trees: list[ParsedTree],
    *,
    gml_id_prefix: str,
    srs_name: str,
    srs_dimension: int,
    coords_sink: list[Coord3D],
    bgt_matches: dict[str, BgtTree],
    bor_matches: dict[str, BorTree],
) -> list[str]:
    """Emit one ``veg:SolitaryVegetationObject`` per :class:`ParsedTree`.

    Every tree gets geometry + CFTree morphometrics
    (height, trunk diameter, crown diameter). When *bgt_matches*
    contains an entry keyed on the tree's gtid, the builder also
    attaches a ``core:externalReference`` pointing at the
    authoritative BGT ``vegetatieobject_punt`` feature. When
    *bor_matches* contains an entry, the Latin scientific name fills
    ``veg:species`` (the only typed CityGML 2.0 vegetation slot the
    BOR layer can fill honestly), the planting year goes to
    ``gen:intAttribute name="plantingYear"``, and the remaining
    fields (Dutch common name, height/diameter class bands,
    protection status, growth form, standplaats) become
    ``gen:stringAttribute`` siblings, plus a second
    ``core:externalReference`` keyed on ``boom_id``. See
    ``builders.vegetation._apply_bor_enrichment`` and
    ``docs/source_to_gml_mapping.md`` for the full mapping. The two
    matches are independent: a tree may carry zero, one, or both
    cross-references.

    Tree crown vertices also widen the city envelope: if we skipped
    them, a SolitaryVegetationObject extending past the building
    footprint would clip at the final ``gml:boundedBy`` and render
    with a dotted line above the camera in some viewers.

    Returns the list of colorable surface ids (``#<gml:id>``) emitted
    under each tree so the downstream vegetation appearance step can
    consume them without a second ``iter_instances`` walk of the whole
    city model. Mirrors how the per-pand build path returns
    ``targets_by_gml_id`` to the energy-label appearance.
    """
    appearance_targets: list[str] = []
    for tree in trees:
        obj = build_solitary_vegetation_object(
            tree,
            gml_id_prefix=gml_id_prefix,
            srs_name=srs_name,
            srs_dimension=srs_dimension,
            bgt_match=bgt_matches.get(tree.gtid),
            bor_match=bor_matches.get(tree.gtid),
        )
        model.add(obj)
        if obj.lod3_geometry is not None and obj.lod3_geometry.multi_surface is not None:
            ms = obj.lod3_geometry.multi_surface
            if ms.id:
                appearance_targets.append(f"#{ms.id}")
            appearance_targets.extend(
                f"#{member.polygon.id}"
                for member in ms.surface_member
                if member.polygon is not None and member.polygon.id
            )
        for polygon in tree.polygons:
            coords_sink.extend(polygon.exterior)
            for hole in polygon.interiors:
                coords_sink.extend(hole)
    return appearance_targets


# Per-Pand build execution (sequential vs multiprocessing pool) lives
# in ``pand_executor`` so this module stays a recipe-style orchestrator.
