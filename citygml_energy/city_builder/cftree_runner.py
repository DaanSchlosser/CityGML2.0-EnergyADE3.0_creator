"""On-demand CFTree generation: the seam that runs the tree pipeline.

The city build reads merged CFTree CityJSON from a configured path (see
:class:`citygml_energy.city_builder.vegetation.VegetationSource`). When
that file is missing and the config carries a ``vegetation.generate``
block, :func:`ensure_tree_file` produces it for the build AOI:

1. Write the AOI polygon as ``cases/<case>/case_area.geojson`` in the
   CFTree checkout (the input CFTree's ``main.py`` expects).
2. Run CFTree end-to-end for that case at the requested AHN version,
   unless a previous *complete* run for the *same* AOI is already on disk
   (recorded by a completion manifest, see below). When the source is
   geometry-only (:attr:`VegetationSource.geometry_only`), CFTree runs
   with ``--geometry-only``, which skips the descriptive morphometrics
   (r50, porosity) for a several-times-faster reconstruction; the same
   flag makes the loader skip the authoritative-register cross-reference,
   so the run and the load never disagree on what a tree carries.
3. Merge the per-tile output into the configured path, clipped to the
   AOI, by calling :func:`tools.merge_cftree_tiles.merge_case` in-process
   (it needs only ``citygml_energy`` + shapely, both already loaded), so
   the clip / re-numbering rules stay in one place and a merge error
   surfaces as a typed exception rather than an opaque exit code.

CFTree is a heavy, separately-installed pipeline (CGAL, PDAL, compiled
C++), so it cannot be imported in-process; it is always a subprocess.
How that subprocess is launched is the one machine-specific decision,
isolated behind the :class:`CFTreeRunner` seam. Two adapters keep it a
real seam rather than indirection:

* :class:`WslRunner` launches the Linux ``cftree`` interpreter from
  Windows via ``wsl.exe`` (the default on Windows), translating the
  checkout path to ``/mnt/<drive>/...``.
* :class:`NativeRunner` launches the interpreter directly (Linux, or a
  native Windows conda env), the default off Windows.

The machine details come from the environment, never the config, so a
checked-in config stays free of absolute paths:

* ``CFTREE_REPO``    the CFTree checkout (default: a sibling ``../CFTree``).
* ``CFTREE_RUNNER``  ``wsl`` or ``native`` (default: ``wsl`` on Windows).
* ``CFTREE_PYTHON``  the interpreter that runs CFTree (e.g.
  ``/home/<user>/miniconda3/envs/cftree/bin/python`` under WSL).

Reuse safety: a previous run is reused only when a completion manifest
(``data/<case>/.cftree_manifest.json``, written by this module after a
clean CFTree exit) matches the requested AOI bounds, buffer, AHN
version, and geometry-only mode. A partial run left by a crash or Ctrl-C
has no manifest and is regenerated rather than silently merged into an
incomplete tree set; a changed AOI (or a flip of the geometry-only flag)
under the same output path likewise regenerates instead of reusing stale
or wrong-mode tiles.

Every failure mode degrades to a treeless build with a warning, matching
the soft-fail contract of the other city fetchers: a missing CFTree
checkout, an unset interpreter, a non-zero CFTree exit, a timeout, or a
merge error returns ``False`` and the build proceeds without vegetation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, Protocol

from . import _env

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from .vegetation import VegetationGenerateSpec, VegetationSource

__all__ = [
    "CFTreeRunner",
    "DockerRunner",
    "NativeRunner",
    "WslRunner",
    "ensure_tree_file",
    "resolve_runner",
]

_LOG = logging.getLogger(__name__)

# citygml_energy/city_builder/cftree_runner.py -> repo root is two up.
_CREATOR_ROOT: Path = Path(__file__).resolve().parents[2]

# Default ceiling on the CFTree subprocess (6 h), comfortably above the
# documented 30-120 min worst case so only a genuinely stuck run is
# killed. Overridable per build via ``vegetation.generate.timeout_min``.
_DEFAULT_CFTREE_TIMEOUT_S: int = 6 * 60 * 60

# Completion marker written next to a case's tiles after a clean CFTree
# run. Holds the AOI fingerprint so a later build can tell a complete,
# same-AOI run (reusable) from a partial or different-AOI one.
_MANIFEST_FILENAME = ".cftree_manifest.json"

# Soft guardrail: warn when the on-demand AOI is far larger than the
# intended small extract (a 250 m address square is ~0.06 km^2), since a
# run that size costs hours and gigabytes.
_AOI_WARN_AREA_M2: float = 4_000_000.0

# subprocess.run-compatible callable, injected in tests so the long
# CFTree run never actually launches. Named distinctly from CFTreeRunner
# (the launch strategy) to keep the two roles apart.
RunCallable = Callable[..., Any]

# tools.merge_cftree_tiles.merge_case-compatible callable, injected in
# tests so the in-process merge can be stubbed without real tiles.
MergeCallable = Callable[..., int]


class CFTreeRunner(Protocol):
    """How to launch CFTree for one case, isolated from the orchestration.

    :attr:`repo` is the CFTree checkout as the *creator* sees it (a
    Windows path under WSL), used for file operations. :attr:`cwd` is the
    working directory for the subprocess (``None`` when the command sets
    it itself, as the WSL ``cd`` does). :meth:`command` returns the argv
    to hand to :func:`subprocess.run`.
    """

    @property
    def repo(self) -> Path: ...

    @property
    def cwd(self) -> Path | None: ...

    def command(
        self,
        *,
        case: str,
        ahn_version: int,
        n_cores: int,
        buffer_m: float,
        geometry_only: bool = False,
    ) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class NativeRunner:
    """Run CFTree's interpreter directly (Linux, or a native conda env)."""

    repo: Path
    python: str

    @property
    def cwd(self) -> Path | None:
        return self.repo

    def command(
        self,
        *,
        case: str,
        ahn_version: int,
        n_cores: int,
        buffer_m: float,
        geometry_only: bool = False,
    ) -> list[str]:
        cmd = [
            self.python,
            "main.py",
            "--case",
            case,
            "--ahn-version",
            str(ahn_version),
            "--n-cores",
            str(n_cores),
            "--buffer",
            _fmt_num(buffer_m),
            "--overwrite",
        ]
        if geometry_only:
            cmd.append("--geometry-only")
        return cmd


