"""Unit-of-measure vocabulary and read-side unit normalisation.

This module is the single declaration site for every ``@uom`` token the
two pipelines (ADR-0003) write into the output GML, and the single
place where unit strings participate in arithmetic. It deliberately
imports nothing from the bindings so every layer of the package
(fetchers, builders, the derived-attribute emitters) can use it without
violating the xsdata layering rule.

Wire-format contract
--------------------

Every token below is registered in the KITModelViewer unit catalog
(``KITModelViewer_V*/Data/UOMList.xml``), either as a ``UOM/@id`` or as
an ``altId`` alias. An unregistered token still serialises and
validates, but the viewer's Properties panel then displays the raw
token instead of a translated unit name. ``tools/audit_silent_bugs.py``
(check H6) cross-checks every ``uom=`` attribute of a generated GML
against the same catalog, so drift between this vocabulary and the
catalog surfaces in the audit. The per-building input loader applies
the same gate up front: every ``uom`` declared in the input JSON must
be a member of :data:`REGISTERED_UOM_TOKENS` (the catalog mirror
below), so an off-catalog token is rejected at load time with the
input path named, instead of three tools later in the audit.

Read-side contract
------------------

``@uom`` is write-only everywhere in this package except one place:
the construction reduction in :mod:`citygml_energy.boundary_attributes`
multiplies layer thickness, material density, and specific heat
capacity into an areal heat capacity. Those three reads go through
:func:`measure_value`, which normalises a declared unit into the SI
base the formula expects and refuses (warn and return ``None``) any
token it does not recognise. The accepted spellings per quantity follow
the catalog's own alias structure (e.g. ``J/(kg*K)`` and ``J/(K*kg)``
are altIds of one catalog entry), so a value the catalog considers
well-labelled is never rejected on spelling alone.

The factor maps are deliberately closed: only catalog-listed aliases
appear, with exact power-of-ten factors. Unit *parsing* (caret forms,
arbitrary products) is a non-goal; an author who writes a token outside
the catalog gets a warning naming the accepted spellings, and the
derived attribute is omitted, which is this project's schema-honest
signal for "could not be derived".
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DENSITY",
    "EMITTED_UOM_TOKENS",
    "LENGTH",
    "REGISTERED_UOM_TOKENS",
    "SPECIFIC_HEAT_CAPACITY",
    "UOM_AREA_M2",
    "UOM_DEGREES",
    "UOM_KG_PER_A",
    "UOM_KG_PER_M2_PER_A",
    "UOM_KJ_PER_K_M2",
    "UOM_KWH_PER_A",
    "UOM_KWH_PER_M2_PER_A",
    "UOM_M3_PER_A",
    "UOM_METRES",
    "UOM_MJ_PER_A",
    "UOM_PERCENT",
    "UOM_VOLUME_M3",
    "Quantity",
]

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geometric and dimensionless tokens
# ---------------------------------------------------------------------------

UOM_METRES: str = "m"  # METRE primary id
UOM_AREA_M2: str = "m2"  # SQUARE_METRE primary id
UOM_VOLUME_M3: str = "m3"  # CUBIC_METRE primary id
UOM_PERCENT: str = "percent"  # PERCENTAGE primary id (NOT "%", which is a sign-glyph)
# DEGREE altId in UOMList.xml (primary id is "grad"; "deg" is the more
# common ASCII synonym and is what the viewer's Properties panel
# accepts as input for filters). Solar-collector orientations and the
# Energy ADE 3.0 ``bdgBdrySurf{Azimuth,Inclination}`` use this token.
UOM_DEGREES: str = "deg"

# ---------------------------------------------------------------------------
# Energy-domain tokens (EP-online regimes, CBS aggregates)
#
# The regime semantics that motivate each choice are documented at the
# emission sites (:mod:`citygml_energy.city_builder.energy_resources`
# and :mod:`citygml_energy.city_builder.builders.epc`) and in § 7 of
# docs/mapping_city.md; this module owns only the spelling.
# ---------------------------------------------------------------------------

# Per-area annual energy. NTA 8800 reports BENG metrics in kWh/m²·jaar.
# In UOMList.xml as ``KILOWATT_PER_SQUAREMETER_PER_YEAR id="kWh/m2/a"``.
# Shared by the NTA 8800 ``nrg3:Energy.amount`` resources and the
# matching ``EnergyPerformanceCertificate.value``, so the two stay in
# lockstep through this one constant.
UOM_KWH_PER_M2_PER_A: str = "kWh/m2/a"

# Per-area annual CO₂ emission (NTA 8800 convention). In UOMList.xml as
# ``KILOGRAM_PER_SQUAREMETER_PER_YEAR id="kg/m2/a"``.
UOM_KG_PER_M2_PER_A: str = "kg/m2/a"

# Total annual energy (legacy regime, NEN 7120 lineage): the absolute
# annual primary fossil energy, not a per-m² intensity. In UOMList.xml
# as ``MEGAJOULE_PER_YEAR id="MJ/a"``. Shared by the legacy resources
# and the legacy ``EnergyPerformanceCertificate.value``.
UOM_MJ_PER_A: str = "MJ/a"

# Total annual CO₂ emission (legacy Nader Voorschrift / ISSO branch),
# total kg/yr rather than per-m². In UOMList.xml as
# ``KILOGRAM_PER_YEAR id="kg/a"``. Companion to ``UOM_MJ_PER_A``.
UOM_KG_PER_A: str = "kg/a"

# Total annual natural-gas volume, used by the CBS Postcode6
# ``UrbanFunctionArea`` resources. In UOMList.xml as
# ``CUBIC_METRE_PER_YEAR id="m3/a"``.
UOM_M3_PER_A: str = "m3/a"

# Total annual electrical energy, the CBS per-dwelling average. In
# UOMList.xml as ``KILOWATT_HOUR_PER_YEAR id="kWh/a"``. Distinct from
# ``UOM_KWH_PER_M2_PER_A``: this is an absolute annual figure, not a
# per-area intensity.
UOM_KWH_PER_A: str = "kWh/a"

# ---------------------------------------------------------------------------
# Building-physics tokens
# ---------------------------------------------------------------------------

# Areal heat capacity for ``bdgBdrySurfHeatCapacity``. SI-conformant
# token (``k`` = kilo prefix, ``K`` = kelvin per BIPM SI Brochure §3.1;
# the ISO 13786 building-physics convention is identical). A typical
# wall sits at 50-500 kJ/(K·m²), so a J-based token would push values
# to 5-6 digits. Wire-format follows the project's conventions: no
# caret superscripts, ``m2`` rather than ``m^2``.
UOM_KJ_PER_K_M2: str = "kJ/(K*m2)"


# Every token the pipelines emit, for registry cross-checks (the unit
# tests assert each member resolves in UOMList.xml; the H6 audit makes
# the same check against generated GML).
EMITTED_UOM_TOKENS: frozenset[str] = frozenset(
    {
        UOM_METRES,
        UOM_AREA_M2,
        UOM_VOLUME_M3,
        UOM_PERCENT,
        UOM_DEGREES,
        UOM_KWH_PER_M2_PER_A,
        UOM_KG_PER_M2_PER_A,
        UOM_MJ_PER_A,
        UOM_KG_PER_A,
        UOM_M3_PER_A,
        UOM_KWH_PER_A,
        UOM_KJ_PER_K_M2,
    }
)


# Every spelling the UOMList.xml catalog registers: each ``UOM/@id``
# plus each ``altId`` alias, mirrored verbatim so the input loader can
# gate hand-authored ``uom`` declarations without a filesystem
# dependency on the viewer directory. ``EMITTED_UOM_TOKENS`` covers
# only what the pipelines themselves write; hand-authored per-building
# inputs legitimately carry further registered tokens (``kW`` device
# power, ``W/(m2*K)`` U-values, ``Cel`` setpoints, ...), so the loader
# gate is this full set. The mirror is kept in sync by a registry test
# (tests/test_units.py) that re-parses the catalog and asserts set
# equality, so extending UOMList.xml without updating this set (or
# vice versa) fails the suite.
REGISTERED_UOM_TOKENS: frozenset[str] = frozenset(
    {
        "-",
        "1/h",
        "A",
        "Cel",
        "F",
        "H",
        "Hz",
        "J",
        "J/(K*kg)",
        "J/(kg*K)",
        "J/(sec*cm2)",
        "K",
        "K*m2/W",
        "KwH",
        "MJ/a",
        "MWh",
        "MWh/a",
        "N",
        "Ohm",
        "Pa",
        "Persons",
        "S",
        "S/m",
        "Sm-1",
        "V",
        "W",
        "W(K*m^2)-1",
        "W/(K*m)",
        "W/(m*K)",
        "W/(m2*K)",
        "W/Persons",
        "W/W",
        "W/m2",
        "WH",
        "Wb",
        "Wh",
        "bar",
        "cd",
        "cloud",
        "cloud_10",
        "cm",
        "deg",
        "g",
        "g/m3",
        "gm-3",
        "grad",
        "h",
        "j",
        "jkg-1k-1",
        "k",
        "kJ",
        "kJ/(K*kg)",
        "kJ/(K*m2)",
        "kJ/(kg*K)",
        "kW",
        "kWh",
        "kWh/a",
        "kWh/m2",
        "kWh/m2/a",
        "kg",
        "kg/a",
        "kg/m2/a",
        "kg/m3",
        "kgm-3",
        "kj",
        "kjkg-1k-1",
        "kw",
        "kwh",
        "kwhm-2",
        "l/m2*sec",
        "l/s",
        "lm",
        "lm-2s-1",
        "ls-1",
        "lx",
        "m",
        "m/s",
        "m2",
        "m2*K/W",
        "m2/Persons",
        "m2kw-1",
        "m2persons-1",
        "m3",
        "m3/a",
        "m3/h",
        "m3/s",
        "m3s-1",
        "mm",
        "mol",
        "ng",
        "ng/(m2*Pa*s)",
        "ngs-1m-2p-1",
        "percent",
        "rad",
        "s",
        "scale",
        "urn:adv:uom:grad",
        "urn:adv:uom:m",
        "urn:adv:uom:m2",
        "urn:adv:uom:m3",
        "w",
        "wh",
        "wm-1k-1",
        "wm-2",
        "wm-2k-1",
        "wpersons-1",
    }
)


# ---------------------------------------------------------------------------
# Read-side normalisation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Quantity:
    """One physical quantity that participates in arithmetic.

    ``factors`` maps every accepted ``@uom`` spelling to the multiplier
    that converts a value so labelled into the quantity's SI base
    (``si_uom``). The accepted spellings mirror the UOMList.xml alias
    structure: every key is a catalog ``id`` or ``altId``, and aliases
    of one catalog entry share one factor. Keys outside the catalog are
    not added here; an unrecognised token is a warn-and-skip, not a
    parse attempt.

    ``name`` and ``si_uom`` exist for log messages: a warning names the
    quantity, the offending token, and the accepted spellings, so an
    input author can fix the declaration without reading this module.
    """

    name: str
    si_uom: str
    factors: Mapping[str, float]


# Layer thickness. METRE / MILLIMETRE / CENTIMETRE catalog entries;
# ``urn:adv:uom:m`` is METRE's second altId (AdV convention).
LENGTH: Quantity = Quantity(
    name="length",
    si_uom="m",
    factors={
        "m": 1.0,
        "urn:adv:uom:m": 1.0,
        "mm": 0.001,
        "cm": 0.01,
    },
)

# Material density. DENSITY_KG (``kg/m3``) and DENSITY_G (``g/m3``)
# catalog entries; the gram form is 10⁻³ of the SI base.
DENSITY: Quantity = Quantity(
    name="density",
    si_uom="kg/m3",
    factors={
        "kg/m3": 1.0,
        "kgm-3": 1.0,
        "g/m3": 0.001,
        "gm-3": 0.001,
    },
)

# Specific heat capacity. SPECIFIC_HEAT_J and SPECIFIC_HEAT_KJ catalog
# entries, three alias spellings each. The kJ forms are the spelling
# most material datasheets use; without the explicit factor they would
# silently under-report heat capacity 1000x (the tokens are valid
# catalog members, so the H6 output audit cannot catch that mistake;
# only this read-side map can).
SPECIFIC_HEAT_CAPACITY: Quantity = Quantity(
    name="specific heat capacity",
    si_uom="J/(kg*K)",
    factors={
        "J/(kg*K)": 1.0,
        "J/(K*kg)": 1.0,
        "jkg-1k-1": 1.0,
        "kJ/(kg*K)": 1000.0,
        "kJ/(K*kg)": 1000.0,
        "kjkg-1k-1": 1000.0,
    },
)


def measure_value(
    measure: Any,
    quantity: Quantity,
    *,
    context: str = "",
) -> float | None:
    """Return the SI-normalised numeric value of a ``gml:MeasureType``-like object.

    Duck-typed on ``.value`` (the number) and ``.uom`` (the unit token)
    so it works on any of the xsdata measure classes without importing
    the bindings.

    Returns ``None`` in three cases, of which only the last warns:

    * *measure* is ``None``: an absent optional measure is normal
      (e.g. a Gas material has no density), so this stays silent.
    * ``.value`` is not a plain number (missing, ``bool``, string):
      the object is malformed rather than mislabelled; silent, matching
      the pre-normalisation behaviour.
    * ``.uom`` is missing or not in ``quantity.factors``: the value
      exists but cannot be trusted into arithmetic. A warning names the
      *context*, the quantity, the offending token, and the accepted
      spellings; the caller omits the derived attribute, which is the
      schema-honest signal for "could not be derived". The XSD requires
      ``@uom`` on every measure, so the missing-uom case only arises on
      hand-built objects.

    The recognised-token case returns ``value * factor`` as ``float``,
    expressed in ``quantity.si_uom``.
    """
    if measure is None:
        return None
    value = getattr(measure, "value", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    uom = getattr(measure, "uom", None)
    token = uom.strip() if isinstance(uom, str) else None
    if token:
        factor = quantity.factors.get(token)
        if factor is not None:
            return float(value) * factor
    _LOG.warning(
        "%s: %s value %r carries uom=%r, expected one of %s; "
        "skipping the value (the derived attribute will be omitted)",
        context or "measure",
        quantity.name,
        value,
        token if token is not None else uom,
        sorted(quantity.factors),
    )
    return None
