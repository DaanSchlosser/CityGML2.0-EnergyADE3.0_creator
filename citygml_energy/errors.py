"""Common exception hierarchy for the package.

All user-facing errors raised by the generation pipelines inherit from
:class:`CityGMLError`, so a caller wanting to treat any input/config
problem uniformly can write ``except CityGMLError``. The two leaf
classes stay semantically distinct:

* :class:`InputFileError` -- raised by the per-building feature-collection
  loader (:mod:`citygml_energy.input_loader`) when the JSON input fails
  validation.
* :class:`CityBuildError` -- raised by the city-scale pipeline
  (:mod:`citygml_energy.city_builder`) when the JSON config, fetched
  data, or orchestration fails.

Both remain ``ValueError`` subclasses so existing callers that catch
``ValueError`` keep working.
"""

from __future__ import annotations


class CityGMLError(ValueError):
    """Root of every user-facing error raised by this package."""


class InputFileError(CityGMLError):
    """Raised when a JSON feature input file is invalid."""


class CityBuildError(CityGMLError):
    """Raised for any user-addressable failure in the city-build pipeline."""
