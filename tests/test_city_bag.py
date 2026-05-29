"""Unit tests for the BAG WFS fetchers in :mod:`city_builder.fetchers.bag`.

These tests stub :func:`_fetch_layer` to feed deterministic raw WFS
features into :func:`fetch_panden` / :func:`fetch_verblijfsobjecten`,
which lets us cover the post-fetch transform in isolation: the cbs_code
filter, the multi-pand ``pandidentificatie`` split, and the dedup that
guards against pagination/subdivision overlap.
"""

from __future__ import annotations

from typing import Any

import pytest

from citygml_energy.city_builder.fetchers import bag as bag_fetchers


def _pand_feature(identificatie: str, bouwjaar: int = 1990) -> dict[str, Any]:
    return {
        "properties": {
            "identificatie": identificatie,
            "bouwjaar": bouwjaar,
            "status": "Pand in gebruik",
        }
    }


def _vbo_feature(identificatie: str, pand_id: str, *, postcode: str = "2611AA") -> dict[str, Any]:
    return {
        "properties": {
            "identificatie": identificatie,
            "pandidentificatie": pand_id,
            "gebruiksdoel": ["woonfunctie"],
            "postcode": postcode,
            "huisnummer": 1,
        },
        "geometry": {"type": "Point", "coordinates": [85000.0, 446500.0]},
    }


def test_fetch_panden_dedupes_repeated_identificatie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Pand returned twice by paginated WFS must collapse to one row.

    PDOK BAG WFS does not promise a stable pagination order, and the
    bbox subdivision fallback re-queries quadrants whose geometries can
    overlap on the shared midpoint lines. Letting duplicates through
    yields ``<bldg:Building>`` elements with colliding ``gml:id``s,
    which silently breaks ``<app:target>`` xlink resolution downstream.
    """
    raw = [
        _pand_feature("0503100000000001"),
        _pand_feature("0503100000000002"),
        _pand_feature("0503100000000001"),  # duplicate of #1
    ]
    monkeypatch.setattr(
        bag_fetchers,
        "_fetch_layer",
        lambda session, layer, *, bbox: raw,
    )
    panden = bag_fetchers.fetch_panden(
        session=None,  # type: ignore[arg-type]
        bbox=(0.0, 0.0, 1.0, 1.0),
        cbs_code="0503",
    )
    ids = [p.identificatie for p in panden]
    assert ids == ["0503100000000001", "0503100000000002"]


def test_fetch_verblijfsobjecten_dedupes_repeated_identificatie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same dedup invariant on the VBO layer (where subdivision actually
    fires for typical city-sized bboxes)."""
    raw = [
        _vbo_feature("0503010000000001", "0503100000000001"),
        _vbo_feature("0503010000000002", "0503100000000001"),
        _vbo_feature("0503010000000001", "0503100000000001"),
    ]
    monkeypatch.setattr(
        bag_fetchers,
        "_fetch_layer",
        lambda session, layer, *, bbox: raw,
    )
    vbos = bag_fetchers.fetch_verblijfsobjecten(
        session=None,  # type: ignore[arg-type]
        bbox=(0.0, 0.0, 1.0, 1.0),
        cbs_code="0503",
    )
    ids = [v.identificatie for v in vbos]
    assert ids == ["0503010000000001", "0503010000000002"]


def test_fetch_panden_cbs_code_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = [
        _pand_feature("0503100000000001"),
        _pand_feature("0344100000000001"),  # different municipality
    ]
    monkeypatch.setattr(
        bag_fetchers,
        "_fetch_layer",
        lambda session, layer, *, bbox: raw,
    )
    panden = bag_fetchers.fetch_panden(
        session=None,  # type: ignore[arg-type]
        bbox=(0.0, 0.0, 1.0, 1.0),
        cbs_code="0503",
    )
    assert [p.identificatie for p in panden] == ["0503100000000001"]


# ---------------------------------------------------------------------------
# _is_startindex_cap_error: separates the 50-k page-cap 400 (recoverable
# by quadrant subdivision) from any other 400 (authoring/upstream bug)
# ---------------------------------------------------------------------------


class _StubResponse:
    """Minimal stand-in for ``requests.Response.content`` used by the helper."""

    def __init__(self, body: str) -> None:
        self.content = body.encode("utf-8") if isinstance(body, str) else body


_OWS_NS = "http://www.opengis.net/ows/1.1"


@pytest.mark.parametrize(
    "body",
    [
        # PDOK's ACTUAL cap response (verified live 2026-05-29): the locator
        # names the wrong parameter ("typename"), so only the ExceptionText
        # reveals the startindex cap. This is the case the original
        # locator-only matcher missed, which let the 400 crash the build.
        f'<ows:ExceptionReport xmlns:ows="{_OWS_NS}">'
        f'  <ows:Exception exceptionCode="InvalidParameterValue" locator="typename">'
        f"    <ows:ExceptionText>It is not possible to use a 'startindex' higher than"
        f" 50.000. When you need to scrape the WFS, please refer to the extracts or the"
        f" ATOM downloads available for this dataset.</ows:ExceptionText>"
        f"  </ows:Exception>"
        f"</ows:ExceptionReport>",
        # Spec-clean server that does set locator="startIndex" (kept so a
        # future PDOK fix or another WFS still matches).
        f'<ows:ExceptionReport xmlns:ows="{_OWS_NS}">'
        f'  <ows:Exception exceptionCode="InvalidParameterValue" locator="startIndex">'
        f"    <ows:ExceptionText>startIndex out of range</ows:ExceptionText>"
        f"  </ows:Exception>"
        f"</ows:ExceptionReport>",
        # No-namespace fallback (some PDOK error pages render namespace-less).
        '<ExceptionReport><Exception locator="startIndex">x</Exception></ExceptionReport>',
    ],
)
def test_is_startindex_cap_error_true_for_cap_400(body: str) -> None:
    assert bag_fetchers._is_startindex_cap_error(_StubResponse(body))


