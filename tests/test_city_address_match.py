"""Unit tests for the BAG ↔ EP-online address matcher."""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.address_match import match_addresses
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel
from tests._factories import make_vbo


def _vbo(
    identificatie: str,
    pand_id: str,
    *,
    postcode: str = "1000AA",
    huisnummer: int = 1,
    street: str = "Mekelweg",
    point: tuple[float, float] | None = None,
) -> Verblijfsobject:
    """File-local default profile (synthetic 1000AA address, oppervlakte unset)."""
    return make_vbo(
        identificatie=identificatie,
        pand_identificatie=pand_id,
        postcode=postcode,
        huisnummer=huisnummer,
        street=street,
        point=point,
        oppervlakte=None,
    )


def _label(
    postcode: str,
    huisnummer: int,
    klasse: str,
    registratie: date | None = None,
    *,
    berekeningstype: str | None = None,
    bag_verblijfsobject_id: str | None = None,
) -> EnergyLabel:
    return EnergyLabel(
        postcode=postcode,
        huisnummer=huisnummer,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=bag_verblijfsobject_id,
        energieklasse=klasse,
        registratiedatum=registratie,
        opnamedatum=None,
        geldig_tot=None,
        berekeningstype=berekeningstype,
    )


def test_vbo_is_grouped_by_pand() -> None:
    vbos = [
        _vbo("V1", "P1", huisnummer=1),
        _vbo("V2", "P1", huisnummer=2),
        _vbo("V3", "P2", huisnummer=3),
    ]
    grouped = match_addresses(vbos=vbos)
    assert sorted(grouped) == ["P1", "P2"]
    assert len(grouped["P1"]) == 2


def test_vbo_without_postcode_is_dropped() -> None:
    vbo = Verblijfsobject(
        identificatie="V1",
        pand_identificatie="P1",
        gebruiksdoel=[],
        oppervlakte=None,
        status=None,
        postcode=None,
        huisnummer=1,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam="Mekelweg",
        woonplaats=None,
        point=None,
        properties={},
    )
    assert match_addresses(vbos=[vbo]) == {}


def test_vbo_without_huisnummer_is_dropped() -> None:
    vbo = Verblijfsobject(
        identificatie="V1",
        pand_identificatie="P1",
        gebruiksdoel=[],
        oppervlakte=None,
        status=None,
        postcode="1000AA",
        huisnummer=None,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam="Mekelweg",
        woonplaats=None,
        point=None,
        properties={},
    )
    assert match_addresses(vbos=[vbo]) == {}


def test_energy_label_is_joined_by_postcode_and_number() -> None:
    vbos = [_vbo("V1", "P1", postcode="2628CD", huisnummer=42)]
    labels = [_label("2628CD", 42, "A")]
    grouped = match_addresses(vbos=vbos, energy_labels=labels)
    [resolved] = grouped["P1"]
    assert resolved.energy_label is not None
    assert resolved.energy_label.energieklasse == "A"
    assert resolved.street == "Mekelweg"


def test_most_recent_label_wins_on_duplicate_key() -> None:
    labels = [
        _label("2628CD", 42, "B", registratie=date(2020, 1, 1)),
        _label("2628CD", 42, "A", registratie=date(2023, 6, 1)),
    ]
    vbos = [_vbo("V1", "P1", postcode="2628CD", huisnummer=42)]
    grouped = match_addresses(vbos=vbos, energy_labels=labels)
    resolved_label = grouped["P1"][0].energy_label
    assert resolved_label is not None
    assert resolved_label.energieklasse == "A"