@dataclass(frozen=True, slots=True)
class WslRunner:
    """Run CFTree's Linux interpreter from Windows through ``wsl.exe``.

    The checkout path is translated to ``/mnt/<drive>/...`` and a login
    shell ``cd``s into it, so the working directory rides inside the
    command and :attr:`cwd` stays ``None``. The interpreter is the
    absolute path to the ``cftree`` env's Python inside WSL, because
    conda's shell hooks are not on a non-interactive login PATH.

    For the same reason the interpreter's own directory is prepended to
    ``PATH`` before launch: CFTree's ``main.py`` spawns each stage as a
    bare ``python -m scripts.<stage>`` subprocess, so without the env's
    ``bin`` on ``PATH`` those children resolve to whatever ``python`` the
    login shell exposes (on Windows, the App-Execution-Alias stub under
    ``WindowsApps`` that exits 127 "Permission denied"). Prepending the
    ``bin`` directory is the minimal activation that makes the child
    stages reuse the same interpreter; conda-built packages find their
    shared libraries by RPATH, so no further activation is needed.
    """

    repo: Path
    python: str

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
        bindir = _wsl_python_bindir(self.python)
        # ``$PATH`` must stay double-quoted: under WSL it inherits the Windows
        # PATH, whose entries contain spaces and parens (``Program Files
        # (x86)``); an unquoted expansion would word-split into a shell syntax
        # error. The bin directory itself is shell-quoted for the same reason.
        activate = f'export PATH={shlex.quote(bindir)}:"$PATH" && ' if bindir else ""
        inner = (
            f"cd {shlex.quote(_to_wsl_path(self.repo))} && "
            f"{activate}"
            f"{shlex.quote(self.python)} main.py "
            f"--case {shlex.quote(case)} "
            f"--ahn-version {ahn_version} "
            f"--n-cores {n_cores} "
            f"--buffer {_fmt_num(buffer_m)} "
            f"--overwrite"
        )
        if geometry_only:
            inner += " --geometry-only"
        return ["wsl.exe", "bash", "-lc", inner]


