"""Unit tests for the EP-online CSV parser."""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.fetchers.eponline import parse_csv

_CSV_HEADER = (
    "Postcode;Huisnummer;Huisletter;Huisnummertoevoeging;BAGVerblijfsobjectID;"
    "Energieklasse;Registratiedatum;Opnamedatum;GeldigTot\n"
)


def _csv(*rows: str) -> str:
    return _CSV_HEADER + "\n".join(rows) + "\n"


def test_parses_complete_row() -> None:
    labels = parse_csv(_csv(
        "2628CD;42;;;;A++;20230514;20230501;20331231"
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
    assert label.opnamedatum == date(2023, 5, 1)
    assert label.geldig_tot == date(2033, 12, 31)


def test_parses_bag_vbo_id() -> None:
    labels = parse_csv(_csv(
        "2628CD;42;;;0503010000000001;A;20240101;;"
    ))
    assert labels[0].bag_verblijfsobject_id == "0503010000000001"


def test_parses_compact_huisnummer_letter() -> None:
    labels = parse_csv(_csv(
        "1000AA;12A;;;;C;20240101;;"
    ))
    assert labels[0].huisnummer == 12
    assert labels[0].huisletter == "A"
    assert labels[0].toevoeging is None


def test_huisletter_column_wins_over_embedded() -> None:
    labels = parse_csv(_csv(
        "1000AA;12;B;;;C;;;"
    ))
    assert labels[0].huisletter == "B"


def test_rejects_rows_without_postcode() -> None:
    labels = parse_csv(_csv(
        ";42;;;;A;;;"
    ))
    assert labels == []


def test_rejects_unparseable_huisnummer() -> None:
    labels = parse_csv(_csv(
        "2628CD;abc;;;;A;;;"
    ))
    assert labels == []


def test_address_key_normalises_postcode_casing() -> None:
    labels = parse_csv(_csv(
        "  2628cd  ;42;a;;;A;;;"
    ))
    assert labels[0].address_key() == ("2628CD", 42, "A", None)


def test_parser_tolerates_missing_optional_columns() -> None:
    # A stripped-down CSV with only the mandatory columns still parses.
    minimal = "Postcode;Huisnummer\n2628CD;42\n"
    labels = parse_csv(minimal)
    assert len(labels) == 1
    assert labels[0].postcode == "2628CD"
    assert labels[0].huisnummer == 42
    assert labels[0].energieklasse is None
    assert labels[0].registratiedatum is None
