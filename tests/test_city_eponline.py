"""Unit tests for the EP-online CSV parser."""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.fetchers.eponline import EnergyLabel, parse_csv

_CSV_HEADER = (
    "Postcode;Huisnummer;Huisletter;Huisnummertoevoeging;BAGVerblijfsobjectID;"
    "Energieklasse;Registratiedatum;Opnamedatum;GeldigTot\n"
)


def _csv(*rows: str) -> str:
    return _CSV_HEADER + "\n".join(rows) + "\n"


def test_parses_complete_row() -> None:
    labels = parse_csv(_csv("2628CD;42;;;;A++;20230514;20230501;20331231"))
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
    labels = parse_csv(_csv("2628CD;42;;;0503010000000001;A;20240101;;"))
    assert labels[0].bag_verblijfsobject_id == "0503010000000001"


def test_parses_compact_huisnummer_letter() -> None:
    labels = parse_csv(_csv("1000AA;12A;;;;C;20240101;;"))
    assert labels[0].huisnummer == 12
    assert labels[0].huisletter == "A"
    assert labels[0].toevoeging is None


def test_huisletter_column_wins_over_embedded() -> None:
    labels = parse_csv(_csv("1000AA;12;B;;;C;;;"))
    assert labels[0].huisletter == "B"


def test_rejects_rows_without_postcode() -> None:
    labels = parse_csv(_csv(";42;;;;A;;;"))
    assert labels == []


def test_rejects_unparseable_huisnummer() -> None:
    labels = parse_csv(_csv("2628CD;abc;;;;A;;;"))
    assert labels == []


def test_address_key_normalises_postcode_casing() -> None:
    labels = parse_csv(_csv("  2628cd  ;42;a;;;A;;;"))
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


# ---------------------------------------------------------------------------
# Regression: bulk byte-level prefilter honours the Postcode column index.
# ---------------------------------------------------------------------------

# The production EP-online CSV ships Postcode at column 12 (after
# Registratiedatum, Opnamedatum, GeldigTot, Certificaathouder, SoortOpname,
# Status, Berekeningstype, OpBasisVanReferentiegebouw, Gebouwklasse,
# Gebouwtype, Gebouwsubtype, SBICode), not at column 0. An earlier version
# of the bulk prefilter read line[:first_semicolon] and compared it to the
# wanted-postcode set, which silently dropped every row of the 5 M-row file.
_REAL_HEADER = (
    b"Registratiedatum;Opnamedatum;GeldigTot;Certificaathouder;SoortOpname;"
    b"Status;Berekeningstype;OpBasisVanReferentiegebouw;Gebouwklasse;"
    b"Gebouwtype;Gebouwsubtype;SBICode;Postcode;Huisnummer;Huisletter;"
    b"Huisnummertoevoeging;BAGVerblijfsobjectID;Energieklasse;"
    b"Registratiedatum;Opnamedatum;GeldigTot\n"
)
_REAL_PREAMBLE = b"# EP-online export\n\n"


def _real_shape_csv(*rows: bytes) -> bytes:
    return _REAL_PREAMBLE + _REAL_HEADER + b"\n".join(rows) + b"\n"


def test_bulk_prefilter_matches_postcode_at_real_column_index() -> None:
    from citygml_energy.city_builder.address_key import address_key
    from citygml_energy.city_builder.fetchers.eponline import parse_csv_from_bulk_bytes

    csv_bytes = _real_shape_csv(
        b"20240101;20240101;20340101;Holder;RV;Final;Conv;No;W;A;B;1234;"
        b"7881AA;42;;;0114010000000001;A;20240101;20240101;20340101",
        b"20240101;20240101;20340101;Holder;RV;Final;Conv;No;W;A;B;1234;"
        b"9999ZZ;99;;;unrelated;C;20240101;20240101;20340101",
    )
    wanted_keys = {address_key("7881AA", 42, None, None)}

    labels = parse_csv_from_bulk_bytes(csv_bytes, wanted_ids=None, wanted_keys=wanted_keys)
    assert len(labels) == 1, "prefilter must not drop the matching row"
    assert labels[0].postcode == "7881AA"
    assert labels[0].huisnummer == 42
    assert labels[0].energieklasse == "A"


