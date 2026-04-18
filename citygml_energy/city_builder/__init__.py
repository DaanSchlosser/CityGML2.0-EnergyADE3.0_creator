"""City-scale CityGML + Energy ADE builder.

Given a small JSON configuration (:mod:`.config`) that names a Dutch
municipality, this package fetches:

* the municipality outline from PDOK ``bestuurlijkegebieden``,
* every BAG ``Pand`` and ``Verblijfsobject`` inside that outline,
* every 3DBAG tile the outline overlaps (LoD 0/1/2 geometries per Pand),
* the full EP-online energy-label dataset (bulk CSV), matched onto the
  BAG addresses by ``(postcode, huisnummer, huisletter, toevoeging)``,

and builds a single :class:`citygml_energy.core.CityModel` containing:

* one ``bldg:Building`` per Pand, with LoD 0/1/2 geometries and basic
  attributes (``yearOfConstruction`` from 3DBAG),
* one ``bldg:address`` per VBO (address fields are embedded directly
  in the PDOK BAG WFS VBO response),
* one ``nrg3:BuildingUnit`` per VBO, each carrying the matched
  ``nrg3:EnergyPerformanceCertificate`` when an EP-online row is found.

The package **does not** introduce schema-specific code: every xsdata
class is resolved by XSD-qualified name through
:mod:`citygml_energy.mapping`, so regenerating the bindings will not
break this pipeline either.

Public API:

.. code-block:: python

    from citygml_energy.city_builder import (
        build_city_model,
        build_city_gml_file,
        load_city_config,
    )
"""

from __future__ import annotations

from .config import CityBuildConfig, CityBuildError, load_city_config
from .pipeline import build_city_gml_file, build_city_model

__all__ = [
    "CityBuildConfig",
    "CityBuildError",
    "build_city_gml_file",
    "build_city_model",
    "load_city_config",
]
