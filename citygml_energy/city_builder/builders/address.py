"""Construct ``core:Address`` (xAL-flavoured) for a resolved BAG VBO.

Structure (xAL-inside-core, plus optional ``multiPoint`` for the
VBO location point):

.. code-block:: text

    core:Address
      core:xalAddress
        xAL:AddressDetails
          xAL:Country
            xAL:CountryNameCode Scheme="iso.3166-1 alpha-2"  ("NL")
            xAL:CountryName                                   ("The Netherlands")
            xAL:Locality Type="Town"
              xAL:LocalityName                                ("Emmen")
              xAL:Thoroughfare Type="Street"
                xAL:ThoroughfareNumber NumberType="Single"    ("38")
                xAL:ThoroughfareNumberSuffix Type="huisletter" ("B")
                xAL:ThoroughfareNumberSuffix Type="huisnummertoevoeging"
                                             NumberSuffixSeparator="-" ("rood-2")
                xAL:ThoroughfareName                          ("Hoofdkanaal WZ")
              xAL:PostalCode
                xAL:PostalCodeNumber                          ("7881AB")
      core:multiPoint   (present when resolved.point is not None)
        gml:MultiPoint
          gml:pointMember/gml:Point/gml:pos                   (BAG geometriePunt)

Why this shape (each decision is grounded; rationale lives next to the
code that needs it).

Country wrapper.  We use the ``xAL:Country`` element to wrap the
locality so the address advertises its country unambiguously, mirroring
the EnergyADE 3.0 Alderaan reference (``Energy_ADE-3.0beta8/test_data/
Alderaan_Energy_ADE_All.gml``).  Country code is ISO 3166-1 alpha-2
(``NL``); the OASIS xAL 2.0 schema's ``CountryNameCode/@Scheme`` is open
(no enum), so ``iso.3166-1 alpha-2`` is acceptable.

huisletter and huisnummertoevoeging.  These two BAG fields have
distinct semantics (huisletter is a single MES-1 letter on the
``Nummeraanduiding`` side; huisnummertoevoeging is a free-text suffix
up to 4 characters) and xAL has exactly one slot that fits both:
``ThoroughfareNumberSuffix``, with ``maxOccurs="unbounded"`` so two
suffix elements on one Thoroughfare is schema-valid.  We disambiguate
the two with the ``@Type`` attribute (``"huisletter"`` /
``"huisnummertoevoeging"``) — that attribute is declared as an open
``xs:anyURI``-flavoured open string (no enum) on
``ThoroughfareNumberSuffix``, exactly so authors can roll their own
discriminator.

Locality is **woonplaats**, not gemeente.  IMBAG defines woonplaats as
the locality component of an address; a woonplaats can span multiple
gemeentes and a gemeente can contain multiple woonplaatsen (gemeente
Emmen contains the woonplaatsen Emmen, Klazienaveen, Nieuw-Amsterdam,
…).  We pull woonplaats off the VBO directly (via PDOK WFS); the
caller-supplied ``city_name`` parameter is kept only as a fallback for
test fixtures that do not surface woonplaats and is **not** the
authoritative source.

Tooling caveat (worth knowing for downstream interop).  3DCityDB v5
silently drops both ``ThoroughfareNumberSuffix`` elements during xAL
import: its ``XALAddressWalker`` overrides ``visit()`` for
``ThoroughfareName`` / ``ThoroughfareNumber`` / ``LocalityName`` /
``PostalCodeNumber`` / ``CountryName`` / ``PostBoxNumber`` only, and
the suffix elements (and any prefixes) have no override.  To stay
compatible we ALSO concatenate huisletter + huisnummertoevoeging into
the ``ThoroughfareNumber`` text (``38B-rood-2``) via
:func:`_assemble_number`, so a 3DCityDB consumer reading only that
slot still gets the full identifier; a consumer that reads
``ThoroughfareNumberSuffix/@Type`` gets the structured form.  This
denormalisation is intentional, not a schema preference.
"""

from __future__ import annotations

from typing import Any

from ...bindings import (
    AddressDetails,
    CountryName,
    ThoroughfareNameType,
    ThoroughfareNumberSuffix,
)
from ...gml_builders import build_multi_point
from ...mapping import resolve_class
from ...schema_types import (
    ADDRESS,
    XAL_ADDRESS_DETAILS,
    XAL_LOCALITY,
    XAL_POSTAL_CODE,
    XAL_THOROUGHFARE,
    XAL_THOROUGHFARE_NUMBER,
)
from .._helpers import safe_gml_id
from ..address_match import ResolvedAddress
from ..config import BuildContext
from ._common import inner_type