def test_streaming_prefilter_matches_postcode_at_real_column_index() -> None:
    # Twin of the bulk-path regression above: parse_csv with wanted_keys
    # routes through _filter_lines_by_postcode, which read column 0
    # (Registratiedatum) instead of the resolved Postcode column and so
    # silently dropped every row of a production-shape CSV.
    from citygml_energy.city_builder.address_key import address_key

    csv_text = _real_shape_csv(
        b"20240101;20240101;20340101;Holder;RV;Final;Conv;No;W;A;B;1234;"
        b"7881AA;42;;;0114010000000001;A;20240101;20240101;20340101",
        b"20240101;20240101;20340101;Holder;RV;Final;Conv;No;W;A;B;1234;"
        b"9999ZZ;99;;;unrelated;C;20240101;20240101;20340101",
    ).decode("utf-8")
    wanted_keys = {address_key("7881AA", 42, None, None)}

    labels = parse_csv(csv_text, wanted_keys=wanted_keys)
    assert len(labels) == 1, "streaming prefilter must not drop the matching row"
    assert labels[0].postcode == "7881AA"
    assert labels[0].huisnummer == 42
    assert labels[0].energieklasse == "A"


def test_bulk_prefilter_tolerates_spaces_and_lowercase_postcodes() -> None:
    from citygml_energy.city_builder.address_key import address_key
    from citygml_energy.city_builder.fetchers.eponline import parse_csv_from_bulk_bytes

    csv_bytes = _real_shape_csv(
        b"20240101;20240101;20340101;Holder;RV;Final;Conv;No;W;A;B;1234;"
        b"7881 aa;42;;;0114010000000001;B;20240101;20240101;20340101",
    )
    wanted_keys = {address_key("7881AA", 42, None, None)}

    labels = parse_csv_from_bulk_bytes(csv_bytes, wanted_ids=None, wanted_keys=wanted_keys)
    assert len(labels) == 1
    assert labels[0].postcode == "7881AA"


# ---------------------------------------------------------------------------
# Extended column surface (P1 plumbing). Every column listed in the per-column
# mapping in `docs/mapping_city.md` § 6.5 with verdict Native /
# Native (derived) / gen:Attribute is round-tripped through the parser.
# ---------------------------------------------------------------------------

# Full production-shape header: columns observed in the v20260401 EP-online
# Mutatiebestand. Order matches `_REAL_HEADER` above plus the long tail of
# classification + energy-flow numerics. Columns the pipeline marks
# Skip-(latent) or Drop are still in the CSV but are not asserted by tests.
_EXTENDED_HEADER = (
    "Registratiedatum;Opnamedatum;GeldigTot;Certificaathouder;SoortOpname;"
    "Status;Berekeningstype;OpBasisVanReferentiegebouw;Gebouwklasse;"
    "Gebouwtype;Gebouwsubtype;SBICode;Postcode;Huisnummer;Huisletter;"
    "Huisnummertoevoeging;BAGVerblijfsobjectID;Energieklasse;Bouwjaar;"
    "GebruiksoppervlakteThermischeZone;Compactheid;Energiebehoefte;"
    "Warmtebehoefte;PrimaireFossieleEnergie;AandeelHernieuwbareEnergie;"
    "Temperatuuroverschrijding;BerekendeCO2Emissie;BerekendeEnergieverbruik\n"
)


def _extended_csv(*rows: str) -> str:
    return _EXTENDED_HEADER + "\n".join(rows) + "\n"


