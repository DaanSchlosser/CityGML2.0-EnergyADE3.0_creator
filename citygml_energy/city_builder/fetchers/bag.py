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

import requests

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

    PDOK enforces the 50 k cap in two ways: (a) a full bbox returns
    exactly 50 000 features and silently truncates, which the post-walk
    threshold below catches; (b) a request with ``startIndex >= 51000``
    returns HTTP 400 with an OWS ExceptionReport whose body names the
    ``startIndex`` parameter. We catch the cap variant here too and
    recurse into quadrants — without this, a city with > 50 k panden
    (Delft, Groningen, Zwolle) would crash on page 51 before the
    threshold check ever ran. Any other 400 (malformed CRS, bad type
    name, server-config error) is re-raised so an authoring or
    upstream bug surfaces immediately rather than being masked by
    4^6 = 4096 silent retries.
    """
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
            and _depth < 6
            and _is_startindex_cap_error(exc.response)
        ):
            _LOGGER.info(
                "BAG %s: PDOK 400 at startIndex cap on bbox %s; subdividing",
                layer,
                bbox,
            )
            return _subdivide(session, layer, bbox, depth=_depth + 1)
        raise
    if len(features) >= BAG_SUBDIVIDE_THRESHOLD and _depth < 6:
        return _subdivide(session, layer, bbox, depth=_depth + 1)
    return features


def _is_startindex_cap_error(response: requests.Response) -> bool:
    """Return ``True`` iff *response* is a PDOK OWS ExceptionReport
    that names ``startIndex`` as the offending parameter.

    PDOK returns an OGC OWS Common ExceptionReport on 400. The cap
    error surfaces as ``<ows:Exception exceptionCode="InvalidParameterValue"
    locator="startIndex">…</ows:Exception>``; other 400s (bad CRS,
    unknown type name, malformed filter) carry a different ``@locator``
    or ``@exceptionCode``. We match on the ``@locator`` attribute of
    any ``Exception`` element, ignoring its XML namespace so OWS 1.0,
    1.1, and 2.0 namespace variants all resolve the same way. The
    attribute check is intentionally stricter than a body-substring
    sniff: a 400 whose human-readable text mentions ``startIndex`` in
    passing (e.g. "the filter is wrong; startIndex is fine") would
    false-positive a substring match and trigger 4^6 silent quadrant
    retries before the underlying authoring bug surfaced.

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
        import lxml.etree as ET  # local import: keeps the BAG fetcher
        # module-import-cheap for the non-error path.
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
