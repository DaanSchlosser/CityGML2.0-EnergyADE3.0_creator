"""Construct ``core:Address`` (xAL-flavoured) for a resolved BAG VBO.

Structure (xAL-inside-core, plus optional ``multiPoint`` for the
VBO location point):

.. code-block:: text

    core:Address
      core:xalAddress
        xAL:AddressDetails
          xAL:Locality (type="city")
            xAL:LocalityName ("Delft")
            xAL:Thoroughfare
              xAL:ThoroughfareNumber ("42")
              xAL:ThoroughfareName   ("Mekelweg")
            xAL:PostalCode
              xAL:PostalCodeNumber   ("2628CD")
      core:multiPoint   (present when resolved.point is not None)
        gml:MultiPoint
          gml:pointMember/gml:Point/gml:pos   (VBO geometriePunt)
"""

from __future__ import annotations

from typing import Any

from ...bindings import ThoroughfareNameType
from ...gml_builders import build_multi_point
from ...mapping import resolve_class
from ...namespaces import DEFAULT_SRS_DIMENSION, DEFAULT_SRS_NAME
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
from ._common import inner_type

__all__ = ["build_address"]


def build_address(
    resolved: ResolvedAddress,
    *,
    gml_id_prefix: str = "",
    city_name: str = "",
    srs_name: str = DEFAULT_SRS_NAME,
    srs_dimension: int = DEFAULT_SRS_DIMENSION,
) -> Any | None:
    """Build a ``core:Address`` for *resolved* or ``None`` when unusable.

    The ``core:multiPoint`` element is typed ``gml:MultiPointPropertyType``
    and documented in the XSD as "locating the entrance(s)". BAG's
    ``geometriePunt`` is the authoritative address-locating point for a
    VBO; it always lies within the parent Pand but is not guaranteed
    to be at the entrance. That semantic mismatch is documentation-level
    only: the schema constraint is just "a MultiPoint", and every
    Dutch BAG-to-CityGML converter populates this element the same way.
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

    number_text = _assemble_number(resolved)
    locality = _build_locality(
        street=street,
        number_text=number_text,
        postcode=postcode,
        city_name=city_name,
    )
    details_cls = resolve_class(XAL_ADDRESS_DETAILS)
    address_details = details_cls(locality=locality)

    address_id = safe_gml_id(gml_id_prefix, "addr", resolved.vbo.identificatie)
    multi_point = None
    if resolved.point is not None:
        multi_point = build_multi_point(
            f"{address_id}_mp",
            [resolved.point],
            srs_name=srs_name,
            srs_dimension=srs_dimension,
        )

    address = address_cls(
        id=address_id,
        xal_address=xal_prop_cls(address_details=address_details),
        multi_point=multi_point,
    )
    return address


def _build_locality(*, street: str, number_text: str, postcode: str, city_name: str = "") -> Any:
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

    thoroughfare = thoroughfare_cls(
        thoroughfare_number=[thoroughfare_number_cls(content=[number_text])],
        thoroughfare_name=[ThoroughfareNameType(content=[street])],
    )

    postal_code = (
        postal_code_cls(postal_code_number=[postal_code_number_cls(content=[postcode])])
        if postcode
        else None
    )

    return locality_cls(
        locality_name=[locality_name_cls(content=[city_name])],
        thoroughfare=thoroughfare,
        postal_code=postal_code,
    )


def _assemble_number(resolved: ResolvedAddress) -> str:
    parts = [str(resolved.huisnummer)]
    if resolved.huisletter:
        parts.append(resolved.huisletter)
    if resolved.toevoeging:
        parts.append(f"-{resolved.toevoeging}")
    return "".join(parts)
