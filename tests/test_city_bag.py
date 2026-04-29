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


def _vbo_feature(
    identificatie: str, pand_id: str, *, postcode: str = "2611AA"
) -> dict[str, Any]:
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
        bag_fetchers, "_fetch_layer",
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
        bag_fetchers, "_fetch_layer",
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
        bag_fetchers, "_fetch_layer",
        lambda session, layer, *, bbox: raw,
    )
    panden = bag_fetchers.fetch_panden(
        session=None,  # type: ignore[arg-type]
        bbox=(0.0, 0.0, 1.0, 1.0),
        cbs_code="0503",
    )
    assert [p.identificatie for p in panden] == ["0503100000000001"]