@dataclass(frozen=True, slots=True)
class DockerRunner:
    """Run CFTree inside a Linux container via ``docker run``.

    The checkout is bind-mounted at ``/work`` and the container's working
    directory is ``/work``, so CFTree resolves ``cases/``, ``data/``, and
    ``resources/`` against the same files the creator's in-process merge later
    reads on the host. The conda environment and the two compiled C++ binaries
    are baked into the image, so a colleague installs no toolchain: the binaries
    are found through the image's ``CFTREE_BIN`` even though the bind-mounted
    source tree carries no ``build/`` outputs.

    :attr:`extra_args` is split from ``CFTREE_DOCKER_ARGS`` and passed verbatim
    to ``docker run`` before the image, for host-specific tuning such as
    ``--gpus all`` (to enable the GPU morphometrics), ``--memory``, ``--cpus``,
    or ``--shm-size``. The image reference itself is part of the reuse
    fingerprint (see :func:`_aoi_fingerprint`), so re-tagging the image
    regenerates rather than reusing tiles a different image produced.
    """

    repo: Path
    image: str
    extra_args: tuple[str, ...] = ()

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
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{_to_docker_mount(self.repo)}:/work",
            "-w",
            "/work",
            *self.extra_args,
            self.image,
            "python",
            "main.py",
            "--case",
            case,
            "--ahn-version",
            str(ahn_version),
            "--n-cores",
            str(n_cores),
            "--buffer",
            _fmt_num(buffer_m),
            "--overwrite",
        ]
        if geometry_only:
            cmd.append("--geometry-only")
        return cmd


def resolve_runner() -> CFTreeRunner | None:
    """Build a :class:`CFTreeRunner` from the environment, or ``None``.

    Loads the repo-root ``.env`` first, then reads ``CFTREE_REPO`` /
    ``CFTREE_RUNNER`` / ``CFTREE_PYTHON``. Unlike the config-local
    EP-Online key, these are machine-level settings, so the ``.env`` is
    discovered from the creator root (and ``CFTREE_REPO`` falls back to a
    sibling ``../CFTree`` checkout), not from a config file's directory.
    Returns ``None`` (with a warning naming the missing piece) when the
    checkout cannot be found, the interpreter is unset, or the checkout is
    not reachable from the chosen runner, so the caller soft-fails to a
    treeless build instead of crashing.
    """
    _env.maybe_load_dotenv(_CREATOR_ROOT)

    repo = _resolve_repo()
    if repo is None:
        return None

    kind = (os.environ.get("CFTREE_RUNNER") or ("wsl" if os.name == "nt" else "native")).strip()
    python = (os.environ.get("CFTREE_PYTHON") or "").strip()

    if kind == "docker":
        image = (os.environ.get("CFTREE_IMAGE") or "").strip()
        if not image:
            _LOG.warning(
                "Tree generation with CFTREE_RUNNER=docker needs CFTREE_IMAGE (the CFTree image "
                "reference, e.g. cftree:local or ghcr.io/<owner>/cftree:<tag>); skipping trees"
            )
            return None
        try:
            _to_docker_mount(repo)
        except ValueError as exc:
            _LOG.warning("%s; skipping trees", exc)
            return None
        extra = tuple(shlex.split(os.environ.get("CFTREE_DOCKER_ARGS") or ""))
        return DockerRunner(repo=repo, image=image, extra_args=extra)
    if kind == "wsl":
        if not python:
            _LOG.warning(
                "Tree generation needs CFTREE_PYTHON (the cftree env interpreter inside "
                "WSL, e.g. /home/<user>/miniconda3/envs/cftree/bin/python); skipping trees"
            )
            return None
        try:
            _to_wsl_path(repo)
        except ValueError as exc:
            _LOG.warning("%s; skipping trees", exc)
            return None
        return WslRunner(repo=repo, python=python)
    if kind == "native":
        return NativeRunner(repo=repo, python=python or "python")
    _LOG.warning("Unknown CFTREE_RUNNER=%r (expected 'wsl' or 'native'); skipping trees", kind)
    return None


