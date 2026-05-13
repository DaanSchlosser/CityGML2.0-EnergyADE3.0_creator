"""BAG fetchers: Pand and Verblijfsobject.

Query strategy: request each layer with a bounding-box filter and
paginate. If a page is suspiciously close to the WFS ``startIndex``
ceiling (PDOK caps server-side at ~50 k) we subdivide the bbox into
four quadrants and recurse.

The PDOK BAG WFS v2.0 exposes: ``bag:pand``, ``bag:verblijfsobject``,
``bag:ligplaats``, ``bag:standplaats``, ``bag:woonplaats``. There are no
``nummeraanduiding`` or ``openbareruimte`` layers, those are joined into
each VBO by the WFS so address data (postcode, huisnummer, street) is
available directly on the VBO feature.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .._helpers import to_clean_str, to_float, to_int
from ..http import CachedSession
from ..pdok_wfs import DEFAULT_PAGE_SIZE, paginate_features

_LOGGER = logging.getLogger(__name__)

BAG_WFS_URL = "https://service.pdok.nl/lv/bag/wfs/v2_0"
BAG_PAGE_SIZE = DEFAULT_PAGE_SIZE
# PDOK's GetFeature hard-caps around 50 000; subdivide when we cross this
# threshold on a single bbox. Very generous so small cities never bother.
BAG_SUBDIVIDE_THRESHOLD = 40_000


@dataclass(frozen=True)
class Pand:
    """A BAG Pand (building polygon + status + construction year)."""

    identificatie: str
    bouwjaar: int | None
    status: str | None
    properties: dict[str, Any]


@dataclass(frozen=True)
class Verblijfsobject:
    """A BAG Verblijfsobject (VBO): an addressable unit inside a Pand.

    Address fields (postcode, huisnummer, etc.) are populated directly
    from the PDOK WFS VBO feature: the WFS joins Nummeraanduiding and
    OpenbareRuimte into each VBO response, so no separate fetches are
    required.

    ``point`` is the BAG ``geometriePunt``: BAG's authoritative
    address-locating point for this VBO (``(x, y)`` in RD New /
    EPSG:28992). It always lies within the parent Pand but is *not*
    guaranteed to be the entrance; CityGML's ``core:Address/multiPoint``
    XSD annotation recommends entrance points but does not constrain the
    MultiPoint semantically, so BAG's verblijfsobjectpunt is a valid
    and standard fill for it. ``None`` when the WFS feature arrived
    without a geometry (rare but possible for legacy records).
    """

    identificatie: str
    pand_identificatie: str
    gebruiksdoel: list[str]
    oppervlakte: float | None
    status: str | None
    postcode: str | None
    huisnummer: int | None
    huisletter: str | None
    toevoeging: str | None
    openbare_ruimte_naam: str | None
    woonplaats: str | None
    point: tuple[float, float] | None
    properties: dict[str, Any]


Bbox = tuple[float, float, float, float]


# ---------------------------------------------------------------------------
# Public fetchers
# ---------------------------------------------------------------------------


def fetch_panden(
    session: CachedSession,
    *,
    bbox: Bbox,
    cbs_code: str | None = None,
) -> list[Pand]:
    """Return every Pand whose centroid lies inside *bbox*.

    *cbs_code* (if given) filters to BAG ``identificatie`` values that
    start with that code, exactly the BAG convention for the 4-digit
    municipality prefix.

    Results are deduplicated by ``identificatie`` (first occurrence wins).
    The PDOK BAG WFS does not guarantee a stable ordering across
    paginated GetFeature requests, and the bbox subdivision fallback
    re-queries quadrants whose geometries can overlap on the shared
    midpoint lines, so the same Pand can appear in multiple raw
    responses. Letting duplicates through produces ``<bldg:Building>``
    elements with colliding ``gml:id``s downstream, which breaks
    ``<app:target>`` xlink resolution in viewers.
    """
    records = _fetch_layer(session, "bag:pand", bbox=bbox)
    panden: list[Pand] = []
    seen: set[str] = set()
    for feature in records:
        props = feature.get("properties") or {}
        identificatie = str(props.get("identificatie") or "").strip()
        if not identificatie:
            continue
        if cbs_code and not identificatie.startswith(cbs_code):
            continue
        if identificatie in seen:
            continue
        seen.add(identificatie)
        panden.append(
            Pand(
                identificatie=identificatie,
                bouwjaar=_as_int(props.get("bouwjaar") or props.get("oorspronkelijkBouwjaar")),
                status=_optional_str(props.get("status")),
                properties=props,
            )
        )
    return panden


def fetch_verblijfsobjecten(
    session: CachedSession,
    *,
    bbox: Bbox,
    cbs_code: str | None = None,
) -> list[Verblijfsobject]:
    """Return every VBO whose centroid lies inside *bbox*.

    Address fields (postcode, huisnummer, street name) are read directly
    from the WFS feature: the PDOK BAG WFS already joins Nummeraanduiding
    and OpenbareRuimte into each VBO response.

    Results are deduplicated by ``identificatie`` (first occurrence wins);
    see :func:`fetch_panden` for the rationale.
    """
    records = _fetch_layer(session, "bag:verblijfsobject", bbox=bbox)
    vbos: list[Verblijfsobject] = []
    seen: set[str] = set()
    for feature in records:
        props = feature.get("properties") or {}
        identificatie = str(props.get("identificatie") or "").strip()
        # BAG WFS can return a comma-separated list when a VBO spans multiple
        # panden (e.g. a flat above a garage registered as two panden). Take
        # the first; it is the primary registration pand.
        pand_id_raw = str(
            props.get("pandidentificatie") or props.get("pand_identificatie") or ""
        ).strip()
        pand_id = pand_id_raw.split(",")[0].strip()
        if not identificatie or not pand_id:
            continue
        if cbs_code and not identificatie.startswith(cbs_code):
            continue
        if identificatie in seen:
            continue
        seen.add(identificatie)
        gebruiksdoel = props.get("gebruiksdoel") or []
        if isinstance(gebruiksdoel, str):
            gebruiksdoel = [gebruiksdoel]
        vbos.append(
            Verblijfsobject(
                identificatie=identificatie,
                pand_identificatie=pand_id,
                gebruiksdoel=[str(g) for g in gebruiksdoel],
                oppervlakte=_as_float(props.get("oppervlakte")),
                status=_optional_str(props.get("status")),
                postcode=_optional_str(props.get("postcode")),
                huisnummer=_as_int(props.get("huisnummer")),
                huisletter=_optional_str(props.get("huisletter")),
                toevoeging=_optional_str(
                    # PDOK WFS shortens IMBAG's ``huisnummertoevoeging`` to
                    # ``toevoeging``; the long form is what BAG-as-LD and
                    # the BAG Extract use, so we look at both for forward
                    # compatibility against schema variants.
                    props.get("toevoeging") or props.get("huisnummertoevoeging")
                ),
                openbare_ruimte_naam=_optional_str(props.get("openbare_ruimte")),
                # ``woonplaats`` is the IMBAG-canonical locality component
                # of a Dutch BAG address: a woonplaats can span multiple
                # gemeentes and a gemeente can contain multiple
                # woonplaatsen (e.g. gemeente Emmen contains the
                # woonplaatsen Emmen, Klazienaveen, Nieuw-Amsterdam, …).
                # PDOK joins it onto every VBO; we surface it here so the
                # address builder doesn't have to fall back to a single
                # caller-provided ``city_name`` argument that loses this
                # within-municipality resolution.
                woonplaats=_optional_str(props.get("woonplaats")),
                point=extract_point(feature.get("geometry")),
                properties=props,
            )
        )
    return vbos


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_layer(
    session: CachedSession,
    layer: str,
    *,
    bbox: Bbox,
    _depth: int = 0,
) -> list[dict[str, Any]]:
    """Paginate through every feature in *layer* inside *bbox*.

    Delegates the WFS 2.0 page walk to
    :func:`citygml_energy.city_builder.pdok_wfs.paginate_features`; the
    BAG-specific concern this wrapper adds is bbox subdivision when a
    single rectangle would cross PDOK's ~50 k startIndex cap. Subdivision
    is depth-limited so a pathological layer cannot recurse forever.
    """
    features = paginate_features(
        session,
        BAG_WFS_URL,
        type_names=layer,
        cache_prefix=layer,
        bbox=bbox,
        page_size=BAG_PAGE_SIZE,
    )
    # PDOK silently truncates a single bbox past ~50 k features. When we
    # hit a result that *could* have been truncated -- a full sweep that
    # ran right up against the soft ceiling -- recurse into quadrants so
    # the missing rows are recoverable. Subdivision is depth-limited
    # because a degenerate input (zero-width bbox, server bug) must not
    # recurse forever.
    if len(features) >= BAG_SUBDIVIDE_THRESHOLD and _depth < 6:
        return _subdivide(session, layer, bbox, depth=_depth + 1)
    return features


def _subdivide(
    session: CachedSession,
    layer: str,
    bbox: Bbox,
    *,
    depth: int,
) -> list[dict[str, Any]]:
    (minx, miny, maxx, maxy) = bbox
    midx = (minx + maxx) / 2
    midy = (miny + maxy) / 2
    quadrants: list[Bbox] = [
        (minx, miny, midx, midy),
        (midx, miny, maxx, midy),
        (minx, midy, midx, maxy),
        (midx, midy, maxx, maxy),
    ]
    out: list[dict[str, Any]] = []
    for q in quadrants:
        out.extend(_fetch_layer(session, layer, bbox=q, _depth=depth))
    return out


def extract_point(geometry: Any) -> tuple[float, float] | None:
    """Return the ``(x, y)`` of a GeoJSON Point geometry, or ``None``.

    PDOK BAG WFS returns VBO geometries as GeoJSON ``Point`` features
    (EPSG:28992 when ``srsName=EPSG:28992`` is requested). Non-Point
    geometries and missing/malformed features are ignored: the caller
    treats ``None`` as "no point available for this VBO".
    """
    if not isinstance(geometry, dict):
        return None
    if geometry.get("type") != "Point":
        return None
    coords = geometry.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None
    try:
        return (float(coords[0]), float(coords[1]))
    except (TypeError, ValueError) as exc:
        _LOGGER.warning("BAG Point coordinates not numeric (%r): %s", coords, exc)
        return None


def _as_int(value: Any) -> int | None:
    """BAG-tagged shim around :func:`_helpers.to_int`.

    Kept as a thin wrapper so the warning log message keeps its
    historical ``"BAG integer field …"`` prefix without forcing every
    call site to repeat the label.
    """
    return to_int(value, logger=_LOGGER, label="BAG")


def _as_float(value: Any) -> float | None:
    """BAG-tagged shim around :func:`_helpers.to_float`."""
    return to_float(value, logger=_LOGGER, label="BAG")


def _optional_str(value: Any) -> str | None:
    """Strip-or-``None`` (BAG flavour: literal ``"None"`` is NOT dropped).

    BAG's WFS rarely ships the literal placeholder, but if it ever does
    we want to surface it rather than silently swallow it; that behaviour
    differs from :data:`_helpers.to_clean_str` with
    ``drop_literal_none=True``, which is the right behaviour for Emmen's
    ArcGIS layer.
    """
    return to_clean_str(value)
