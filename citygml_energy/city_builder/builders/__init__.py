"""xsdata builders for the city pipeline, split per CityGML domain.

Sub-modules:

* :mod:`.building`: ``bldg:Building`` + ``nrg3:BuildingUnit``
  (per-Pand and per-VBO construction, plus all 3DBAG attribute and
  LoD geometry mapping).
* :mod:`.address`: ``core:Address`` (xAL-flavoured, attached under a
  BuildingUnit).
* :mod:`.epc`: year-of-construction attribution +
  ``nrg3:EnergyPerformanceCertificate`` + EP-online classification.
* :mod:`.vegetation`: ``veg:SolitaryVegetationObject``, including
  CFTree morphometric mapping and BGT / Emmen-BOR enrichment.
* :mod:`._common`: cross-domain xsdata-aware helpers
  (:func:`_common.inner_type`, UOM constants).

The CBS-Postcode6 ``nrg3:UrbanFunctionArea`` step is its own self-
contained module one level up at
:mod:`citygml_energy.city_builder.postcode6` (fetch + filter + build +
group-join + attach behind one seam, rather than scattered across
``builders/`` + ``pipeline.py``).

Cross-cutting type-coercion helpers live one level up at
:mod:`citygml_energy.city_builder._helpers` so the fetchers can share
them without transitively pulling in xsdata bindings.

The package re-exports the same public + tested-private surface that
the previous monolithic ``builders.py`` module did, so external imports
of the form ``from citygml_energy.city_builder.builders import X``
keep working unchanged.
"""

from __future__ import annotations

from ..fetchers.eponline import EnergyLabel
from .address import build_address
from .building import (
    attach_building_units_to_building,
    build_building,
    build_building_unit,
    iter_lod2_thematic_classification,
    lod2_thematic_surface_gml_id,
)
from .epc import (
    apply_bag_year_metadata_to_building,
    apply_eponline_pand_attribution_to_building,
    build_epc,
)
from .vegetation import build_solitary_vegetation_object

__all__ = [
    "EnergyLabel",
    "apply_bag_year_metadata_to_building",
    "apply_eponline_pand_attribution_to_building",
    "attach_building_units_to_building",
    "build_address",
    "build_building",
    "build_building_unit",
    "build_epc",
    "build_solitary_vegetation_object",
    "iter_lod2_thematic_classification",
    "lod2_thematic_surface_gml_id",
]
