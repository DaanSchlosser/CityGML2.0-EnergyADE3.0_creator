"""Per-Pand build execution: sequential vs multiprocessing pool.

The orchestrator in :mod:`citygml_energy.city_builder.pipeline` is the
"what" of the city build (load BAG, fetch 3DBAG, match addresses, fan
out per-Pand work, assemble city model). This module is the "how" of
the per-Pand step: given a list of Panden plus pre-fetched per-Pand
inputs, produce the list of :class:`PandArtifacts` records the
orchestrator then folds into the :class:`citygml_energy.core.CityModel`.

Splitting the executor out of ``pipeline.py`` keeps the orchestrator
readable as a recipe: ten ``_maybe_*`` helpers in linear order, with
the worker-pool plumbing tucked into one place. The recipe never has
to think about chunk sizes, ``spawn`` vs ``fork``, picklability of
xsdata artefacts, or the env-var override.

Process parallelism is opt-in via the
``CITYGML_ENERGY_ASSEMBLY_WORKERS`` env var. It only pays off past a
few thousand panden; below that, worker startup + pickle cost exceeds
the pure-CPU gain, so the default of ``1`` (sequential) is the right
choice for the city-pipeline PoC scope.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from .._step import Coord3D
from .address_match import ResolvedAddress
from .builders import (
    apply_bag_year_metadata_to_building,
    apply_eponline_pand_attribution_to_building,
    attach_building_units_to_building,
    build_building,
)
from .cityjson_parse import ParsedBuilding, SemanticPolygon
from .config import BuildContext, CityBuildConfig
from .fetchers import bag as bag_fetchers
from .solar_panels import ProjectedPanel, attach_solar_collectors_to_building

__all__ = [
    "EMPTY_INPUTS",
    "PandArtifacts",
    "PandInputs",
    "assembly_worker_count",
    "bundle_per_pand_inputs",
    "run_per_pand_build",
]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PandArtifacts:
    """Per-pand build output the main process folds into the CityModel.

    Frozen + slots so the four fields stay picklable across the
    ``spawn`` worker-pool boundary at no extra cost relative to the
    plain tuple this used to be. Adding a new per-pand output
    (thermal zones, indicators, ...) is a one-line addition here
    instead of re-plumbing every unpack site.
    """

    building: Any
    resolved: list[ResolvedAddress]
    targets: list[str]
    coords: list[Coord3D]


@dataclass(frozen=True, slots=True)
class PandInputs:
    """Everything the per-pand build needs beyond geometry + config.

    Bundling the parallel per-pand dicts (``resolved_per_pand`` and
    ``solar_matches_per_pand``) under one key keeps the worker-pool job
    tuple flat and ready for any future "another thing per pand"
    input (indicators, schedules, …) without re-plumbing every call
    site.
    """

    resolved: list[ResolvedAddress]
    solar_panels: tuple[ProjectedPanel, ...]


EMPTY_INPUTS = PandInputs(resolved=[], solar_panels=())


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def bundle_per_pand_inputs(
    *,
    panden: list[bag_fetchers.Pand],
    resolved_per_pand: dict[str, list[ResolvedAddress]],
    solar_matches_per_pand: dict[str, list[ProjectedPanel]],
) -> dict[str, PandInputs]:
    """Collapse the parallel per-pand dicts into a single dict of structs.

    Only panden that appear in at least one of the sources get an
    entry; everyone else falls through to :data:`EMPTY_INPUTS` at
    lookup time.
    """
    ids = {p.identificatie for p in panden}
    ids &= set(resolved_per_pand) | set(solar_matches_per_pand)
    return {
        pid: PandInputs(
            resolved=resolved_per_pand.get(pid, []),
            solar_panels=tuple(solar_matches_per_pand.get(pid, ())),
        )
        for pid in ids
    }


def assembly_worker_count(n_panden: int) -> int:
    """Return the effective worker count, respecting the opt-in env var.

    ``CITYGML_ENERGY_ASSEMBLY_WORKERS`` > 1 enables process parallelism.
    Silently capped at the pand count (no point spawning 16 workers
    for 20 buildings). Returns ``1`` (sequential) on any parsing error
    so a malformed env var never breaks a run.
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


