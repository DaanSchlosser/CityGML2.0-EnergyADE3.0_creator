#!/usr/bin/env sh
# One-command, offline reproduction of the per-building CityGML 2.0 + Energy
# ADE 3.0 document in the frozen container environment. Regenerates the GML
# and validates it against the bundled XSDs with networking disabled, so the
# result depends only on the image, not on any live service.
#
# Usage:
#   tools/reproduce.sh              # use the published image
#   tools/reproduce.sh --build      # build the image from the Dockerfile first
#   IMAGE=other:tag tools/reproduce.sh   # override the image reference
set -eu

IMAGE="${IMAGE:-ghcr.io/daanschlosser/citygml2.0-energyade3.0-beta8-creator:1.1.0}"

if [ "${1:-}" = "--build" ]; then
  echo "Building image from Dockerfile ..."
  docker build -t "$IMAGE" .
fi

echo "Reproducing the per-building document offline in $IMAGE ..."
docker run --rm --network none "$IMAGE" sh -c \
  "python examples/create_building.py && python tools/validate_xsd.py generated/NL-single-family-house.gml"

echo "PASS: regenerated and validated NL-single-family-house.gml with no network access."