def ensure_tree_file(
    source: VegetationSource,
    aoi_geom: BaseGeometry | None,
    *,
    run: RunCallable = subprocess.run,
    merge: MergeCallable | None = None,
    runner: CFTreeRunner | None = None,
) -> bool:
    """Make sure *source*'s merged CityJSON exists, generating it if needed.

    Returns ``True`` when the file is present afterwards (already there,
    or freshly produced), ``False`` when nothing could be done. A
    ``False`` is never fatal: the caller's loader treats a missing file
    as a treeless build. ``True`` means the file exists, not that it
    holds trees (an AOI with no trees yields a valid empty file).

    The work runs only when the file is missing *and* the config carries
    a ``generate`` spec. A previous *complete* run for the same AOI
    (matching completion manifest) is reused, skipping the long CFTree
    run; otherwise CFTree runs end-to-end and the AOI is clipped and
    merged into *source*'s path.

    The CFTree subprocess inherits this process's stdout/stderr, so its
    progress is visible when the build is launched from a terminal (the
    two shipped CLIs); a caller that captures or discards child output
    sees nothing until completion. The case directory is assumed to have
    a single writer: two concurrent builds targeting the same output path
    and AHN version share ``cases/<case>/`` and ``data/<case>/`` and would
    race, so do not run them in parallel. On timeout the direct child is
    terminated; under the WSL runner the Linux-side CFTree process tree can
    outlive that kill, so a timed-out run may need a manual check on the
    WSL side.

    ``run`` (the CFTree subprocess) and ``merge`` (the in-process tile
    merge) are injectable for tests.
    """
    out = Path(source.path)
    spec = source.generate

    # No generate spec: the file at ``path`` is a user-supplied input,
    # authoritative when present and impossible to produce when absent.
    if spec is None:
        return out.is_file()
    if aoi_geom is None:
        _LOG.warning("Tree generation requested but no AOI geometry is available; skipping trees")
        return out.is_file()

    runner = runner if runner is not None else resolve_runner()
    if runner is None:
        return out.is_file()

    resolved = _resolve_merge()
    if resolved is None:
        return out.is_file()
    default_merge, tree_filename = resolved
    merge = merge if merge is not None else default_merge

    # Namespace the case by AHN version so bumping ahn_version never reuses
    # the previous version's per-tile output. An explicit spec.case opts out.
    case = spec.case or f"{_derive_case(out)}_AHN{spec.ahn_version}"
    if not _is_safe_case(case):
        # Defence in depth behind the config validator: case becomes a
        # directory segment in the CFTree checkout, so refuse anything
        # that is not a single safe path component (traversal, separators).
        _LOG.error(
            "Refusing unsafe CFTree case name %r (must be a single path segment); skipping trees",
            case,
        )
        return out.is_file()

    _warn_if_large_aoi(aoi_geom)

    data_dir = _data_dir(runner.repo, case)
    # The docker runner carries an image reference; fold it into the fingerprint
    # so tiles built by one image are not reused for a build that asks for a
    # different image (a re-tag can change the binaries or the GPU/CPU metric
    # path). The WSL and native runners have no such attribute, so their
    # fingerprint is unchanged and existing manifests still match.
    runner_id = getattr(runner, "image", None)
    fingerprint = _aoi_fingerprint(
        aoi_geom, spec, geometry_only=source.geometry_only, runner_id=runner_id
    )
    manifest = _read_manifest(data_dir)
    tiles = _existing_tiles(data_dir, tree_filename)

    # An existing merged output is reused unless a completion manifest proves it
    # was built for a *different* AOI. A user-supplied file (no manifest) and a
    # matching prior run are both served as-is; a stale generated file (manifest
    # for a different AOI/buffer/AHN/mode) is regenerated. This is the check that
    # stops a reused output path -- two addresses pointed at one vegetation file
    # -- from serving the first address's trees for the second.
    if out.is_file() and (manifest is None or manifest == fingerprint):
        _LOG.info("Reusing existing vegetation file %s for case %r", out, case)
        return True

    geojson_path = _case_geojson_path(runner.repo, case)
    try:
        _write_case_geojson(geojson_path, aoi_geom)
    except OSError as exc:
        _LOG.error(
            "Could not write CFTree case geometry %s (%s); skipping trees", geojson_path, exc
        )
        return out.is_file()

    # Reuse the heavy CFTree run when the manifest matches this AOI, even if no
    # merged output is on disk yet (re-merge only) and even when the run was
    # legitimately treeless (no tiles): a matching manifest is itself proof the
    # run completed, so it must not be gated on a non-empty tile set.
    if manifest != fingerprint:
        _log_regeneration_reason(manifest, tiles, fingerprint, case)
        if not _run_cftree(runner, spec, case, geometry_only=source.geometry_only, run=run):
            return out.is_file()
        try:
            _write_manifest(data_dir, fingerprint)
        except OSError as exc:
            _LOG.warning(
                "Could not write CFTree completion manifest for case %r (%s); "
                "the next build may regenerate",
                case,
                exc,
            )
    else:
        _LOG.info(
            "Reusing complete CFTree run for case %r (AOI bounds %s)", case, fingerprint["bounds"]
        )

    if not _merge_case(merge, data_dir, geojson_path, out, tree_filename=tree_filename):
        return out.is_file()
    return out.is_file()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_repo() -> Path | None:
    """Resolve the CFTree checkout from ``CFTREE_REPO`` or a sibling dir."""
    raw = (os.environ.get("CFTREE_REPO") or "").strip()
    if raw:
        repo = Path(raw)
        if repo.is_dir():
            return repo
        _LOG.warning("CFTREE_REPO=%s is not a directory; skipping trees", raw)
        return None
    sibling = _CREATOR_ROOT.parent / "CFTree"
    if sibling.is_dir():
        return sibling
    _LOG.warning(
        "Tree generation needs the CFTree checkout: set CFTREE_REPO or place it at %s; "
        "skipping trees",
        sibling,
    )
    return None


