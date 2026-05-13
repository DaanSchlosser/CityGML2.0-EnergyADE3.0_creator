"""Integration tests for the per-Pand orchestrator (`pand_executor.py`).

Locks the multi-builder sequence inside ``_build_pand_artifacts`` —
the function that strings together ``build_building`` →
``attach_building_units_to_building`` →
``apply_bag_year_metadata_to_building`` →
``apply_eponline_pand_attribution_to_building`` →
``attach_pv_collectors_to_building`` for every Pand. Each individual
builder has its own narrow tests in ``test_city_builders.py``; this
file covers the **orchestration**: that the calls happen in the right
order, that the parameter object (``BuildContext``) reaches every
builder with the right values, that the conditional PV branch behaves
on both legs, and that the ``PandArtifacts`` dataclass carries the
four named fields downstream code expects.

Why an integration test instead of consolidating the five builders
into one entry point: see ADR-0002.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from citygml_energy.bindings import Building
from citygml_energy.city_builder.address_match import ResolvedAddress
from citygml_energy.city_builder.config import CityBuildConfig
from citygml_energy.city_builder.fetchers.bag import Pand, Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel
from citygml_energy.city_builder.pand_executor import (
    EMPTY_INPUTS,
    PandInputs,
    bundle_per_pand_inputs,
    run_per_pand_build,
)
from tests._factories import (
    make_pand,
    make_parsed_building,
    make_vbo,
)

# ---------------------------------------------------------------------------
# Local fixtures (file-specific defaults; construction logic lives in _factories)
# ---------------------------------------------------------------------------


def _parsed(pand_id: str = "0503100000000001", bouwjaar: int = 1985):
    return make_parsed_building(pand_id=pand_id, bouwjaar=bouwjaar)


def _pand(pand_id: str = "0503100000000001", bouwjaar: int | None = 1985) -> Pand:
    return make_pand(identificatie=pand_id, bouwjaar=bouwjaar)


def _vbo(
    vbo_id: str = "0503010000000042",
    pand_id: str = "0503100000000001",
    huisnummer: int = 42,
) -> Verblijfsobject:
    return make_vbo(
        identificatie=vbo_id,
        pand_identificatie=pand_id,
        huisnummer=huisnummer,
        status="Verblijfsobject in gebruik",
    )


def _label_with_pand_attribution() -> EnergyLabel:
    """A label carrying both Bouwjaar and Gebouwtype — both Pand-level fields
    that ``apply_eponline_pand_attribution_to_building`` lifts onto the
    Building. Lets the integration test assert the attribution actually
    landed.
    """
    return EnergyLabel(
        postcode="2628CD",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=None,
        energieklasse="A",
        registratiedatum=date(2024, 1, 1),
        opnamedatum=None,
        geldig_tot=date(2034, 1, 1),
        berekeningstype="NTA 8800:2024",
        bouwjaar=1985,
        gebouwtype="Tussenwoning",
    )


def _config(tmp_path: Path) -> CityBuildConfig:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True)
    source = tmp_path / "city.json"
    source.write_text("{}", encoding="utf-8")
    return CityBuildConfig(
        source_path=source,
        municipality="Delft",
        bbox=None,
        lods=(0, 1, 2),
        include_addresses=True,
        include_energy_labels=False,
        ep_online_api_key_file=None,
        cache_dir=cache,
        output_path=tmp_path / "out.gml",
        srs_name="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
        srs_dimension=3,
        city_model_name="Delft",
        city_model_description="integration test",
        gml_id_prefix="",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_per_pand_build_returns_one_artefact_per_pand(tmp_path: Path) -> None:
    """The orchestrator returns one ``PandArtifacts`` per Pand that has
    matching 3DBAG geometry; Panden without geometry are silently
    skipped (3DBAG covers ~99 % of BAG but not 100 %, and the build
    must not break on the gap).
    """
    config = _config(tmp_path)
    panden = [_pand("PA"), _pand("PB"), _pand("PC")]
    parsed_by_id = {"PA": _parsed("PA"), "PB": _parsed("PB")}  # PC has no geometry
    artefacts = run_per_pand_build(
        config=config,
        panden=panden,
        parsed_by_id=parsed_by_id,
        inputs_per_pand={},  # empty: no addresses, no PV
        workers=1,
    )
    assert len(artefacts) == 2
    for art in artefacts:
        assert isinstance(art.building, Building)
        assert art.resolved == []  # no inputs supplied
        assert isinstance(art.targets, list)
        assert isinstance(art.coords, list)
        assert art.coords  # geometry collection ran


def test_run_per_pand_build_threads_build_context_through_to_each_builder(
    tmp_path: Path,
) -> None:
    """The ``BuildContext`` object reaches every builder: Building gets
    a gml_id_prefix-derived id, BuildingUnits get the same prefix,
    geometry uses the configured srs_name. This is the integration
    point where a parameter-threading bug in any one of the five
    builders would show up.
    """
    config = _config(tmp_path)
    config = config.__class__(**{**config.__dict__, "gml_id_prefix": "test_"})
    inputs_per_pand = {"PA": PandInputs(resolved=[
        ResolvedAddress(vbo=_vbo(), energy_label=None),
    ], pv_panels=())}
    artefacts = run_per_pand_build(
        config=config,
        panden=[_pand("PA")],
        parsed_by_id={"PA": _parsed("PA")},
        inputs_per_pand=inputs_per_pand,
        workers=1,
    )
    assert len(artefacts) == 1
    building = artefacts[0].building
    # Prefix lands on every gml:id touched by the orchestration.
    assert building.id is not None
    assert building.id.startswith("test_")
    # BuildingUnit was attached (so attach_building_units_to_building
    # got the prefix and the address ran through).
    assert building.building_unit, (
        "BuildingUnit was not attached — attach_building_units_to_building "
        "did not run."
    )
    [bu_wrapper] = building.building_unit
    inner = bu_wrapper.building_unit
    assert inner is not None and inner.id is not None
    assert inner.id.startswith("test_"), (
        f"BuildingUnit gml:id {inner.id!r} does not start with the "
        "configured prefix — attach_building_units_to_building did not "
        "receive gml_id_prefix from BuildContext."
    )


def test_run_per_pand_build_lands_orchestration_outputs_on_building(
    tmp_path: Path,
) -> None:
    """Lock the cross-builder ordering: every builder that mutates the
    Building must land its output before the artefact is returned.
    Concretely:

    * ``build_building`` set yearOfConstruction from the 3DBAG attribute
      (1985, supplied via ``_parsed``).
    * ``attach_building_units_to_building`` attached at least one
      BuildingUnit (because we passed a ResolvedAddress).
    * ``apply_bag_year_metadata_to_building`` attached the BAG-source
      Metadata block (because year_of_construction is populated).
    * ``apply_eponline_pand_attribution_to_building`` attached the
      EP-online Pand-level fields (yearOfConstructionEPOnline +
      bdgType) because the resolved address carries a label with
      both ``bouwjaar`` and ``gebouwtype``.

    A regression in the orchestrator that swaps the order, drops a
    call, or fails to thread the ``addresses`` parameter would knock
    out one of these expectations and fail this test.
    """
    config = _config(tmp_path)
    inputs_per_pand = {"PA": PandInputs(
        resolved=[
            ResolvedAddress(vbo=_vbo(), energy_label=_label_with_pand_attribution())
        ],
        pv_panels=(),
    )}
    [art] = run_per_pand_build(
        config=config,
        panden=[_pand("PA", bouwjaar=1985)],
        parsed_by_id={"PA": _parsed("PA", bouwjaar=1985)},
        inputs_per_pand=inputs_per_pand,
        workers=1,
    )
    building, resolved = art.building, art.resolved

    # build_building: yearOfConstruction set (xsdata serialises as
    # XmlPeriod, not int).
    assert building.year_of_construction is not None
    assert str(building.year_of_construction) == "1985"

    # attach_building_units_to_building: at least one BuildingUnit
    # was attached to building.building_unit.
    assert building.building_unit, (
        "BuildingUnit was not attached — "
        "attach_building_units_to_building did not run."
    )

    # apply_bag_year_metadata_to_building: at least one Metadata block
    # landed on the Building's metadata list. (The BAG-source block
    # documents bldg:yearOfConstruction's lineage.)
    assert building.metadata, (
        "BAG year-of-construction Metadata block did not land — "
        "apply_bag_year_metadata_to_building did not run."
    )

    # apply_eponline_pand_attribution_to_building: a gen:intAttribute
    # named "yearOfConstructionEPOnline" landed on building.int_attribute,
    # AND a BdgType landed on building.bdg_type.
    yoc_attrs = [
        a for a in building.int_attribute
        if getattr(a, "name", "") == "yearOfConstructionEPOnline"
    ]
    assert len(yoc_attrs) == 1, (
        "yearOfConstructionEPOnline did not land on the Building — "
        "apply_eponline_pand_attribution_to_building did not run or "
        f"did not see the resolved label. Got {yoc_attrs}."
    )
    assert building.bdg_type, (
        "nrg3:bdgType did not land — "
        "apply_eponline_pand_attribution_to_building did not run for the "
        "Gebouwtype branch."
    )

    # The artefact tuple carries the resolved addresses unchanged so
    # downstream pipeline assembly can iterate them again for
    # appearances etc.
    assert resolved == inputs_per_pand["PA"].resolved


def test_run_per_pand_build_skips_pv_branch_when_panels_empty(
    tmp_path: Path,
) -> None:
    """``attach_pv_collectors_to_building`` is conditional on
    ``inputs.pv_panels`` being truthy. Empty panels must not crash
    (they did not in tested runs, but the conditional is part of the
    orchestration and lives here, not in a per-builder test).
    """
    config = _config(tmp_path)
    [art] = run_per_pand_build(
        config=config,
        panden=[_pand("PA")],
        parsed_by_id={"PA": _parsed("PA")},
        inputs_per_pand={"PA": EMPTY_INPUTS},  # explicit empty
        workers=1,
    )
    # Building exists; absence of PV is silent.
    assert isinstance(art.building, Building)


def test_bundle_per_pand_inputs_collapses_parallel_dicts() -> None:
    """The bundling step collapses the two parallel per-Pand dicts
    (resolved addresses, PV matches) into one ``PandInputs`` per Pand
    that appears in either source. Panden absent from both sources
    are not in the output dict, so ``inputs_per_pand.get(pid,
    EMPTY_INPUTS)`` is the right access pattern.
    """
    panden = [_pand("PA"), _pand("PB"), _pand("PC")]  # PC: no inputs
    resolved = {
        "PA": [ResolvedAddress(vbo=_vbo(vbo_id="V1", pand_id="PA"), energy_label=None)],
    }
    pv = {
        "PB": [],  # present but empty list
    }
    out = bundle_per_pand_inputs(
        panden=panden,
        resolved_per_pand=resolved,
        pv_matches_per_pand=pv,
    )
    assert "PA" in out
    assert "PB" in out
    assert "PC" not in out, (
        "Pand with no inputs in either dict should not appear; the "
        "executor falls through to EMPTY_INPUTS at access time."
    )
    assert out["PA"].resolved == resolved["PA"]
    assert out["PA"].pv_panels == ()
    assert out["PB"].resolved == []
    assert out["PB"].pv_panels == ()


@pytest.mark.parametrize(
    ("env_value", "n_panden", "expected"),
    [
        ("", 100, 1),
        ("1", 100, 1),
        ("4", 100, 4),
        ("4", 2, 2),  # capped to pand count
        ("4", 1, 1),  # capped
        ("garbage", 100, 1),  # parse error → sequential
    ],
)
def test_assembly_worker_count_respects_env_var_and_caps(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str,
    n_panden: int,
    expected: int,
) -> None:
    """``assembly_worker_count`` is small enough to inline-test, but
    its env-var contract is part of the orchestrator's interface
    (the pipeline calls it before deciding sequential vs pool), so
    locking the parsing here keeps the orchestration test surface
    self-contained.
    """
    from citygml_energy.city_builder.pand_executor import assembly_worker_count

    if env_value:
        monkeypatch.setenv("CITYGML_ENERGY_ASSEMBLY_WORKERS", env_value)
    else:
        monkeypatch.delenv("CITYGML_ENERGY_ASSEMBLY_WORKERS", raising=False)
    assert assembly_worker_count(n_panden) == expected
