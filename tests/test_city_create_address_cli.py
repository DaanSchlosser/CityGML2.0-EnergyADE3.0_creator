"""Tests for the ``examples/create_address.py`` CLI.

The CLI is exercised through its ``main(argv)`` seam with
``build_city_model`` monkeypatched out, so no network and no real build
runs. The override path matters most: command-line values are folded
into the raw profile dict and validated like any hand-edited profile,
which is what keeps ``--extent 500000`` from bypassing the config bound
it used to skip.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from examples import create_address

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _quiet_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep main() from reconfiguring the root logger onto capsys buffers."""
    monkeypatch.setattr(create_address, "_configure_logging", lambda verbosity: None)


class _FakeModel:
    def __init__(self) -> None:
        self.xsd = SimpleNamespace(city_object_member=[])
        self.written: Path | None = None

    def write(self, path: Path) -> None:
        self.written = path


@pytest.fixture
def captured_build(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace build_city_model with a capture-and-return-fake seam."""
    captured: dict[str, Any] = {}

    def fake_build(config: Any, *, refresh: bool = False) -> _FakeModel:
        captured["config"] = config
        captured["refresh"] = refresh
        return _FakeModel()

    monkeypatch.setattr(create_address, "build_city_model", fake_build)
    return captured


def _write_profile(tmp_path: Path, **overrides: Any) -> Path:
    data: dict[str, Any] = {
        "address": {"query": "Annie Romeinsingel 72-152 Leiden", "extent_m": 400},
        "include_energy_labels": False,
        "output": "generated/address_leiden.gml",
        "city_model": {"name": "Profile title"},
        "vegetation": {"path": "trees/leiden.city.json"},
    }
    data.update(overrides)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Validated overrides
# ---------------------------------------------------------------------------


def test_extent_override_out_of_bounds_gets_the_config_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    captured_build: dict[str, Any],
) -> None:
    """--extent used to be applied after load_city_config and so bypassed
    the 50-5000 m bound; it must now fail with the normal extent_m error."""
    profile = _write_profile(tmp_path)
    rc = create_address.main(["--profile", str(profile), "--extent", "500000"])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "extent_m" in err
    assert "config" not in captured_build  # rejected before any build started


def test_address_override_rederives_names_and_clears_the_title(
    tmp_path: Path,
    captured_build: dict[str, Any],
) -> None:
    profile = _write_profile(tmp_path)
    rc = create_address.main(["--profile", str(profile), "--address", "Langegracht 76 Leiden"])
    assert rc == 0
    config = captured_build["config"]
    assert config.address_source.query == "Langegracht 76 Leiden"
    assert config.address_source.extent_m == 400.0  # profile extent kept
    assert config.output_path.name == "langegracht-76-leiden_400m.gml"
    assert config.output_path.parent.name == "generated"
    assert config.city_model_name is None  # title falls back to the query
    assert config.vegetation_source is not None
    assert config.vegetation_source.path.name == "langegracht-76-leiden_400m.city.json"


def test_extent_override_rederives_names_from_the_profile_query(
    tmp_path: Path,
    captured_build: dict[str, Any],
) -> None:
    profile = _write_profile(tmp_path)
    rc = create_address.main(["--profile", str(profile), "--extent", "250"])
    assert rc == 0
    config = captured_build["config"]
    assert config.address_source.extent_m == 250.0
    assert config.output_path.name == "annie-romeinsingel-72-152-leiden_250m.gml"


def test_output_override_wins_after_rederivation(
    tmp_path: Path,
    captured_build: dict[str, Any],
) -> None:
    out = tmp_path / "custom" / "run.gml"
    profile = _write_profile(tmp_path)
    rc = create_address.main(
        ["--profile", str(profile), "--address", "Langegracht 76 Leiden", "--output", str(out)]
    )
    assert rc == 0
    assert captured_build["config"].output_path == out.resolve()


def test_profile_values_pass_through_without_overrides(
    tmp_path: Path,
    captured_build: dict[str, Any],
) -> None:
    profile = _write_profile(tmp_path)
    rc = create_address.main(["--profile", str(profile)])
    assert rc == 0
    config = captured_build["config"]
    assert config.city_model_name == "Profile title"
    assert config.output_path.name == "address_leiden.gml"


# ---------------------------------------------------------------------------
# New flags
# ---------------------------------------------------------------------------


def test_no_energy_labels_flag_enables_a_keyless_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    captured_build: dict[str, Any],
) -> None:
    """A shipped profile with labels enabled must be runnable without an
    EP-Online key by passing --no-energy-labels; without the flag the
    normal key-requirement error appears."""
    monkeypatch.delenv("EP_ONLINE_API_KEY", raising=False)
    profile = _write_profile(tmp_path, include_energy_labels=True)

    rc = create_address.main(["--profile", str(profile)])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "include_energy_labels" in err

    rc = create_address.main(["--profile", str(profile), "--no-energy-labels"])
    assert rc == 0
    assert captured_build["config"].include_energy_labels is False


def test_refresh_flag_reaches_build_city_model(
    tmp_path: Path,
    captured_build: dict[str, Any],
) -> None:
    profile = _write_profile(tmp_path)
    rc = create_address.main(["--profile", str(profile), "--refresh"])
    assert rc == 0
    assert captured_build["refresh"] is True
    rc = create_address.main(["--profile", str(profile)])
    assert rc == 0
    assert captured_build["refresh"] is False


# ---------------------------------------------------------------------------
# Friendly errors
# ---------------------------------------------------------------------------


def test_request_exception_prints_one_line_naming_the_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import requests

    def boom(config: Any, *, refresh: bool = False) -> None:
        exc = requests.ConnectionError("connection reset")
        exc.request = requests.Request(
            method="GET", url="https://service.pdok.nl/lv/bag/wfs/v2_0?service=WFS"
        )
        raise exc

    monkeypatch.setattr(create_address, "build_city_model", boom)
    rc = create_address.main(["--profile", str(_write_profile(tmp_path))])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "service.pdok.nl" in err
    assert "retry" in err
    assert len(err.strip().splitlines()) == 1


def test_address_resolution_error_gets_a_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from citygml_energy.city_builder.address_extent import AddressResolutionError

    def boom(config: Any, *, refresh: bool = False) -> None:
        raise AddressResolutionError("could not geocode any anchor for 'Nowhere 1'")

    monkeypatch.setattr(create_address, "build_city_model", boom)
    rc = create_address.main(["--profile", str(_write_profile(tmp_path))])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "place name" in err
    assert len(err.strip().splitlines()) == 1


def test_missing_profile_is_a_friendly_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = create_address.main(["--profile", str(tmp_path / "missing.json")])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "not found" in err


def test_profile_without_address_block_exits_via_argparse(
    tmp_path: Path,
) -> None:
    path = tmp_path / "gemeente.json"
    path.write_text(
        json.dumps({"municipality": "Delft", "output": "o.gml", "include_energy_labels": False}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as excinfo:
        create_address.main(["--profile", str(path)])
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# Extras import guard
# ---------------------------------------------------------------------------


def test_import_without_requests_names_the_city_extras(tmp_path: Path) -> None:
    """A base install (no [city] extras) used to die with a bare
    ModuleNotFoundError from fetchers.bag's module-scope requests import;
    the package __init__ must re-raise with the install command. Runs in
    a subprocess with a stub requests module so the installed package is
    untouched."""
    stub = tmp_path / "requests.py"
    stub.write_text(
        "raise ModuleNotFoundError(\"No module named 'requests'\", name='requests')\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", "import citygml_energy.city_builder"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "pip install -e .[city]" in result.stderr
