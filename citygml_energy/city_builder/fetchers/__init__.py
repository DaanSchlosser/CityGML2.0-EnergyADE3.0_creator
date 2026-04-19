"""Data source adapters for the city-scale builder.

Each module exposes a small, testable interface: a function (or class)
that takes a :class:`citygml_energy.city_builder.http.CachedSession`
plus source-specific arguments and returns a list of normalised
records. No fetcher constructs xsdata objects; that is the pipeline's
job, so the fetchers stay easy to mock.
"""

from __future__ import annotations
