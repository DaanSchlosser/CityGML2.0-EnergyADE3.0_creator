"""BAG fetchers: Pand and Verblijfsobject.

Query strategy: request each layer with a bounding-box filter and
paginate. PDOK caps a WFS GetFeature at ``startIndex`` 50 000 (a request
past it returns HTTP 400 with the text "It is not possible to use a
'startindex' higher than 50.000"), so a city with more panden than that
cannot be walked in one bbox. We ask the server how many features the
bbox holds first (a cheap ``resultType=hits`` probe) and, when that
exceeds the window, subdivide the bbox into four quadrants and recurse
*before* spending a doomed deep walk. A reactive fallback still catches
the 400 (and a near-cap page count when the probe is unavailable) so the
walk degrades gracefully rather than crashing.

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

import requests

from .._helpers import to_clean_str, to_float, to_int
from ..http import CachedSession
from ..pdok_wfs import DEFAULT_PAGE_SIZE, count_matched_features, paginate_features

_LOGGER = logging.getLogger(__name__)

BAG_WFS_URL = "https://service.pdok.nl/lv/bag/wfs/v2_0"
BAG_PAGE_SIZE = DEFAULT_PAGE_SIZE
# PDOK rejects ``startIndex`` higher than 50 000. With BAG_PAGE_SIZE=1000 the
# deepest valid page (startIndex=50000) still reads rows 50000-50999, so up to
# ~51 000 features are reachable; subdividing once the match count passes
# 50 000 keeps a comfortable margin below that hard wall.
BAG_MAX_FETCHABLE = 50_000
# Reactive fallback only (used when the hits probe is unavailable): a completed
# walk that returns at least this many features may have silently truncated at
# the server window, so split and re-fetch to be safe. Generous so small cities
# never bother.
BAG_SUBDIVIDE_THRESHOLD = 40_000
# Depth limit so a pathological layer cannot recurse forever: 4**6 = 4096 leaf
# quadrants is far more than any Dutch municipality needs.
BAG_MAX_SUBDIVIDE_DEPTH = 6


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
    single rectangle would cross PDOK's 50 k ``startIndex`` cap.
    Subdivision is depth-limited (:data:`BAG_MAX_SUBDIVIDE_DEPTH`) so a
    pathological layer cannot recurse forever.

    The primary guard is proactive: :func:`count_matched_features` asks
    the server (one ``resultType=hits`` round trip) how many features the
    bbox holds, and we split *before* walking when that exceeds
    :data:`BAG_MAX_FETCHABLE`. This is what keeps a > 50 k-pand city
    (Delft, Groningen, Zwolle) from ever issuing the doomed
    ``startIndex=51000`` request.

    Two reactive fallbacks remain for when the hits probe is unavailable
    or under-counts: (a) PDOK returns HTTP 400 once a page crosses the
    cap -- its OWS ExceptionReport puts the cap message in the
    ``ExceptionText`` (with a misleading ``locator="typename"``), which
    :func:`_is_startindex_cap_error` recognises -- and (b) a completed
    walk that returns at least :data:`BAG_SUBDIVIDE_THRESHOLD` features
    may have truncated, so we split it. Any other 400 (malformed CRS, bad
    type name, server-config error) is re-raised so an authoring or
    upstream bug surfaces immediately rather than being masked by silent
    retries.
    """
    matched = count_matched_features(
        session,
        BAG_WFS_URL,
        type_names=layer,
        cache_prefix=layer,
        bbox=bbox,
    )
    if matched is not None and matched > BAG_MAX_FETCHABLE and _depth < BAG_MAX_SUBDIVIDE_DEPTH:
        _LOGGER.info(
            "BAG %s: %d features in bbox %s exceed the %d WFS window; subdividing",
            layer,
            matched,
            bbox,
            BAG_MAX_FETCHABLE,
        )
        return _subdivide(session, layer, bbox, depth=_depth + 1)

    try:
        features = paginate_features(
            session,
            BAG_WFS_URL,
            type_names=layer,
            cache_prefix=layer,
            bbox=bbox,
            page_size=BAG_PAGE_SIZE,
        )
    except requests.HTTPError as exc:
        if (
            exc.response is not None
            and exc.response.status_code == 400
            and _depth < BAG_MAX_SUBDIVIDE_DEPTH
            and _is_startindex_cap_error(exc.response)
        ):
            _LOGGER.info(
                "BAG %s: PDOK startindex-cap 400 on bbox %s; subdividing",
                layer,
                bbox,
            )
            return _subdivide(session, layer, bbox, depth=_depth + 1)
        raise

    # Fallback when the hits probe was unavailable (``matched is None``): a
    # walk at or above the threshold may have silently truncated at the
    # server window, so split and re-fetch. When ``matched`` is known and
    # under the cap the walk is complete by construction, so we trust it
    # and skip this re-split.
    if (
        matched is None
        and len(features) >= BAG_SUBDIVIDE_THRESHOLD
        and _depth < BAG_MAX_SUBDIVIDE_DEPTH
    ):
        return _subdivide(session, layer, bbox, depth=_depth + 1)
    return features


def _is_startindex_cap_error(response: requests.Response) -> bool:
    """Return ``True`` iff *response* is PDOK's ``startIndex`` cap 400.

    PDOK returns an OGC OWS Common ExceptionReport on 400. The real cap
    response is::

        <ows:Exception exceptionCode="InvalidParameterValue" locator="typename">
          <ows:ExceptionText>It is not possible to use a 'startindex'
            higher than 50.000. …</ows:ExceptionText>
        </ows:Exception>

    so the ``@locator`` is the misleading ``"typename"``, not
    ``"startIndex"`` -- matching on the locator alone (the original
    implementation) missed the real error and let the 400 crash the
    build. We recognise the cap two ways, both scoped to any element
    whose local name is ``Exception`` (the OWS namespace varies across
    versions and PDOK does not pin one):

    * ``@locator == "startIndex"`` -- a spec-clean server, kept so a
      future PDOK fix or another WFS still matches; or
    * an ``InvalidParameterValue`` exception whose text names the
      ``startindex`` *and* the "higher than" cap. Requiring both tokens
      keeps this from false-positiving on a 400 that merely mentions
      startIndex in passing (e.g. "the filter is wrong; startIndex is
      fine"), which would otherwise trigger silent quadrant retries
      before an authoring bug surfaced.

    Any response that fails to parse as XML (binary, empty, truncated)
    is treated as "not a cap error" so the caller re-raises and the
    upstream bug surfaces immediately rather than being masked.
    """
    try:
        body = response.content
    except AttributeError:
        return False
    if not body:
        return False
    try:
        # Local import keeps the BAG fetcher module-import-cheap for the
        # non-error path; ET is the conventional ElementTree alias.
        import lxml.etree as ET  # noqa: N812

        root = ET.fromstring(
            body, parser=ET.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        )
    except ET.XMLSyntaxError:
        return False
    for exc in root.iter():
        # Match any element whose local name is ``Exception``; the OWS
        # namespace varies across versions and PDOK does not pin one.
        if ET.QName(exc.tag).localname != "Exception":
            continue
        if (exc.get("locator") or "").strip() == "startIndex":
            return True
        if (exc.get("exceptionCode") or "").strip() == "InvalidParameterValue":
            # itertext() is typed str | bytes in lxml-stubs; text nodes are str.
            text = " ".join(t for t in exc.itertext() if isinstance(t, str)).lower()
            if "startindex" in text and "higher than" in text:
                return True
    return False


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
