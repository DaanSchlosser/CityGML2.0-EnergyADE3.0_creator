"""Unit tests for the city-build JSON config loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citygml_energy.city_builder.config import (
    CityBuildError,
    load_city_config,
)


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_config(tmp_path: Path) -> dict:
    return {
        "municipality": "Delft",
        "lods": [0, 1, 2],
        "include_addresses": True,
        "include_energy_labels": False,  # no key needed
        "cache_dir": str(tmp_path / "cache"),
        "output": str(tmp_path / "out.gml"),
        "city_model": {"name": "Delft"},
    }


def test_valid_config_loads(tmp_path: Path) -> None:
    path = _write(tmp_path / "city.json", _valid_config(tmp_path))
    config = load_city_config(path)
    assert config.municipality == "Delft"
    assert config.lods == (0, 1, 2)
    assert config.include_addresses is True
    assert config.include_energy_labels is False
    assert config.cache_dir.is_absolute()
    assert config.output_path.is_absolute()


def test_file_header_parses(tmp_path: Path) -> None:
    payload = _valid_config(tmp_path)
    payload["file_header"] = "Banner\nCopyright (c) 2026 TU Delft. CC-BY-4.0 data, MIT toolkit."
    config = load_city_config(_write(tmp_path / "c.json", payload))
    assert config.file_header is not None
    assert config.file_header.startswith("Banner")


def test_file_header_with_double_hyphen_rejected(tmp_path: Path) -> None:
    """A '--' in the header would produce an unparseable XML comment."""
    payload = _valid_config(tmp_path)
    payload["file_header"] = "valid line\nan illegal -- sequence"
    with pytest.raises(CityBuildError, match="--"):
        load_city_config(_write(tmp_path / "c.json", payload))


def test_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    payload = _valid_config(tmp_path)
    payload["unexpected"] = 42
    with pytest.raises(CityBuildError, match="unexpected top-level"):
        load_city_config(_write(tmp_path / "c.json", payload))


def test_energy_labels_require_api_key_file(tmp_path: Path) -> None:
    payload = _valid_config(tmp_path)
    payload["include_energy_labels"] = True
    with pytest.raises(CityBuildError, match="ep_online_api_key_file"):
        load_city_config(_write(tmp_path / "c.json", payload))


def test_relative_paths_resolve_against_config_parent(tmp_path: Path) -> None:
    nested = tmp_path / "configs"
    nested.mkdir()
    payload = _valid_config(tmp_path)
    payload["cache_dir"] = "cache"
    payload["output"] = "out.gml"
    config = load_city_config(_write(nested / "city.json", payload))
    assert config.cache_dir.parent == nested
    assert config.output_path.parent == nested


def test_bbox_must_have_four_numbers(tmp_path: Path) -> None:
    payload = _valid_config(tmp_path)
    payload["bbox"] = [1, 2, 3]
    with pytest.raises(CityBuildError, match="bbox"):
        load_city_config(_write(tmp_path / "c.json", payload))


def test_bbox_requires_ordered_corners(tmp_path: Path) -> None:
    payload = _valid_config(tmp_path)
    payload["bbox"] = [10, 10, 5, 5]
    with pytest.raises(CityBuildError, match="minx<maxx"):
        load_city_config(_write(tmp_path / "c.json", payload))


def test_lods_reject_non_subset(tmp_path: Path) -> None:
    payload = _valid_config(tmp_path)
    payload["lods"] = [0, 1, 9]
    with pytest.raises(CityBuildError, match="lods entries"):
        load_city_config(_write(tmp_path / "c.json", payload))


def test_ep_online_key_is_read_lazily(tmp_path: Path) -> None:
    key_path = tmp_path / "ep.key"
    key_path.write_text("  secret-token  ", encoding="utf-8")
    payload = _valid_config(tmp_path)
    payload["include_energy_labels"] = True
    payload["ep_online_api_key_file"] = str(key_path)
    config = load_city_config(_write(tmp_path / "c.json", payload))
    assert config.ep_online_api_key == "secret-token"