def test_newer_label_wins_across_calculation_regimes() -> None:
    """Cross-cutting invariant: when a VBO has labels from different
    calculation regimes (NTA 8800 vs legacy NEN-7120), the timestamp-
    ordering inside ``match_addresses`` decides which regime gets emitted
    by the downstream resource builder. Newer wins regardless of regime.

    Captures the load-bearing chain: changing ``_label_timestamp``
    ordering would silently flip which regime's resources land on the
    BuildingUnit. Label selection (here) and regime classification
    (in :mod:`energy_resources`) live in separate modules; this test
    is the cross-module assertion that the chain stays intact.
    """
    legacy = _label(
        "2628CD", 42, "C",
        registratie=date(2018, 1, 1),
        berekeningstype="Definitief Energielabel",
    )
    nta = _label(
        "2628CD", 42, "A",
        registratie=date(2024, 6, 1),
        berekeningstype="NTA 8800:2024",
    )
    vbos = [_vbo("V1", "P1", postcode="2628CD", huisnummer=42)]
    grouped = match_addresses(vbos=vbos, energy_labels=[legacy, nta])
    resolved = grouped["P1"][0].energy_label
    assert resolved is not None
    assert resolved.energieklasse == "A"
    assert resolved.calculation_regime() == "nta8800"


def test_older_nta_loses_to_newer_legacy() -> None:
    """The mirror case: when the legacy label is newer, regime
    classification follows the timestamp-ordering, even though NTA 8800
    is the more modern method. The matcher does not prefer one regime
    over another; freshness is the only tie-breaker.
    """
    nta = _label(
        "2628CD", 42, "A",
        registratie=date(2018, 1, 1),
        berekeningstype="NTA 8800:2020",
    )
    legacy = _label(
        "2628CD", 42, "G",
        registratie=date(2024, 6, 1),
        berekeningstype="Nader Voorschrift",
    )
    vbos = [_vbo("V1", "P1", postcode="2628CD", huisnummer=42)]
    grouped = match_addresses(vbos=vbos, energy_labels=[nta, legacy])
    resolved = grouped["P1"][0].energy_label
    assert resolved is not None
    assert resolved.energieklasse == "G"
    assert resolved.calculation_regime() == "legacy_total"


def test_vbo_id_match_wins_over_address_key_match() -> None:
    """When the same VBO has labels matching via *both* indices
    (BAGVerblijfsobjectID + address-key fallback), the VBO-id index
    is consulted first by ``match_addresses`` so a label keyed on the
    VBO id wins regardless of address-key freshness. This is the
    "EP-online v5+ schema upgrade" path: labels with a real BAG id
    are more reliable than the older address-key inference, so they
    take precedence even when older.
    """
    vbo = _vbo("V1", "P1", postcode="2628CD", huisnummer=42)
    label_by_id = _label(
        "2628CD", 42, "B",
        registratie=date(2018, 1, 1),
        bag_verblijfsobject_id="V1",
        berekeningstype="NTA 8800:2018",
    )
    label_by_key_only = _label(
        "2628CD", 42, "F",
        registratie=date(2024, 1, 1),
        berekeningstype="Nader Voorschrift",
    )
    grouped = match_addresses(
        vbos=[vbo], energy_labels=[label_by_id, label_by_key_only],
    )
    resolved = grouped["P1"][0].energy_label
    assert resolved is not None
    assert resolved.energieklasse == "B"
    assert resolved.calculation_regime() == "nta8800"


def test_two_vbos_in_one_pand_can_carry_different_regimes() -> None:
    """Pand-grouping does not conflate regime selections across VBOs.
    Two VBOs in the same Pand can each receive a label from a
    different regime; the resource builder will then emit different
    resource shapes per BuildingUnit, which is the correct semantics
    when an apartment building has been re-certified per-VBO at
    different times under different methods.
    """
    vbos = [
        _vbo("V1", "P1", postcode="2628CD", huisnummer=42),
        _vbo("V2", "P1", postcode="2628CD", huisnummer=43),
    ]
    labels = [
        _label("2628CD", 42, "A", registratie=date(2024, 1, 1),
               berekeningstype="NTA 8800:2024"),
        _label("2628CD", 43, "G", registratie=date(2018, 1, 1),
               berekeningstype="Definitief Energielabel"),
    ]
    grouped = match_addresses(vbos=vbos, energy_labels=labels)
    by_huisnummer = {r.huisnummer: r for r in grouped["P1"]}
    label_42 = by_huisnummer[42].energy_label
    label_43 = by_huisnummer[43].energy_label
    assert label_42 is not None and label_42.calculation_regime() == "nta8800"
    assert label_43 is not None and label_43.calculation_regime() == "legacy_total"
