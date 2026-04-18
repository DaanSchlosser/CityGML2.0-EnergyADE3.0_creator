"""Top-level city-build orchestrator.

:func:`build_city_model` wires the fetchers, CityJSON parser, address
matcher, and xsdata builders into a single :class:`CityModel` ready for
serialization. :func:`build_city_gml_file` is a convenience that writes
the result to :attr:`CityBuildConfig.output_path`.

Network calls are delegated to :class:`CachedSession` through the
fetchers; tests inject a pre-populated cache dir or monkeypatch
``session.session`` so they never hit the wire.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._gml_builders import build_envelope
from .._step import Coord3D
from ..core import CityModel
from .address_match import ResolvedAddress, match_addresses
from .builders import attach_building_units_to_building, build_building
from .cityjson_parse import ParsedBuilding, SemanticPolygon
from .config import CityBuildConfig, CityBuildError, load_city_config
from .fetchers import bag as bag_fetchers
from .fetchers import eponline as eponline_fetchers
from .fetchers import municipality as muni_fetchers
from .fetchers import threedbag
from .http import CachedSession

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry


PathLike = str | Path


def build_city_gml_file(config_path: PathLike) -> CityModel:
    """Load *config_path*, build the CityModel, and write the GML."""
    config = load_city_config(config_path)
    model = build_city_model(config)
    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(output_path)
    return model


def build_city_model(
    config: CityBuildConfig,
    *,
    session: CachedSession | None = None,
) -> CityModel:
    """Build a :class:`CityModel` from *config*.

    When *session* is omitted a fresh :class:`CachedSession` rooted at
    ``config.cache_dir`` is used. Tests inject a pre-built session (or
    one with ``use_cache=False``) to control HTTP behaviour.
    """
    if session is None:
        session = CachedSession(cache_dir=config.cache_dir)

    print(f"[city-builder] Fetching municipality outline: {config.municipality}")
    outline = muni_fetchers.fetch_municipality_outline(
        session, name=config.municipality
    )
    bbox = config.bbox or outline.bbox
    cbs_code = outline.cbs_code or None
    print(f"[city-builder] CBS code: {cbs_code!r}  bbox: {bbox}")

    print("[city-builder] Fetching BAG panden …")
    panden = bag_fetchers.fetch_panden(session, bbox=bbox, cbs_code=cbs_code)
    known_pand_ids = {pand.identificatie for pand in panden}
    print(f"[city-builder] {len(panden)} panden")

    resolved_per_pand: dict[str, list[ResolvedAddress]] = {}
    if config.include_addresses:
        print("[city-builder] Fetching BAG verblijfsobjecten …")
        vbos = bag_fetchers.fetch_verblijfsobjecten(
            session, bbox=bbox, cbs_code=cbs_code
        )
        print(f"[city-builder] {len(vbos)} verblijfsobjecten")

        energy_labels = _maybe_fetch_energy_labels(session, config)
        if energy_labels is not None:
            print(f"[city-builder] {len(energy_labels)} EP-online labels loaded")

        resolved_per_pand = match_addresses(
            vbos=vbos,
            energy_labels=energy_labels,
        )
        matched_vbos = sum(len(v) for v in resolved_per_pand.values())
        print(f"[city-builder] {matched_vbos} VBOs matched to {len(resolved_per_pand)} panden")

    print("[city-builder] Fetching 3DBAG tiles …")
    parsed_buildings = _fetch_parsed_buildings(session, outline=outline, bbox=bbox)
    parsed_by_id = {pb.pand_id: pb for pb in parsed_buildings if pb.pand_id in known_pand_ids}
    print(
        f"[city-builder] {len(parsed_buildings)} buildings from 3DBAG tiles; "
        f"{len(parsed_by_id)} match known BAG panden"
    )
    skipped = len(panden) - len(parsed_by_id)
    if skipped:
        print(f"[city-builder] {skipped} panden have no 3DBAG geometry (skipped)")

    print("[city-builder] Assembling CityModel …")
    model = _assemble_city_model(
        config=config,
        panden=panden,
        parsed_by_id=parsed_by_id,
        resolved_per_pand=resolved_per_pand,
    )
    print(f"[city-builder] Done — {len(model.xsd.city_object_member)} buildings in model")
    return model


# ---------------------------------------------------------------------------
# Sub-step helpers
# ---------------------------------------------------------------------------


def _maybe_fetch_energy_labels(
    session: CachedSession,
    config: CityBuildConfig,
) -> list[eponline_fetchers.EnergyLabel] | None:
    if not config.include_energy_labels:
        return None
    api_key = config.ep_online_api_key
    if api_key is None:
        raise CityBuildError(
            "include_energy_labels=true but ep_online_api_key_file did not yield a token"
        )
    return eponline_fetchers.fetch_energy_labels(session, api_key=api_key)


def _fetch_parsed_buildings(
    session: CachedSession,
    *,
    outline: muni_fetchers.MunicipalityOutline,
    bbox: tuple[float, float, float, float] | None,
) -> list[ParsedBuilding]:
    """Pull intersecting 3DBAG tiles and parse per-pand geometry.

    When *bbox* is provided, the municipality outline is clipped to it
    before the tile query so only tiles that overlap the requested area
    are downloaded — critical for sub-municipality smoke tests.
    """
    geom = _outline_to_shapely(outline.feature.get("geometry") or {})
    if bbox is not None:
        import contextlib

        from shapely.errors import ShapelyError
        from shapely.geometry import box as shapely_box

        # Degenerate bbox (e.g. zero-area) → fall back to the full outline.
        # ImportError is deliberately NOT suppressed: missing shapely must
        # fail loudly, which _outline_to_shapely already enforces.
        with contextlib.suppress(ShapelyError, ValueError):
            geom = geom.intersection(shapely_box(*bbox))
    return threedbag.fetch_buildings_for_outline(session, outline=geom)


def _outline_to_shapely(geometry: dict[str, Any]) -> BaseGeometry:
    try:
        from shapely.geometry import shape
    except ImportError as exc:  # pragma: no cover — optional dep
        raise RuntimeError(
            "City build needs shapely; install with: pip install -e .[city]"
        ) from exc
    return shape(geometry)


def _assemble_city_model(
    *,
    config: CityBuildConfig,
    panden: list[bag_fetchers.Pand],
    parsed_by_id: dict[str, ParsedBuilding],
    resolved_per_pand: dict[str, list[ResolvedAddress]],
) -> CityModel:
    model = CityModel(
        gml_description=config.city_model_description,
        gml_name=config.city_model_name,
    )

    all_coords: list[Coord3D] = []
    for pand in panden:
        parsed = parsed_by_id.get(pand.identificatie)
        if parsed is None:
            continue

        _merge_attributes(parsed.attributes, pand)
        building = build_building(
            parsed,
            gml_id_prefix=config.gml_id_prefix,
            lods=config.lods,
            srs_name=config.srs_name,
            srs_dimension=config.srs_dimension,
        )
        attach_building_units_to_building(
            building,
            resolved_per_pand.get(pand.identificatie, []),
            gml_id_prefix=config.gml_id_prefix,
            city_name=config.municipality,
        )
        model.add(building)
        _collect_coordinates(parsed, all_coords)

    if all_coords:
        model.set_envelope(
            build_envelope(
                all_coords,
                srs_name=config.srs_name,
                srs_dimension=config.srs_dimension,
            )
        )
    return model


def _merge_attributes(parsed_attrs: dict[str, Any], pand: bag_fetchers.Pand) -> None:
    """Merge BAG Pand attributes into the parsed CityJSON attributes.

    3DBAG already carries ``oorspronkelijkbouwjaar`` but BAG sometimes
    has a newer / corrected value. BAG wins when present — direct
    assignment so the BAG value always overwrites the 3DBAG value.
    """
    if pand.bouwjaar is not None:
        parsed_attrs["oorspronkelijkbouwjaar"] = pand.bouwjaar
    if pand.status and "status" not in parsed_attrs:
        parsed_attrs["status"] = pand.status


def _collect_coordinates(
    parsed: ParsedBuilding, sink: list[Coord3D]
) -> None:
    for polygons in parsed.geometries.values():
        for sp in polygons:
            _extend_polygon_coords(sp, sink)


def _extend_polygon_coords(sp: SemanticPolygon, sink: list[Coord3D]) -> None:
    sink.extend(sp.polygon.exterior)
    for ring in sp.polygon.interiors:
        sink.extend(ring)
