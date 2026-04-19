"""CLI entry point for the city-scale CityGML builder.

Run with::

    python examples/create_city.py --input inputs/city_example.json

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
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from citygml_energy.city_builder import build_city_gml_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "inputs" / "city_example.json",
        help="Path to a city-build JSON config (schema_version=city-1).",
    )
    args = parser.parse_args(argv)

    model = build_city_gml_file(args.input)
    print(f"Wrote {len(model.xsd.city_object_member)} city objects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
