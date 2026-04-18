"""Unit tests for the EP-online CSV parser."""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.fetchers.eponline import parse_csv

_CSV_HEADER = (
    "Postcode;Huisnummer;Huisletter;Huisnummertoevoeging;BAGVerblijfsobjectID;"
    "Energieklasse;Registratiedatum;Opnamedatum;GeldigTot;EnergieIndex;"
    "PrimaireFossieleEnergie;AandeelHernieuwbareEnergie;BerekendeCO2Emissie;"
    "Gebouwtype;GebouwSubtype;GebruiksoppervlakteThermischeZone;Compactheid\n"
)


def _csv(*rows: str) -> str:
    return _CSV_HEADER + "\n".join(rows) + "\n"


def test_parses_complete_row() -> None:
    labels = parse_csv(_csv(
        "2628CD;42;;;;A++;20230514;20230501;20331231;"
        "0,85;45,2;12,5;8,4;Woonfunctie;EGW;120,5;0,82"
    ))
    assert len(labels) == 1
    label = labels[0]
    assert label.postcode == "2628CD"
    assert label.huisnummer == 42
    assert label.huisletter is None
    assert label.toevoeging is None
    assert label.bag_verblijfsobject_id is None
    assert label.energieklasse == "A++"
    assert label.registratiedatum == date(2023, 5, 14)
    assert label.geldig_tot == date(2033, 12, 31)
    assert label.energieindex == 0.85
    assert label.gebruiksoppervlakte_thermische_zone == 120.5


def test_parses_bag_vbo_id() -> None:
    labels = parse_csv(_csv(
        "2628CD;42;;;0503010000000001;A;20240101;;;;;;;;;;;;"
    ))
    assert labels[0].bag_verblijfsobject_id == "0503010000000001"


def test_parses_compact_huisnummer_letter() -> None:
    labels = parse_csv(_csv(
        "1000AA;12A;;;;C;20240101;;;;;;;;;;"
    ))
    assert labels[0].huisnummer == 12
    assert labels[0].huisletter == "A"
    assert labels[0].toevoeging is None


def test_huisletter_column_wins_over_embedded() -> None:
    labels = parse_csv(_csv(
        "1000AA;12;B;;;C;;;;;;;;;;;"
    ))
    assert labels[0].huisletter == "B"


def test_rejects_rows_without_postcode() -> None:
    labels = parse_csv(_csv(
        ";42;;;;A;;;;;;;;;;;"
    ))
    assert labels == []


def test_rejects_unparseable_huisnummer() -> None:
    labels = parse_csv(_csv(
        "2628CD;abc;;;;A;;;;;;;;;;;"
    ))
    assert labels == []


def test_dutch_decimals_are_normalised() -> None:
    labels = parse_csv(_csv(
        "2628CD;42;;;;A;;;;1,25;;;;;;;"
    ))
    assert labels[0].energieindex == 1.25


def test_address_key_normalises_postcode_casing() -> None:
    labels = parse_csv(_csv(
        "  2628cd  ;42;a;;;A;;;;;;;;;;;"
    ))
    assert labels[0].address_key() == ("2628CD", 42, "A", None)
