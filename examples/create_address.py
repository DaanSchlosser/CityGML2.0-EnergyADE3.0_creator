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
address, extent, and output path can be overridden on the command line so
one profile serves any address; overrides are validated exactly like the
profile values. ``--no-energy-labels`` disables the EP-Online step for
one run (the documented keyless first run for anyone without an API key)
and ``--refresh`` bypasses cached HTTP responses while still refilling
the cache with fresh downloads.

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
(``inputs/address/annie-romeinsingel-72-152-leiden_400m.json`` is the generate-enabled profile;
the default ``leiden_example.json`` has no vegetation block). CFTree runs
as a subprocess in its own environment, configured by ``CFTREE_REPO`` /
``CFTREE_RUNNER`` / ``CFTREE_PYTHON`` in ``.env`` (see ``.env.example``);
generation soft-fails to a treeless build when CFTree is unavailable. The
address profile also sets ``vegetation.geometry_only`` so trees carry
CFTree geometry only and the build skips the BGT register cross-reference
(and its PDOK round-trip)::

    python examples/create_address.py --profile inputs/address/annie-romeinsingel-72-152-leiden_400m.json
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from citygml_energy.city_builder import (
    build_city_model,
    load_city_config_data,
    validate_city_config,
)
from citygml_energy.city_builder.address_extent import AddressResolutionError
from citygml_energy.city_builder.config import CityBuildError

try:
    from requests import RequestException as _RequestError
except ImportError:  # pragma: no cover, the extras guard above fires first

    class _RequestError(Exception):  # type: ignore[no-redef]
        pass


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


def _build_parser() -> argparse.ArgumentParser:
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
        "--no-energy-labels",
        action="store_true",
        help=(
            "Disable the EP-Online energy-label step for this run, so no API "
            "key is needed (overrides the profile's include_energy_labels)."
        ),
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=("Bypass cached HTTP responses for this run; fresh downloads still refill the cache."),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="Increase log verbosity (default: INFO; -v: DEBUG).",
    )
    return parser


def _apply_cli_overrides(data: dict[str, Any], args: argparse.Namespace) -> None:
    """Fold the command-line overrides into the raw profile dict.

    Overrides land on the dict *before* validation so every value passes
    through the same checks a hand-edited profile would (an out-of-range
    ``--extent`` gets the normal ``address.extent_m`` error instead of
    silently bypassing the bound).
    """
    if args.no_energy_labels:
        data["include_energy_labels"] = False
    # A malformed address block is left alone so validation reports it
    # with the standard message rather than a CLI-flavoured crash.
    address = data.get("address")
    if isinstance(address, dict):
        if args.address is not None:
            address["query"] = args.address
        if args.extent is not None:
            address["extent_m"] = args.extent
        if args.address is not None or args.extent is not None:
            _apply_derived_names(data, address)
    if args.output is not None:
        # Resolved against the invoker's cwd, not the profile directory:
        # an explicit path on the command line means "right here".
        data["output"] = str(Path(args.output).resolve())


def _apply_derived_names(data: dict[str, Any], address: dict[str, Any]) -> None:
    """Re-derive the profile's names from an overridden address or extent.

    An ad-hoc address or size override re-derives the names so each run is
    self-describing and distinct: the output file and the on-demand tree file
    are named for the address and the square's size rather than overwriting
    the profile's defaults, and the dataset title is cleared so it falls back
    to the address (the pipeline builds the default from the query, see
    ``_address_model_name``). One profile therefore serves every address
    without one run clobbering another run's output or trees. Malformed
    profile values skip the rename and are reported by validation instead.
    """
    query = address.get("query")
    extent = address.get("extent_m", 500.0)
    if (
        not isinstance(query, str)
        or isinstance(extent, bool)
        or not isinstance(extent, (int, float))
    ):
        return
    stem = f"{_slugify(query)}_{extent:g}m"
    city_model = data.get("city_model")
    if isinstance(city_model, dict):
        city_model.pop("name", None)
    output = data.get("output")
    if isinstance(output, str) and output.strip():
        data["output"] = str(Path(output).with_name(f"{stem}.gml"))
    vegetation = data.get("vegetation")
    if isinstance(vegetation, dict):
        veg_path = vegetation.get("path")
        if isinstance(veg_path, str) and veg_path.strip():
            vegetation["path"] = str(Path(veg_path).with_name(f"{stem}.city.json"))


def _describe_request_failure(exc: Exception) -> str:
    """One-line description of a failed fetch, naming the host when known."""
    url = getattr(getattr(exc, "request", None), "url", None) or getattr(
        getattr(exc, "response", None), "url", None
    )
    host = urlsplit(url).netloc if url else ""
    subject = f"request to {host} failed" if host else "a network request failed"
    return (
        f"{subject}: {exc}; check your internet connection and retry "
        f"(PDOK / 3DBAG / EP-Online outages are usually brief)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    try:
        data = load_city_config_data(args.profile)
        if "address" not in data:
            parser.error(
                f"profile {args.profile} has no 'address' block; it is not an address profile"
            )
        _apply_cli_overrides(data, args)
        config = validate_city_config(data, source_path=args.profile)
        model = build_city_model(config, refresh=args.refresh)
    except AddressResolutionError as exc:
        print(
            f"error: {exc}; check the address spelling and include a place "
            f"name, for example 'Langegracht 76 Leiden'",
            file=sys.stderr,
        )
        return 1
    except _RequestError as exc:
        print(f"error: {_describe_request_failure(exc)}", file=sys.stderr)
        return 1
    except (CityBuildError, ValueError) as exc:
        # CityBuildError subclasses ValueError; it is named anyway so the
        # config-and-build failure family is visible here. Both message
        # families already say what to fix. Unexpected exception types
        # keep their traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(output_path)
    print(f"Wrote {len(model.xsd.city_object_member)} city objects to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
