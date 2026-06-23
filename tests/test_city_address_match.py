"""Unit tests for the BAG ↔ EP-online address matcher."""

from __future__ import annotations

from datetime import date

from citygml_energy.city_builder.address_match import match_addresses, wanted_label_filter
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


def test_vbo_without_postcode_is_emitted_without_label() -> None:
    """A postcode-less VBO (a garage or storage box) is still a
    BuildingUnit. It is emitted, grouped under its Pand, with no energy
    label, and is never dropped (ADR-0005)."""
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
    grouped = match_addresses(vbos=[vbo])
    [resolved] = grouped["P1"]
    assert resolved.vbo.identificatie == "V1"
    assert resolved.energy_label is None


def test_vbo_without_huisnummer_is_emitted_without_label() -> None:
    """A VBO with no huisnummer is still emitted as a BuildingUnit with
    no energy label; it simply cannot take part in the address-key
    fallback (ADR-0005)."""
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
    grouped = match_addresses(vbos=[vbo])
    [resolved] = grouped["P1"]
    assert resolved.vbo.identificatie == "V1"
    assert resolved.energy_label is None


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
        "2628CD",
        42,
        "C",
        registratie=date(2018, 1, 1),
        berekeningstype="Definitief Energielabel",
    )
    nta = _label(
        "2628CD",
        42,
        "A",
        registratie=date(2024, 6, 1),
        berekeningstype="NTA 8800:2024",
    )
    vbos = [_vbo("V1", "P1", postcode="2628CD", huisnummer=42)]
    grouped = match_addresses(vbos=vbos, energy_labels=[legacy, nta])
    resolved = grouped["P1"][0].energy_label
    assert resolved is not None
    assert resolved.energieklasse == "A"
    assert resolved.calculation_regime() == "nta8800"


def test_recency_key_is_shared_with_eponline_pand_pick() -> None:
    """The per-VBO de-duplication and the per-Pand canonical pick must
    use the same recency key.

    Two consumers exist for the EP-online recency ordering: the per-
    VBO de-duplication in :func:`match_addresses` (via
    :func:`address_match._label_timestamp`) and the per-Pand canonical
    pick in :func:`builders.epc._pick_canonical_eponline_label` (via
    ``_eponline_label_recency_key``). If they ever diverge — e.g.
    one weights ``opnamedatum`` differently from the other — the
    BuildingUnit-level resources (NTA 8800 vs legacy) and the Pand-
    level ``bdgType`` / ``yearOfConstructionEPOnline`` would silently
    pick from different rows.

    The aliasing in ``builders/epc.py`` routes both through the same
    function object; this test locks that invariant by identity check.
    """
    from citygml_energy.city_builder.address_match import _label_timestamp
    from citygml_energy.city_builder.builders.epc import (
        _eponline_label_recency_key,
    )

    assert _eponline_label_recency_key is _label_timestamp


def test_older_nta_loses_to_newer_legacy() -> None:
    """The mirror case: when the legacy label is newer, regime
    classification follows the timestamp-ordering, even though NTA 8800
    is the more modern method. The matcher does not prefer one regime
    over another; freshness is the only tie-breaker.
    """
    nta = _label(
        "2628CD",
        42,
        "A",
        registratie=date(2018, 1, 1),
        berekeningstype="NTA 8800:2020",
    )
    legacy = _label(
        "2628CD",
        42,
        "G",
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
        "2628CD",
        42,
        "B",
        registratie=date(2018, 1, 1),
        bag_verblijfsobject_id="V1",
        berekeningstype="NTA 8800:2018",
    )
    label_by_key_only = _label(
        "2628CD",
        42,
        "F",
        registratie=date(2024, 1, 1),
        berekeningstype="Nader Voorschrift",
    )
    grouped = match_addresses(
        vbos=[vbo],
        energy_labels=[label_by_id, label_by_key_only],
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
        _label("2628CD", 42, "A", registratie=date(2024, 1, 1), berekeningstype="NTA 8800:2024"),
        _label(
            "2628CD",
            43,
            "G",
            registratie=date(2018, 1, 1),
            berekeningstype="Definitief Energielabel",
        ),
    ]
    grouped = match_addresses(vbos=vbos, energy_labels=labels)
    by_huisnummer = {r.huisnummer: r for r in grouped["P1"]}
    label_42 = by_huisnummer[42].energy_label
    label_43 = by_huisnummer[43].energy_label
    assert label_42 is not None and label_42.calculation_regime() == "nta8800"
    assert label_43 is not None and label_43.calculation_regime() == "legacy_total"


def _postcode_less_vbo(identificatie: str, pand_id: str) -> Verblijfsobject:
    """A VBO with no postcode (a garage or storage box).

    It is still emitted as a BuildingUnit; it just cannot form an address
    key, so it never reaches the EP-online address-key fallback.
    """
    return Verblijfsobject(
        identificatie=identificatie,
        pand_identificatie=pand_id,
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


def test_postcode_less_vbo_is_emitted_and_matchable_by_bag_id() -> None:
    """A postcode-less VBO is emitted and can still receive a label by
    BAG id.

    The BAG-id match does not depend on the address, so a garage that
    EP-online holds a certificate for (keyed on its ``verblijfsobject_id``)
    still gets it, even though it has no postcode and no address key. This
    is the regression guard for ADR-0005: the old code dropped this VBO
    before the join, losing both the unit and a matchable label.
    """
    vbos = [_postcode_less_vbo("V2", "P1")]
    label = _label("9999ZZ", 9, "C", bag_verblijfsobject_id="V2")
    grouped = match_addresses(vbos=vbos, energy_labels=[label])
    [resolved] = grouped["P1"]
    assert resolved.vbo.identificatie == "V2"
    assert resolved.energy_label is not None
    assert resolved.energy_label.energieklasse == "C"


def test_label_filter_covers_every_id_but_only_address_key_keys() -> None:
    """Every VBO id reaches the CSV filter (the id match is primary, and
    every VBO has a BAG id), but only the address-key VBOs contribute a
    fallback address key.

    The postcode-less VBO's id must be present so EP-online can match it
    by ``BAGVerblijfsobjectID``; its (absent) address key must not be,
    because a partial key cannot join reliably.
    """
    vbos = [_vbo("V1", "P1"), _postcode_less_vbo("V2", "P1")]
    flt = wanted_label_filter(vbos)
    assert flt.ids == frozenset({"V1", "V2"})
    assert len(flt.keys) == 1


def test_label_filter_id_population_equals_the_join_population() -> None:
    """The fetch filter's id set covers exactly the joined units: every
    VBO is both filtered for and emitted, so the two populations match."""
    vbos = [
        _vbo("V1", "P1"),
        _vbo("V2", "P2", huisnummer=7),
        _postcode_less_vbo("V3", "P3"),
    ]
    flt = wanted_label_filter(vbos)
    grouped = match_addresses(vbos=vbos)
    joined_ids = {r.vbo.identificatie for group in grouped.values() for r in group}
    assert flt.ids == frozenset(joined_ids)
    assert joined_ids == {"V1", "V2", "V3"}


def test_label_filter_is_order_independent() -> None:
    """Equal VBO sets give equal filters regardless of input order; the
    pipeline's filtered-labels cache digest depends on this."""
    a = [_vbo("V1", "P1"), _vbo("V2", "P2", huisnummer=7)]
    assert wanted_label_filter(a) == wanted_label_filter(list(reversed(a)))
