# KITModelViewer compatibility

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