def test_extended_columns_round_trip_through_parser() -> None:
    """A full production-shape row populates every surfaced field.

    Guards every Native / Native (derived) / gen:Attribute target from
    `docs/mapping_city.md` § 6.5. The Skip-(latent) and Drop
    columns are present in the CSV but are not asserted: an
    :class:`EnergyLabel` does not surface them.
    """
    csv_text = _extended_csv(
        # Reg=2023-05-14, Opname=2023-05-01, Geldig=2033-12-31
        "20230514;20230501;20331231;"
        # Certificaathouder; SoortOpname; Status
        "Energielabel Deskundige;Detailopname;Bestaand;"
        # Berekeningstype; OpBasisVanReferentiegebouw; Gebouwklasse
        "NTA 8800:2024 (detailopname woningbouw);Nee;W;"
        # Gebouwtype; Gebouwsubtype; SBICode
        "Rijwoning hoek;;;"
        # Postcode;Huisnummer;Huisletter;Toevoeging;BAGVerblijfsobjectID
        "7881AA;42;;;0114010000000001;"
        # Energieklasse;Bouwjaar
        "A++;1955;"
        # GebruiksoppervlakteThermischeZone (Dutch comma decimal); Compactheid
        "112,5;1,42;"
        # Energiebehoefte;Warmtebehoefte;PrimaireFossieleEnergie
        "28,5;25,1;63,0;"
        # AandeelHernieuwbareEnergie;Temperatuuroverschrijding
        "42;312;"
        # BerekendeCO2Emissie;BerekendeEnergieverbruik
        "14,7;35,4"
    )
    labels = parse_csv(csv_text)
    assert len(labels) == 1
    label = labels[0]

    # Identifying / certifying metadata.
    assert label.energieklasse == "A++"
    assert label.berekeningstype == "NTA 8800:2024 (detailopname woningbouw)"
    assert label.soort_opname == "Detailopname"
    assert label.registratiedatum == date(2023, 5, 14)
    assert label.opnamedatum == date(2023, 5, 1)
    assert label.geldig_tot == date(2033, 12, 31)

    # Building classification + physics.
    assert label.gebouwtype == "Rijwoning hoek"
    assert label.gebouwsubtype is None  # column present, value empty in fixture
    assert label.bouwjaar == 1955
    assert label.gebruiksoppervlakte_thermische_zone == 112.5

    # Energy-flow metrics. Dutch comma decimals must come through as float.
    assert label.energiebehoefte == 28.5
    assert label.warmtebehoefte == 25.1
    assert label.primaire_fossiele_energie == 63.0
    assert label.berekende_energieverbruik == 35.4
    assert label.berekende_co2_emissie == 14.7
    assert label.aandeel_hernieuwbare_energie == 42.0


def test_gebouwsubtype_round_trips_when_populated() -> None:
    """A populated ``Gebouwsubtype`` cell is surfaced verbatim on EnergyLabel.

    The Dutch RVO term lands on the BuildingUnit downstream as
    ``gen:stringAttribute name="bdgSubtypeEPOnline"`` (no native
    ``nrg3:bdgSubtype`` slot in EnergyADE 3.0, no translation step).
    """
    csv_text = _extended_csv(
        "20230514;20230501;20331231;"
        "Energielabel Deskundige;Detailopname;Bestaand;"
        "NTA 8800:2024 (detailopname woningbouw);Nee;W;"
        # Gebouwtype; Gebouwsubtype; SBICode (subtype populated)
        "Rijwoning hoek;rijwoning-hoek-kopgevel;;"
        "7881AA;42;;;0114010000000001;"
        "A++;1955;"
        "112,5;1,42;"
        "28,5;25,1;63,0;"
        "42;312;"
        "14,7;35,4"
    )
    labels = parse_csv(csv_text)
    assert len(labels) == 1
    assert labels[0].gebouwtype == "Rijwoning hoek"
    assert labels[0].gebouwsubtype == "rijwoning-hoek-kopgevel"


