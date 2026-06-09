# One-command, offline reproduction of the per-building CityGML 2.0 + Energy
# ADE 3.0 document in the frozen container environment. Regenerates the GML and
# validates it against the bundled XSDs with networking disabled, so the result
# depends only on the image, not on any live service.
#
# Usage:
#   .\tools\reproduce.ps1            # use the published image
#   .\tools\reproduce.ps1 -Build     # build the image from the Dockerfile first
#   .\tools\reproduce.ps1 -Image other:tag
param(
  [switch]$Build,
  [string]$Image = "ghcr.io/daanschlosser/citygml-energy:1.0.0"
)
$ErrorActionPreference = "Stop"

if ($Build) {
  Write-Host "Building image from Dockerfile ..."
  docker build -t $Image .
  if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE)" }
}

Write-Host "Reproducing the per-building document offline in $Image ..."
docker run --rm --network none $Image sh -c "python examples/create_building.py && python tools/validate_xsd.py generated/NL-single-family-house.gml"
if ($LASTEXITCODE -ne 0) { throw "Reproduction failed (exit $LASTEXITCODE)" }

Write-Host "PASS: regenerated and validated NL-single-family-house.gml with no network access."