@pytest.mark.parametrize(
    "body",
    [
        # Different locator → different parameter is at fault.
        f'<ows:ExceptionReport xmlns:ows="{_OWS_NS}">'
        f'  <ows:Exception exceptionCode="InvalidParameterValue" locator="srsName">'
        f"    <ows:ExceptionText>Unknown CRS</ows:ExceptionText>"
        f"  </ows:Exception>"
        f"</ows:ExceptionReport>",
        # Body mentions startIndex in passing but does NOT name it as the locator.
        # The substring approach would false-positive here; the @locator check correctly
        # treats this as a non-cap 400.
        f'<ows:ExceptionReport xmlns:ows="{_OWS_NS}">'
        f'  <ows:Exception exceptionCode="InvalidParameterValue" locator="filter">'
        f"    <ows:ExceptionText>filter is wrong; startIndex is fine</ows:ExceptionText>"
        f"  </ows:Exception>"
        f"</ows:ExceptionReport>",
        # Non-XML body (HTML 500 page, plaintext server error).
        "Unknown type name bag:foobar",
        # Empty body.
        "",
    ],
)
def test_is_startindex_cap_error_false_for_other_400(body: str) -> None:
    """Non-cap 400s must NOT trigger quadrant subdivision: a malformed
    CRS, unknown type name, unrelated exception, empty body, or
    non-XML response is an authoring/upstream error and re-raising
    surfaces it immediately rather than spinning 4^6 silent retries.
    """
    assert not bag_fetchers._is_startindex_cap_error(_StubResponse(body))


# ---------------------------------------------------------------------------
# _fetch_layer: proactive (hits-count) subdivision keeps a > 50 k-pand city
# from ever issuing the doomed startIndex=51000 request.
# ---------------------------------------------------------------------------


def test_fetch_layer_subdivides_before_walking_when_count_over_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bbox the server reports as over the startIndex window is split
    BEFORE any page walk, so the full bbox is never paginated."""
    monkeypatch.setattr(bag_fetchers, "BAG_MAX_FETCHABLE", 50)

    def fake_count(session, url, *, type_names, cache_prefix, bbox):  # type: ignore[no-untyped-def]
        # Use bbox area as a stand-in count: the root is over the window,
        # each quadrant comfortably under it.
        minx, miny, maxx, maxy = bbox
        return int((maxx - minx) * (maxy - miny))

    walked: list[tuple[float, float, float, float]] = []

    def fake_paginate(session, url, *, type_names, cache_prefix, bbox, page_size):  # type: ignore[no-untyped-def]
        walked.append(bbox)
        return [{"properties": {"identificatie": f"id-{bbox}"}}]

    monkeypatch.setattr(bag_fetchers, "count_matched_features", fake_count)
    monkeypatch.setattr(bag_fetchers, "paginate_features", fake_paginate)

    root = (0.0, 0.0, 10.0, 10.0)  # area 100 > 50 -> subdivide
    out = bag_fetchers._fetch_layer(None, "bag:pand", bbox=root)  # type: ignore[arg-type]

    assert root not in walked  # the over-cap bbox is never walked
    assert len(walked) == 4  # exactly the four quadrants (each area 25 <= 50)
    assert len(out) == 4


def test_fetch_layer_walks_directly_when_count_under_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bbox under the window is walked once, with no subdivision."""
    monkeypatch.setattr(bag_fetchers, "BAG_MAX_FETCHABLE", 50)
    monkeypatch.setattr(
        bag_fetchers,
        "count_matched_features",
        lambda session, url, *, type_names, cache_prefix, bbox: 10,
    )
    walked: list[tuple[float, float, float, float]] = []

    def fake_paginate(session, url, *, type_names, cache_prefix, bbox, page_size):  # type: ignore[no-untyped-def]
        walked.append(bbox)
        return [{"properties": {"identificatie": "x"}}]

    monkeypatch.setattr(bag_fetchers, "paginate_features", fake_paginate)
    bbox = (0.0, 0.0, 1.0, 1.0)
    out = bag_fetchers._fetch_layer(None, "bag:pand", bbox=bbox)  # type: ignore[arg-type]

    assert walked == [bbox]
    assert len(out) == 1


def test_fetch_layer_reactive_fallback_when_count_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the hits probe returns None (server declined to count), a walk
    that comes back at or above the threshold still triggers subdivision."""
    monkeypatch.setattr(bag_fetchers, "BAG_SUBDIVIDE_THRESHOLD", 2)
    monkeypatch.setattr(
        bag_fetchers,
        "count_matched_features",
        lambda session, url, *, type_names, cache_prefix, bbox: None,
    )

    def fake_paginate(session, url, *, type_names, cache_prefix, bbox, page_size):  # type: ignore[no-untyped-def]
        # The root walk hits the threshold (2); each quadrant returns one.
        count = 2 if (bbox[2] - bbox[0]) >= 10 else 1
        return [{"properties": {"identificatie": f"a-{bbox}-{i}"}} for i in range(count)]

    monkeypatch.setattr(bag_fetchers, "paginate_features", fake_paginate)
    out = bag_fetchers._fetch_layer(None, "bag:pand", bbox=(0.0, 0.0, 10.0, 10.0))  # type: ignore[arg-type]

    # Root walk (2 == threshold, count unknown) -> subdivide; 4 quadrants x 1.
    assert len(out) == 4