def _resolve_merge() -> tuple[MergeCallable, str] | None:
    """Import the in-process merge entry point and the per-tile filename.

    Returns ``(merge_case, tile_filename)`` from
    :mod:`tools.merge_cftree_tiles` (the single source of truth for the
    filename, so the reuse glob and the merge can never disagree), or
    ``None`` with an error log when the merge tool cannot be imported.
    """
    try:
        from tools.merge_cftree_tiles import TILE_FILENAME, merge_case
    except ImportError:
        # Entry points add the repo root to sys.path; add it here too for
        # contexts (some embeddings) that import this module another way.
        if str(_CREATOR_ROOT) not in sys.path:
            sys.path.insert(0, str(_CREATOR_ROOT))
        try:
            from tools.merge_cftree_tiles import TILE_FILENAME, merge_case
        except ImportError as exc:  # pragma: no cover - repo layout broken
            _LOG.error(
                "Cannot import the CFTree merge tool (tools.merge_cftree_tiles): %s; skipping trees",
                exc,
            )
            return None
    return merge_case, TILE_FILENAME


def _run_cftree(
    runner: CFTreeRunner,
    spec: VegetationGenerateSpec,
    case: str,
    *,
    geometry_only: bool,
    run: RunCallable,
) -> bool:
    """Launch CFTree for *case*; return whether it exited cleanly.

    *geometry_only* forwards CFTree's ``--geometry-only`` flag, which
    skips the descriptive morphometrics (r50, porosity) for a several-
    times-faster reconstruction. It is driven by
    :attr:`VegetationSource.geometry_only`, the same flag that makes the
    loader skip the authoritative-register cross-reference, so the run
    and the load stay in agreement.
    """
    try:
        cmd = runner.command(
            case=case,
            ahn_version=spec.ahn_version,
            n_cores=spec.n_cores,
            buffer_m=spec.buffer_m,
            geometry_only=geometry_only,
        )
    except ValueError as exc:
        _LOG.error("Cannot build the CFTree command (%s); building without trees", exc)
        return False

    timeout_s = spec.timeout_min * 60 if spec.timeout_min else _DEFAULT_CFTREE_TIMEOUT_S
    if geometry_only:
        _LOG.info(
            "Running CFTree (AHN%d, geometry-only) for case %r. Geometry-only skips the "
            "descriptive metrics and runs several times faster than a full reconstruction; "
            "leave the build running …",
            spec.ahn_version,
            case,
        )
    else:
        _LOG.info(
            "Running CFTree (AHN%d) for case %r. This can take 30-120 min on this machine; "
            "leave the build running …",
            spec.ahn_version,
            case,
        )
    _LOG.debug("CFTree command: %s", " ".join(cmd))
    try:
        result = run(cmd, cwd=runner.cwd, check=False, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _LOG.error(
            "CFTree exceeded its %d-minute timeout for case %r; building without trees. "
            "Raise vegetation.generate.timeout_min for a larger AOI.",
            round(timeout_s / 60),
            case,
        )
        return False
    except OSError as exc:
        _LOG.error("Could not launch CFTree (%s); building without trees", exc)
        return False
    code = getattr(result, "returncode", 1)
    if code != 0:
        _LOG.error(
            "CFTree exited with status %s for case %r; building without trees. Check that "
            "CFTREE_PYTHON points at a valid cftree env and the CFTree install is intact. "
            "Command: %s",
            code,
            case,
            " ".join(cmd),
        )
        return False
    return True


def _merge_case(
    merge: MergeCallable,
    data_dir: Path,
    boundary_geojson: Path,
    output: Path,
    *,
    tree_filename: str,
) -> bool:
    """Merge a CFTree case's tiles into *output* in-process, clipped to the AOI.

    Calls :func:`tools.merge_cftree_tiles.merge_case` directly (no
    subprocess: it needs only ``citygml_energy`` + shapely, already
    loaded). Any merge problem soft-fails to a treeless build, matching
    the module's contract that no vegetation step is ever fatal.
    """
    _LOG.info("Merging CFTree tiles from %s into %s", data_dir, output)
    try:
        merge(data_dir, boundary_geojson, output, tree_filename=tree_filename)
    except FileNotFoundError:
        # A completed run with no per-tile tree files is a legitimately treeless
        # AOI, not a merge error. Write a valid empty CityJSON so the result is
        # cached (the matching manifest is already on disk) instead of
        # re-running the whole pipeline on every build.
        _LOG.info("CFTree case at %s produced no trees; writing an empty vegetation file", data_dir)
        try:
            from tools.merge_cftree_tiles import write_empty_merged_cityjson

            write_empty_merged_cityjson(
                output, case_label=data_dir.name, boundary_label=boundary_geojson.name
            )
        except Exception as exc:  # soft-fail to a treeless build
            _LOG.error("Could not write empty vegetation file (%s); building without trees", exc)
            return False
        return True
    except Exception as exc:  # soft-fail any other merge problem to a treeless build
        _LOG.error("CFTree tile merge failed (%s); building without trees", exc)
        return False
    return True


def _existing_tiles(data_dir: Path, tree_filename: str) -> list[Path]:
    """Per-tile CFTree outputs already present for a case (empty if none)."""
    tiles_dir = data_dir / "tiles"
    if not tiles_dir.is_dir():
        return []
    return sorted(tiles_dir.glob(f"*/{tree_filename}"))


def _geometry_digest(aoi_geom: BaseGeometry) -> str:
    """Shape-sensitive, jitter-tolerant digest of the AOI geometry.

    The bounds alone cannot distinguish two AOIs that share a bounding box but
    differ in shape (an edited concave boundary, a different parcel union), so
    a bounds-only fingerprint would reuse one shape's tiles for the other.
    Coordinates are snapped to a 0.1 m grid first so float jitter on a re-read
    of the same boundary does not flip the digest, matching the bounds
    rounding.
    """
    try:
        from shapely import set_precision

        wkb = set_precision(aoi_geom, 0.1).wkb
    except Exception:  # pragma: no cover - older shapely without set_precision
        wkb = aoi_geom.wkb
    return hashlib.sha256(wkb).hexdigest()


def _aoi_fingerprint(
    aoi_geom: BaseGeometry,
    spec: VegetationGenerateSpec,
    *,
    geometry_only: bool = False,
    runner_id: str | None = None,
) -> dict[str, Any]:
    """Identity of the reconstruction a case stands for: AOI + buffer + AHN + mode.

    Bounds are rounded to 0.1 m so float jitter never forces a needless
    regenerate, while a real AOI change (different extent, edited
    boundary) still flips the fingerprint and invalidates reuse. The bounds
    are paired with a shape digest so two AOIs that share a bounding box but
    differ in shape do not collide on the same fingerprint.

    *geometry_only* is part of the identity because a geometry-only run
    writes null morphometrics: a tile set built one way must not be
    reused for a build that asked for the other, so flipping the flag
    regenerates rather than serving tiles with the wrong attribute
    completeness.

    *runner_id* (the docker image reference, when the docker runner is used)
    is folded in for the same reason: tiles a given image produced must not be
    reused for a build pinned to a different image. It is omitted from the dict
    when ``None`` (the WSL and native runners), so their fingerprints, and any
    manifest already on disk, are byte-for-byte unchanged.
    """
    minx, miny, maxx, maxy = aoi_geom.bounds
    fingerprint: dict[str, Any] = {
        "bounds": [round(minx, 1), round(miny, 1), round(maxx, 1), round(maxy, 1)],
        "geometry": _geometry_digest(aoi_geom),
        "buffer_m": float(spec.buffer_m),
        "ahn_version": int(spec.ahn_version),
        "geometry_only": bool(geometry_only),
    }
    if runner_id:
        fingerprint["runner"] = str(runner_id)
    return fingerprint


def _read_manifest(data_dir: Path) -> dict[str, Any] | None:
    """Read a case's completion manifest, or ``None`` if absent/unreadable."""
    path = data_dir / _MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_manifest(data_dir: Path, fingerprint: dict[str, Any]) -> None:
    """Record a clean CFTree run's AOI fingerprint next to its tiles."""
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / _MANIFEST_FILENAME).write_text(json.dumps(fingerprint), encoding="utf-8")