def run_per_pand_build(
    *,
    config: CityBuildConfig,
    panden: list[bag_fetchers.Pand],
    parsed_by_id: dict[str, ParsedBuilding],
    inputs_per_pand: dict[str, PandInputs],
    workers: int,
) -> list[PandArtifacts]:
    """Build the per-Pand artefacts, sequentially or via a worker pool.

    *workers* of ``1`` runs in-process; any value > 1 spawns a
    multiprocessing pool (caller is expected to have already passed
    *workers* through :func:`assembly_worker_count`). Returns the same
    list of :class:`PandArtifacts` records in either case so the caller
    is agnostic to the execution strategy.
    """
    if workers > 1:
        return _build_pand_artifacts_parallel(
            config=config,
            panden=panden,
            parsed_by_id=parsed_by_id,
            inputs_per_pand=inputs_per_pand,
            workers=workers,
        )
    return _build_pand_artifacts_sequential(
        config=config,
        panden=panden,
        parsed_by_id=parsed_by_id,
        inputs_per_pand=inputs_per_pand,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _build_pand_artifacts_sequential(
    *,
    config: CityBuildConfig,
    panden: list[bag_fetchers.Pand],
    parsed_by_id: dict[str, ParsedBuilding],
    inputs_per_pand: dict[str, PandInputs],
) -> list[PandArtifacts]:
    """Sequentially build the per-pand artifacts. Default path."""
    build_context = BuildContext.from_config(config)
    return [
        _build_pand_artifacts(
            pand=pand,
            parsed=parsed_by_id[pand.identificatie],
            inputs=inputs_per_pand.get(pand.identificatie, EMPTY_INPUTS),
            build_context=build_context,
        )
        for pand in panden
        if pand.identificatie in parsed_by_id
    ]


def _build_pand_artifacts_parallel(
    *,
    config: CityBuildConfig,
    panden: list[bag_fetchers.Pand],
    parsed_by_id: dict[str, ParsedBuilding],
    inputs_per_pand: dict[str, PandInputs],
    workers: int,
) -> list[PandArtifacts]:
    """Run the per-pand build in a ``multiprocessing.Pool``.

    Only panden that have matching 3DBAG geometry are dispatched; the
    chunk size is tuned so each worker churns through a reasonable
    batch before hitting the IPC boundary (pickling xsdata Building
    objects back to the main process is the main ongoing cost in this
    path).
    """
    import multiprocessing

    build_context = BuildContext.from_config(config)
    jobs: list[tuple[Any, ...]] = [
        (
            pand,
            parsed_by_id[pand.identificatie],
            inputs_per_pand.get(pand.identificatie, EMPTY_INPUTS),
            build_context,
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
    _LOG.info(
        "Assembly worker pool: %d processes x %d panden/chunk",
        workers,
        chunksize,
    )
    # ``spawn`` is the right start method here: fork-safety with xsdata's
    # lazy registry and requests sessions is not guaranteed, and ``spawn``
    # is the Windows default anyway. The child imports ``citygml_energy``
    # fresh, which warms its bindings cache once per worker.
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        return pool.map(_build_pand_worker, jobs, chunksize=chunksize)


def _build_pand_worker(
    job: tuple[bag_fetchers.Pand, ParsedBuilding, PandInputs, BuildContext],
) -> PandArtifacts:
    """Worker entry point: must be module-level to be picklable on spawn."""
    pand, parsed, inputs, build_context = job
    return _build_pand_artifacts(
        pand=pand,
        parsed=parsed,
        inputs=inputs,
        build_context=build_context,
    )


def _build_pand_artifacts(
    *,
    pand: bag_fetchers.Pand,
    parsed: ParsedBuilding,
    inputs: PandInputs,
    build_context: BuildContext,
) -> PandArtifacts:
    """Build the xsdata artefacts for one Pand.

    The returned :class:`PandArtifacts` carries the minimal slice the
    main process needs to assemble the city model: the xsdata Building
    object, the list of matched addresses, the pre-collected appearance
    target ids, and the flat coordinate sequence used to widen the model
    envelope. All four fields pickle cheaply across the worker-pool
    boundary.

    The five-builder sequence (build_building → attach_building_units →
    apply_bag_year_metadata → apply_eponline_pand_attribution → optional
    attach_solar_collectors) is the canonical orchestration. The builders
    stay individually public so each can be tested in isolation; the
    cross-builder ordering invariants are locked by integration tests
    in ``tests/test_city_pand_executor.py``.
    """
    _merge_attributes(parsed.attributes, pand)
    targets: list[str] = []
    building = build_building(
        parsed,
        build_context,
        surface_targets_out=targets,
    )
    attach_building_units_to_building(building, inputs.resolved, build_context)
    # Building-level year of construction: BAG metadata for
    # bldg:yearOfConstruction, plus the EP-online ``Bouwjaar`` as a
    # gen:intAttribute (with its own Metadata block) when at least one
    # VBO under this Pand has an EP-online label that carries Bouwjaar.
    # Year of construction is structurally a Pand-level fact (one
    # bouwjaar per physical building); the rest of EP-online's
    # classification (Gebouwtype, renewable share, energy metrics) is
    # genuinely per-VBO and lives on each BuildingUnit, attached inside
    # build_building_unit.
    apply_bag_year_metadata_to_building(building)
    apply_eponline_pand_attribution_to_building(building, inputs.resolved)
    if inputs.solar_panels:
        attach_solar_collectors_to_building(
            building,
            list(inputs.solar_panels),
            build_context,
        )
    coords: list[Coord3D] = []
    _collect_coordinates(parsed, coords, lods=build_context.lods)
    _collect_solar_panel_coordinates(inputs.solar_panels, coords)
    _collect_address_coordinates(inputs.resolved, coords)
    return PandArtifacts(
        building=building,
        resolved=inputs.resolved,
        targets=targets,
        coords=coords,
    )


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
    parsed: ParsedBuilding,
    sink: list[Coord3D],
    *,
    lods: tuple[int, ...],
) -> None:
    """Append every vertex of every emitted building polygon to *sink*.

    Restricted to the LoDs the user actually asked for via ``config.lods``;
    ``parsed.geometries`` carries every LoD the 3DBAG tile contains, but
    only the requested ones become ``gml:posList`` entries. Including
    excluded-LoD vertices in the envelope made ``gml:boundedBy`` claim
    Z extents that no emitted coordinate ever reached (e.g. lods=[0] runs
    bounding the LoD 2.2 mesh's roof tips).

    Mirrors the LoD 0 Z-lift the building builder applies (``builders.
    building`` rewrites footprint Z from 3DBAG's nominal 0.001 m to
    ``b3_h_maaiveld``). Without the mirror the envelope picks up the
    input footprint Z, which no emitted posList ever reaches.
    """
    requested = {str(lod) for lod in lods}
    h_maaiveld = _maaiveld_or_none(parsed)
    for lod_key, polygons in parsed.geometries.items():
        if lod_key not in requested:
            continue
        if lod_key == "0" and h_maaiveld is not None:
            for sp in polygons:
                sink.extend((x, y, h_maaiveld) for (x, y, _z) in sp.polygon.exterior)
                for ring in sp.polygon.interiors:
                    sink.extend((x, y, h_maaiveld) for (x, y, _z) in ring)
        else:
            for sp in polygons:
                _extend_polygon_coords(sp, sink)


def _maaiveld_or_none(parsed: ParsedBuilding) -> float | None:
    raw = parsed.attributes.get("b3_h_maaiveld")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _collect_solar_panel_coordinates(
    panels: tuple[ProjectedPanel, ...],
    sink: list[Coord3D],
) -> None:
    """Append every projected solar-panel vertex to *sink*.

    Panels are attached to the building inside this executor regardless of
    the requested 3DBAG LoDs, so their vertices belong in the envelope too.
    Without this the envelope clips just below the panel mounting plane
    (panels sit at roof Z + ``z_offset_m``) and bbox queries silently drop
    the rooftop pixel.
    """
    for panel in panels:
        for poly in panel.lod2_polygons:
            sink.extend(poly.exterior)
            for ring in poly.interiors:
                sink.extend(ring)


def _collect_address_coordinates(
    resolved: list[ResolvedAddress],
    sink: list[Coord3D],
) -> None:
    """Append every BAG VBO address point to *sink*.

    Addresses are emitted as ``gml:MultiPoint`` children of each
    ``bldg:Address`` (see :mod:`builders.address`). BAG ``geometriePunt``
    is 2D, so :func:`gml_builders.build_multi_point` pads Z to 0.0; the
    envelope must include that Z=0 to stay a true bounding box of every
    emitted position element.
    """
    for r in resolved:
        if r.point is None:
            continue
        x, y = r.point
        sink.append((x, y, 0.0))


def _extend_polygon_coords(sp: SemanticPolygon, sink: list[Coord3D]) -> None:
    sink.extend(sp.polygon.exterior)
    for ring in sp.polygon.interiors:
        sink.extend(ring)
