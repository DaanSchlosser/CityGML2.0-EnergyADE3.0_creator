# syntax=docker/dockerfile:1.7
#
# Reproducible runtime image for the citygml2.0-energyade3.0-beta8-creator
# toolkit (CityGML 2.0 + Energy ADE 3.0 beta 8 generator).
#
# The base image is pinned by digest and the Python environment is resolved
# from uv.lock, so the build is deterministic: the same Dockerfile plus the
# same lockfile reconstruct the same lxml / libxml2 / shapely versions on any
# host. The bundled XSD validation depends on this, because libxml2 strictness
# differs between stock OS builds; freezing it here makes validation behave the
# same everywhere.

# python:3.12-slim, multi-arch index pinned 2026-06-08.
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

# Pinned uv (matches the uv that produced uv.lock: 0.11.19).
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Resolve dependencies from the lockfile only. This layer is cached and only
#    re-runs when pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra city

# 2) Toolkit source, the bundled XSD set (Energy ADE beta 8 + CityGML 2.0 +
#    GML/xlink/xAL), examples and tools, and the small offline per-building
#    inputs. The large city-scale inputs and the FME workspace are excluded via
#    .dockerignore; the city pipeline mounts its data at runtime.
COPY citygml_energy/ ./citygml_energy/
COPY examples/ ./examples/
COPY tools/ ./tools/
COPY xsd/ ./xsd/
COPY schemas/ ./schemas/
COPY Energy_ADE-3.0beta8/xsd/ ./Energy_ADE-3.0beta8/xsd/
COPY inputs/buildings/ ./inputs/buildings/
COPY inputs/stp/ ./inputs/stp/
COPY README.md ./

# 3) Install the project itself into the locked environment.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra city

ENV PATH="/app/.venv/bin:$PATH"

# Default run regenerates the offline per-building document from the baked
# inputs, with no network access. Mount a volume at /app/generated to collect
# the output:
#   docker run --rm -v "$PWD/out:/app/generated" <image>
CMD ["python", "examples/create_building.py"]
