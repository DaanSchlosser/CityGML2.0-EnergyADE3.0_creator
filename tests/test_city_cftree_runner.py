"""Tests for the on-demand CFTree generation seam (``cftree_runner.py``).

Two concerns are covered without ever launching CFTree, docker, or a
real tile merge:

* the runner adapters build the exact argv (WSL path translation, docker
  mounts, flags), and :func:`resolve_runner` maps the environment to the
  right adapter or raises :class:`CityBuildError` on a setup problem;
  the docker preflight (daemon check, image inspect, auto-pull, digest
  resolution) runs against an injected ``run`` callable.
* :func:`ensure_tree_file` orchestrates write-case -> run -> merge, reuses
  a *complete* prior run via the AOI completion manifest, regenerates a
  partial/stale one, and soft-fails to ``False`` on every runtime error.
  The CFTree subprocess (``run``) and the in-process merge (``merge``)
  are both injected so neither side effect actually happens.

The producer/consumer contract of ``case_area.geojson`` is pinned with a
real round-trip through the merge tool's boundary loader.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("shapely")

from shapely.geometry import MultiPolygon, Polygon, box

from citygml_energy.city_builder import _env as env_module
from citygml_energy.city_builder import cftree_runner as runner_mod
from citygml_energy.city_builder.boundary import BoundarySource, load_boundary_polygon
from citygml_energy.city_builder.cftree_runner import (
    DockerRunner,
    NativeRunner,
    WslRunner,
    _aoi_fingerprint,
    _data_dir,
    _derive_case,
    _fmt_num,
    _is_safe_case,
    _to_docker_mount,
    _to_wsl_path,
    _write_case_geojson,
    _write_manifest,
    _wsl_python_bindir,
    ensure_tree_file,
    resolve_runner,
)
from citygml_energy.city_builder.vegetation import VegetationGenerateSpec, VegetationSource
from citygml_energy.errors import CityBuildError
from tools.merge_cftree_tiles import TILE_FILENAME

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeRunner:
    """Minimal :class:`CFTreeRunner` whose command never actually runs.

    Mirrors the real adapters by appending ``--geometry-only`` when asked,
    so a test can assert the flag reaches the argv via ``run`` calls.
    """

    repo: Path

    @property
    def cwd(self) -> Path | None:
        return None

    def command(
        self,
        *,
        case: str,
        ahn_version: int,
        n_cores: int,
        buffer_m: float,
        geometry_only: bool = False,
    ) -> list[str]:
        cmd = ["cftree-run", case, str(ahn_version), str(n_cores)]
        if geometry_only:
            cmd.append("--geometry-only")
        return cmd


def _source(
    out: Path,
    *,
    generate: bool = True,
    geometry_only: bool = False,
    **spec_kwargs: Any,
) -> VegetationSource:
    kwargs: dict[str, Any] = {"ahn_version": 5, "n_cores": 8, "buffer_m": 20.0}
    kwargs.update(spec_kwargs)
    spec = VegetationGenerateSpec(**kwargs) if generate else None
    return VegetationSource(path=out, generate=spec, geometry_only=geometry_only)


def _make_run(
    *,
    cftree_code: int = 0,
    calls: list[list[str]] | None = None,
    raise_oserror: bool = False,
):
    """A ``subprocess.run`` stand-in for the CFTree subprocess only."""

    def _run(
        cmd: Any, cwd: Any = None, check: bool = False, timeout: Any = None
    ) -> SimpleNamespace:
        if calls is not None:
            calls.append([str(c) for c in cmd])
        if raise_oserror:
            raise OSError("wsl.exe not found")
        return SimpleNamespace(returncode=cftree_code)

    return _run


def _make_merge(
    out: Path,
    *,
    write: bool = True,
    raise_exc: BaseException | None = None,
    calls: list[tuple[str, ...]] | None = None,
):
    """A ``merge_cftree_tiles.merge_case`` stand-in (in-process merge)."""

    def _merge(
        case_dir: Any,
        boundary: Any,
        output: Any,
        *,
        tree_filename: str = "trees_lod3.city.json",
        **_kw: Any,
    ) -> int:
        if calls is not None:
            calls.append(("merge", str(case_dir), str(boundary), str(output)))
        if raise_exc is not None:
            raise raise_exc
        if write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}", encoding="utf-8")
        return 0

    return _merge


def _seed_tile(repo: Path, case: str) -> Path:
    """Create one per-tile CFTree output for *case* under *repo*."""
    tile = _data_dir(repo, case) / "tiles" / "T1" / TILE_FILENAME
    tile.parent.mkdir(parents=True)
    tile.write_text("{}", encoding="utf-8")
    return tile


def _no_dotenv(monkeypatch) -> None:
    """Stop ``resolve_runner`` re-reading a real .env over the test env."""
    monkeypatch.setattr(env_module, "maybe_load_dotenv", lambda *_a, **_k: None)


def _clear_cftree_env(monkeypatch) -> None:
    """Remove every CFTREE_* variable so a developer's real env never leaks in."""
    for var in (
        "CFTREE_REPO",
        "CFTREE_RUNNER",
        "CFTREE_PYTHON",
        "CFTREE_IMAGE",
        "CFTREE_DOCKER_ARGS",
        "CFTREE_WORKDIR",
    ):
        monkeypatch.delenv(var, raising=False)


_REPO_DIGEST = "ghcr.io/x/cftree@sha256:aaaa"
_IMAGE_ID = "sha256:bbbb"


