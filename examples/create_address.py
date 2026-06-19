"""CLI entry point for the address-driven CityGML builder.

Give it a Dutch address and it builds a square extract centred on the
building(s) the address covers, painting those buildings a light
yellow-orange and everything around them white::

    python examples/create_address.py --address "Annie Romeinsingel 72-152 Leiden"

The address may be a single house, a range, or several streets, and it
tolerates the loose formatting of a typical listing::

    --address "Lange gracht 76-214 Leiden"
    --address "Etta Palmstraat en Joke Smitstraat z.n. Leiden"

Settings other than the address come from a profile JSON (``--profile``,
default ``inputs/address/leiden_example.json``): extent, LoDs, whether to
include EP-Online energy labels, the highlight colours, and so on. The
address and output path can be overridden on the command line so one
profile serves any address.

Requires the ``city`` optional extras (``requests`` + ``shapely``)::

    pip install -e .[city]

Network endpoints used:

* PDOK Locatieserver: geocode the address to a coarse anchor
* PDOK BAG WFS: Pand / VBO (authoritative address-to-building resolution)
* ``data.3dbag.nl``: LoD 0/1/2 CityJSON tiles
* ``public.ep-online.nl``: energy-label bulk file (only when energy
  labels are enabled; needs ``EP_ONLINE_API_KEY`` in ``.env`` or an
  ``ep_online_api_key_file`` in the profile)

On-demand tree generation:

A profile may add a ``vegetation.generate`` block so LoD3 trees are
reconstructed by CFTree on demand when the merged file is missing
(``inputs/address/leiden_250.json`` is the generate-enabled profile;
the default ``leiden_example.json`` has no vegetation block). CFTree runs
as a subprocess in its own environment, configured by ``CFTREE_REPO`` /
``CFTREE_RUNNER`` / ``CFTREE_PYTHON`` in ``.env`` (see ``.env.example``);
generation soft-fails to a treeless build when CFTree is unavailable. The
address profile also sets ``vegetation.geometry_only`` so trees carry
CFTree geometry only and the build skips the BGT register cross-reference
(and its PDOK round-trip)::

    python examples/create_address.py --profile inputs/address/leiden_250.json
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from citygml_energy.city_builder import build_city_model, load_city_config
from citygml_energy.city_builder.address_extent import AddressResolutionError
from citygml_energy.city_builder.config import CityBuildError

_DEFAULT_PROFILE = REPO_ROOT / "inputs" / "address" / "leiden_example.json"


def _configure_logging(verbosity: int) -> None:
    """Route package progress messages to stderr at the requested level."""
    level = (
        logging.WARNING if verbosity <= 0 else (logging.INFO if verbosity == 1 else logging.DEBUG)
    )
    logging.basicConfig(
        level=level,
        format="[%(name)s] %(message)s",
        stream=sys.stderr,
        force=True,
    )


def _slugify(text: str) -> str:
    """Turn an address into a filesystem-safe slug for a default output name."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "address-extract"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        type=Path,
        default=_DEFAULT_PROFILE,
        help="Path to an address-build profile JSON (default: inputs/address/leiden_example.json).",
    )
    parser.add_argument(
        "--address",
        type=str,
        default=None,
        help="Dutch address to build for; overrides the profile's address.query.",
    )
    parser.add_argument(
        "--extent",
        type=float,
        default=None,
        help="Side length of the square extent in metres; overrides the profile.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .gml path; overrides the profile (default derives from the address).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="Increase log verbosity (default: INFO; -v: DEBUG).",
    )
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    config = load_city_config(args.profile)
    if config.address_source is None:
        parser.error(f"profile {args.profile} has no 'address' block; it is not an address profile")

    # Apply command-line overrides onto the frozen config.
    address_source = config.address_source
    if args.address is not None:
        address_source = dataclasses.replace(address_source, query=args.address)
    if args.extent is not None:
        address_source = dataclasses.replace(address_source, extent_m=args.extent)
    config = dataclasses.replace(config, address_source=address_source)

    if args.output is not None:
        config = dataclasses.replace(config, output_path=args.output.resolve())
    elif args.address is not None:
        # A custom address should not overwrite the profile's default output;
        # derive a per-address filename next to it.
        derived = config.output_path.with_name(f"address_{_slugify(args.address)}.gml")
        config = dataclasses.replace(config, output_path=derived)

    try:
        model = build_city_model(config)
    except (CityBuildError, AddressResolutionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(output_path)
    print(f"Wrote {len(model.xsd.city_object_member)} city objects to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
