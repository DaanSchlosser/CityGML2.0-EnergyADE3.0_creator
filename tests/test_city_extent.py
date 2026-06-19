"""Tests for the build-extent resolution seam (``extent.py``).

:func:`resolve_build_extent` turns a config plus a session into one
:class:`BuildExtent`, dispatching once to the gemeente adapter or the
address adapter. Both network seams are mocked so these run offline.
They check that each adapter fills the fields the orchestrator relies on,
that the address path keeps border neighbours (``cbs_code`` ``None``),
boxes the clip geometry, and backfills the gemeente name without mutating
the config, and that :func:`_select_building_painter` maps the resolved
extent to the right painter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from shapely.geometry import box

from citygml_energy.city_builder import address_extent as address_extent_module
from citygml_energy.city_builder import extent as extent_module
from citygml_energy.city_builder.address_extent import AddressResolution
from citygml_energy.city_builder.address_query import parse_address_query
from citygml_energy.city_builder.config import AddressSource, CityBuildConfig
from citygml_energy.city_builder.extent import BuildExtent, resolve_build_extent
from citygml_energy.city_builder.fetchers import municipality as muni_module
from citygml_energy.city_builder.fetchers.municipality import MunicipalityOutline
from citygml_energy.city_builder.http import CachedSession
from citygml_energy.city_builder.painters import EnergyLabelPainter, HighlightPainter
from citygml_energy.city_builder.pipeline import _select_building_painter


def _session(tmp_path: Path) -> CachedSession:
    return CachedSession(cache_dir=tmp_path / "cache", use_cache=False)


def _config(tmp_path: Path, **overrides: Any) -> CityBuildConfig:
    source = tmp_path / "city.json"
    source.write_text("{}", encoding="utf-8")
    base: dict[str, Any] = dict(
        source_path=source,
        municipality="Delft",
        bbox=None,
        lods=(0, 1, 2),
        include_addresses=True,
        include_energy_labels=False,
        ep_online_api_key_file=None,
        cache_dir=tmp_path / "cache",
        output_path=tmp_path / "out.gml",
        srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
        srs_dimension=3,
        city_model_name=None,
        city_model_description=None,
        gml_id_prefix="",
    )
    base.update(overrides)
    return CityBuildConfig(**base)


def _outline(bbox: tuple[float, float, float, float] = (84000.0, 445000.0, 86000.0, 447000.0)):
    minx, miny, maxx, maxy = bbox
    ring = [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]
    return MunicipalityOutline(
        name="Delft",
        cbs_code="0503",
        feature={"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}},
        bbox=bbox,
    )


def _resolution(
    bbox: tuple[float, float, float, float] = (1000.0, 2000.0, 1500.0, 2500.0),
    pands: frozenset[str] = frozenset({"pandA", "pandB"}),
    municipality: str | None = "Leiden",
) -> AddressResolution:
    return AddressResolution(
        bbox=bbox,
        center=((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
        target_pand_ids=pands,
        municipality=municipality,
        woonplaats="Leiden",
        matched_addresses=len(pands),
        query=parse_address_query("Annie Romeinsingel 72-152 Leiden"),
    )


# ---------------------------------------------------------------------------
# Gemeente adapter
# ---------------------------------------------------------------------------


def test_municipality_extent_uses_outline_bbox_cbs_and_no_targets(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        muni_module, "fetch_municipality_outline", lambda session, *, name: _outline()
    )
    ext = resolve_build_extent(_config(tmp_path), _session(tmp_path))
    assert ext.bbox == (84000.0, 445000.0, 86000.0, 447000.0)
    assert ext.cbs_code == "0503"
    assert ext.municipality == "Delft"
    assert ext.boundary_geom is None
    assert ext.target_pand_ids == frozenset()
    assert ext.has_targets is False
    # The clip geometry is the real outline geometry (covers the bbox).
    assert ext.clip_geom.bounds == pytest.approx(ext.bbox)


def test_municipality_extent_prefers_config_bbox(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        muni_module, "fetch_municipality_outline", lambda session, *, name: _outline()
    )
    cfg = _config(tmp_path, bbox=(84500.0, 445500.0, 85500.0, 446500.0))
    ext = resolve_build_extent(cfg, _session(tmp_path))
    assert ext.bbox == (84500.0, 445500.0, 85500.0, 446500.0)


def test_municipality_extent_uses_boundary_bounds(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        muni_module, "fetch_municipality_outline", lambda session, *, name: _outline()
    )
    poly = box(84200.0, 445200.0, 84800.0, 445800.0)
    monkeypatch.setattr(extent_module, "_load_boundary", lambda config: poly)
    ext = resolve_build_extent(_config(tmp_path), _session(tmp_path))
    assert ext.boundary_geom is poly
    assert ext.bbox == pytest.approx((84200.0, 445200.0, 84800.0, 445800.0))


# ---------------------------------------------------------------------------
# Address adapter
# ---------------------------------------------------------------------------


def test_address_extent_boxes_clip_nulls_cbs_and_carries_targets(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        address_extent_module,
        "resolve_address_extent",
        lambda session, query, *, extent_m: _resolution(),
    )
    cfg = _config(
        tmp_path,
        municipality="",
        address_source=AddressSource(query="Annie Romeinsingel 72-152 Leiden"),
    )
    ext = resolve_build_extent(cfg, _session(tmp_path))
    assert ext.cbs_code is None
    assert ext.target_pand_ids == frozenset({"pandA", "pandB"})
    assert ext.has_targets is True
    assert ext.boundary_geom is None
    # The clip geometry is the square box of the resolved extent bbox.
    assert ext.clip_geom.bounds == pytest.approx((1000.0, 2000.0, 1500.0, 2500.0))
    # The gemeente is backfilled from the geocode; the config is untouched.
    assert ext.municipality == "Leiden"
    assert cfg.municipality == ""


def test_address_extent_keeps_user_municipality_when_supplied(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        address_extent_module,
        "resolve_address_extent",
        lambda session, query, *, extent_m: _resolution(municipality="Leiden"),
    )
    cfg = _config(tmp_path, municipality="Leiden", address_source=AddressSource(query="X 1 Leiden"))
    ext = resolve_build_extent(cfg, _session(tmp_path))
    assert ext.municipality == "Leiden"


# ---------------------------------------------------------------------------
# Painter selection
# ---------------------------------------------------------------------------


def _extent(target_pand_ids: frozenset[str] = frozenset()) -> BuildExtent:
    return BuildExtent(
        bbox=(0.0, 0.0, 500.0, 500.0),
        clip_geom=box(0.0, 0.0, 500.0, 500.0),
        cbs_code=None,
        municipality="Leiden",
        boundary_geom=None,
        target_pand_ids=target_pand_ids,
    )


def test_select_painter_picks_highlight_with_address_colours(tmp_path) -> None:
    cfg = _config(
        tmp_path,
        municipality="",
        address_source=AddressSource(query="X 1 Leiden", target_color=(0.1, 0.2, 0.3)),
    )
    painter = _select_building_painter(cfg, _extent(frozenset({"pandA"})))
    assert isinstance(painter, HighlightPainter)
    assert painter.target_pand_ids == frozenset({"pandA"})
    assert painter.target_color == (0.1, 0.2, 0.3)


def test_select_painter_defaults_to_energy_label(tmp_path) -> None:
    painter = _select_building_painter(_config(tmp_path), _extent())
    assert isinstance(painter, EnergyLabelPainter)
