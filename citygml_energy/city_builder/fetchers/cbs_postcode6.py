"""CBS Postcode6 fetcher: per-postcode dwelling statistics.

Queries PDOK's CBS Postcode6 WFS for the ``postcode6:postcode6`` layer
filtered to the build bbox, returning one :class:`Postcode6Area` per
feature. The dataset is the official CBS *"Statistische gegevens per
postcode"* publication, surfaced by PDOK as a single FeatureType with
~130 demographic / amenity / energy attributes per Dutch 6-position
postcode (PC6).

This fetcher reads only the **two energy fields** that the city
pipeline maps:

* ``gemiddeldGasverbruikWoning`` — gemiddeld jaarverbruik aardgas van
  particuliere woningen, **m³ / jaar / woning**, computed by CBS from
  the energienetbedrijven aansluitingenregister. Includes dwellings on
  stadsverwarming (district heating), which lowers the average for
  postcodes with shared heat networks.
* ``gemiddeldElektriciteitsverbruikWoning`` — same lineage, **kWh /
  jaar / woning**, individuele aansluitingen only. Excludes
  collective consumption (lifts, gallery lighting) and excludes
  self-generated electricity (e.g. from solar panels).

CBS rounds both values to fifties and **suppresses** them when the
postcode area contains fewer than 6 occupied dwellings (privacy rule).
The WFS surfaces the suppression as either ``null`` or one of the
sentinel integers ``-99995`` / ``-99997`` / ``-99999``. The two energy
fields preserve the raw sentinel (CBS's documented "no measurement
here" code rides as the value verbatim, so the downstream
``nrg3:UrbanFunctionArea`` ships an ``nrg3:Energy`` resource for every
postcode and a consumer reading the GML can distinguish "CBS sentinel
-99997" from "CBS shipped a real measurement"). Only ``null`` —
genuinely absent — folds to Python ``None`` and skips the resource
emission. The dwelling-count fields keep the older "any sentinel folds
to None" coercion: a negative dwelling count would be incoherent in a
``gen:intAttribute`` whose semantics is a physical count.

The remaining ~130 columns (demographics, amenity proximities,
educational attainment, etc.) are out of scope: the city pipeline only
emits the energy figures, and pulling extra columns would inflate the
on-disk cache without modelling value.

The fetcher returns a list of :class:`Postcode6Area` records (one per
postcode polygon) with the postcode, the two energy figures, the
dwelling counts (used downstream to flag postcodes near the suppression
threshold), and the 2D polygon geometry as a list of
:class:`citygml_energy._step.GeometryPolygon`. The pipeline clips this
list against the user's boundary polygon before passing the survivors
to the UrbanFunctionArea builder.

Source semantics references:

* CBS Longread *"Statistische gegevens per vierkant en postcode 2022,
  2023, 2024"* (cbs.nl/nl-nl/longread/diversen/2025/...) §4
  Beschrijving cijfers — verbatim definitions and the
  rounded-to-fifties / 6-dwelling suppression rule.
* PDOK CBS Postcode6 dataset metadata page
  (nationaalgeoregister.nl, UUID ed2f2381-873b-4d88-9c55-616e3a78d711) —
  WFS endpoint and licence (CC-BY-4.0).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..._step import GeometryPolygon
from .._helpers import to_clean_str, to_int
from ..http import CachedSession
from ..pdok_wfs import DEFAULT_PAGE_SIZE, paginate_features

__all__ = [
    "CBS_POSTCODE6_WFS_URL_TEMPLATE",
    "Postcode6Area",
    "fetch_postcode6_areas",
    "normalise_postcode",
]

_LOG = logging.getLogger(__name__)

# PDOK serves a year-versioned WFS endpoint; the integer is interpolated
# into the URL at fetch time. The 2024 vintage (current at time of
# writing) covers the 2023 calendar year per CBS's documented one-year
# offset between publication and data scope.
CBS_POSTCODE6_WFS_URL_TEMPLATE: str = "https://service.pdok.nl/cbs/postcode6/{year}/wfs/v1_0"

# WFS layer name and the two energy properties we read. Spelled
# verbatim against the live DescribeFeatureType response (camelCase, not
# snake_case as elsewhere in the project — CBS published the schema
# this way).
_LAYER: str = "postcode6:postcode6"
_F_POSTCODE: str = "postcode6"
_F_GAS: str = "gemiddeldGasverbruikWoning"
_F_ELEC: str = "gemiddeldElektriciteitsverbruikWoning"
_F_AANTAL_WONINGEN: str = "aantalWoningen"
_F_AANTAL_NIET_BEWOOND: str = "aantalNietBewoondeWoningen"

# CBS suppression / placeholder sentinels (CBS Longread §4 Beschrijving
# cijfers, 2025 publication):
#
# * ``-99997`` = "0 tot en met 4 / geheim / niet aanwezig" — fewer than
#   5 dwellings (statistically disclosed), or absent in this vintage.
#   The 6-dwelling privacy rule for the energy fields is enforced
#   inside this branch: an energy figure for a postcode with < 6
#   occupied dwellings is shipped as ``-99997``.
# * ``-99995`` = "Onderwerp wordt in een latere versie gepubliceerd"
#   — field reserved in this vintage, will be filled in a later
#   release. Empirically the 2024 vintage ships every energy value as
#   ``-99995`` because CBS has not yet published energy data for that
#   vintage (publication runs ~1 year behind the dataset's nominal
#   year).
# * ``-99999`` is also reserved by CBS for unknown values across
#   sister datasets; treating it as a sentinel keeps the fetcher
#   forward-compatible.
#
# Energy / dwelling counts are physical totals that are positive by
# construction (negative consumption is meaningless), so a single
# threshold subsumes the whole sentinel block without admitting any
# plausible real measurement. ``-99000`` is comfortably below the
# entire ``-99995`` … ``-99999`` block and well above any real
# rounded-to-50 figure CBS publishes.
_SUPPRESSION_THRESHOLD: int = -99000

# Bbox subdivision is deliberately NOT used here: a single municipality
# tops out at ~30 k PC6 polygons (well below PDOK's ~50 k startIndex
# cap), and the city pipeline's bbox is always a fraction of one
# municipality. Pagination alone is enough.
_PAGE_SIZE: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, slots=True)
class Postcode6Area:
    """One CBS Postcode6 area with its energy aggregates and polygon.

    Attributes:
        postcode: 6-character Dutch postcode (e.g. ``"7881AD"``), with
            no whitespace and uppercase letters. The CBS WFS already
            ships the value in this canonical form; the parser
            normalises defensively in case a future vintage drifts.
        gemiddeld_gasverbruik_woning: average annual natural-gas
            consumption per occupied private dwelling in this postcode,
            in m³/year, rounded to nearest 50. CBS-shipped sentinels
            (``-99995`` / ``-99997`` / ``-99999`` — see module docstring
            for the definitions) are preserved verbatim so the value
            survives into ``nrg3:Energy/amount`` as the literal CBS
            datum. ``None`` only when the WFS shipped no value at all
            (``null`` / missing).
        gemiddeld_elektriciteitsverbruik_woning: same shape, kWh/year,
            individual connections only (excludes collective and
            self-generated electricity, e.g. from solar panels). Same sentinel-vs-null contract as the
            gas field.
        aantal_woningen: total dwellings registered in BAG for the
            postcode. ``None`` when missing. Surfaced for the builder
            so `nrg3:UrbanFunctionArea` can carry the dwelling count
            as context alongside the suppressed-or-not energy values.
        aantal_niet_bewoonde_woningen: vacant-dwelling count. ``None``
            when missing. The CBS suppression rule is *occupied*
            dwellings, so a postcode with high vacancy can carry
            suppressed energy values even when ``aantal_woningen`` is
            well above the 6-dwelling threshold.
        polygons: 2D polygon geometry of the postcode area, in
            EPSG:28992. Always at least one polygon; CBS occasionally
            ships disjoint MultiPolygon for fragmented postcodes (e.g.
            an island plus its mainland sliver), in which case every
            ring is materialised as its own
            :class:`GeometryPolygon` with z = 0.
    """

    postcode: str
    gemiddeld_gasverbruik_woning: int | None
    gemiddeld_elektriciteitsverbruik_woning: int | None
    aantal_woningen: int | None
    aantal_niet_bewoonde_woningen: int | None
    polygons: list[GeometryPolygon] = field(default_factory=list)


Bbox = tuple[float, float, float, float]


def fetch_postcode6_areas(
    session: CachedSession,
    *,
    bbox: Bbox,
    year: int,
) -> list[Postcode6Area]:
    """Fetch every CBS Postcode6 record whose polygon intersects *bbox*.

    *year* selects the WFS endpoint (CBS publishes one URL per
    publication year; vintages 2022, 2023, 2024 are currently live).
    The fetcher does not validate the year against the live PDOK
    catalogue: an invalid year surfaces as a 404 from the WFS, which
    :class:`CachedSession` re-raises with the URL attached so the
    caller can correct the config.

    Returns the deduplicated record list (postcode is the dedup key;
    PDOK has been observed to ship the same feature twice when a
    postcode straddles a tile boundary in their internal index).
    """
    url = CBS_POSTCODE6_WFS_URL_TEMPLATE.format(year=year)
    features = _fetch_layer(session, url, bbox=bbox, year=year)
    areas: list[Postcode6Area] = []
    seen: set[str] = set()
    for feature in features:
        props = feature.get("properties") or {}
        postcode = normalise_postcode(props.get(_F_POSTCODE))
        if postcode is None:
            continue
        if postcode in seen:
            # PDOK has been observed to return duplicates on tile
            # boundary straddles. First occurrence wins, matching the
            # BAG fetcher's dedup semantics.
            continue
        seen.add(postcode)

        polygons = _extract_polygons(feature.get("geometry"))
        if not polygons:
            # Suppressed-geometry features are useless to a downstream
            # builder that needs to emit a polygon: skip rather than
            # synthesise a zero-area placeholder.
            _LOG.debug("CBS Postcode6 %s has no polygon geometry; skipping", postcode)
            continue

        areas.append(
            Postcode6Area(
                postcode=postcode,
                gemiddeld_gasverbruik_woning=_int_preserve_sentinel(props.get(_F_GAS)),
                gemiddeld_elektriciteitsverbruik_woning=_int_preserve_sentinel(props.get(_F_ELEC)),
                aantal_woningen=_value_or_suppressed(props.get(_F_AANTAL_WONINGEN)),
                aantal_niet_bewoonde_woningen=_value_or_suppressed(
                    props.get(_F_AANTAL_NIET_BEWOOND)
                ),
                polygons=polygons,
            )
        )
    return areas


def normalise_postcode(value: Any) -> str | None:
    """Return a CBS-canonical postcode (``"NNNNAA"``) or ``None``.

    CBS already ships the canonical form; this helper mostly defends
    against future drift (mixed-case letters, embedded whitespace) so a
    schema change does not silently produce postcodes that don't
    round-trip with BAG's ``postcode`` field on the VBO.
    """
    text = to_clean_str(value)
    if text is None:
        return None
    cleaned = "".join(text.split()).upper()
    # 4 digits + 2 letters is the only valid PC6 shape; anything else is
    # corrupt and would join to nothing on the BAG side anyway.
    if len(cleaned) != 6 or not cleaned[:4].isdigit() or not cleaned[4:].isalpha():
        _LOG.warning("CBS Postcode6 value not in NNNNAA shape (%r)", value)
        return None
    return cleaned


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _value_or_suppressed(value: Any) -> int | None:
    """Coerce a CBS count field to ``int`` or ``None`` (suppressed).

    Treats ``None`` / ``""`` as suppressed, casts through float so a
    rare ``"1850.0"`` string round-trips, and folds any negative
    value at-or-below :data:`_SUPPRESSION_THRESHOLD` into ``None``
    (CBS uses several distinct negative sentinels — ``-99995``,
    ``-99997``, ``-99999`` — for different suppression reasons; the
    threshold subsumes the whole documented block without admitting
    any plausible real measurement). A genuine zero survives as
    ``0``, but that is exceedingly unlikely on a populated PC6 (CBS
    rounds to 50).

    Used for the dwelling-count fields (``aantalWoningen``,
    ``aantalNietBewoondeWoningen``), where a negative value is
    physically incoherent and the downstream ``gen:intAttribute``
    would carry a meaningless number. The two energy fields take a
    different path via :func:`_int_preserve_sentinel`: their CBS
    sentinel rides into ``nrg3:Energy/amount`` verbatim so the
    downstream consumer can tell "CBS sentinel" from "CBS shipped a
    real measurement" by inspecting the value, without needing the
    fetcher to make that call for them.
    """
    coerced = to_int(value, logger=_LOG, label="CBS Postcode6")
    if coerced is None:
        return None
    if coerced <= _SUPPRESSION_THRESHOLD:
        return None
    return coerced


def _int_preserve_sentinel(value: Any) -> int | None:
    """Coerce a CBS energy field to ``int`` or ``None`` (genuinely missing).

    Mirrors :func:`_value_or_suppressed`'s null/empty/coercion
    handling but does **not** collapse the documented CBS sentinel
    block ``-99995`` / ``-99997`` / ``-99999`` to ``None``. The raw
    CBS value rides through and lands on ``nrg3:Energy/amount``
    verbatim, so a downstream consumer can distinguish the three
    sentinel meanings (privacy-suppressed vs. deferred publication
    vs. unknown) — and from a real positive measurement — by reading
    the amount itself. Only ``None`` / ``""`` (the WFS shipped no
    value at all) folds to ``None`` and triggers a "no resource
    emitted" path in the builder.
    """
    return to_int(value, logger=_LOG, label="CBS Postcode6")


def _fetch_layer(
    session: CachedSession,
    url: str,
    *,
    bbox: Bbox,
    year: int,
) -> list[dict[str, Any]]:
    """Paginate through the CBS Postcode6 layer for *bbox*.

    The CBS vintage year folds into the cache prefix so two builds
    against different vintages (e.g. 2023 vs. 2024) do not share
    on-disk cache entries: the underlying postcode polygons drift
    slightly year-over-year and CBS occasionally re-aggregates a row.
    """
    return paginate_features(
        session,
        url,
        type_names=_LAYER,
        cache_prefix=f"cbs_postcode6.{year}",
        bbox=bbox,
        page_size=_PAGE_SIZE,
    )


def _extract_polygons(geometry: Any) -> list[GeometryPolygon]:
    """Convert a GeoJSON geometry into a list of :class:`GeometryPolygon`.

    CBS ships ``Polygon`` for the common case and ``MultiPolygon`` for
    fragmented postcodes. Each ring is read with z = 0 (the WFS does
    not publish elevation; the polygons are 2D administrative
    boundaries). Any other geometry type is logged and dropped — the
    pipeline cannot emit a non-polygon UrbanFunctionArea, and a single
    bad feature must not fail the whole fetch.
    """
    if not isinstance(geometry, dict):
        return []
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Polygon":
        if not isinstance(coords, list):
            return []
        polygon = _polygon_from_rings(coords)
        return [polygon] if polygon is not None else []
    if kind == "MultiPolygon":
        if not isinstance(coords, list):
            return []
        out: list[GeometryPolygon] = []
        for sub in coords:
            polygon = _polygon_from_rings(sub)
            if polygon is not None:
                out.append(polygon)
        return out
    _LOG.warning("CBS Postcode6 geometry type %r not supported", kind)
    return []


def _polygon_from_rings(rings: Any) -> GeometryPolygon | None:
    """Build a :class:`GeometryPolygon` from GeoJSON ring coordinates.

    GeoJSON Polygon coordinates are ``[exterior, *holes]``. Each ring
    is a list of ``[x, y]`` pairs (the WFS may also emit ``[x, y, z]``
    on some vintages; the third value is honoured if present, else
    ``z = 0``). Degenerate rings (< 3 vertices, fewer dimensions than
    expected) collapse to ``None`` so they don't make it into the
    output as zero-area artefacts.
    """
    if not isinstance(rings, list) or not rings:
        return None
    exterior = _ring_to_coords(rings[0])
    if exterior is None:
        return None
    interiors: list[list[tuple[float, float, float]]] = []
    for hole_ring in rings[1:]:
        hole = _ring_to_coords(hole_ring)
        if hole is not None:
            interiors.append(hole)
    return GeometryPolygon(exterior=exterior, interiors=interiors)


def _ring_to_coords(ring: Any) -> list[tuple[float, float, float]] | None:
    if not isinstance(ring, list) or len(ring) < 3:
        return None
    out: list[tuple[float, float, float]] = []
    for pt in ring:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            return None
        try:
            x = float(pt[0])
            y = float(pt[1])
        except (TypeError, ValueError):
            return None
        z = 0.0
        if len(pt) >= 3:
            try:
                z = float(pt[2])
            except (TypeError, ValueError):
                z = 0.0
        out.append((x, y, z))
    return out
