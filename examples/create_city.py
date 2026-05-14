"""CLI entry point for the city-scale CityGML builder.

Run with::

    python examples/create_city.py --input inputs/cities/emmer-compascuum_small-area.json

Requires the ``city`` optional extras (``requests`` + ``shapely``)::

    pip install -e .[city]

Network endpoints used:

* PDOK ``bestuurlijkegebieden``: municipality outline
* PDOK BAG WFS: Pand / VBO (address fields embedded in VBO response)
* ``data.3dbag.nl``: LoD 0/1/2 CityJSON tiles
* ``public.ep-online.nl``: energy-label bulk mutatiebestand (needs an
  API token; set ``EP_ONLINE_API_KEY`` in ``.env`` at project root or
  reference via ``ep_online_api_key_file`` in the config)

The first run populates the cache directory configured in the JSON;
subsequent runs are near-instant as long as the cache stays on disk.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from citygml_energy.city_builder import build_city_gml_file


def _configure_logging(verbosity: int) -> None:
    """Route package progress messages to stderr at the requested level.

    ``-v`` shows pipeline INFO (the old ``[city-builder]`` progress
    lines); ``-vv`` drops to DEBUG and includes fetcher / HTTP retry
    detail. Default (no flag) keeps only WARNING+ so piped use stays
    quiet.
    """
    level = logging.WARNING if verbosity <= 0 else (
        logging.INFO if verbosity == 1 else logging.DEBUG
    )
    logging.basicConfig(
        level=level,
        format="[%(name)s] %(message)s",
        stream=sys.stderr,
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "inputs" / "cities" / "emmer-compascuum_small-area.json",
        help="Path to a city-build JSON config.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count", default=1,
        help="Increase log verbosity (default: INFO; -vv: DEBUG).",
    )
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    model = build_city_gml_file(args.input)
    print(f"Wrote {len(model.xsd.city_object_member)} city objects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
