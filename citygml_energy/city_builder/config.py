"""Configuration schema for the city-scale builder.

A single JSON document drives the whole workflow. The loader keeps
validation explicit so errors surface with the file path + JSON pointer
that triggered them, matching the style of the per-building
``input_loader`` in the rest of the package.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import CityBuildError
from ..namespaces import DEFAULT_SRS_DIMENSION, DEFAULT_SRS_NAME

PathLike = str | Path


# ``BuildContext`` is defined ahead of the per-source imports below
# because the same per-source modules (``solar_panels``, ``vegetation``)
# re-import it via the ``builders/`` package: defining the class first
# makes it available when those modules' import-time chains land back
# in this module mid-load. Reordering the imports the other way around
# triggers the circular-import diagnostic at first use.
@dataclass(frozen=True, slots=True)
class BuildContext:
    """Layout-constant context shared by every model-mutating builder.

    The pipeline assembles one :class:`BuildContext` from a
    :class:`CityBuildConfig` (via :meth:`from_config` or
    :meth:`CityBuildConfig.build_context`) and threads it into every
    function that materialises xsdata features for the city: the
    per-Pand builders, the solar-collector attach, the postcode6 attach,
    and the vegetation attach. Carrying the trio (and the two related
    constants ``lods`` + ``municipality``) on one struct removes the
    per-call kwarg threading that previously leaked into every
    builder's signature.

    Field defaults match the validation defaults applied by
    :func:`load_city_config`, so a unit test that constructs a context
    explicitly (e.g. ``BuildContext(srs_dimension=2)``) inherits the
    same baseline a production run starts from. Frozen +
    ``slots=True`` matches the immutability + small-payload semantics
    of the other source dataclasses (:class:`SolarPanelsSource`,
    :class:`VegetationSource`, :class:`TreeBundle`); the instance is
    cheap to share across the worker-pool boundary.
    """

    gml_id_prefix: str = ""
    lods: tuple[int, ...] = (0, 1, 2)
    srs_name: str = DEFAULT_SRS_NAME
    srs_dimension: int = DEFAULT_SRS_DIMENSION
    municipality: str = ""

    @classmethod
    def from_config(cls, config: CityBuildConfig) -> BuildContext:
        """Build a :class:`BuildContext` from a fully-validated config."""
        return cls(
            gml_id_prefix=config.gml_id_prefix,
            lods=tuple(config.lods),
            srs_name=config.srs_name,
            srs_dimension=config.srs_dimension,
            municipality=config.municipality,
        )


from .boundary import (  # noqa: E402
    BoundarySource,
)
from .solar_panels import SolarPanelsSource  # noqa: E402
from .vegetation import VegetationSource  # noqa: E402


@dataclass(frozen=True)
class CbsPostcode6Source:
    """Validated CBS Postcode6 source configuration.

    Attributes:
        year: which CBS publication vintage to fetch from PDOK (e.g.
            ``2024``, which covers 2023 calendar-year consumption per
            CBS's documented one-year offset). Selects the WFS
            endpoint URL; the suppression rules and field semantics
            are stable across vintages.
    """

    year: int


# Environment variable name the builder consults for the EP-online key when
# no explicit ``ep_online_api_key_file`` is given. Works with python-dotenv:
# any ``.env`` next to the config is loaded before this lookup.
EP_ONLINE_ENV_VAR = "EP_ONLINE_API_KEY"

_NCNAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")

_ALLOWED_LODS: frozenset[int] = frozenset({0, 1, 2})


@dataclass(frozen=True)
class CityBuildConfig:
    """Validated city-build configuration.

    Attributes:
        source_path: the JSON file the config was loaded from (used for
            resolving relative paths such as ``ep_online_api_key_file``
            and ``cache_dir``).
        municipality: municipality name as used by PDOK
            ``bestuurlijkegebieden`` (e.g. ``"Delft"``).
        bbox: optional ``(minx, miny, maxx, maxy)`` in EPSG:28992 that
            further restricts the fetched area after the municipality
            outline is resolved. Useful for dev / smoke tests.
        lods: subset of ``{0, 1, 2}`` indicating which 3DBAG LoDs to
            attach. LoD 3 is not published in 3DBAG.
        include_addresses: whether to emit ``bldg:address`` per VBO.
        include_energy_labels: whether to download EP-online and emit
            ``nrg3:EnergyPerformanceCertificate`` per matched VBO.
        ep_online_api_key_file: absolute path to a file containing the
            EP-online API token; resolved relative to
            :attr:`source_path` when given as a relative path.
        cache_dir: directory used to cache remote downloads (FlatGeoBuf
            tile index, CityJSON tiles, EP-online CSV bundle); resolved
            relative to :attr:`source_path` when given relative.
        output_path: where the generated GML is written. Resolved
            relative to :attr:`source_path` when relative.
        srs_name / srs_dimension: written onto every produced
            ``gml:Envelope``, ``gml:MultiSurface`` and ``gml:Solid``.
        city_model_name / city_model_description: optional
            ``core:CityModel`` ``gml:name`` / ``gml:description``.
        gml_id_prefix: reserved for a future disambiguation scheme when
            multiple cities are merged; the BAG identificatie is
            globally unique already so this is left as an opt-in.
        solar_panels_source: optional external solar panel polygon
            GeoPackage; see
            :class:`citygml_energy.city_builder.solar_panels.SolarPanelsSource`.
            When present, the pipeline attaches one
            ``nrg3:GenericSolarCollector`` per panel to the Building
            whose LoD 2 RoofSurface has the largest 2D overlap. The
            source is a 2D aerial annotation with no module-level
            metadata, so the technology-agnostic
            ``GenericSolarCollector`` is emitted rather than asserting
            a specific cell type via ``PhotovoltaicCollector``.
        boundary_source: optional (free-form, possibly concave) polygon
            from a GeoPackage; see
            :class:`citygml_energy.city_builder.boundary.BoundarySource`.
            When present, the pipeline derives its rectangular fetch
            extent from the polygon's bounds and then drops any
            building whose 2D LoD 0 footprint does not intersect the
            polygon, so a hand-drawn concave outline trims cleanly.
            Mutually exclusive with :attr:`bbox`.
    """

    source_path: Path
    municipality: str
    bbox: tuple[float, float, float, float] | None
    lods: tuple[int, ...]
    include_addresses: bool
    include_energy_labels: bool
    ep_online_api_key_file: Path | None
    cache_dir: Path
    output_path: Path
    srs_name: str
    srs_dimension: int
    city_model_name: str | None
    city_model_description: str | None
    gml_id_prefix: str
    file_header: str | None = None
    solar_panels_source: SolarPanelsSource | None = None
    boundary_source: BoundarySource | None = None
    vegetation_source: VegetationSource | None = None
    """Optional path to a merged CFTree CityJSON file (produced by
    :mod:`tools.merge_cftree_tiles` from
    https://github.com/NoahAlting/CFTree output). When set, the pipeline
    emits one ``veg:SolitaryVegetationObject`` per tree inside the bbox
    / boundary. See
    :class:`citygml_energy.city_builder.vegetation.VegetationSource`."""
    cbs_postcode6_source: CbsPostcode6Source | None = None
    """Optional CBS Postcode6 statistics source. When set, the pipeline
    fetches per-postcode dwelling-energy averages from PDOK's CBS WFS
    and emits one ``nrg3:UrbanFunctionArea`` per postcode polygon
    intersecting the build extent. See
    :class:`citygml_energy.city_builder.config.CbsPostcode6Source`."""

    def build_context(self) -> BuildContext:
        """Return the immutable :class:`BuildContext` derived from this config.

        Convenience for the pipeline orchestrator: rather than calling
        :meth:`BuildContext.from_config` from every assembly site, the
        caller produces one context once and threads it into every
        model-mutating builder.
        """
        return BuildContext.from_config(self)

    @property
    def ep_online_api_key(self) -> str | None:
        """Return the EP-online API key text (trimmed) or ``None``.

        Resolution order:

        1. If :attr:`ep_online_api_key_file` is set, read from that file.
        2. Otherwise, try the ``EP_ONLINE_API_KEY`` environment variable
           (a ``.env`` file next to the config is loaded first if
           ``python-dotenv`` is installed).
        3. Return ``None`` if neither source yields a value.

        Raises :class:`CityBuildError` when the configured file is set
        but missing: energy labels cannot continue without a token.
        """
        if self.ep_online_api_key_file is not None:
            try:
                return self.ep_online_api_key_file.read_text(encoding="utf-8").strip()
            except FileNotFoundError as exc:  # pragma: no cover, filesystem path
                raise CityBuildError(
                    f"EP-online API key file not found: {self.ep_online_api_key_file}"
                ) from exc
        _maybe_load_dotenv(self.source_path.parent)
        from_env = os.environ.get(EP_ONLINE_ENV_VAR)
        if from_env and from_env.strip():
            return from_env.strip()
        return None


_ALLOWED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "$schema",
        "file_header",
        "municipality",
        "bbox",
        "boundary",
        "lods",
        "include_addresses",
        "include_energy_labels",
        "ep_online_api_key_file",
        "cache_dir",
        "output",
        "srs_name",
        "srs_dimension",
        "city_model",
        "gml_id_prefix",
        "solar_panels",
        "vegetation",
        "cbs_postcode6",
    }
)

_ALLOWED_CITY_MODEL_KEYS: frozenset[str] = frozenset({"name", "description"})
_ALLOWED_SOLAR_PANELS_KEYS: frozenset[str] = frozenset({"path", "layer", "z_offset_m"})
_ALLOWED_BOUNDARY_KEYS: frozenset[str] = frozenset({"path"})
_ALLOWED_VEGETATION_KEYS: frozenset[str] = frozenset({"path"})
_ALLOWED_CBS_POSTCODE6_KEYS: frozenset[str] = frozenset({"year"})

# CBS publishes a year-versioned WFS endpoint. The acceptable values
# are intentionally bounded: 2022 / 2023 / 2024 are live as of writing,
# and a misspelled year would otherwise surface as an opaque 404 from
# PDOK halfway through a build. Range is permissive enough to admit
# the next several vintages without a config schema bump.
_CBS_POSTCODE6_YEAR_MIN: int = 2022
_CBS_POSTCODE6_YEAR_MAX: int = 2030


def load_city_config(path: PathLike) -> CityBuildConfig:
    """Load and validate a city-build JSON file.

    Relative filesystem paths in the config are resolved against the
    config file's parent directory, so the JSON stays portable across
    machines.
    """
    source_path = Path(path).resolve()
    try:
        raw_text = source_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise CityBuildError(f"City config file not found: {source_path}") from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CityBuildError(
            f"Invalid JSON in {source_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    return _validate(data, source=str(source_path), source_path=source_path)


def _validate(data: Any, *, source: str, source_path: Path) -> CityBuildConfig:
    if not isinstance(data, dict):
        raise CityBuildError(f"{source}: top-level JSON value must be an object")

    unexpected = sorted(set(data) - _ALLOWED_TOP_LEVEL_KEYS)
    if unexpected:
        raise CityBuildError(f"{source}: unexpected top-level key(s): {', '.join(unexpected)}")

    if "$schema" in data and not isinstance(data["$schema"], str):
        raise CityBuildError(f"{source}: $schema must be a string when provided")

    municipality = data.get("municipality")
    if not isinstance(municipality, str) or not municipality.strip():
        raise CityBuildError(f"{source}: municipality must be a non-empty string")

    bbox = _validate_bbox(data.get("bbox"), source=source)
    lods = _validate_lods(data.get("lods"), source=source)

    include_addresses = _validate_bool(data, "include_addresses", source=source, default=True)
    include_energy_labels = _validate_bool(
        data, "include_energy_labels", source=source, default=True
    )

    base_dir = source_path.parent
    ep_key_file = data.get("ep_online_api_key_file")
    if ep_key_file is None:
        ep_key_path = None
    elif isinstance(ep_key_file, str) and ep_key_file.strip():
        ep_key_path = _resolve_path(ep_key_file, base_dir)
    else:
        raise CityBuildError(
            f"{source}: ep_online_api_key_file must be a non-empty string when provided"
        )

    if include_energy_labels and ep_key_path is None:
        # Defer failure to :pyattr:`CityBuildConfig.ep_online_api_key`:
        # the env / .env fallback can still supply a token at run time.
        _maybe_load_dotenv(source_path.parent)
        if not (os.environ.get(EP_ONLINE_ENV_VAR) or "").strip():
            raise CityBuildError(
                f"{source}: include_energy_labels=true requires either "
                f"ep_online_api_key_file or the {EP_ONLINE_ENV_VAR} env var "
                f"(e.g. via a .env file next to the config)"
            )

    cache_dir_raw = data.get("cache_dir", ".cache/citygml_energy_city")
    if not isinstance(cache_dir_raw, str) or not cache_dir_raw.strip():
        raise CityBuildError(f"{source}: cache_dir must be a non-empty string when provided")
    cache_dir = _resolve_path(cache_dir_raw, base_dir)

    output_raw = data.get("output")
    if not isinstance(output_raw, str) or not output_raw.strip():
        raise CityBuildError(f"{source}: output must be a non-empty string")
    output_path = _resolve_path(output_raw, base_dir)

    srs_name = data.get("srs_name", DEFAULT_SRS_NAME)
    if not isinstance(srs_name, str) or not srs_name.strip():
        raise CityBuildError(f"{source}: srs_name must be a non-empty string when provided")

    srs_dimension = data.get("srs_dimension", DEFAULT_SRS_DIMENSION)
    if (
        isinstance(srs_dimension, bool)
        or not isinstance(srs_dimension, int)
        or srs_dimension not in (2, 3)
    ):
        raise CityBuildError(
            f"{source}: srs_dimension must be 2 or 3 when provided (got {srs_dimension!r})"
        )

    city_model = data.get("city_model", {})
    if not isinstance(city_model, dict):
        raise CityBuildError(f"{source}: city_model must be an object when provided")
    unexpected_cm = sorted(set(city_model) - _ALLOWED_CITY_MODEL_KEYS)
    if unexpected_cm:
        raise CityBuildError(f"{source}: unexpected city_model key(s): {', '.join(unexpected_cm)}")
    for key, value in city_model.items():
        if not isinstance(value, str):
            raise CityBuildError(f"{source}: city_model.{key} must be a string")

    file_header = data.get("file_header")
    if file_header is not None:
        if not isinstance(file_header, str) or not file_header.strip():
            raise CityBuildError(
                f"{source}: file_header must be a non-empty string when provided"
            )
        # Emitted as an XML comment; XML 1.0 forbids '--' inside a comment.
        if "--" in file_header:
            raise CityBuildError(
                f"{source}: file_header may not contain the sequence '--' "
                f"(forbidden inside an XML comment)"
            )

    gml_id_prefix = data.get("gml_id_prefix", "")
    if not isinstance(gml_id_prefix, str):
        raise CityBuildError(f"{source}: gml_id_prefix must be a string when provided")
    if gml_id_prefix and not _NCNAME_RE.match(gml_id_prefix):
        raise CityBuildError(
            f"{source}: gml_id_prefix {gml_id_prefix!r} is not a valid XML NCName prefix"
        )

    solar_panels_source = _validate_solar_panels(
        data.get("solar_panels"), source=source, base_dir=base_dir
    )
    boundary_source = _validate_boundary(data.get("boundary"), source=source, base_dir=base_dir)
    vegetation_source = _validate_vegetation(
        data.get("vegetation"), source=source, base_dir=base_dir
    )
    cbs_postcode6_source = _validate_cbs_postcode6(
        data.get("cbs_postcode6"),
        source=source,
    )
    if boundary_source is not None and bbox is not None:
        raise CityBuildError(
            f"{source}: 'bbox' and 'boundary' are mutually exclusive; "
            f"the fetch extent is derived from the boundary polygon itself"
        )

    return CityBuildConfig(
        source_path=source_path,
        municipality=municipality.strip(),
        bbox=bbox,
        lods=lods,
        include_addresses=include_addresses,
        include_energy_labels=include_energy_labels,
        ep_online_api_key_file=ep_key_path,
        cache_dir=cache_dir,
        output_path=output_path,
        srs_name=srs_name,
        srs_dimension=srs_dimension,
        city_model_name=city_model.get("name"),
        city_model_description=city_model.get("description"),
        file_header=file_header,
        gml_id_prefix=gml_id_prefix,
        solar_panels_source=solar_panels_source,
        boundary_source=boundary_source,
        vegetation_source=vegetation_source,
        cbs_postcode6_source=cbs_postcode6_source,
    )


def _validate_bbox(value: Any, *, source: str) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value)
    ):
        raise CityBuildError(
            f"{source}: bbox must be an array of 4 numbers [minx, miny, maxx, maxy] (got {value!r})"
        )
    minx, miny, maxx, maxy = (float(v) for v in value)
    if minx >= maxx or miny >= maxy:
        raise CityBuildError(
            f"{source}: bbox corners must satisfy minx<maxx and miny<maxy (got {value!r})"
        )
    return (minx, miny, maxx, maxy)


def _validate_lods(value: Any, *, source: str) -> tuple[int, ...]:
    if value is None:
        return tuple(sorted(_ALLOWED_LODS))
    if not isinstance(value, list) or not value:
        raise CityBuildError(
            f"{source}: lods must be a non-empty array of integers from {{0, 1, 2}}"
        )
    lods: list[int] = []
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, int) or entry not in _ALLOWED_LODS:
            raise CityBuildError(
                f"{source}: lods entries must be one of {{0, 1, 2}} (got {entry!r})"
            )
        if entry not in lods:
            lods.append(entry)
    return tuple(sorted(lods))


def _validate_solar_panels(value: Any, *, source: str, base_dir: Path) -> SolarPanelsSource | None:
    """Validate the optional ``solar_panels`` block.

    Returns ``None`` when unset. Path is resolved relative to the
    config's directory (matching the handling of ``cache_dir`` and
    ``output``); existence and CRS are checked lazily at read time in
    :func:`citygml_energy.city_builder.solar_panels.load_panels_in_bbox`,
    so a config authored on a machine without the GPKG still validates.

    The ``layer`` field is interpolated directly into the GeoPackage
    SQL query (SQLite has no parameterised table-name syntax), so it is
    validated against :data:`_NCNAME_RE` here to reject any string that
    would inject SQL or escape a quoted identifier.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CityBuildError(f"{source}: solar_panels must be an object when provided")
    unexpected = sorted(set(value) - _ALLOWED_SOLAR_PANELS_KEYS)
    if unexpected:
        raise CityBuildError(f"{source}: unexpected solar_panels key(s): {', '.join(unexpected)}")
    path_raw = value.get("path")
    if not isinstance(path_raw, str) or not path_raw.strip():
        raise CityBuildError(f"{source}: solar_panels.path must be a non-empty string")
    layer = value.get("layer")
    if not isinstance(layer, str) or not layer.strip():
        raise CityBuildError(f"{source}: solar_panels.layer must be a non-empty string")
    layer = layer.strip()
    if not _NCNAME_RE.match(layer):
        raise CityBuildError(
            f"{source}: solar_panels.layer {layer!r} must start with a letter or underscore "
            f"and contain only letters, digits, underscores, dots, or hyphens "
            f"(unsafe characters would cause SQL injection via the GeoPackage query)"
        )
    kwargs: dict[str, Any] = {
        "path": _resolve_path(path_raw, base_dir),
        "layer": layer,
    }
    if "z_offset_m" in value:
        z_offset_raw = value["z_offset_m"]
        if isinstance(z_offset_raw, bool) or not isinstance(z_offset_raw, (int, float)):
            raise CityBuildError(
                f"{source}: solar_panels.z_offset_m must be a number when provided "
                f"(got {z_offset_raw!r})"
            )
        kwargs["z_offset_m"] = float(z_offset_raw)
    return SolarPanelsSource(**kwargs)


def _validate_vegetation(value: Any, *, source: str, base_dir: Path) -> VegetationSource | None:
    """Validate the optional ``vegetation`` block.

    Returns ``None`` when unset. The path is resolved relative to the
    config's parent and must point at a ``.city.json`` file produced by
    :mod:`tools.merge_cftree_tiles`. File existence is checked lazily at
    build time via
    :func:`citygml_energy.city_builder.vegetation.load_trees_in_bbox`,
    so a config authored on a machine without the merged output still
    validates.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CityBuildError(f"{source}: vegetation must be an object when provided")
    unexpected = sorted(set(value) - _ALLOWED_VEGETATION_KEYS)
    if unexpected:
        raise CityBuildError(f"{source}: unexpected vegetation key(s): {', '.join(unexpected)}")
    path_raw = value.get("path")
    if not isinstance(path_raw, str) or not path_raw.strip():
        raise CityBuildError(f"{source}: vegetation.path must be a non-empty string")
    resolved_path = _resolve_path(path_raw, base_dir)
    if not resolved_path.name.endswith(".city.json"):
        raise CityBuildError(
            f"{source}: vegetation.path must end in .city.json (got {resolved_path.name!r})"
        )
    return VegetationSource(path=resolved_path)


def _validate_cbs_postcode6(value: Any, *, source: str) -> CbsPostcode6Source | None:
    """Validate the optional ``cbs_postcode6`` block.

    Returns ``None`` when unset. Only ``year`` is configurable; the
    PDOK WFS endpoint is hard-coded in the fetcher and the field set
    (gas + electricity) is fixed by the city pipeline's mapping. A
    config that wanted to pull additional CBS columns would belong to
    a separate generic-attribute extension, not to this energy-focused
    block.

    Year is range-checked rather than enum-checked: 2022 / 2023 / 2024
    are live as of writing, and admitting up to 2030 lets the next
    several vintages roll out without a config schema bump while still
    catching obvious typos (e.g. 2042).
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CityBuildError(f"{source}: cbs_postcode6 must be an object when provided")
    unexpected = sorted(set(value) - _ALLOWED_CBS_POSTCODE6_KEYS)
    if unexpected:
        raise CityBuildError(f"{source}: unexpected cbs_postcode6 key(s): {', '.join(unexpected)}")
    year_raw = value.get("year")
    if (
        isinstance(year_raw, bool)
        or not isinstance(year_raw, int)
        or not (_CBS_POSTCODE6_YEAR_MIN <= year_raw <= _CBS_POSTCODE6_YEAR_MAX)
    ):
        raise CityBuildError(
            f"{source}: cbs_postcode6.year must be an integer in "
            f"[{_CBS_POSTCODE6_YEAR_MIN}, {_CBS_POSTCODE6_YEAR_MAX}] "
            f"(got {year_raw!r})"
        )
    return CbsPostcode6Source(year=int(year_raw))


def _validate_boundary(value: Any, *, source: str, base_dir: Path) -> BoundarySource | None:
    """Validate the optional ``boundary`` block.

    Returns ``None`` when unset. Path is resolved relative to the
    config's directory. Only ``.geojson`` / ``.json`` files are
    accepted; the file must be a single GeoJSON ``Feature``. Existence
    and geometry are checked lazily at read time in
    :func:`.boundary.load_boundary_polygon`, so a config authored on a
    machine without the polygon file still validates.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CityBuildError(f"{source}: boundary must be an object when provided")
    unexpected = sorted(set(value) - _ALLOWED_BOUNDARY_KEYS)
    if unexpected:
        raise CityBuildError(f"{source}: unexpected boundary key(s): {', '.join(unexpected)}")
    path_raw = value.get("path")
    if not isinstance(path_raw, str) or not path_raw.strip():
        raise CityBuildError(f"{source}: boundary.path must be a non-empty string")
    resolved_path = _resolve_path(path_raw, base_dir)
    if resolved_path.suffix.lower() not in (".geojson", ".json"):
        raise CityBuildError(
            f"{source}: boundary.path must be a .geojson file (got {resolved_path.suffix!r})"
        )
    return BoundarySource(path=resolved_path)


def _validate_bool(data: dict[str, Any], key: str, *, source: str, default: bool) -> bool:
    if key not in data:
        return default
    value = data[key]
    if not isinstance(value, bool):
        raise CityBuildError(f"{source}: {key} must be a boolean when provided")
    return value


def _resolve_path(value: str, base_dir: Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


_DOTENV_LOADED_FROM: set[Path] = set()


def _maybe_load_dotenv(start_dir: Path) -> None:
    """Best-effort load of the nearest ``.env`` into ``os.environ``.

    Walks *start_dir* and its ancestors looking for the first ``.env``
    file, mirroring how ``python-dotenv``'s ``find_dotenv()`` behaves.
    Silent no-op when ``python-dotenv`` is not installed. Each resolved
    directory chain is searched at most once per process.
    """
    start_dir = start_dir.resolve()
    if start_dir in _DOTENV_LOADED_FROM:
        return
    _DOTENV_LOADED_FROM.add(start_dir)
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in [start_dir, *start_dir.parents]:
        env_file = candidate / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            return


# Re-exported for downstream callers that want the frozenset directly.
ALLOWED_LODS: frozenset[int] = _ALLOWED_LODS