__all__ = ["build_address"]


# ISO 3166-1 alpha-2 code for the Netherlands. The country-code pair
# rides on the address through ``CountryNameCode/@Scheme`` +
# ``CountryName``; the ``CountryNameCode/@Scheme`` value is the
# universally-recognised string for ISO 3166-1 alpha-2 (Wikipedia,
# OGC, libpostal, libphonenumber all spell it the same way). Pinned
# here so changing the country surface is a one-line edit.
_NL_COUNTRY_CODE: str = "NL"
_NL_COUNTRY_NAME: str = "The Netherlands"
_NL_COUNTRY_CODE_SCHEME: str = "iso.3166-1 alpha-2"

# xAL ``Locality/@Type`` and ``Thoroughfare/@Type`` are open strings
# with no published Dutch profile. We pin the values used by the
# EnergyADE 3.0 Alderaan reference (``Town`` / ``Street``) so a
# downstream consumer that already understands Alderaan's xAL shape
# does not have to special-case ours.
_LOCALITY_TYPE_TOWN: str = "Town"
_THOROUGHFARE_TYPE_STREET: str = "Street"

# ``ThoroughfareNumberSuffix/@Type`` is the discriminator between
# huisletter and huisnummertoevoeging on the same Thoroughfare. Values
# match the IMBAG attribute names so any consumer can resolve them
# directly against the IMBAG vocabulary.
_SUFFIX_TYPE_HUISLETTER: str = "huisletter"
_SUFFIX_TYPE_TOEVOEGING: str = "huisnummertoevoeging"

# Separator for huisnummertoevoeging when written in flat form. BAG's
# own canonical-string representation joins the parts with a hyphen
# (``38-rood-2``); reusing the hyphen here matches what humans expect
# to read on a Dutch address.
_TOEVOEGING_SEPARATOR: str = "-"


def build_address(
    resolved: ResolvedAddress,
    build_context: BuildContext = BuildContext(),
) -> Any | None:
    """Build a ``core:Address`` for *resolved* or ``None`` when unusable.

    The ``core:multiPoint`` element is typed ``gml:MultiPointPropertyType``
    and documented in the XSD as "locating the entrance(s)". BAG's
    ``geometriePunt`` is the authoritative address-locating point for a
    VBO; it always lies within the parent Pand but is not guaranteed
    to be at the entrance. That semantic mismatch is documentation-level
    only: the schema constraint is just "a MultiPoint", and every
    Dutch BAG-to-CityGML converter populates this element the same way.

    *build_context.municipality* is used only when the VBO has no
    ``woonplaats`` (rare; legacy records or test fixtures). The VBO's
    own ``woonplaats`` is the authoritative source of the locality
    component otherwise (see the module docstring).
    """
    street = resolved.street.strip()
    postcode = resolved.postcode.strip()
    huisnummer = resolved.huisnummer
    if not street or huisnummer is None:
        return None

    address_cls = resolve_class(ADDRESS)
    xal_prop_cls = inner_type(address_cls, "xal_address")
    if xal_prop_cls is None:
        return None

    # Authoritative locality is the VBO's woonplaats; the build context's
    # municipality is a caller-supplied fallback used only when the VBO
    # has none (for legacy fixtures and tests pre-dating the woonplaats
    # join).
    locality_name = (resolved.woonplaats or build_context.municipality or "").strip()

    locality = _build_locality(
        street=street,
        huisnummer=huisnummer,
        huisletter=(resolved.huisletter or "").strip() or None,
        toevoeging=(resolved.toevoeging or "").strip() or None,
        postcode=postcode,
        locality_name=locality_name,
    )

    # Wrap the Locality in an ``xAL:Country`` element so the address
    # advertises its country unambiguously (mirrors the Alderaan
    # reference shape; see module docstring).
    country = AddressDetails.Country(
        country_name_code=[
            AddressDetails.Country.CountryNameCode(
                scheme=_NL_COUNTRY_CODE_SCHEME,
                content=[_NL_COUNTRY_CODE],
            )
        ],
        country_name=[CountryName(content=[_NL_COUNTRY_NAME])],
        locality=locality,
    )

    details_cls = resolve_class(XAL_ADDRESS_DETAILS)
    address_details = details_cls(country=country)

    address_id = safe_gml_id(build_context.gml_id_prefix, "addr", resolved.vbo.identificatie)
    multi_point = None
    if resolved.point is not None:
        multi_point = build_multi_point(
            f"{address_id}_mp",
            [resolved.point],
            srs_name=build_context.srs_name,
            srs_dimension=build_context.srs_dimension,
        )

    address = address_cls(
        id=address_id,
        xal_address=xal_prop_cls(address_details=address_details),
        multi_point=multi_point,
    )
    return address