def _log_regeneration_reason(
    manifest: dict[str, Any] | None,
    tiles: list[Path],
    fingerprint: dict[str, Any],
    case: str,
) -> None:
    """Explain why a CFTree run is (re)launched rather than reused."""
    if manifest is None and tiles:
        _LOG.warning(
            "Found %d CFTree tile(s) for case %r without a completion manifest (a prior run may "
            "have been interrupted, or predates this check); regenerating",
            len(tiles),
            case,
        )
    elif manifest is not None and manifest != fingerprint:
        _LOG.warning(
            "CFTree output for case %r was built for a different AOI/buffer/AHN; regenerating "
            "(had %s, want %s)",
            case,
            manifest,
            fingerprint,
        )


def _warn_if_large_aoi(aoi_geom: BaseGeometry) -> None:
    """Warn when the on-demand AOI is far larger than the intended extract."""
    try:
        area = float(aoi_geom.area)
    except (AttributeError, TypeError):  # pragma: no cover - shapely always has .area
        return
    if area > _AOI_WARN_AREA_M2:
        _LOG.warning(
            "CFTree AOI is %.2f km^2 (above the %.1f km^2 guideline for on-demand generation); a "
            "run this size can take many hours and a lot of disk. Consider a smaller extent or a "
            "pre-built vegetation file.",
            area / 1e6,
            _AOI_WARN_AREA_M2 / 1e6,
        )