def test_minimal_header_backward_compatible() -> None:
    """The pre-extension 9-column header still parses; new fields are ``None``.

    Guards the documented "every default is ``None``" contract on the
    extended dataclass: a CSV missing the new columns must continue to
    work, and existing test fixtures (which use the 9-column header) must
    not need updating.
    """
    minimal_csv = _csv("2628CD;42;;;;A;20240101;;")
    labels = parse_csv(minimal_csv)
    assert len(labels) == 1
    label = labels[0]

    # New fields all default to None when the column is absent.
    assert label.soort_opname is None
    assert label.gebouwtype is None
    assert label.gebouwsubtype is None
    assert label.bouwjaar is None
    assert label.gebruiksoppervlakte_thermische_zone is None
    assert label.energiebehoefte is None
    assert label.warmtebehoefte is None
    assert label.primaire_fossiele_energie is None
    assert label.berekende_energieverbruik is None
    assert label.berekende_co2_emissie is None
    assert label.aandeel_hernieuwbare_energie is None


def test_decimal_comma_parses_to_float() -> None:
    """``parse_decimal`` swaps the Dutch comma decimal marker."""
    from citygml_energy.city_builder.fetchers.eponline import parse_decimal

    assert parse_decimal("28,5") == 28.5
    assert parse_decimal("0,0") == 0.0
    assert parse_decimal("1") == 1.0
    # Dutch thousands separator (rare for energy values, defensively handled).
    assert parse_decimal("1.234,56") == 1234.56
    # Defensive: dot-decimal still works in case the format ever shifts.
    assert parse_decimal("28.5") == 28.5
    # Empty / whitespace / malformed: None.
    assert parse_decimal("") is None
    assert parse_decimal("   ") is None
    assert parse_decimal("not-a-number") is None


# ---------------------------------------------------------------------------
# Full 42-column production-shape header. Locks down that ``_resolve_column_indices``
# walks the entire header and that no column-position drift in the long tail
# (the 24 columns past Energieklasse) silently breaks the alias resolution.
# ---------------------------------------------------------------------------

# 42 columns matching the EP-online v20260401 Mutatiebestand. The first 18
# follow the order documented in `_REAL_HEADER` above (Postcode at column 12,
# Energieklasse at column 17). The remaining 24 chain the §5 mapping-doc
# categories — building physics + energy-flow + BENG thresholds + BAG
# cross-references + project metadata — each in the order the spec lists
# them. Skip-(latent) and Drop columns are still in the header (because the
# real CSV ships them) but the parser silently ignores them.
_PRODUCTION_HEADER_42 = (
    "Registratiedatum;Opnamedatum;GeldigTot;Certificaathouder;SoortOpname;"
    "Status;Berekeningstype;OpBasisVanReferentiegebouw;Gebouwklasse;"
    "Gebouwtype;Gebouwsubtype;SBICode;Postcode;Huisnummer;Huisletter;"
    "Huisnummertoevoeging;BAGVerblijfsobjectID;Energieklasse;Bouwjaar;"
    "GebruiksoppervlakteThermischeZone;Compactheid;EnergieIndex;"
    "EnergieIndexEMGForfaitair;Energiebehoefte;Warmtebehoefte;"
    "PrimaireFossieleEnergie;PrimaireFossieleEnergieEMGForfaitair;"
    "AandeelHernieuwbareEnergie;AandeelHernieuwbareEnergieEMGForfaitair;"
    "BerekendeCO2Emissie;BerekendeEnergieverbruik;Temperatuuroverschrijding;"
    "EisEnergiebehoefte;EisPrimaireFossieleEnergie;"
    "EisAandeelHernieuwbareEnergie;EisTemperatuuroverschrijding;"
    "BAGLigplaatsID;BAGStandplaatsID;BAGPandIDs;Projectnaam;Projectobject;"
    "Detailaanduiding\n"
)


