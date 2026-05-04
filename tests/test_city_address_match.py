"""Unit tests for the BAG ↔ EP-online address matcher."""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.address_match import match_addresses
from citygml_energy.city_builder.fetchers.bag import Verblijfsobject
from citygml_energy.city_builder.fetchers.eponline import EnergyLabel


def _vbo(
    identificatie: str,
    pand_id: str,
    *,
    postcode: str = "1000AA",
    huisnummer: int = 1,
    street: str = "Mekelweg",
    point: tuple[float, float] | None = None,
) -> Verblijfsobject:
    return Verblijfsobject(
        identificatie=identificatie,
        pand_identificatie=pand_id,
        gebruiksdoel=["woonfunctie"],
        oppervlakte=None,
        status=None,
        postcode=postcode,
        huisnummer=huisnummer,
        huisletter=None,
        toevoeging=None,
        openbare_ruimte_naam=street,
        woonplaats=None,
        point=point,
        properties={},
    )


def _label(
    postcode: str,
    huisnummer: int,
    klasse: str,
    registratie: date | None = None,
) -> EnergyLabel:
    return EnergyLabel(
        postcode=postcode,
        huisnummer=huisnummer,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=None,
        energieklasse=klasse,
        registratiedatum=registratie,
        opnamedatum=None,
        geldig_tot=None,
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