def _is_safe_case(case: str) -> bool:
    """True when *case* is a single safe path segment (no traversal, no whitespace)."""
    if not case or case in {".", ".."}:
        return False
    if "/" in case or "\\" in case or any(ch.isspace() for ch in case):
        return False
    return case == Path(case).name


def _case_geojson_path(repo: Path, case: str) -> Path:
    """Where a case's AOI GeoJSON lives inside the CFTree checkout."""
    return repo / "cases" / case / "case_area.geojson"


def _data_dir(repo: Path, case: str) -> Path:
    """Where a case's per-tile CFTree output lives inside the checkout."""
    return repo / "data" / case


def _write_case_geojson(path: Path, aoi_geom: BaseGeometry) -> None:
    """Write *aoi_geom* as a single-feature EPSG:28992 FeatureCollection.

    This is exactly the shape CFTree's ``cases/<case>/case_area.geojson``
    and the merge tool's ``--boundary`` both accept, so one file serves
    both the reconstruction AOI and the merge clip.
    """
    from shapely.geometry import mapping

    path.parent.mkdir(parents=True, exist_ok=True)
    feature_collection = {
        "type": "FeatureCollection",
        "name": path.parent.name,
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::28992"}},
        "features": [
            {"type": "Feature", "properties": {}, "geometry": mapping(aoi_geom)},
        ],
    }
    path.write_text(json.dumps(feature_collection), encoding="utf-8")


