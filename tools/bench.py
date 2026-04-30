"""Wall-time micro-benchmark for both GML-generation pipelines.

Runs the per-building (reference) pipeline and the city-scale
smoke-test pipeline, each a configurable number of times, and prints a
compact table of timings (mean / min / stdev). Intended as a quick
regression guard during perf work, not a scientific benchmark.

Usage::

    python tools/bench.py                        # defaults: 3 per-building, 1 city
    python tools/bench.py --building-iters 5      # more per-building runs
    python tools/bench.py --city-iters 0         # skip the city smoke run
    python tools/bench.py --city-input path.json # override city config

The first run of the city pipeline populates its on-disk cache; follow-up
runs hit the cache and reflect the CPU cost only. The per-building
pipeline is fully offline.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from citygml_energy import DEFAULT_INPUT_PATH, DEFAULT_OUTPUT_PATH, generate_gml_file
from citygml_energy.city_builder import build_city_gml_file


def _time_one(callable_) -> float:
    t0 = time.perf_counter()
    callable_()
    return time.perf_counter() - t0


def _report(label: str, samples: list[float]) -> None:
    if not samples:
        print(f"{label:<28}  (skipped)")
        return
    mean = statistics.fmean(samples)
    best = min(samples)
    worst = max(samples)
    stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
    print(
        f"{label:<28}  n={len(samples)}  "
        f"mean={mean:7.3f}s  min={best:7.3f}s  max={worst:7.3f}s  stdev={stdev:6.3f}s"
    )


def bench_building(iters: int, *, input_path: Path, output_path: Path) -> list[float]:
    return [
        _time_one(
            lambda: generate_gml_file(input_path=input_path, output_path=output_path)
        )
        for _ in range(iters)
    ]


def bench_city(iters: int, *, input_path: Path) -> list[float]:
    return [_time_one(lambda: build_city_gml_file(input_path)) for _ in range(iters)]


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--building-iters", type=int, default=3)
    parser.add_argument("--city-iters", type=int, default=1)
    parser.add_argument(
        "--building-input", type=Path, default=DEFAULT_INPUT_PATH,
        help="Per-building JSON input.",
    )
    parser.add_argument(
        "--building-output", type=Path, default=DEFAULT_OUTPUT_PATH,
        help="Output GML path for the per-building run.",
    )
    parser.add_argument(
        "--city-input", type=Path,
        default=REPO_ROOT / "inputs" / "cities" / "emmer-compascuum_small-area.json",
        help="City-scale JSON config (default: inputs/cities/emmer-compascuum_small-area.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_argument_parser().parse_args(argv)
    print(f"Python {sys.version.split()[0]}: CityGML/Energy-ADE bench\n")

    building_samples = bench_building(
        args.building_iters,
        input_path=args.building_input,
        output_path=args.building_output,
    )
    city_samples = bench_city(args.city_iters, input_path=args.city_input)

    print()
    _report("Per-building (reference)", building_samples)
    _report("City smoke (city-scale)", city_samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