def _make_docker_probes(
    *,
    present: bool = True,
    version_code: int = 0,
    pull_code: int = 0,
    repo_digest: str | None = _REPO_DIGEST,
    calls: list[list[str]] | None = None,
):
    """A ``subprocess.run`` stand-in for the docker CLI preflight probes.

    Answers ``docker version``, ``docker image inspect``, ``docker pull``,
    and ``docker run`` so no test ever touches a real docker daemon. With
    ``present=False`` the image only inspects successfully after a pull,
    which is the colleague-first-run path.
    """
    state = {"pulled": False}

    def _run(cmd: Any, **_kw: Any) -> SimpleNamespace:
        argv = [str(c) for c in cmd]
        if calls is not None:
            calls.append(argv)
        if argv[:2] == ["docker", "version"]:
            return SimpleNamespace(returncode=version_code, stdout="27.0\n", stderr="")
        if argv[:3] == ["docker", "image", "inspect"]:
            if not present and not state["pulled"]:
                return SimpleNamespace(returncode=1, stdout="", stderr="Error: No such image")
            digests = json.dumps([repo_digest] if repo_digest else [])
            return SimpleNamespace(returncode=0, stdout=f"{_IMAGE_ID} {digests}\n", stderr="")
        if argv[:2] == ["docker", "pull"]:
            state["pulled"] = pull_code == 0
            return SimpleNamespace(returncode=pull_code)
        if argv[:2] == ["docker", "run"]:
            return SimpleNamespace(returncode=0)
        raise AssertionError(f"unexpected command through the docker probe stub: {argv}")

    return _run


def _docker_env(monkeypatch, tmp_path: Path) -> Path:
    """Point the env at the docker runner's no-clone mode; returns the work root."""
    work = tmp_path / "work"
    monkeypatch.setenv("CFTREE_RUNNER", "docker")
    monkeypatch.setenv("CFTREE_IMAGE", "cftree:local")
    monkeypatch.setenv("CFTREE_WORKDIR", str(work))
    return work


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_to_wsl_path_translates_drive() -> None:
    assert _to_wsl_path(Path("C:/Users/x/CFTree")) == "/mnt/c/Users/x/CFTree"


def test_to_wsl_path_posix_is_noop() -> None:
    assert _to_wsl_path(Path("/opt/CFTree")) == "/opt/CFTree"


def test_to_wsl_path_relative_is_noop() -> None:
    assert _to_wsl_path(Path("relative/sub")) == "relative/sub"


def test_to_wsl_path_unc_raises() -> None:
    with pytest.raises(ValueError, match="UNC"):
        _to_wsl_path(Path(r"\\server\share\CFTree"))


def test_wsl_python_bindir() -> None:
    assert _wsl_python_bindir("/home/u/envs/cftree/bin/python") == "/home/u/envs/cftree/bin"
    # A bare command name or a root-level interpreter has nothing useful to prepend.
    assert _wsl_python_bindir("python") is None
    assert _wsl_python_bindir("/python") is None


def test_fmt_num_drops_trailing_zero() -> None:
    assert _fmt_num(20.0) == "20"
    assert _fmt_num(2.5) == "2.5"


def test_derive_case_strips_city_json() -> None:
    assert _derive_case(Path("/x/leiden_250.city.json")) == "leiden_250"


def test_is_safe_case() -> None:
    assert _is_safe_case("leiden_250_AHN5")
    assert _is_safe_case("250m_AHN5")  # leading digit is fine for a derived case
    assert not _is_safe_case("../escape")
    assert not _is_safe_case("a/b")
    assert not _is_safe_case("a\\b")
    assert not _is_safe_case("a b")  # embedded whitespace
    assert not _is_safe_case("  ")
    assert not _is_safe_case("..")
    assert not _is_safe_case("")


# ---------------------------------------------------------------------------
# Runner adapters
# ---------------------------------------------------------------------------


def test_wsl_runner_command() -> None:
    runner = WslRunner(repo=Path("C:/Users/x/CFTree"), python="/home/u/envs/cftree/bin/python")
    cmd = runner.command(case="leiden_250", ahn_version=5, n_cores=8, buffer_m=20.0)
    assert cmd[:3] == ["wsl.exe", "bash", "-lc"]
    inner = cmd[3]
    assert "cd /mnt/c/Users/x/CFTree" in inner
    # The env bin is prepended to PATH so CFTree's child stages reuse the interpreter;
    # $PATH stays double-quoted so the space-bearing WSL PATH does not word-split.
    assert 'export PATH=/home/u/envs/cftree/bin:"$PATH"' in inner
    assert "/home/u/envs/cftree/bin/python main.py" in inner
    assert "--case leiden_250" in inner
    assert "--ahn-version 5" in inner
    assert "--n-cores 8" in inner
    assert "--buffer 20" in inner
    assert "--overwrite" in inner
    assert "--geometry-only" not in inner
    assert runner.cwd is None


def test_wsl_runner_command_geometry_only() -> None:
    runner = WslRunner(repo=Path("C:/Users/x/CFTree"), python="/home/u/envs/cftree/bin/python")
    inner = runner.command(
        case="leiden_250", ahn_version=5, n_cores=8, buffer_m=20.0, geometry_only=True
    )[3]
    assert inner.endswith("--geometry-only")