def _derive_case(output: Path) -> str:
    """Derive a stable CFTree case name from the merged-file name.

    ``leiden_250.city.json`` -> ``leiden_250`` so one AOI maps to one
    ``cases/<case>/`` and ``data/<case>/`` pair across rebuilds.
    """
    name = output.name
    if name.endswith(".city.json"):
        return name[: -len(".city.json")]
    return output.stem


def _to_wsl_path(path: Path) -> str:
    """Translate a Windows path to its ``/mnt/<drive>/...`` WSL form.

    A non-drive path (already POSIX) is returned with separators
    normalised, so the helper is a no-op on Linux. A UNC path
    (``\\\\server\\share\\...``) has no ``/mnt`` mapping, so it raises
    :class:`ValueError` rather than emitting a path WSL cannot ``cd``
    into.
    """
    win = PureWindowsPath(path)
    if win.drive.startswith("\\\\"):
        raise ValueError(
            f"UNC path {str(path)!r} is not supported by the WSL runner; use a drive-letter "
            f"checkout (e.g. C:\\...) or set CFTREE_RUNNER=native"
        )
    if len(win.drive) == 2 and win.drive.endswith(":"):
        drive = win.drive[0].lower()
        tail = "/".join(win.parts[1:])
        return f"/mnt/{drive}/{tail}"
    return str(path).replace("\\", "/")


def _to_docker_mount(path: Path) -> str:
    """Render *path* as a ``docker run -v`` source.

    Docker accepts a Windows drive path written with forward slashes
    (``C:/Users/...``), which avoids any backslash quoting in the argv. A UNC
    path (``\\\\server\\share\\...``) has no bind-mount form, so it raises
    :class:`ValueError` rather than emitting a spec docker cannot mount. On Linux
    the POSIX path is returned unchanged, so the helper is a no-op there.
    """
    win = PureWindowsPath(path)
    if win.drive.startswith("\\\\"):
        raise ValueError(
            f"UNC path {str(path)!r} is not supported by the docker runner; use a drive-letter "
            f"checkout (e.g. C:\\...) or set CFTREE_RUNNER=native"
        )
    if len(win.drive) == 2 and win.drive.endswith(":"):
        return win.as_posix()
    return str(path).replace("\\", "/")


def _wsl_python_bindir(python: str) -> str | None:
    """The interpreter's own directory, for prepending to ``PATH``.

    CFTree's child stages call a bare ``python``, so the env's ``bin``
    must be on ``PATH`` for them to reuse the configured interpreter (see
    :class:`WslRunner`). Returns the POSIX parent directory of *python*
    when it is an absolute POSIX path (the normal WSL case, e.g.
    ``/home/<user>/miniconda3/envs/cftree/bin/python`` ->
    ``/home/<user>/miniconda3/envs/cftree/bin``); returns ``None`` for a
    bare command name or the filesystem root, where there is nothing
    useful to prepend.
    """
    posix = PurePosixPath(python)
    if posix.is_absolute() and posix.parent != PurePosixPath("/"):
        return str(posix.parent)
    return None


def _fmt_num(value: float) -> str:
    """Render a number without a trailing ``.0`` so ``20.0`` reads ``20``."""
    return str(int(value)) if float(value).is_integer() else str(value)
