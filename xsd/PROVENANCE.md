# Provenance: bundled W3C / OASIS / OGC schemas

The schemas under `xsd/` (and the single file under `tools/schemas/`) are
vendored third-party copies, bundled so the toolkit can validate its output
offline against the exact schemas it targets, without a network round-trip to a
remote schema host. They are **not** authored by this project.

Each file keeps the copyright notice it shipped with. Consult that notice and
the issuing body's terms for the exact licence; the table below is for
orientation, not a substitute for those terms.

| Path | Standard | Copyright / issuer |
|---|---|---|
| `xsd/citygml/2.0/` | CityGML 2.0 | © Open Geospatial Consortium (see the header of each file and http://www.opengeospatial.org/legal/) |
| `xsd/gml/3.1.1/` | GML 3.1.1 | © Open Geospatial Consortium (see the header of each file and http://www.opengeospatial.org/legal/) |
| `xsd/xAL.xsd` | OASIS xAL 2.0 | © 2000 OASIS (see the header of the file and http://www.oasis-open.org) |
| `xsd/xlink/xlink.xsd` | XLink attributes (namespace `http://www.w3.org/1999/xlink`) | as distributed with the OGC GML / CityGML schema set |
| `tools/schemas/xml.xsd` | W3C XML-namespace schema | © W3C (see the dedication notice inside the file) |

## Local changes

These vendored copies are **not** guaranteed byte-for-byte identical to the
upstream distributions. Two deliberate changes were made for offline,
strict-validator compatibility:

1. **`xsd/gml/3.1.1/base/gmlBase.xsd` — `MetaDataPropertyType`.** The bundled
   copy carried a local `<any processContents="lax"/>` in this type's content
   model. Because `nrg3:MetadataType` (Energy ADE) extends this type with
   explicit elements (`author`, `owner`, ...), the lax wildcard makes the
   content model non-deterministic, which strict libxml2 rejects as a Unique
   Particle Attribution violation. It was changed back to the stock GML 3.1.1
   `<element ref="gml:_MetaData"/>`. The change is documented inline at the edit
   site. No instance content relies on the wildcard, so all existing documents
   stay valid.

2. **`tools/schemas/xml.xsd` — added.** The W3C XML-namespace schema (`xml:lang`,
   `xml:space`, `xml:base`, `xml:id`) was vendored from
   https://www.w3.org/2001/xml.xsd so that `xml:lang` resolves during offline
   schema compilation. It lives under `tools/` rather than `xsd/` because `xsd/`
   is staged verbatim for the xsdata binding generation, which resolves the XML
   namespace internally and must not be handed a local `xml.xsd`.

Treat these directories as vendored, possibly-modified copies for validation,
not as an authoritative source of the upstream standards.