def _build_locality(
    *,
    street: str,
    huisnummer: int,
    huisletter: str | None,
    toevoeging: str | None,
    postcode: str,
    locality_name: str,
) -> Any:
    """Build the ``xAL:Locality`` (Town) wrapping the Thoroughfare + PostalCode."""
    locality_cls = resolve_class(XAL_LOCALITY)
    # ``LocalityName`` and ``PostalCodeNumber`` are xsdata-generated nested
    # classes on their parents; ``resolve_class`` returns ``type`` so mypy
    # cannot see the nested attribute. Verified to exist at runtime by the
    # xsd-valid output tests.
    locality_name_cls = locality_cls.LocalityName  # type: ignore[attr-defined]
    thoroughfare_cls = resolve_class(XAL_THOROUGHFARE)
    thoroughfare_number_cls = resolve_class(XAL_THOROUGHFARE_NUMBER)
    postal_code_cls = resolve_class(XAL_POSTAL_CODE)
    postal_code_number_cls = postal_code_cls.PostalCodeNumber  # type: ignore[attr-defined]

    # ``ThoroughfareNumber`` carries the BAG huisnummer. The text content
    # ALSO embeds huisletter and huisnummertoevoeging (joined by the BAG-
    # canonical hyphen separator) so a consumer that reads only this slot
    # still sees the full identifier — see the module docstring for the
    # 3DCityDB-compatibility rationale. ``NumberType="Single"`` flags this
    # as one address (xAL distinguishes Single vs Range numbers).
    flat_number_text = _assemble_number(
        huisnummer=huisnummer,
        huisletter=huisletter,
        toevoeging=toevoeging,
    )
    thoroughfare_numbers = [
        thoroughfare_number_cls(
            number_type="Single",  # type: ignore[arg-type]
            content=[flat_number_text],
        )
    ]

    # huisletter and huisnummertoevoeging each get their own
    # ``ThoroughfareNumberSuffix`` element under the same Thoroughfare.
    # The xAL XSD allows this with ``maxOccurs="unbounded"``; the
    # @Type discriminator names the IMBAG attribute the value came from.
    thoroughfare_number_suffixes: list[ThoroughfareNumberSuffix] = []
    if huisletter:
        thoroughfare_number_suffixes.append(
            ThoroughfareNumberSuffix(
                type_value=_SUFFIX_TYPE_HUISLETTER,
                content=[huisletter],
            )
        )
    if toevoeging:
        thoroughfare_number_suffixes.append(
            ThoroughfareNumberSuffix(
                type_value=_SUFFIX_TYPE_TOEVOEGING,
                # The hyphen separator mirrors the canonical Dutch
                # rendering (``38-rood``); xAL surfaces it as a
                # dedicated attribute rather than embedding it in the
                # textual content, so a strict reader can preserve the
                # separator between the number and this suffix.
                number_suffix_separator=_TOEVOEGING_SEPARATOR,
                content=[toevoeging],
            )
        )

    thoroughfare = thoroughfare_cls(
        type_value=_THOROUGHFARE_TYPE_STREET,
        thoroughfare_number=thoroughfare_numbers,
        thoroughfare_number_suffix=thoroughfare_number_suffixes,
        thoroughfare_name=[ThoroughfareNameType(content=[street])],
    )

    postal_code = (
        postal_code_cls(postal_code_number=[postal_code_number_cls(content=[postcode])])
        if postcode
        else None
    )

    return locality_cls(
        type_value=_LOCALITY_TYPE_TOWN,
        locality_name=[locality_name_cls(content=[locality_name])],
        thoroughfare=thoroughfare,
        postal_code=postal_code,
    )


def _assemble_number(
    *,
    huisnummer: int,
    huisletter: str | None,
    toevoeging: str | None,
) -> str:
    """Concatenate huisnummer, huisletter, toevoeging into the flat form.

    The flat form (``38B-rood-2``) is what BAG itself uses when
    serialising an address to a single string and what most CityGML
    consumers (3DCityDB, FME's reader, citygml-tools) read out of
    ``ThoroughfareNumber``. We emit the flat form here AND emit the
    structured suffixes via separate elements above; the flat form is
    the lowest-common-denominator readable identifier, the structured
    form preserves the IMBAG semantics for tools that look for it.
    """
    parts = [str(huisnummer)]
    if huisletter:
        parts.append(huisletter)
    if toevoeging:
        parts.append(f"{_TOEVOEGING_SEPARATOR}{toevoeging}")
    return "".join(parts)
