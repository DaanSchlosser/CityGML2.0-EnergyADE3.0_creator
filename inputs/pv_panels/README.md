# PV Panel Polygons

## Source

- Zenodo: https://zenodo.org/records/14860030 (DOI 10.5281/zenodo.14860030)
- RUG page: https://research.rug.nl/en/datasets/annotated-high-resolution-aerial-imagery-of-the-dutch-landscape-f/
- Companion model code (not data): https://git.lwp.rug.nl/cs.projects/solarpanel_segmentation/
- License: CC-BY-4.0 (attribution required).

The Zenodo record contains the polygons as a shapefile
(`annotations/annotations.shp`); I checked it, and re-exported it as a GPKG for further processing.

## How the data was made

Aerial true-ortho imagery was captured in 2023 by the local government of
Emmen (NL). Solar panel polygons were then annotated across 18.55 km^2
of that imagery, using an AI-pipeline. See the Zenodo record and the dataset's accompanying paper for the full methodology.
