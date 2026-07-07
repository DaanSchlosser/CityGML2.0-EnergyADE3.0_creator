"""Tests for the ``address`` config block validation.

The address-driven profile makes ``municipality`` optional (it is
derived from the geocode) and is mutually exclusive with ``bbox`` /
``boundary``. Energy labels are disabled in these fixtures so no
EP-Online key is needed to validate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from citygml_energy.city_builder.config import (
    CityBuildError,
    load_city_config,
    load_city_config_data,
    validate_city_config,
)


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _base(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"output": "out.gml", "include_energy_labels": False}
    data.update(overrides)
    return data


def test_address_block_loads_with_defaults_and_optional_municipality(tmp_path) -> None:
    cfg = load_city_config(
        _write(tmp_path, _base(address={"query": "Annie Romeinsingel 72-152 Leiden"}))
    )
    assert cfg.address_source is not None
    assert cfg.address_source.query == "Annie Romeinsingel 72-152 Leiden"
    assert cfg.address_source.extent_m == 500.0
    assert cfg.address_source.target_color == (0.98, 0.78, 0.42)
    assert cfg.address_source.surroundings_color == (1.0, 1.0, 1.0)
    # municipality may be omitted in address mode.
    assert cfg.municipality == ""


def test_address_block_accepts_overrides(tmp_path) -> None:
    cfg = load_city_config(
        _write(
            tmp_path,
            _base(
                address={
                    "query": "Langegracht 76 Leiden",
                    "extent_m": 300,
                    "target_color": [1.0, 0.5, 0.0],
                    "surroundings_color": [0.9, 0.9, 0.9],
                }
            ),
        )
    )
    src = cfg.address_source
    assert src is not None
    assert src.extent_m == 300.0
    assert src.target_color == (1.0, 0.5, 0.0)
    assert src.surroundings_color == (0.9, 0.9, 0.9)


def test_address_extent_out_of_range_rejected(tmp_path) -> None:
    with pytest.raises(CityBuildError, match="extent_m"):
        load_city_config(
            _write(tmp_path, _base(address={"query": "X 1 Leiden", "extent_m": 500000}))
        )


def test_address_bad_color_rejected(tmp_path) -> None:
    with pytest.raises(CityBuildError, match="target_color"):
        load_city_config(
            _write(
                tmp_path, _base(address={"query": "X 1 Leiden", "target_color": [2.0, 0.0, 0.0]})
            )
        )


def test_address_unexpected_key_rejected(tmp_path) -> None:
    with pytest.raises(CityBuildError, match="unexpected address key"):
        load_city_config(
            _write(tmp_path, _base(address={"query": "X 1 Leiden", "colour": [1, 1, 1]}))
        )


def test_address_mutually_exclusive_with_bbox(tmp_path) -> None:
    with pytest.raises(CityBuildError, match="mutually exclusive"):
        load_city_config(
            _write(
                tmp_path,
                _base(address={"query": "X 1 Leiden"}, bbox=[0, 0, 100, 100]),
            )
        )


def test_address_mutually_exclusive_with_boundary(tmp_path) -> None:
    with pytest.raises(CityBuildError, match="mutually exclusive"):
        load_city_config(
            _write(
                tmp_path,
                _base(address={"query": "X 1 Leiden"}, boundary={"path": "area.geojson"}),
            )
        )


def test_missing_both_municipality_and_address_rejected(tmp_path) -> None:
    with pytest.raises(CityBuildError, match="municipality"):
        load_city_config(_write(tmp_path, _base()))


# ---------------------------------------------------------------------------
# Dict-level loading + validation (the CLI-override seam)
# ---------------------------------------------------------------------------


def test_validate_city_config_accepts_a_dict(tmp_path) -> None:
    cfg = validate_city_config(
        _base(address={"query": "X 1 Leiden"}),
        source_path=tmp_path / "cfg.json",
    )
    assert cfg.address_source is not None
    assert cfg.address_source.query == "X 1 Leiden"
    # Relative paths resolve against the (virtual) config file's parent,
    # exactly as load_city_config resolves them.
    assert cfg.output_path == (tmp_path / "out.gml").resolve()


def test_validate_city_config_applies_the_same_bounds_as_the_file_loader(tmp_path) -> None:
    """The CLI folds --extent into the dict before validating, so an
    out-of-range override must hit the normal extent_m bound here."""
    data = _base(address={"query": "X 1 Leiden", "extent_m": 500000})
    with pytest.raises(CityBuildError, match="extent_m"):
        validate_city_config(data, source_path=tmp_path / "cfg.json")


def test_load_city_config_data_returns_the_raw_dict(tmp_path) -> None:
    path = _write(tmp_path, _base(address={"query": "X 1 Leiden"}))
    data = load_city_config_data(path)
    assert data["address"]["query"] == "X 1 Leiden"
    assert data["include_energy_labels"] is False


def test_load_city_config_data_rejects_missing_file_and_bad_json(tmp_path) -> None:
    with pytest.raises(CityBuildError, match="not found"):
        load_city_config_data(tmp_path / "missing.json")

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(CityBuildError, match="Invalid JSON"):
        load_city_config_data(bad)

    arr = tmp_path / "arr.json"
    arr.write_text("[]", encoding="utf-8")
    with pytest.raises(CityBuildError, match="must be an object"):
        load_city_config_data(arr)
