# KITModelViewer compatibility

Get the viewer from KIT IAI (a free, separate download, not bundled here):
https://www.iai.kit.edu/english/1266_4808.php. The KITModelViewer is KIT's
CityGML and IFC viewer, the successor to the FZKViewer.

The KITModelViewer ships with an Energy ADE **2.0** schema
(`EnergyADE-local.xsd`, namespace
`http://www.sig3d.org/citygml/2.0/energy/2.0`). GML files using Energy
ADE **3.0** (`http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0`)
will not display correctly until you replace that schema. The generated
GML is XSD-valid either way; `tools/validate_xsd.py` never consults the
viewer's schemas.

**Symptoms without the fix:** child element names ("ZoneWallSurface 4")
shown instead of building names; solar panels invisible; building tree
garbled.

**Fix** (applied to your own KIT viewer install, not this repo):

1. Copy
   [../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd](../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd)
   to `<KITModelViewer>/GMLSchemata/CityGML_2_0/CityGML/EnergyADE-local.xsd`.
2. In the copied file, replace each online `<import>` `schemaLocation`
   URL with the local relative path. All
   `http://schemas.opengis.net/citygml/.../<name>.xsd` URLs map to
   `<name>.xsd` in the same directory, except:
   - `http://schemas.opengis.net/gml/3.1.1/base/gml.xsd` → `../3.1.1/base/gml.xsd`
3. Restart the KITModelViewer and reload the GML file.

## Provenance and licence of the tracked files

Two files under `KITModelViewer_V7.5.2_Build-3777/` are tracked in this
repository; the viewer install itself is a separate KIT download and is not
included.

- `GMLSchemata/CityGML_2_0/CityGML/EnergyADE-local.xsd` is the CityGML Energy
  ADE 3.0 (beta 8) schema by Dr. Giorgio Agugiaro (3D Geoinformation group, TU
  Delft), the same upstream as [`../Energy_ADE-3.0beta8/`](../Energy_ADE-3.0beta8/),
  under the **Apache License 2.0**. It is a slightly earlier beta 8 vintage
  (header `Last update: 2026-05-06`) renamed to `EnergyADE-local.xsd` for the
  viewer, with the online `<import>` `schemaLocation` URLs rewritten to local
  relative paths (the fix above). It is therefore a modified copy in Apache-2.0
  terms.
- `Data/UOMList.xml` is the KIT ModelViewer's unit-of-measurement configuration
  file (KIT IAI), extended by this project with three Energy ADE unit entries
  (`kWh/a`, `m3/a`, `W/W`); see the in-file comment dated 2026-05-27. It is
  kept here only to document the viewer setup and carries the KIT ModelViewer's
  own terms.
