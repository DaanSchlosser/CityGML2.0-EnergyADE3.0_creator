"""Build-extent resolution: the seam between config and the fetch plan.

:func:`resolve_build_extent` turns a :class:`CityBuildConfig` plus a
:class:`CachedSession` into one :class:`BuildExtent`: the rectangular
fetch envelope, the geometry the 3DBAG tile query is clipped to, the BAG
municipality restriction, the resolved gemeente name, an optional
post-fetch boundary polygon, and the set of Panden a query singled out.

The orchestrator resolves the extent once, before any bulk fetch, and
never branches on which kind of extent it is. Two adapters sit behind
the one entry point:

* :func:`_resolve_municipality_extent` for the gemeente family
  (gemeente-only, gemeente + bbox, gemeente + boundary), and
* :func:`_resolve_address_extent` for the free-text address path.

Two adapters make this a real seam rather than indirection. A future
extent kind (a postcode, a cadastral parcel, a hand-drawn polygon, a
list of explicit Pand ids) is a third adapter plus one arm of the
dispatch in :func:`resolve_build_extent`, with no change to the
orchestrator or to :class:`BuildExtent`. If a third kind lands on this
or the painter seam, promoting the dispatch to a small registry (one
entry per kind) is the natural next step.

Shapely is imported lazily inside the helpers, mirroring the rest of the
city pipeline, so the module imports without the optional ``[city]``
extra installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .boundary import load_boundary_polygon
from .config import CityBuildConfig
from .fetchers import municipality as muni_fetchers
from .http import CachedSession

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

_LOG = logging.getLogger(__name__)

Bbox = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class BuildExtent:
    """The resolved geographic area one city build emits, fully described.

    Replaces the positional ``(config, bbox, cbs_code, outline,
    boundary_geom, target_pand_ids)`` tuple the orchestrator used to
    thread around. Every field is total: optionality is expressed by the
    type, never by a ``None`` whose meaning a reader has to recover from
    which branch produced it.

    Attributes:
        bbox: ``(minx, miny, maxx, maxy)`` fetch envelope in EPSG:28992.
        clip_geom: the geometry the 3DBAG tile query is clipped to. The
            gemeente family hands the real municipality outline; the
            address path hands the square box itself. Always a real
            shapely geometry, so no synthetic ``MunicipalityOutline`` is
            fabricated to carry it.
        cbs_code: restricts the BAG Pand / VBO fetch to one gemeente, or
            ``None`` to keep neighbours (the address path nulls it so a
            box near a gemeente border keeps the buildings across the
            line).
        municipality: the resolved gemeente name. ``config.municipality``
            for the gemeente family, the geocoded name for the address
            path. Carried here so :class:`BuildContext` can take it
            without the config ever being mutated.
        boundary_geom: the concave polygon buildings are filtered to
            after the fetch, or ``None`` when no post-fetch filter
            applies.
        target_pand_ids: the BAG Panden a query singled out, empty for
            every non-address extent. :attr:`has_targets` is the single
            switch the painter seam reads; emptiness (not ``None``) is
            the signal, so the field stays total.
    """

    bbox: Bbox
    clip_geom: BaseGeometry
    cbs_code: str | None
    municipality: str
    boundary_geom: BaseGeometry | None = None
    target_pand_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def has_targets(self) -> bool:
        """True when the run singled out Panden (drives the highlight painter)."""
        return bool(self.target_pand_ids)


def resolve_build_extent(config: CityBuildConfig, session: CachedSession) -> BuildExtent:
    """Resolve the build extent before any bulk fetch.

    Dispatches on the config exactly once: an ``address`` block selects
    the address adapter, everything else the gemeente adapter (which
    absorbs the bbox and boundary sub-variants internally). All I/O runs
    through *session*.

    Raises :class:`ValueError` when a gemeente name is unknown
    (gemeente family) or
    :class:`~citygml_energy.city_builder.address_extent.AddressResolutionError`
    when the address query resolves to nothing; neither path adds a new
    failure mode over the code this replaced.
    """
    if config.address_source is not None:
        return _resolve_address_extent(config, session)
    return _resolve_municipality_extent(config, session)


def _resolve_municipality_extent(config: CityBuildConfig, session: CachedSession) -> BuildExtent:
    """Gemeente family: gemeente-only, gemeente + bbox, gemeente + boundary."""
    boundary_geom = _load_boundary(config)
    _LOG.info("Fetching municipality outline: %s", config.municipality)
    outline = muni_fetchers.fetch_municipality_outline(session, name=config.municipality)
    bbox = _resolve_bbox(config, outline=outline, boundary_geom=boundary_geom)
    clip_geom = _outline_to_shapely(outline.feature.get("geometry") or {})
    return BuildExtent(
        bbox=bbox,
        clip_geom=clip_geom,
        cbs_code=outline.cbs_code or None,
        municipality=config.municipality,
        boundary_geom=boundary_geom,
    )


def _resolve_address_extent(config: CityBuildConfig, session: CachedSession) -> BuildExtent:
    """Address path: free-text address to a centred box plus target Panden.

    ``cbs_code`` is ``None`` so a box near a gemeente border keeps its
    neighbours, ``clip_geom`` is the box itself (no fake outline), and
    the gemeente name comes from the geocode when the user did not supply
    one. The config is never mutated; the resolved name rides on
    :attr:`BuildExtent.municipality` and reaches the builders through
    :class:`BuildContext`.
    """
    from .address_extent import resolve_address_extent

    source = config.address_source
    assert source is not None  # caller guards on this
    _LOG.info("Resolving address-driven extent: %r", source.query)
    resolution = resolve_address_extent(session, source.query, extent_m=source.extent_m)
    _LOG.info(
        "Address %r resolved to %d pand(en) over %d address(es); gemeente=%s",
        source.query,
        len(resolution.target_pand_ids),
        resolution.matched_addresses,
        resolution.municipality,
    )
    return BuildExtent(
        bbox=resolution.bbox,
        clip_geom=_box(resolution.bbox),
        cbs_code=None,
        municipality=config.municipality or resolution.municipality or "",
        boundary_geom=None,
        target_pand_ids=resolution.target_pand_ids,
    )


# ---------------------------------------------------------------------------
# Internals (shapely imported lazily, matching the rest of the city pipeline)
# ---------------------------------------------------------------------------


def _load_boundary(config: CityBuildConfig) -> BaseGeometry | None:
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
) -> Bbox:
    """Return the fetch bbox, preferring the boundary polygon when set.

    Resolution order: the boundary polygon's 2D bounds (the pipeline
    later clips builds to the concave polygon itself, so this bbox is
    just the rectangular fetch envelope); else the user-supplied
    ``config.bbox``; else the municipality outline's own bbox.
    """
    if boundary_geom is not None:
        minx, miny, maxx, maxy = boundary_geom.bounds
        return (float(minx), float(miny), float(maxx), float(maxy))
    if config.bbox is not None:
        return config.bbox
    return outline.bbox


def _outline_to_shapely(geometry: dict) -> BaseGeometry:
    try:
        from shapely.geometry import shape
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "City build needs shapely; install with: pip install -e .[city]"
        ) from exc
    return shape(geometry)


def _box(bbox: Bbox) -> BaseGeometry:
    try:
        from shapely.geometry import box as shapely_box
    except ImportError as exc:  # pragma: no cover, optional dep
        raise RuntimeError(
            "City build needs shapely; install with: pip install -e .[city]"
        ) from exc
    return shapely_box(*bbox)