def test_full_42_column_production_header_parses_every_surfaced_field() -> None:
    """A 42-column production-shape row populates every Native / gen:Attribute target.

    Skip-(latent) and Drop columns occupy the long tail (Compactheid, the
    legacy ``EnergieIndex*``, the EMG-Forfaitair variants, BENG ``Eis*``
    thresholds, BAG-Ligplaats / Standplaats / PandIDs, project metadata)
    and must be present in the header without breaking column-index
    resolution; their values are silently dropped because they are not
    surfaced on :class:`EnergyLabel`.
    """
    # Header has 42 columns; the data row mirrors the same 42 fields. Skip-
    # (latent) / Drop cells carry plausible values to prove the parser
    # tolerates them without parsing them.
    row = (
        # Registratiedatum;Opnamedatum;GeldigTot;Certificaathouder
        "20230514;20230501;20331231;Energielabel Deskundige BV;"
        # SoortOpname;Status;Berekeningstype;OpBasisVanReferentiegebouw
        "Detailopname;Bestaand;NTA 8800:2024 (detailopname woningbouw);Nee;"
        # Gebouwklasse;Gebouwtype;Gebouwsubtype;SBICode
        "W;Rijwoning hoek;;;"
        # Postcode;Huisnummer;Huisletter;Huisnummertoevoeging;BAGVerblijfsobjectID
        "7881AA;42;;;0114010000000001;"
        # Energieklasse;Bouwjaar;GebruiksoppervlakteThermischeZone;Compactheid
        "A++;1955;112,5;1,42;"
        # EnergieIndex;EnergieIndexEMGForfaitair;Energiebehoefte;Warmtebehoefte
        "0,82;0,80;28,5;25,1;"
        # PrimaireFossieleEnergie;PrimaireFossieleEnergieEMGForfaitair
        "63,0;61,2;"
        # AandeelHernieuwbareEnergie;AandeelHernieuwbareEnergieEMGForfaitair
        "42;38;"
        # BerekendeCO2Emissie;BerekendeEnergieverbruik;Temperatuuroverschrijding
        "14,7;35,4;312;"
        # EisEnergiebehoefte;EisPrimaireFossieleEnergie
        "55;160;"
        # EisAandeelHernieuwbareEnergie;EisTemperatuuroverschrijding
        "50;450;"
        # BAGLigplaatsID;BAGStandplaatsID;BAGPandIDs
        ";;0114100000000001;"
        # Projectnaam;Projectobject;Detailaanduiding
        "Naam Project;Object;Detailaanduiding tekst"
    )
    csv_text = _PRODUCTION_HEADER_42 + row + "\n"

    labels = parse_csv(csv_text)
    assert len(labels) == 1
    label = labels[0]

    # Address keys + VBO id (filter-only but still exposed on the dataclass).
    assert label.postcode == "7881AA"
    assert label.huisnummer == 42
    assert label.bag_verblijfsobject_id == "0114010000000001"

    # Identifying / certifying metadata.
    assert label.energieklasse == "A++"
    assert label.berekeningstype == "NTA 8800:2024 (detailopname woningbouw)"
    assert label.soort_opname == "Detailopname"
    assert label.registratiedatum == date(2023, 5, 14)
    assert label.opnamedatum == date(2023, 5, 1)
    assert label.geldig_tot == date(2033, 12, 31)

    # Building classification + physics.
    assert label.gebouwtype == "Rijwoning hoek"
    assert label.gebouwsubtype is None  # column present, value empty in fixture
    assert label.bouwjaar == 1955
    assert label.gebruiksoppervlakte_thermische_zone == 112.5

    # Energy-flow metrics.
    assert label.energiebehoefte == 28.5
    assert label.warmtebehoefte == 25.1
    assert label.primaire_fossiele_energie == 63.0
    assert label.berekende_energieverbruik == 35.4
    assert label.berekende_co2_emissie == 14.7
    assert label.aandeel_hernieuwbare_energie == 42.0


