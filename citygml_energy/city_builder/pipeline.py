"""Top-level city-build orchestrator.

:func:`build_city_model` wires the fetchers, CityJSON parser, address
matcher, and xsdata builders into a single :class:`CityModel` ready for
serialization. :func:`build_city_gml_file` is a convenience that writes
the result to :attr:`CityBuildConfig.output_path`.

Network calls are delegated to :class:`CachedSession` through the
fetchers; tests inject a pre-populated cache dir or monkeypatch
``session.session`` so they never hit the wire.
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._gml_builders import build_envelope
from .._step import Coord3D
from ..core import CityModel
from .address_key import address_key_from_vbo
from .address_match import ResolvedAddress, match_addresses
from .appearance import (
    append_energy_label_appearance,
    append_pv_panel_appearance,
)
from .boundary import BoundarySource, load_boundary_polygon
from .builders import attach_building_units_to_building, build_building
from .cityjson_parse import ParsedBuilding, SemanticPolygon
from .config import CityBuildConfig, CityBuildError, load_city_config
from .fetchers import bag as bag_fetchers
from .fetchers import eponline as eponline_fetchers
from .fetchers import municipality as muni_fetchers
from .fetchers import threedbag
from .http import CachedSession
from . import pv_panels as pv_panels_module
from .pv_panels import ProjectedPanel, attach_pv_collectors_to_building

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry


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

    print(f"[city-builder] Fetching municipality outline: {config.municipality}")
    outline = muni_fetchers.fetch_municipality_outline(
        session, name=config.municipality
    )
    bbox = _resolve_bbox(config, outline=outline, boundary_geom=boundary_geom)
    cbs_code = outline.cbs_code or None
    print(f"[city-builder] CBS code: {cbs_code!r}  bbox: {bbox}")

    print("[city-builder] Fetching BAG panden …")
    panden = bag_fetchers.fetch_panden(session, bbox=bbox, cbs_code=cbs_code)
    known_pand_ids = {pand.identificatie for pand in panden}
    print(f"[city-builder] {len(panden)} panden")

    resolved_per_pand: dict[str, list[ResolvedAddress]] = {}
    if config.include_addresses:
        print("[city-builder] Fetching BAG verblijfsobjecten …")
        vbos = bag_fetchers.fetch_verblijfsobjecten(
            session, bbox=bbox, cbs_code=cbs_code
        )
        print(f"[city-builder] {len(vbos)} verblijfsobjecten")

        energy_labels = _maybe_fetch_energy_labels(session, config, vbos=vbos)
        if energy_labels is not None:
            print(f"[city-builder] {len(energy_labels)} EP-online labels matched")

        resolved_per_pand = match_addresses(
            vbos=vbos,
            energy_labels=energy_labels,
        )
        matched_vbos = sum(len(v) for v in resolved_per_pand.values())
        print(f"[city-builder] {matched_vbos} VBOs matched to {len(resolved_per_pand)} panden")

    print("[city-builder] Fetching 3DBAG tiles …")
    parsed_buildings = _fetch_parsed_buildings(session, outline=outline, bbox=bbox)
    parsed_by_id = {pb.pand_id: pb for pb in parsed_buildings if pb.pand_id in known_pand_ids}
    print(
        f"[city-builder] {len(parsed_buildings)} buildings from 3DBAG tiles; "
        f"{len(parsed_by_id)} match known BAG panden"
    )
    skipped = len(panden) - len(parsed_by_id)
    if skipped:
        print(f"[city-builder] {skipped} panden have no 3DBAG geometry (skipped)")

    if boundary_geom is not None:
        before = len(parsed_by_id)
        parsed_by_id = _filter_by_boundary(parsed_by_id, boundary_geom)
        dropped = before - len(parsed_by_id)
        kept_ids = set(parsed_by_id)
        panden = [p for p in panden if p.identificatie in kept_ids]
        print(
            f"[city-builder] Boundary polygon kept {len(parsed_by_id)} / {before} "
            f"buildings ({dropped} outside)"
        )

    pv_matches_per_pand = _maybe_match_pv_panels(
        config=config, bbox=bbox, parsed_by_id=parsed_by_id,
    )

    print("[city-builder] Assembling CityModel …")
    model = _assemble_city_model(
        config=config,
        panden=panden,
        parsed_by_id=parsed_by_id,
        resolved_per_pand=resolved_per_pand,
        pv_matches_per_pand=pv_matches_per_pand,
    )
    print(f"[city-builder] Done: {len(model.xsd.city_object_member)} buildings in model")
    return model


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
        print(
            "[city-builder] WARNING: pv_panels configured but LoD 2 is "
            "disabled; skipping PV attach"
        )
        return {}

    print(f"[city-builder] Loading PV panels: {source.path.name} ({source.layer})")
    panels = pv_panels_module.load_panels_in_bbox(source, bbox)
    if not panels:
        print("[city-builder] PV panels: 0 polygons inside bbox; skipping")
        return {}

    matches, skipped = pv_panels_module.match_and_project_panels(
        panels=panels,
        parsed_buildings=parsed_by_id.values(),
        z_offset_m=source.z_offset_m,
    )
    total = sum(len(v) for v in matches.values())
    print(
        f"[city-builder] PV panels: {total} projected onto {len(matches)} buildings "
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
    print(
        f"[city-builder] Loading boundary polygon: {source.path.name} "
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


def _footprint_xy(sp: SemanticPolygon, Polygon: Any) -> Any:
    """Return a 2D shapely Polygon for *sp*, healing rings with ``buffer(0)``.

    3DBAG LoD 0 is a single-polygon MultiSurface, so using the first
    SemanticPolygon is sufficient. Returns ``None`` for degenerate rings
    (< 3 vertices) or geometry that ``buffer(0)`` couldn't rescue: in
    either case the building is dropped from the boundary-filter result.
    """
    ring = sp.polygon.exterior
    if len(ring) < 3:
        return None
    exterior = [(x, y) for (x, y, _z) in ring]
    interiors = [
        [(x, y) for (x, y, _z) in hole] for hole in sp.polygon.interiors
    ]
    try:
        poly = Polygon(exterior, interiors)
        if not poly.is_valid:
            poly = poly.buffer(0)
    except Exception:  # noqa: BLE001, malformed rings: skip silently
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
            print(f"[city-builder] EP-online labels loaded from filter cache ({cache_path.name})")
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
    return session.cache_dir / f"ep_online_filtered.{digest}.pkl"


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

    inputs_per_pand = _bundle_per_pand_inputs(
        panden=panden,
        resolved_per_pand=resolved_per_pand,
        pv_matches_per_pand=pv_matches_per_pand or {},
    )
    workers = _assembly_worker_count(len(panden))
    if workers > 1:
        build_results = _build_pand_artifacts_parallel(
            config=config,
            panden=panden,
            parsed_by_id=parsed_by_id,
            inputs_per_pand=inputs_per_pand,
            workers=workers,
        )
    else:
        build_results = _build_pand_artifacts_sequential(
            config=config,
            panden=panden,
            parsed_by_id=parsed_by_id,
            inputs_per_pand=inputs_per_pand,
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

    if all_coords:
        model.set_envelope(
            build_envelope(
                all_coords,
                srs_name=config.srs_name,
                srs_dimension=config.srs_dimension,
            )
        )
    return model


def _assembly_worker_count(n_panden: int) -> int:
    """Return the effective worker count, respecting the opt-in env var.

    ``CITYGML_ENERGY_ASSEMBLY_WORKERS`` > 1 enables process parallelism.
    Silently capped at the pand count (no point spawning 16 workers for
    20 buildings). Returns ``1`` (sequential) on any parsing error so a
    malformed env var never breaks a run.
    """
    raw = os.environ.get("CITYGML_ENERGY_ASSEMBLY_WORKERS", "").strip()
    if not raw:
        return 1
    try:
        requested = int(raw)
    except ValueError:
        return 1
    if requested < 2 or n_panden < 2:
        return 1
    return min(requested, n_panden)


# Compact tuple type emitted by the per-pand build step: small, picklable,
# and exactly what the main process needs to assemble the final CityModel.
_PandArtifacts = tuple[Any, list[ResolvedAddress], list[str], list[Coord3D]]


@dataclass(frozen=True, slots=True)
class _PandInputs:
    """Everything the per-pand build needs beyond geometry + config.

    Bundling the two parallel per-pand dicts (``resolved_per_pand`` and
    ``pv_matches_per_pand``) under one key keeps the worker-pool job
    tuple flat and ready for any future "another thing per pand" input
    (indicators, schedules, …) without re-plumbing every call site.
    """

    resolved: list[ResolvedAddress]
    pv_panels: tuple[ProjectedPanel, ...]


_EMPTY_INPUTS = _PandInputs(resolved=[], pv_panels=())


def _bundle_per_pand_inputs(
    *,
    panden: list[bag_fetchers.Pand],
    resolved_per_pand: dict[str, list[ResolvedAddress]],
    pv_matches_per_pand: dict[str, list[ProjectedPanel]],
) -> dict[str, _PandInputs]:
    """Collapse the two per-pand dicts into a single dict of structs.

    Only panden that appear in at least one of the sources get an
    entry; everyone else falls through to :data:`_EMPTY_INPUTS` at
    lookup time.
    """
    ids = {p.identificatie for p in panden}
    ids &= set(resolved_per_pand) | set(pv_matches_per_pand)
    return {
        pid: _PandInputs(
            resolved=resolved_per_pand.get(pid, []),
            pv_panels=tuple(pv_matches_per_pand.get(pid, ())),
        )
        for pid in ids
    }


def _build_pand_artifacts_sequential(
    *,
    config: CityBuildConfig,
    panden: list[bag_fetchers.Pand],
    parsed_by_id: dict[str, ParsedBuilding],
    inputs_per_pand: dict[str, _PandInputs],
) -> list[_PandArtifacts]:
    """Sequentially build the per-pand artifacts. Default path."""
    build_params = _BuildParams.from_config(config)
    return [
        _build_pand_artifacts(
            pand=pand,
            parsed=parsed_by_id[pand.identificatie],
            inputs=inputs_per_pand.get(pand.identificatie, _EMPTY_INPUTS),
            build_params=build_params,
        )
        for pand in panden
        if pand.identificatie in parsed_by_id
    ]


def _build_pand_artifacts_parallel(
    *,
    config: CityBuildConfig,
    panden: list[bag_fetchers.Pand],
    parsed_by_id: dict[str, ParsedBuilding],
    inputs_per_pand: dict[str, _PandInputs],
    workers: int,
) -> list[_PandArtifacts]:
    """Run the per-pand build in a ``multiprocessing.Pool``.

    Only panden that have matching 3DBAG geometry are dispatched; the
    chunk size is tuned so each worker churns through a reasonable batch
    before hitting the IPC boundary (pickling xsdata Building objects
    back to the main process is the main ongoing cost in this path).
    """
    import multiprocessing

    build_params = _BuildParams.from_config(config)
    jobs: list[tuple[Any, ...]] = [
        (
            pand,
            parsed_by_id[pand.identificatie],
            inputs_per_pand.get(pand.identificatie, _EMPTY_INPUTS),
            build_params,
        )
        for pand in panden
        if pand.identificatie in parsed_by_id
    ]
    if not jobs:
        return []

    # ``chunksize=max(1, len(jobs) // (workers * 4))`` is ``Pool.map``'s
    # built-in default tuned down slightly. Batching amortises worker
    # dispatch overhead without losing responsiveness on smaller runs.
    chunksize = max(1, len(jobs) // (workers * 4))
    print(f"[city-builder] Assembly worker pool: {workers} processes × {chunksize} panden/chunk")
    # ``spawn`` is the right start method here: fork-safety with xsdata's
    # lazy registry and requests sessions is not guaranteed, and ``spawn``
    # is the Windows default anyway. The child imports ``citygml_energy``
    # fresh, which warms its bindings cache once per worker.
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        return pool.map(_build_pand_worker, jobs, chunksize=chunksize)


@dataclass(frozen=True, slots=True)
class _BuildParams:
    """Immutable subset of :class:`CityBuildConfig` shared across workers.

    Defined as a frozen dataclass so it pickles cheaply (one flat tuple,
    no recursion through the full config) and because workers should not
    be mutating pipeline-level settings by accident.
    """

    gml_id_prefix: str
    lods: tuple[int, ...]
    srs_name: str
    srs_dimension: int
    municipality: str

    @classmethod
    def from_config(cls, config: CityBuildConfig) -> _BuildParams:
        return cls(
            gml_id_prefix=config.gml_id_prefix,
            lods=tuple(config.lods),
            srs_name=config.srs_name,
            srs_dimension=config.srs_dimension,
            municipality=config.municipality,
        )


def _build_pand_worker(
    job: tuple[bag_fetchers.Pand, ParsedBuilding, _PandInputs, _BuildParams],
) -> _PandArtifacts:
    """Worker entry point: must be module-level to be picklable on spawn."""
    pand, parsed, inputs, build_params = job
    return _build_pand_artifacts(
        pand=pand, parsed=parsed, inputs=inputs, build_params=build_params,
    )


def _build_pand_artifacts(
    *,
    pand: bag_fetchers.Pand,
    parsed: ParsedBuilding,
    inputs: _PandInputs,
    build_params: _BuildParams,
) -> _PandArtifacts:
    """Build the xsdata artefacts for one Pand.

    Returned tuple is the minimal slice the main process needs to
    assemble the city model: the xsdata Building object, the list of
    matched addresses, the pre-collected appearance target ids, and the
    flat coordinate sequence used to widen the model envelope. All four
    values pickle cheaply across the worker-pool boundary.
    """
    _merge_attributes(parsed.attributes, pand)
    targets: list[str] = []
    building = build_building(
        parsed,
        gml_id_prefix=build_params.gml_id_prefix,
        lods=build_params.lods,
        srs_name=build_params.srs_name,
        srs_dimension=build_params.srs_dimension,
        surface_targets_out=targets,
    )
    attach_building_units_to_building(
        building,
        inputs.resolved,
        gml_id_prefix=build_params.gml_id_prefix,
        city_name=build_params.municipality,
        srs_name=build_params.srs_name,
        srs_dimension=build_params.srs_dimension,
    )
    if inputs.pv_panels:
        attach_pv_collectors_to_building(
            building,
            list(inputs.pv_panels),
            srs_name=build_params.srs_name,
            srs_dimension=build_params.srs_dimension,
        )
    coords: list[Coord3D] = []
    _collect_coordinates(parsed, coords)
    return building, inputs.resolved, targets, coords


def _merge_attributes(parsed_attrs: dict[str, Any], pand: bag_fetchers.Pand) -> None:
    """Merge BAG Pand attributes into the parsed CityJSON attributes.

    3DBAG already carries ``oorspronkelijkbouwjaar`` but BAG sometimes
    has a newer / corrected value. BAG wins when present: direct
    assignment so the BAG value always overwrites the 3DBAG value.
    """
    if pand.bouwjaar is not None:
        parsed_attrs["oorspronkelijkbouwjaar"] = pand.bouwjaar
    if pand.status and "status" not in parsed_attrs:
        parsed_attrs["status"] = pand.status


def _collect_coordinates(
    parsed: ParsedBuilding, sink: list[Coord3D]
) -> None:
    for polygons in parsed.geometries.values():
        for sp in polygons:
            _extend_polygon_coords(sp, sink)


def _extend_polygon_coords(sp: SemanticPolygon, sink: list[Coord3D]) -> None:
    sink.extend(sp.polygon.exterior)
    for ring in sp.polygon.interiors:
        sink.extend(ring)
