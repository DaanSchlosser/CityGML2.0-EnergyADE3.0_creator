"""Wall-time micro-benchmark for both GML-generation pipelines.

Runs the canonical RenoDAT per-building pipeline and the city-scale
smoke-test pipeline, each a configurable number of times, and prints a
compact table of timings (mean / min / stdev). Intended as a quick
regression guard during perf work, not a scientific benchmark.

Usage::

    python tools/bench.py                        # defaults: 3 RenoDAT, 1 city
    python tools/bench.py --renodat-iters 5      # more RenoDAT runs
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


def bench_renodat(iters: int, *, input_path: Path, output_path: Path) -> list[float]:
    samples: list[float] = []
    for _ in range(iters):
        samples.append(
            _time_one(
                lambda: generate_gml_file(
                    input_path=input_path, output_path=output_path
                )
            )
        )
    return samples


def bench_city(iters: int, *, input_path: Path) -> list[float]:
    samples: list[float] = []
    for _ in range(iters):
        samples.append(_time_one(lambda: build_city_gml_file(input_path)))
    return samples


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renodat-iters", type=int, default=3)
    parser.add_argument("--city-iters", type=int, default=1)
    parser.add_argument(
        "--renodat-input", type=Path, default=DEFAULT_INPUT_PATH,
        help="RenoDAT JSON input.",
    )
    parser.add_argument(
        "--renodat-output", type=Path, default=DEFAULT_OUTPUT_PATH,
        help="Output GML path for the per-building run.",
    )
    parser.add_argument(
        "--city-input", type=Path,
        default=REPO_ROOT / "inputs" / "city_smoke_test.json",
        help="City-scale JSON config (default: inputs/city_smoke_test.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_argument_parser().parse_args(argv)
    print(f"Python {sys.version.split()[0]}: CityGML/Energy-ADE bench\n")

    renodat_samples = bench_renodat(
        args.renodat_iters,
        input_path=args.renodat_input,
        output_path=args.renodat_output,
    )
    city_samples = bench_city(args.city_iters, input_path=args.city_input)

    print()
    _report("RenoDAT (per-building)", renodat_samples)
    _report("City smoke (city-scale)", city_samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