def test_decimal_preserves_zero_distinct_from_missing() -> None:
    """``"0"`` is a real zero, not a missing measurement.

    A zero renewable share or zero CO₂ emission is meaningful in the EPC
    register (BENG-3 reports ``0`` for buildings with no renewable
    contribution). It must round-trip as ``0.0`` and not collapse to
    ``None``, which would swallow valid data.
    """
    csv_text = _extended_csv("20240101;;20340101;;;;;;;;;;7777ZZ;1;;;;C;;;;0;0;0;0;;0;0")
    labels = parse_csv(csv_text)
    assert len(labels) == 1
    label = labels[0]
    assert label.energiebehoefte == 0.0
    assert label.warmtebehoefte == 0.0
    assert label.primaire_fossiele_energie == 0.0
    assert label.aandeel_hernieuwbare_energie == 0.0
    assert label.berekende_co2_emissie == 0.0
    assert label.berekende_energieverbruik == 0.0


# ---------------------------------------------------------------------------
# Calculation-regime classification (EnergyLabel.calculation_regime /
# co2_is_placeholder).
#
# The regime drives unit selection downstream
# (:mod:`citygml_energy.city_builder.energy_resources`):
# NTA 8800 → kWh/(m²·yr) per-m², legacy → MJ/yr total. Empirical
# evidence behind these rules is in § 5i of the EP-online mapping doc.
# ---------------------------------------------------------------------------


def _label_with_method(berekeningstype: str | None) -> EnergyLabel:
    """Return a minimal EnergyLabel carrying just the Berekeningstype to classify."""
    return EnergyLabel(
        postcode="7881AA",
        huisnummer=42,
        huisletter=None,
        toevoeging=None,
        bag_verblijfsobject_id=None,
        energieklasse=None,
        registratiedatum=None,
        opnamedatum=None,
        geldig_tot=None,
        berekeningstype=berekeningstype,
    )


def test_calculation_regime_nta8800_variants() -> None:
    """Every flavour of "NTA 8800:..." resolves to the ``nta8800`` regime."""
    for method in (
        "NTA 8800:2024 (basisopname woningbouw)",
        "NTA 8800:2024 (detailopname woningbouw)",
        "NTA 8800:2024 (basisopname utiliteitsbouw)",
        "NTA 8800:2020 (detailopname utiliteitsbouw)",
        "NTA 8800:2018",
    ):
        assert _label_with_method(method).calculation_regime() == "nta8800", method


def test_calculation_regime_definitief_energielabel_is_legacy_total() -> None:
    """The pre-NTA-8800 "Rekenmethodiek Definitief Energielabel" is legacy_total.

    Specifically the v1.2 / 16 september 2014 string that ships in 1.44 M
    rows of the production v20260401 vintage.
    """
    method = "Rekenmethodiek Definitief Energielabel, versie 1.2, 16 september 2014"
    assert _label_with_method(method).calculation_regime() == "legacy_total"


def test_calculation_regime_nader_voorschrift_is_legacy_total() -> None:
    """Nader Voorschrift (ISSO 75.3 lineage, ~1.40 M rows) is legacy_total."""
    for method in (
        "Nader Voorschrift, versie 1.0, 1 februari 2014",
        "ISSO75.3, versie 3.0, oktober 2011",
        "ISSO 75.3 versie 4.0",
        "ISSO82.3",
    ):
        assert _label_with_method(method).calculation_regime() == "legacy_total", method


def test_calculation_regime_unknown_for_unrecognised_string() -> None:
    """Unrecognised method string falls into ``unknown`` (no resources emitted)."""
    assert _label_with_method("Some 2030 method we have not seen").calculation_regime() == "unknown"


def test_calculation_regime_unknown_when_berekeningstype_missing() -> None:
    """Empty / missing Berekeningstype is ``unknown`` (no scope to classify)."""
    assert _label_with_method(None).calculation_regime() == "unknown"
    assert _label_with_method("").calculation_regime() == "unknown"
    assert _label_with_method("   ").calculation_regime() == "unknown"