def test_native_runner_command() -> None:
    runner = NativeRunner(repo=Path("/opt/CFTree"), python="python")
    assert runner.command(case="c", ahn_version=6, n_cores=4, buffer_m=10.0) == [
        "python",
        "main.py",
        "--case",
        "c",
        "--ahn-version",
        "6",
        "--n-cores",
        "4",
        "--buffer",
        "10",
        "--overwrite",
    ]
    assert runner.cwd == Path("/opt/CFTree")


def test_native_runner_command_geometry_only() -> None:
    runner = NativeRunner(repo=Path("/opt/CFTree"), python="python")
    cmd = runner.command(case="c", ahn_version=6, n_cores=4, buffer_m=10.0, geometry_only=True)
    assert cmd[-1] == "--geometry-only"
    # The default keeps the flag off, so a full reconstruction is unaffected.
    assert "--geometry-only" not in runner.command(
        case="c", ahn_version=6, n_cores=4, buffer_m=10.0
    )


def test_to_docker_mount_drive_uses_forward_slashes() -> None:
    assert _to_docker_mount(Path("C:/Users/x/CFTree")) == "C:/Users/x/CFTree"
    assert _to_docker_mount(Path(r"C:\Users\x\CFTree")) == "C:/Users/x/CFTree"


def test_to_docker_mount_posix_is_noop() -> None:
    assert _to_docker_mount(Path("/opt/CFTree")) == "/opt/CFTree"


def test_to_docker_mount_unc_raises() -> None:
    with pytest.raises(ValueError, match="UNC"):
        _to_docker_mount(Path(r"\\server\share\CFTree"))


def test_docker_runner_command_no_clone_mounts_work_dirs() -> None:
    """The default (no-clone) mode mounts only cases/ and data/ of the work root."""
    runner = DockerRunner(repo=Path("C:/Users/x/creator/.cache/cftree"), image="cftree:local")
    cmd = runner.command(case="leiden_250", ahn_version=5, n_cores=8, buffer_m=20.0)
    assert cmd[:3] == ["docker", "run", "--rm"]
    mounts = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-v"]
    assert mounts == [
        "C:/Users/x/creator/.cache/cftree/cases:/opt/cftree/cases",
        "C:/Users/x/creator/.cache/cftree/data:/opt/cftree/data",
    ]
    # The working directory is the image's baked source tree, so CFTree
    # resolves resources/ from the image, not the host.
    assert cmd[cmd.index("-w") + 1] == "/opt/cftree"
    # The CFTree invocation rides after the image, with the same flags as native.
    tail = cmd[cmd.index("cftree:local") + 1 :]
    assert tail == [
        "python",
        "main.py",
        "--case",
        "leiden_250",
        "--ahn-version",
        "5",
        "--n-cores",
        "8",
        "--buffer",
        "20",
        "--overwrite",
    ]
    assert "--geometry-only" not in cmd
    assert runner.cwd is None


def test_docker_runner_command_checkout_mode_mounts_repo_at_work() -> None:
    """checkout=True keeps the single-mount behavior: the checkout at /work."""
    runner = DockerRunner(repo=Path("C:/Users/x/CFTree"), image="cftree:local", checkout=True)
    cmd = runner.command(case="leiden_250", ahn_version=5, n_cores=8, buffer_m=20.0)
    assert cmd[cmd.index("-v") + 1] == "C:/Users/x/CFTree:/work"
    assert cmd.count("-v") == 1
    assert cmd[cmd.index("-w") + 1] == "/work"
    tail = cmd[cmd.index("cftree:local") + 1 :]
    assert tail[:4] == ["python", "main.py", "--case", "leiden_250"]


def test_docker_runner_command_names_container_uniquely() -> None:
    """Each run gets a unique --name so a timed-out container can be killed."""
    runner = DockerRunner(repo=Path("C:/Users/x/CFTree"), image="cftree:local")
    cmd_a = runner.command(case="leiden_250", ahn_version=5, n_cores=8, buffer_m=20.0)
    cmd_b = runner.command(case="leiden_250", ahn_version=5, n_cores=8, buffer_m=20.0)
    name_a = cmd_a[cmd_a.index("--name") + 1]
    name_b = cmd_b[cmd_b.index("--name") + 1]
    assert name_a.startswith("cftree-leiden_250-")
    assert name_a != name_b


def test_docker_runner_command_threads_extra_args_before_image() -> None:
    runner = DockerRunner(
        repo=Path("C:/Users/x/CFTree"),
        image="cftree:local",
        extra_args=("--gpus", "all", "--shm-size", "1g"),
    )
    cmd = runner.command(case="c", ahn_version=6, n_cores=4, buffer_m=10.0, geometry_only=True)
    # Extra args land after the mounts and before the image, exactly as docker expects.
    assert "--gpus" in cmd and cmd[cmd.index("--gpus") + 1] == "all"
    assert cmd.index("--gpus") < cmd.index("cftree:local")
    assert cmd[-1] == "--geometry-only"


# ---------------------------------------------------------------------------
# resolve_runner
# ---------------------------------------------------------------------------