def test_co2_is_placeholder_only_for_definitief_energielabel() -> None:
    """``BerekendeCO2Emissie=0`` is treated as data EXCEPT for the v1.2 branch.

    Empirical: 99.997% of Definitief Energielabel rows ship 0,00 (the
    method does not compute CO₂); other regimes compute it as data.
    """
    assert (
        _label_with_method(
            "Rekenmethodiek Definitief Energielabel, versie 1.2, 16 september 2014"
        ).co2_is_placeholder()
        is True
    )
    assert (
        _label_with_method("NTA 8800:2024 (basisopname woningbouw)").co2_is_placeholder() is False
    )
    assert _label_with_method("Nader Voorschrift, versie 1.0").co2_is_placeholder() is False
    assert _label_with_method("ISSO75.3, versie 3.0, oktober 2011").co2_is_placeholder() is False
    assert _label_with_method(None).co2_is_placeholder() is False


# ---------------------------------------------------------------------------
# Warm-cache fetch: no network, no API key
# ---------------------------------------------------------------------------


def _bundle_zip_bytes(csv_text: str) -> bytes:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mutatiebestand.csv", csv_text)
    return buf.getvalue()


class _NetworkForbidden:
    """Stand-in requests.Session that fails the test on any request."""

    def request(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("fetch_energy_labels touched the network despite a warm cache")


def test_fetch_serves_warm_cache_without_network_or_api_key(tmp_path, monkeypatch) -> None:
    """The bundle cache key is fixed, so a warm cache must short-circuit
    the DownloadInfo round-trip (the only step needing the API key)."""
    from citygml_energy.city_builder.fetchers.eponline import fetch_energy_labels
    from citygml_energy.city_builder.http import CachedSession

    session = CachedSession(cache_dir=tmp_path)

    class _SeedResponse:
        status_code = 200
        content = _bundle_zip_bytes(_csv("2628CD;42;;;;A++;20230514;20230501;20331231"))

        def raise_for_status(self) -> None:
            return None

    class _SeedSession:
        def request(self, *args: object, **kwargs: object) -> _SeedResponse:
            return _SeedResponse()

    # Seed the cache through the public API (one fake network round-trip).
    monkeypatch.setattr(session, "_session", _SeedSession())  # documented test seam, see http.py
    seeded = session.get_bytes("https://example.invalid/bundle", cache_key="ep_online_bundle")
    assert session.cached_bytes("ep_online_bundle") == seeded

    # From here on any network use fails the test; the API key is junk.
    monkeypatch.setattr(session, "_session", _NetworkForbidden())
    labels = fetch_energy_labels(session, api_key="not-a-real-key")
    assert len(labels) == 1
    assert labels[0].postcode == "2628CD"


def test_cached_bytes_reports_cold_and_respects_use_cache(tmp_path) -> None:
    from citygml_energy.city_builder.http import CachedSession

    session = CachedSession(cache_dir=tmp_path)
    assert session.cached_bytes("ep_online_bundle") is None

    uncached = CachedSession(cache_dir=tmp_path, use_cache=False)
    assert uncached.cached_bytes("ep_online_bundle") is None


def test_cached_bytes_warm_hit_logs_the_entry_age(tmp_path, caplog, monkeypatch) -> None:
    """A warm hit names the entry's date and age, so a months-old vintage
    is visible instead of being served silently forever (fixed-key entries
    never expire)."""
    import logging

    from citygml_energy.city_builder.http import CachedSession

    session = CachedSession(cache_dir=tmp_path)

    class _SeedResponse:
        status_code = 200
        content = b"zip-bytes"

        def raise_for_status(self) -> None:
            return None

    class _SeedSession:
        def request(self, *args: object, **kwargs: object) -> _SeedResponse:
            return _SeedResponse()

    monkeypatch.setattr(session, "_session", _SeedSession())  # documented test seam, see http.py
    session.get_bytes("https://example.invalid/bundle", cache_key="ep_online_bundle")

    with caplog.at_level(logging.INFO, logger="citygml_energy.city_builder.http"):
        assert session.cached_bytes("ep_online_bundle") == b"zip-bytes"

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "'ep_online_bundle'" in message and "dated" in message and "delete" in message
        for message in messages
    )