def test_resolve_runner_wsl(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    monkeypatch.setenv("CFTREE_RUNNER", "wsl")
    monkeypatch.setenv("CFTREE_PYTHON", "/home/u/envs/cftree/bin/python")
    runner = resolve_runner()
    assert isinstance(runner, WslRunner)
    assert runner.repo == tmp_path
    assert runner.python == "/home/u/envs/cftree/bin/python"


def test_resolve_runner_native(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    monkeypatch.setenv("CFTREE_RUNNER", "native")
    monkeypatch.setenv("CFTREE_PYTHON", "python3")
    runner = resolve_runner()
    assert isinstance(runner, NativeRunner)
    assert runner.python == "python3"


def test_resolve_runner_kind_is_case_insensitive(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    monkeypatch.setenv("CFTREE_RUNNER", " Native ")
    assert isinstance(resolve_runner(), NativeRunner)
    monkeypatch.setenv("CFTREE_RUNNER", "WSL")
    monkeypatch.setenv("CFTREE_PYTHON", "/home/u/envs/cftree/bin/python")
    assert isinstance(resolve_runner(), WslRunner)


def test_resolve_runner_default_is_docker_on_windows(monkeypatch, tmp_path) -> None:
    # Only the dispatch is exercised: with os.name patched to "nt" on a
    # POSIX host, pathlib dispatches Path() to WindowsPath, whose joins
    # raise NotImplementedError, so the real docker resolver cannot run.
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.delenv("CFTREE_RUNNER", raising=False)
    sentinel = DockerRunner(repo=tmp_path, image="ghcr.io/example/cftree:latest")
    monkeypatch.setattr(runner_mod, "_resolve_docker_runner", lambda *, run: sentinel)
    assert resolve_runner() is sentinel


def test_resolve_runner_default_is_native_off_windows(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    runner = resolve_runner()
    assert isinstance(runner, NativeRunner)
    assert runner.python == "python"


def test_resolve_runner_wsl_without_python_raises(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    monkeypatch.setenv("CFTREE_RUNNER", "wsl")
    with pytest.raises(CityBuildError, match="CFTREE_PYTHON"):
        resolve_runner()


def test_resolve_runner_missing_repo_raises(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("CFTREE_RUNNER", "native")
    monkeypatch.setenv("CFTREE_PYTHON", "python")
    with pytest.raises(CityBuildError, match="not a directory"):
        resolve_runner()


def test_resolve_runner_sibling_default_for_native(monkeypatch, tmp_path) -> None:
    """Without CFTREE_REPO the wsl/native checkout falls back to ../CFTree."""
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    creator = tmp_path / "creator"
    sibling = tmp_path / "CFTree"
    creator.mkdir()
    sibling.mkdir()
    monkeypatch.setattr(runner_mod, "_CREATOR_ROOT", creator)
    monkeypatch.setenv("CFTREE_RUNNER", "native")
    runner = resolve_runner()
    assert isinstance(runner, NativeRunner)
    assert runner.repo == sibling


def test_resolve_runner_unknown_kind_raises_naming_all_runners(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    monkeypatch.setenv("CFTREE_RUNNER", "podman")
    with pytest.raises(CityBuildError) as excinfo:
        resolve_runner()
    for name in ("docker", "wsl", "native"):
        assert name in str(excinfo.value)


def test_resolve_runner_wsl_unreachable_repo_raises(monkeypatch, tmp_path) -> None:
    """A repo the WSL runner cannot translate (e.g. UNC) is a setup error."""
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    monkeypatch.setenv("CFTREE_RUNNER", "wsl")
    monkeypatch.setenv("CFTREE_PYTHON", "/home/u/envs/cftree/bin/python")

    def _raise(_path):
        raise ValueError("UNC path is not supported by the WSL runner")

    monkeypatch.setattr(runner_mod, "_to_wsl_path", _raise)
    with pytest.raises(CityBuildError, match="UNC"):
        resolve_runner()


# ---------------------------------------------------------------------------
# resolve_runner: docker preflight
# ---------------------------------------------------------------------------


def test_resolve_runner_docker_no_clone_is_default(monkeypatch, tmp_path) -> None:
    """Without CFTREE_REPO the docker runner needs no checkout at all."""
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    work = _docker_env(monkeypatch, tmp_path)
    monkeypatch.setenv("CFTREE_DOCKER_ARGS", "--shm-size 1g")
    runner = resolve_runner(run=_make_docker_probes())
    assert isinstance(runner, DockerRunner)
    assert runner.checkout is False
    assert runner.repo == work
    assert runner.image == "cftree:local"
    assert runner.digest == _REPO_DIGEST
    # CFTREE_DOCKER_ARGS is shell-split and threaded through verbatim.
    assert runner.extra_args == ("--shm-size", "1g")
    # The two bind-mount sources exist before docker ever runs.
    assert (work / "cases").is_dir()
    assert (work / "data").is_dir()


def test_resolve_runner_docker_default_work_root_is_creator_cache(monkeypatch, tmp_path) -> None:
    """Without CFTREE_WORKDIR the work root is .cache/cftree in the creator repo."""
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    creator = tmp_path / "creator"
    creator.mkdir()
    # A sibling checkout exists, and must NOT engage the docker checkout mode.
    (tmp_path / "CFTree").mkdir()
    monkeypatch.setattr(runner_mod, "_CREATOR_ROOT", creator)
    monkeypatch.setenv("CFTREE_RUNNER", "docker")
    monkeypatch.setenv("CFTREE_IMAGE", "cftree:local")
    runner = resolve_runner(run=_make_docker_probes())
    assert runner.checkout is False
    assert runner.repo == creator / ".cache" / "cftree"


def test_resolve_runner_docker_checkout_mode_with_repo(monkeypatch, tmp_path) -> None:
    """An explicit CFTREE_REPO switches the docker runner to checkout mode."""
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_RUNNER", "docker")
    monkeypatch.setenv("CFTREE_IMAGE", "cftree:local")
    monkeypatch.setenv("CFTREE_REPO", str(tmp_path))
    runner = resolve_runner(run=_make_docker_probes())
    assert isinstance(runner, DockerRunner)
    assert runner.checkout is True
    assert runner.repo == tmp_path
    assert runner.digest == _REPO_DIGEST


def test_resolve_runner_docker_without_image_raises(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_RUNNER", "docker")
    with pytest.raises(CityBuildError, match="CFTREE_IMAGE"):
        resolve_runner(run=_make_docker_probes())


def test_resolve_runner_docker_daemon_unreachable_raises(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    _docker_env(monkeypatch, tmp_path)
    with pytest.raises(CityBuildError, match="daemon"):
        resolve_runner(run=_make_docker_probes(version_code=1))


def test_resolve_runner_docker_cli_missing_raises(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    _docker_env(monkeypatch, tmp_path)

    def _run(_cmd: Any, **_kw: Any) -> SimpleNamespace:
        raise OSError("docker not found")

    with pytest.raises(CityBuildError, match="docker CLI"):
        resolve_runner(run=_run)


def test_resolve_runner_docker_pulls_absent_image(monkeypatch, tmp_path) -> None:
    """A colleague's first run auto-pulls the image instead of failing."""
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    _docker_env(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    runner = resolve_runner(run=_make_docker_probes(present=False, calls=calls))
    assert isinstance(runner, DockerRunner)
    assert runner.digest == _REPO_DIGEST
    assert ["docker", "pull", "cftree:local"] in calls


def test_resolve_runner_docker_pull_failure_raises(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    _docker_env(monkeypatch, tmp_path)
    with pytest.raises(CityBuildError, match="docker pull"):
        resolve_runner(run=_make_docker_probes(present=False, pull_code=1))


def test_resolve_runner_docker_local_image_digest_falls_back_to_id(monkeypatch, tmp_path) -> None:
    """A locally-built image has no RepoDigests; its .Id becomes the identity."""
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    _docker_env(monkeypatch, tmp_path)
    runner = resolve_runner(run=_make_docker_probes(repo_digest=None))
    assert runner.digest == _IMAGE_ID


def test_resolve_runner_docker_unc_work_root_raises(monkeypatch, tmp_path) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_RUNNER", "docker")
    monkeypatch.setenv("CFTREE_IMAGE", "cftree:local")
    monkeypatch.setenv("CFTREE_WORKDIR", r"\\server\share\cftree")
    with pytest.raises(CityBuildError, match="UNC"):
        resolve_runner(run=_make_docker_probes())


# ---------------------------------------------------------------------------
# ensure_tree_file: short-circuits
# ---------------------------------------------------------------------------


def test_ensure_returns_true_when_file_exists(tmp_path) -> None:
    out = tmp_path / "veg" / "leiden_250.city.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=tmp_path / "cftree"),
    )
    assert ok is True
    assert run_calls == []  # nothing launched


def test_ensure_returns_false_without_generate(tmp_path) -> None:
    out = tmp_path / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out, generate=False),
        box(0, 0, 250, 250),
        run=_make_run(),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=tmp_path / "cftree"),
    )
    assert ok is False


def test_ensure_returns_false_without_aoi(tmp_path) -> None:
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out),
        None,
        run=_make_run(),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=tmp_path / "cftree"),
    )
    assert ok is False


def test_ensure_returns_false_for_directory_output(tmp_path) -> None:
    """A directory at the output path is not mistaken for an existing file."""
    out = tmp_path / "veg" / "leiden_250.city.json"
    out.mkdir(parents=True)
    ok = ensure_tree_file(
        _source(out, generate=False),
        box(0, 0, 250, 250),
        run=_make_run(),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=tmp_path / "cftree"),
    )
    assert ok is False


def test_ensure_rejects_unsafe_case(tmp_path) -> None:
    """A traversal case (bypassing config validation) soft-fails, writes nothing."""
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out, case="../escape"),
        box(0, 0, 250, 250),
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is False
    assert run_calls == []
    assert not (repo / "cases").exists()


# ---------------------------------------------------------------------------
# ensure_tree_file: run -> merge happy path
# ---------------------------------------------------------------------------


def test_ensure_runs_cftree_then_merges(tmp_path) -> None:
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    merge_calls: list[tuple[str, ...]] = []
    ok = ensure_tree_file(
        _source(out),
        box(1000, 2000, 1250, 2250),
        run=_make_run(calls=run_calls),
        merge=_make_merge(out, calls=merge_calls),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert out.is_file()
    # The case is namespaced by AHN version (spec uses AHN5).
    geo = repo / "cases" / "leiden_250_AHN5" / "case_area.geojson"
    assert geo.is_file()
    feature_collection = json.loads(geo.read_text(encoding="utf-8"))
    assert feature_collection["type"] == "FeatureCollection"
    assert feature_collection["features"][0]["geometry"]["type"] == "Polygon"
    # A completion manifest is written after the clean run, holding the full
    # AOI fingerprint (bounds + shape digest + buffer + AHN + mode).
    manifest = repo / "data" / "leiden_250_AHN5" / ".cftree_manifest.json"
    assert manifest.is_file()
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    assert json.loads(manifest.read_text(encoding="utf-8")) == _aoi_fingerprint(
        box(1000, 2000, 1250, 2250), spec
    )
    # CFTree ran once, the merge ran once.
    assert len(run_calls) == 1
    assert len(merge_calls) == 1


def test_ensure_ahn6_namespaces_case(tmp_path) -> None:
    """A different AHN version maps to its own case directory."""
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out, ahn_version=6),
        box(0, 0, 250, 250),
        run=_make_run(),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert (repo / "cases" / "leiden_250_AHN6" / "case_area.geojson").is_file()
    assert (repo / "data" / "leiden_250_AHN6" / ".cftree_manifest.json").is_file()
    assert not (repo / "cases" / "leiden_250_AHN5").exists()


# ---------------------------------------------------------------------------
# ensure_tree_file: reuse vs regenerate
# ---------------------------------------------------------------------------


def test_ensure_reuses_complete_run(tmp_path) -> None:
    """Tiles plus a matching completion manifest skip the CFTree run."""
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    aoi = box(0, 0, 250, 250)
    _seed_tile(repo, "leiden_250_AHN5")
    _write_manifest(_data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(aoi, spec))
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    merge_calls: list[tuple[str, ...]] = []
    ok = ensure_tree_file(
        _source(out),
        aoi,
        run=_make_run(calls=run_calls),
        merge=_make_merge(out, calls=merge_calls),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert run_calls == []  # CFTree run skipped
    assert len(merge_calls) == 1  # merge still runs


def test_ensure_regenerates_partial_run_without_manifest(tmp_path) -> None:
    """Tiles with no completion manifest (interrupted run) are not trusted."""
    repo = tmp_path / "cftree"
    _seed_tile(repo, "leiden_250_AHN5")  # tiles present, but no manifest
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert len(run_calls) == 1  # regenerated despite tiles being present


def test_ensure_regenerates_on_changed_aoi(tmp_path) -> None:
    """A manifest for a different AOI invalidates reuse."""
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    _seed_tile(repo, "leiden_250_AHN5")
    # Manifest recorded for an old, smaller AOI.
    _write_manifest(_data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(box(0, 0, 100, 100), spec))
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),  # new, larger AOI under the same output path
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert len(run_calls) == 1  # stale tiles not reused


def test_ensure_runs_when_tiles_dir_empty(tmp_path) -> None:
    """An empty tiles/ directory with no manifest is not reusable output."""
    repo = tmp_path / "cftree"
    (_data_dir(repo, "leiden_250_AHN5") / "tiles").mkdir(parents=True)
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert len(run_calls) == 1


def test_ensure_regenerates_existing_file_built_for_other_aoi(tmp_path) -> None:
    """An existing merged file is NOT trusted when its manifest is for another AOI.

    The reuse bug: a vegetation path shared across two addresses served the
    first address's trees for the second because the existing file short-
    circuited before the AOI was ever checked.
    """
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    _seed_tile(repo, "leiden_250_AHN5")
    # Manifest + merged file left by a prior build for a different (smaller) AOI.
    _write_manifest(_data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(box(0, 0, 100, 100), spec))
    out = tmp_path / "veg" / "leiden_250.city.json"
    out.parent.mkdir(parents=True)
    out.write_text('{"stale": true}', encoding="utf-8")
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),  # the current build's AOI differs from the manifest
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert len(run_calls) == 1  # regenerated rather than serving the stale file


def test_ensure_reuses_existing_file_when_manifest_matches(tmp_path) -> None:
    """An existing merged file IS served as-is when its manifest matches the AOI."""
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    aoi = box(0, 0, 250, 250)
    _write_manifest(_data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(aoi, spec))
    out = tmp_path / "veg" / "leiden_250.city.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")
    run_calls: list[list[str]] = []
    merge_calls: list[tuple[str, ...]] = []
    ok = ensure_tree_file(
        _source(out),
        aoi,
        run=_make_run(calls=run_calls),
        merge=_make_merge(out, calls=merge_calls),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert run_calls == [] and merge_calls == []  # neither re-ran nor re-merged


def test_aoi_fingerprint_distinguishes_same_bbox_different_shape() -> None:
    """Two AOIs sharing a bounding box but differing in shape must not collide."""
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    full = box(0, 0, 250, 250)
    l_shape = Polygon([(0, 0), (250, 0), (250, 100), (100, 100), (100, 250), (0, 250)])
    assert full.bounds == l_shape.bounds
    assert _aoi_fingerprint(full, spec) != _aoi_fingerprint(l_shape, spec)


def test_aoi_fingerprint_omits_runner_when_none() -> None:
    """WSL/native fingerprints carry no runner key, so old manifests still match."""
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    assert "runner" not in _aoi_fingerprint(box(0, 0, 250, 250), spec)


def test_aoi_fingerprint_includes_runner_id() -> None:
    """A docker image tag is part of the identity, so a re-tag invalidates reuse."""
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    aoi = box(0, 0, 250, 250)
    a = _aoi_fingerprint(aoi, spec, runner_id="cftree:v1")
    b = _aoi_fingerprint(aoi, spec, runner_id="cftree:v2")
    assert a["runner"] == "cftree:v1"
    assert a != b


@dataclass
class _FakeDockerRunner:
    """A docker-like runner: carries ``digest``/``image`` for the fingerprint."""

    repo: Path
    image: str = "cftree:local"
    digest: str = ""

    @property
    def cwd(self) -> Path | None:
        return None

    def command(
        self,
        *,
        case: str,
        ahn_version: int,
        n_cores: int,
        buffer_m: float,
        geometry_only: bool = False,
    ) -> list[str]:
        cmd = ["docker", "run", self.image, case, str(ahn_version)]
        if geometry_only:
            cmd.append("--geometry-only")
        return cmd


def test_ensure_records_docker_digest_in_manifest(tmp_path) -> None:
    """A docker runner's resolved image digest is recorded in the manifest."""
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(),
        merge=_make_merge(out),
        runner=_FakeDockerRunner(repo=repo, digest="sha256:abc"),
    )
    assert ok is True
    manifest = json.loads(
        (repo / "data" / "leiden_250_AHN5" / ".cftree_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["runner"] == "sha256:abc"


def test_ensure_manifest_falls_back_to_image_without_digest(tmp_path) -> None:
    """A docker-style runner without a resolved digest still pins its tag."""
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(),
        merge=_make_merge(out),
        runner=_FakeDockerRunner(repo=repo),
    )
    assert ok is True
    manifest = json.loads(
        (repo / "data" / "leiden_250_AHN5" / ".cftree_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["runner"] == "cftree:local"


def test_ensure_regenerates_when_docker_digest_changes(tmp_path) -> None:
    """Tiles built by one image are not reused after a re-pull under the same tag."""
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    aoi = box(0, 0, 250, 250)
    _seed_tile(repo, "leiden_250_AHN5")
    _write_manifest(
        _data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(aoi, spec, runner_id="sha256:old")
    )
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out),
        aoi,
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeDockerRunner(repo=repo, digest="sha256:new"),
    )
    assert ok is True
    assert len(run_calls) == 1  # a different digest regenerates rather than reusing


def test_ensure_caches_treeless_completed_run(tmp_path) -> None:
    """A completed-but-treeless run caches a valid empty file instead of looping.

    The bug: reuse required a non-empty tile set, so a legitimately treeless AOI
    re-ran CFTree every build and the merge raised FileNotFoundError, so no
    output was ever cached. Here a matching manifest with an empty tiles/ dir
    must skip the run and write a valid empty CityJSON.
    """
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    aoi = box(0, 0, 250, 250)
    (_data_dir(repo, "leiden_250_AHN5") / "tiles").mkdir(parents=True)
    _write_manifest(_data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(aoi, spec))
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []

    def _merge_raises_no_tiles(
        case_dir: Any, boundary: Any, output: Any, *, tree_filename: str = TILE_FILENAME, **_kw: Any
    ) -> int:
        # Mirrors the real merge_case on a tile set with no tree files.
        raise FileNotFoundError(f"No {tree_filename} files found under {case_dir}/tiles/")

    ok = ensure_tree_file(
        _source(out),
        aoi,
        run=_make_run(calls=run_calls),
        merge=_merge_raises_no_tiles,
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert run_calls == []  # the completed run was reused, not re-run
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["type"] == "CityJSON"
    assert payload["CityObjects"] == {}


# ---------------------------------------------------------------------------
# ensure_tree_file: geometry-only mode
# ---------------------------------------------------------------------------


def test_ensure_threads_geometry_only_to_command_and_manifest(tmp_path) -> None:
    """A geometry-only source runs CFTree with --geometry-only and records the mode."""
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out, geometry_only=True),
        box(0, 0, 250, 250),
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert len(run_calls) == 1
    assert "--geometry-only" in run_calls[0]
    manifest = json.loads(
        (repo / "data" / "leiden_250_AHN5" / ".cftree_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["geometry_only"] is True


def test_ensure_reuses_complete_geometry_only_run(tmp_path) -> None:
    """A geometry-only manifest is reused for a geometry-only request."""
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    aoi = box(0, 0, 250, 250)
    _seed_tile(repo, "leiden_250_AHN5")
    _write_manifest(
        _data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(aoi, spec, geometry_only=True)
    )
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out, geometry_only=True),
        aoi,
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert run_calls == []  # geometry-only tiles reused for a geometry-only build


def test_ensure_regenerates_when_geometry_only_flag_flips(tmp_path) -> None:
    """A full-mode manifest does not satisfy a geometry-only request: the mode is part of identity."""
    repo = tmp_path / "cftree"
    spec = VegetationGenerateSpec(ahn_version=5, n_cores=8, buffer_m=20.0)
    aoi = box(0, 0, 250, 250)
    _seed_tile(repo, "leiden_250_AHN5")
    # Manifest recorded for a full (non-geometry-only) run.
    _write_manifest(_data_dir(repo, "leiden_250_AHN5"), _aoi_fingerprint(aoi, spec))
    out = tmp_path / "veg" / "leiden_250.city.json"
    run_calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out, geometry_only=True),  # now asking for geometry-only
        aoi,
        run=_make_run(calls=run_calls),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is True
    assert len(run_calls) == 1  # full-mode tiles not reused for a geometry-only build
    assert "--geometry-only" in run_calls[0]


# ---------------------------------------------------------------------------
# ensure_tree_file: soft-fail paths
# ---------------------------------------------------------------------------


def test_ensure_soft_fails_when_cftree_errors(tmp_path) -> None:
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(cftree_code=1),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is False
    assert not out.exists()
    # No manifest is written for a failed run.
    assert not (repo / "data" / "leiden_250_AHN5" / ".cftree_manifest.json").exists()


def test_ensure_soft_fails_when_cftree_launch_raises_oserror(tmp_path) -> None:
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(raise_oserror=True),
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is False
    assert not out.exists()


def test_ensure_soft_fails_when_cftree_times_out(tmp_path) -> None:
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    seen: dict[str, Any] = {}

    def _run(cmd: Any, cwd: Any = None, check: bool = False, timeout: Any = None) -> Any:
        seen["timeout"] = timeout
        raise subprocess.TimeoutExpired(cmd, timeout)

    ok = ensure_tree_file(
        _source(out, timeout_min=1),
        box(0, 0, 250, 250),
        run=_run,
        merge=_make_merge(out),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is False
    assert not out.exists()
    # timeout_min=1 reaches run() as 60 seconds (proves the plumbing, not just the branch).
    assert seen["timeout"] == 60


def test_ensure_kills_named_docker_container_on_timeout(tmp_path) -> None:
    """A timed-out docker run is killed by its --name so no orphan keeps running."""
    work = tmp_path / "work"
    work.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    calls: list[list[str]] = []

    def _run(cmd: Any, cwd: Any = None, check: bool = False, timeout: Any = None) -> Any:
        argv = [str(c) for c in cmd]
        calls.append(argv)
        if argv[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(argv, timeout)
        return SimpleNamespace(returncode=0)

    ok = ensure_tree_file(
        _source(out, timeout_min=1),
        box(0, 0, 250, 250),
        run=_run,
        merge=_make_merge(out),
        runner=DockerRunner(repo=work, image="cftree:local"),
    )
    assert ok is False
    run_cmd = calls[0]
    name = run_cmd[run_cmd.index("--name") + 1]
    assert ["docker", "kill", name] in calls


def test_ensure_resolves_docker_runner_from_env_with_injected_probes(tmp_path, monkeypatch) -> None:
    """With no injected runner, the env resolves to no-clone docker end-to-end.

    The same injected ``run`` serves the preflight probes and the CFTree
    launch, so nothing touches a real docker daemon; the case geojson and
    manifest land under the work root and the manifest pins the digest.
    """
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    work = _docker_env(monkeypatch, tmp_path)
    out = tmp_path / "veg" / "leiden_250.city.json"
    calls: list[list[str]] = []
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_docker_probes(calls=calls),
        merge=_make_merge(out),
    )
    assert ok is True
    assert (work / "cases" / "leiden_250_AHN5" / "case_area.geojson").is_file()
    manifest = json.loads(
        (work / "data" / "leiden_250_AHN5" / ".cftree_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["runner"] == _REPO_DIGEST
    docker_runs = [c for c in calls if c[:2] == ["docker", "run"]]
    assert len(docker_runs) == 1
    assert docker_runs[0][docker_runs[0].index("-w") + 1] == "/opt/cftree"


def test_ensure_setup_error_names_existing_output_file(tmp_path, monkeypatch) -> None:
    """A setup error with a reusable file on disk points at the escape hatch.

    The runner env is validated before the reuse check (the image digest
    is part of the reuse fingerprint), so a broken env fails even when a
    previous output could be served; the error must then name the file
    and the way to build with it as-is.
    """
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_RUNNER", "docker")  # CFTREE_IMAGE missing: setup error
    out = tmp_path / "veg" / "leiden_250.city.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")
    with pytest.raises(CityBuildError, match="existing vegetation file"):
        ensure_tree_file(_source(out), box(0, 0, 250, 250), run=_make_docker_probes())


def test_ensure_setup_error_without_output_file_has_no_hint(tmp_path, monkeypatch) -> None:
    _no_dotenv(monkeypatch)
    _clear_cftree_env(monkeypatch)
    monkeypatch.setenv("CFTREE_RUNNER", "docker")
    out = tmp_path / "veg" / "leiden_250.city.json"
    with pytest.raises(CityBuildError) as excinfo:
        ensure_tree_file(_source(out), box(0, 0, 250, 250), run=_make_docker_probes())
    assert "existing vegetation file" not in str(excinfo.value)


def test_ensure_soft_fails_when_merge_raises(tmp_path) -> None:
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(),
        merge=_make_merge(out, raise_exc=ValueError("boom")),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is False
    assert not out.exists()


def test_ensure_false_when_merge_writes_nothing(tmp_path) -> None:
    """A merge that returns cleanly but writes no file still reports False."""
    repo = tmp_path / "cftree"
    repo.mkdir()
    out = tmp_path / "veg" / "leiden_250.city.json"
    ok = ensure_tree_file(
        _source(out),
        box(0, 0, 250, 250),
        run=_make_run(),
        merge=_make_merge(out, write=False),
        runner=_FakeRunner(repo=repo),
    )
    assert ok is False


# ---------------------------------------------------------------------------
# case_area.geojson producer/consumer contract
# ---------------------------------------------------------------------------


def test_write_case_geojson_polygon_roundtrips(tmp_path) -> None:
    """The written AOI parses back through the merge tool's boundary loader."""
    aoi = box(1000, 2000, 1250, 2250)
    geo = tmp_path / "cases" / "c" / "case_area.geojson"
    _write_case_geojson(geo, aoi)
    loaded = load_boundary_polygon(BoundarySource(path=geo))
    assert isinstance(loaded, Polygon)
    assert loaded.equals(aoi)


def test_write_case_geojson_multipolygon_roundtrips(tmp_path) -> None:
    aoi = MultiPolygon([box(0, 0, 10, 10), box(20, 20, 30, 30)])
    geo = tmp_path / "cases" / "c" / "case_area.geojson"
    _write_case_geojson(geo, aoi)
    feature_collection = json.loads(geo.read_text(encoding="utf-8"))
    assert feature_collection["features"][0]["geometry"]["type"] == "MultiPolygon"
    loaded = load_boundary_polygon(BoundarySource(path=geo))
    assert loaded.equals(aoi)
