# EP-online to CityGML 2.0 / Energy ADE 3.0 mapping

**Status:** specification (Phase 0 of the comprehensive EP-online integration). Locks every EP-online column to a CityGML / Energy ADE target before any code change. No code is written until this document is reviewed and accepted.

**Scope:** every column shipped by the EP-online Mutatiebestand CSV (production header, 42 columns + 2 metadata rows). Each column gets one verdict, one target, and a defensible rationale grounded in the XSD or in privacy / data-quality considerations.

**Supersedes** the column-classification half of [docs/ep_online_classification_plan.md](ep_online_classification_plan.md) (Gebouwklasse / Gebouwtype / SoortOpname / Status / Certificaathouder / OpBasisVanReferentiegebouw / SBICode). That plan's three-PR implementation breakdown stays valid and is referenced from §11 below; this document is the umbrella spec the breakdown executes against.

## 1. Why this document exists

The city pipeline currently writes only 4 EP-online columns into the GML output: `Energieklasse`, `Registratiedatum`, `GeldigTot`, `Berekeningstype`. Eight further columns are parsed and dropped, and the entire energy-flow domain (thermal-zone area, BENG demand, primary energy, CO2, BENG thresholds) is untouched, even though Energy ADE 3.0 is precisely the schema designed to carry it.

For the RenoDAT thesis question (*is CityGML 2.0 + Energy ADE 3.0 a meaningful starting point for Building Renovation Passports?*) the honest answer requires testing both directions: what the schema can carry, and what it cannot. This document is the test plan for both.

Three constraints govern every verdict:

- **XSD adherence.** Every native target is cited by file:line in [Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd](../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd) and cross-checked against the UML diagrams ([Energy_ADE-3.0beta8/documentation/Energy_ADE_3.0_beta8_UML_diagrams.pdf](../Energy_ADE-3.0beta8/documentation/Energy_ADE_3.0_beta8_UML_diagrams.pdf), pages 8 / 10 / 12 / 19-20). When the XSD says no, the verdict is no.
- **Personal data stays out.** EP-online is openly licensed but contains certifier and inspection metadata that is not strictly load-bearing for energy modelling. Where redaction is the senior call, the verdict is *Drop* with reasoning.
- **Existing pipeline shape preserved.** Address-key joining, multi-VBO buildings, and the existing per-building input format set the aggregation rules (§4). The mapping does not invent a new authoring convention.

## 2. Sources of truth

| Source | Location |
|---|---|
| Production EP-online CSV header (42 columns) | [tests/test_city_eponline.py:101-107](../tests/test_city_eponline.py#L101-L107) for the first 21 columns; the remaining 21 are documented in [docs/city_data_sources_overview.md:165-208](city_data_sources_overview.md#L165-L208). The CSV vintage is `v20260401`. |
| Energy ADE 3.0 beta8 XSD | [Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd](../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd) |
| Energy ADE 3.0 beta8 UML diagrams | [Energy_ADE-3.0beta8/documentation/Energy_ADE_3.0_beta8_UML_diagrams.pdf](../Energy_ADE-3.0beta8/documentation/Energy_ADE_3.0_beta8_UML_diagrams.pdf) |
| CityGML 2.0 generic-attribute element set | [xsd/citygml/2.0/generics.xsd](../xsd/citygml/2.0/generics.xsd) |
| RVO column-meaning reference | NTA 8800 calculation specification + RVO Mutatiebestand documentation (external; cited inline where a meaning is non-obvious from the column name) |

## 3. Target inventory: what the schema offers

A consolidated list of the destination types referenced in the per-column tables in §5. Read this once before the mapping.

| Target | XSD location | Cardinality on parent | What it carries |
|---|---|---|---|
| `nrg3:EnergyPerformanceCertificate` | line 1424 | `[0..*]` natively on BuildingUnit (XSD line 1532, composition slot on `BuildingUnitType`); also `[0..*]` on Building via the `nrg3:energyPerformanceCertificate` substitution element (XSD line 1627). The pipeline uses the BuildingUnit slot because every EP-online cert is per-VBO. | One certificate per record. Already used. Slots: `type`, `label`, optional `value` (`gml:MeasureType`), optional `certificationMethod`; inherited `validFrom` / `validTo`. |
| `nrg3:Energy` (extends `AbstractResource`) | line 2133 | child of any `AbstractCityObject` via the `nrg3:resource` substitution element (line 1366) | One per (energy-type, end-use) pair. Slots: `type` (Code, e.g. `netEnergy` / `primaryEnergy` / `finalEnergy`), `endUse` (Code, e.g. `spaceHeating` / `spaceCooling` / `domesticHotWater`), `energyCarrier`, `source`. Inherited from `AbstractResource` (line 633): `amount` (Measure), `referencePeriod` (Code, e.g. `"year"`), `isAmountNormalized` (boolean, required), `normalizationValue` (Measure, optional), `normalizationParameter` (string, optional, e.g. `"netFloorArea"`), `co2Equivalent` (Measure, optional). |
| `nrg3:QualifiedArea` | line 243 (extends `AbstractQualifiedAttribute` at line 227) | `[0..*]` on `nrg3:AbstractCityObjectSpace.area` | Single measure with `type` (Code), inherited `description` / `source` / `value` (Measure). Used for both the BAG `oppervlakte` and the EP-online `GebruiksoppervlakteThermischeZone` on each BuildingUnit, distinguished by `source`. The repeat-with-different-source pattern from the QualifiedAttribute multi-source memory applies here. |
| `nrg3:bdgType` (extension on `_AbstractBuilding`) | line 1599 | `[0..*]` on Building | `gml:CodeType`. Codelist `BuildingTypeValue.xml` (English Energy ADE vocabulary). |
| `gen:stringAttribute` / `doubleAttribute` / `dateAttribute` / `measureAttribute` | [xsd/citygml/2.0/generics.xsd:76-164](../xsd/citygml/2.0/generics.xsd) | `[0..*]` on any city object | Fallback for fields with no native Energy ADE slot. `measureAttribute` carries `name`, `value`, `uom`. |

Two structural facts that constrain everything below:

1. **`nrg3:Energy` attaches directly to any `AbstractCityObject` via the `nrg3:resource` substitution element** (line 1366: `<element name="resource" substitutionGroup="core:_GenericApplicationPropertyOfCityObject" type="nrg3:AbstractResourcePropertyType">`). Building, BuildingUnit, Zone, Device, all of them host an `nrg3:resource` slot. The existing per-building input parents Energy under a *device* because the device is itself an AbstractCityObject; EP-online metrics are VBO-scoped, so they parent under the BuildingUnit. No xlink, no top-level workaround.
2. **There is no native slot for regulatory thresholds, thermal-comfort metrics, EMG-Forfaitair calculation conventions, or a multi-source `yearOfConstruction`.** Each of these is a deliberately-skipped column or a documented schema gap; see §9.

## 4. Aggregation model: per-VBO vs. per-Pand

EP-online ships one row per certificate, keyed on `BAGVerblijfsobjectID` or address. A Pand (BAG building) may contain multiple VBOs (apartments / commercial units), each with its own certificate. The pipeline already builds one `bldg:Building` per Pand and one `nrg3:BuildingUnit` per VBO. EP-online metrics inherit this split:

| Metric kind | Lives on | Reason |
|---|---|---|
| Identifying / certifying metadata (label, dates, methodology) | `nrg3:EnergyPerformanceCertificate` under each `BuildingUnit` | already in use; per-VBO is correct because each apartment can hold its own certificate. |
| EP-online classification (Gebouwtype) | `nrg3:BuildingUnit` via `gen:stringAttribute name="bdgTypeEPOnline"` (mapped value, see § 5e), plus one `nrg3:Metadata` block on each BuildingUnit attributing the EP-online source for the per-VBO emissions | NTA 8800's Gebouwtype classifies the dwelling unit's typology (e.g. "Rijwoning hoek" = corner unit in a row), which can differ across VBOs in a mixed-use Pand. The native `nrg3:bdgType` element substitutes onto Building only (XSD line 1599) so a per-VBO bdgType is structurally impossible — we use a generic string attribute with the same English-mapped value (Energy ADE `BuildingTypeValue.xml` vocabulary) so consumers can lift it to native bdgType if a future schema revision adds a per-VBO slot. |
| Year of construction (BAG + EP-online `Bouwjaar`) | `bldg:yearOfConstruction` (BAG, existing) **and** `gen:intAttribute name="yearOfConstructionEPOnline"` (EP-online), both on the Building. Two `nrg3:Metadata` blocks on the Building, one per source. | A building is constructed once: year of construction is a Pand-level fact regardless of how many VBOs sit inside. EP-online ships ``Bouwjaar`` per-VBO only because the CSV is row-per-cert; the underlying datum is still per-Pand. Multi-VBO Pands take the most-recently-registered cert's Bouwjaar (mirroring `address_match._label_timestamp`); disagreement between VBOs surfaces as warning-grade data-quality noise but the canonical pick stays single-valued. |
| Thermal-zone area (`GebruiksoppervlakteThermischeZone`) | second `nrg3:QualifiedArea` on the BuildingUnit (alongside the BAG `oppervlakte`), `type="netFloorArea"` and `source="EP-online Mutatiebestand v4 (RVO)"` | The schema lets `BuildingUnit/area` repeat: emitting the EP-online thermal-zone area as a sibling QualifiedArea (same type, distinct source) keeps both numbers queryable without an intermediate `nrg3:Zone` wrapper. Every per-m² energy metric on that BuildingUnit still uses this same area as its `normalizationValue`. |
| Energy-flow metrics (Energiebehoefte, primary, renewable share, CO2) | `nrg3:Energy` attached to the BuildingUnit via the `nrg3:resource` substitution slot | The XSD lets any AbstractCityObject host an Energy resource (line 1366); the BuildingUnit is the right scope because EP-online ships these as per-VBO numbers. The renewable-share gen:measureAttribute also lives on the BuildingUnit (the EPC cannot host generic attributes, see § 5j). |

This mirrors how RVO publishes the data: a certificate is a per-VBO event, and every metric in the row pertains to the VBO's thermal volume. Every EP-online emission lives on the per-VBO BuildingUnit; nothing is forced onto the Building beyond the `yearOfConstructionEPOnline` Pand-level fact (§ 5h). **No Pand-level reduction or tiebreak** for the per-VBO fields: each VBO surfaces its own EP-online classification independently.

## 5. Per-column mapping (the 42 columns)

Verdicts:
- **Native:** direct fit; the column has a one-element XSD slot.
- **Native (derived):** the column needs a small lookup or normalisation before it can fill a native slot.
- **Filter-only:** read for joining or de-duplication; never written.
- **gen:Attribute:** no native slot; emit as a typed `gen:*Attribute` to preserve the value losslessly under a documented `name`. Used sparingly: only where the value is load-bearing for the thesis question and the schema offers no native home.
- **Skip (latent):** fetched but not written. Could be added later either via a `gen:*Attribute` or via a future schema extension; this doc records the potential target and the reason it is not mapped today, so future-me does not re-investigate.
- **Drop:** privacy, redundancy with another source, or out of scope. Not a candidate for later mapping.

### 5a. Address and identifier columns (5)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Postcode` | NL postcode | address-key join only | Filter-only | Already on `core:Address` from BAG; duplicating would create source-attribution ambiguity. |
| `Huisnummer` | House number | address-key join only | Filter-only | Same. |
| `Huisletter` | House letter | address-key join only | Filter-only | Same. |
| `Huisnummertoevoeging` | House number suffix | address-key join only | Filter-only | Same. |
| `BAGVerblijfsobjectID` | BAG VBO id | primary join key | Filter-only | Already on `nrg3:BuildingUnit/identifier` (codeSpace `CS_BAG_VERBLIJFSOBJECT`) from BAG. |

### 5b. Date columns (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Registratiedatum` | Cert registration date | `nrg3:EnergyPerformanceCertificate/validFrom` (XmlDateTime, midnight UTC) | Native | Already wired. Also drives multi-VBO tiebreak (§4). |
| `GeldigTot` | Cert expiry | `nrg3:EnergyPerformanceCertificate/validTo` | Native | Already wired. |
| `Opnamedatum` | Inspection / measurement date | none today; potential target = `gen:dateAttribute` on the EPC `name="epOnlineOpnamedatum"`, OR a future Energy ADE EPC field `inspectionDate` | Skip (latent) | Distinct from `Registratiedatum`: the inspection may be months earlier. No native EPC slot for inspection date in beta8. Retained as the address-match tiebreaker only. |

### 5c. Label (1)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Energieklasse` | Letter grade A+++++ to G | `nrg3:EnergyPerformanceCertificate/label` + `app:Appearance` theme `energyLabel` colour | Native | Already wired. |

### 5d. Methodology and quality flags (5)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Berekeningstype` | NTA 8800 calculation variant string | `nrg3:EnergyPerformanceCertificate/certificationMethod` | Native | Already wired. Verbatim string; no codelist in NTA 8800 maps cleanly. |
| `SoortOpname` | `Basisopname` / `Detailopname` | concatenated into `certificationMethod` (e.g. `"Basisopname / NTA 8800:2024 (basisopname woningbouw)"`) | Native (derived) | Inspection-rigour qualifier. The existing classification plan picks concatenation over a separate field; this doc keeps that call. The separator is `" / "` (no em dashes per repo convention). |
| `Status` | `Bestaand` / `Nieuwbouw` / `Verbouw` | none today; potential target = `gen:stringAttribute name="epOnlineStatus"` on the BuildingUnit, OR a future `bldg:condition`-style lifecycle field | Skip (latent) | Lifecycle signal at certification time. SIG3D's `bldg:class` is a CityGML usage codelist (residential / commercial), not a lifecycle one. No native Energy ADE lifecycle slot. Skipping for now to avoid generic-attribute clutter; revisit if the thesis needs the lifecycle facet. |
| `OpBasisVanReferentiegebouw` | `Ja`/`Nee`: was the cert based on a reference building rather than measured | none today; potential target = `gen:stringAttribute name="epOnlineReferenceBuildingBased"` on the EPC | Skip (latent) | Quality flag. Important for thesis-grade interpretation but not load-bearing for the building-physics output. The information is also encodable as part of `certificationMethod` if needed later (e.g. `"... (reference-building based)"`). |
| `Certificaathouder` | Name of the certifying organisation | none | Drop | Personal-ish data and not load-bearing for energy modelling. The cert *type* (`type="EP-online"`) already attributes the source register; adding the certifier introduces FAIR-data noise without modelling value. |

### 5e. Building classification (4)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Gebouwklasse` | `W` (woning) / `U` (utility) | none today; potential target = `gen:stringAttribute name="epOnlineGebouwklasse"` on Building, OR derivable from the `Gebouwtype` lookup | Skip (latent) | Coarse class. Mostly redundant with `Gebouwtype` (every Gebouwtype belongs unambiguously to one Gebouwklasse). Skipping for now; revisit if a thesis analysis needs the W/U cut without consulting the per-row Gebouwtype. |
| `Gebouwtype` | RVO building-type taxonomy (e.g. `Rijwoning hoek`, `Vrijstaande woning`, `Kantoorgebouw`) | `gen:stringAttribute name="bdgTypeEPOnline"` on each `nrg3:BuildingUnit`, with the English-mapped Energy ADE `BuildingTypeValue.xml` value | Native (derived) | EP-online ships Gebouwtype per-VBO so the emission is per-VBO. Native `nrg3:bdgType` is structurally Building-only (XSD line 1599 substitutes onto `bldg:_GenericApplicationPropertyOfAbstractBuilding`), so a generic string attribute on the BuildingUnit is the schema-permissible per-VBO encoding; the value still uses the English Energy ADE codelist term so consumers can lift it to native bdgType if a future schema revision adds a per-VBO slot. The lookup table lives in [`citygml_energy/city_builder/gebouwtype_lookup.py`](../citygml_energy/city_builder/gebouwtype_lookup.py); the RVO `Gebouwtype` enumeration becomes the single hand-maintained surface. **Unmapped values:** logged + dropped (no generic-attribute fallback for the raw Dutch term per § 5e direction). |
| `Gebouwsubtype` | Further qualifier (e.g. `apartement-portiekflat`) | none today; potential target = `gen:stringAttribute name="epOnlineGebouwsubtype"` on Building | Skip (latent) | Rarely populated. The Energy ADE `BuildingTypeValue` codelist is too coarse to map subtypes natively. Skipping for now; revisit when a downstream consumer asks for the granularity. |
| `SBICode` | Economic-activity code (utility buildings only) | none today; potential target = `gen:stringAttribute name="sbiCode"` on Building | Skip (latent) | Applies only to utility buildings. Skipping for now; the ISO-registered SBI codelist is well-known so a future map-on-demand step can recover it. |

### 5f. BAG cross-references (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `BAGLigplaatsID` | BAG handle for a houseboat mooring | none | Drop | The pipeline only builds Pand-based Buildings; ligplaatsen are out of scope. |
| `BAGStandplaatsID` | BAG handle for a caravan plot | none | Drop | Same reason as ligplaats. |
| `BAGPandIDs` | Comma-separated parent Pand ids | none | Drop | Redundant with `pandidentificatie` from BAG VBO; the join already resolves this. |

### 5g. Project metadata (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Projectnaam` | Free-text project name | none | Drop | Operator-entered free text whose semantics RVO does not document; not load-bearing for energy modelling. |
| `Projectobject` | Free-text project sub-identifier | none | Drop | Same. |
| `Detailaanduiding` | Long-form address supplement | none | Drop | BAG's structured xAL is the authoritative address; EP-online's free-text supplement adds noise without resolving anything BAG cannot. |

### 5h. Building physics / area (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Bouwjaar` | Year of construction | (a) `bldg:yearOfConstruction` (CityGML core, **not** Energy ADE) populated from BAG `bouwjaar`, behaviour unchanged at Building level; (b) `gen:intAttribute name="yearOfConstructionEPOnline"` on the **Building** (Pand level, picked from the most-recently-registered EP-online cert across the Pand's VBOs); (c) two `nrg3:Metadata` blocks on the Building, one attributing BAG for `bldg:yearOfConstruction`, one attributing EP-online for `yearOfConstructionEPOnline`. | Native (BAG) + gen:Attribute with metadata (EP-online, per-Pand) | A building is constructed once: year-of-construction is a Pand-level fact. EP-online ships `Bouwjaar` per-VBO only because the Mutatiebestand CSV is one-row-per-cert — the underlying datum is per-Pand. Multi-VBO Pands take the most-recently-registered cert's Bouwjaar (mirroring `address_match._label_timestamp` so the per-Pand reduction order matches the per-VBO de-duplication order earlier in the pipeline); inter-VBO disagreement on `Bouwjaar` is a data-quality signal that does not cause the model to lie about the construction year. The native multi-source pattern in Energy ADE (`bdgArea` / `bdgHeight` / `bdgVolume` repeating with different `source` strings) is Measure-typed and so cannot be used for an `xs:gYear`; documented as a schema gap in § 9. |
| `GebruiksoppervlakteThermischeZone` | Thermal-zone floor area (m²) | second `nrg3:QualifiedArea` on the BuildingUnit (sibling of the BAG `oppervlakte` entry), `type="netFloorArea"` (codeSpace `AreaTypeValue.xml`), `source="EP-online Mutatiebestand v4 (RVO)"`, uom `m2` | Native | The denominator for every per-m² energy metric below. `BuildingUnit/area` is `[0..*]` so emitting the EP-online value as a sibling of the BAG `oppervlakte` (same type, distinct `source`) is the cleanest schema-permissible encoding — both numbers stay queryable side-by-side without an intermediate `nrg3:Zone` wrapper. The two values typically differ slightly because the EP-online thermal envelope excludes some annex spaces that NEN 2580 `gebruiksoppervlakte` includes. |
| `Compactheid` | Surface-to-volume ratio (m²/m³) | none today; potential target = `gen:doubleAttribute name="compactheid"` on the BuildingUnit, OR a future Energy ADE `Zone/compactness` field | Skip (latent) | No native slot for a scalar building-shape descriptor. Marked here because it is a useful research signal (low compactness correlates with high heating demand) and a candidate for a future Energy ADE extension; not load-bearing for the current pipeline output. |

### 5i. Energy indices: legacy and current (4)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `EnergieIndex` | Pre-NTA-8800 EI metric | none | Drop (legacy) | Pre-2021 metric, mathematically incompatible with NTA 8800 BENG metrics. Including it would confuse longitudinal analysis rather than help it. |
| `EnergieIndexEMGForfaitair` | Same with EMG forfait correction | none | Drop (legacy) | Same as above. |
| `Energiebehoefte` | Net energy demand for heating + cooling (kWh/m²·yr) | `nrg3:Energy` resource attached to BuildingUnit via `<nrg3:resource>`: `type="netEnergy"` (codeSpace `EnergyTypeValue.xml`), `endUse="spaceHeating"` (codeSpace `EnergyEndUseValue.xml`), `operationType="demands"`, `referencePeriod="year"`, `amount` carries the value with uom `kWh/m2/a`, `isAmountNormalized=true`, `normalizationValue` = thermal-zone area in m², `normalizationParameter="netFloorArea"`. | Native (derived) | This is BENG-1. The CSV ships one combined heating+cooling number; the schema can split if RVO publishes a breakdown column in a future vintage. Both the uom (`kWh/m2/a`) and `referencePeriod="year"` carry the annual scope (matching the existing per-building convention in [`inputs/owner_occupier_building.json`](../inputs/owner_occupier_building.json) which pairs `MWh/a` with `referencePeriod="year"`). The `kWh/m2/a` token is introduced by this project; see §7. |
| `Warmtebehoefte` | Net heating-only demand (kWh/m²·yr) | second `nrg3:Energy` resource on the same BuildingUnit: `type="netEnergy"`, `endUse="spaceHeating"`, `description="Warmtebehoefte (NTA 8800 net heating demand)"`, otherwise as above. | Native (derived) | NTA 8800 reports both numbers and they are not redundant: `Warmtebehoefte` is heating-only, `Energiebehoefte` is the BENG-1 sum (heating + cooling). The `endUse` codelist has no "combined" entry, so both Energy resources use `endUse=spaceHeating` and the `description` field on each carries the unambiguous Dutch source name (`"Energiebehoefte (BENG-1, heating + cooling)"` vs. `"Warmtebehoefte (NTA 8800 net heating demand)"`). The difference between the two values is implicitly the cooling component. |

### 5j. Primary energy and renewable share (4)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `PrimaireFossieleEnergie` | Primary fossil energy use (kWh/m²·yr; BENG-2) | `nrg3:Energy` resource on the BuildingUnit: `type="primaryEnergy"`, `endUse="spaceHeating"` (RVO does not break out by end-use here), `operationType="demands"`, `referencePeriod="year"`, `amount` with uom `kWh/m2/a`, `isAmountNormalized=true`, `normalizationValue` = thermal-zone area. | Native | The clean BENG-2 fit. `EnergyTypeValue.xml` includes `primaryEnergy` exactly for this purpose (UML page 20). |
| `PrimaireFossieleEnergieEMGForfaitair` | Same with EMG-Forfaitair correction | none | Drop | Same physical quantity computed under a different convention; the schema has no slot for "the same metric, calculated differently" and the BENG-2 value already carries the canonical answer. The Forfaitair correction is an internal NTA 8800 calculation step, not an independent metric. |
| `AandeelHernieuwbareEnergie` | Renewable-energy share (BENG-3, %) | `gen:measureAttribute` on the **`nrg3:BuildingUnit`** (not the EPC), `name="epOnlineAandeelHernieuwbareEnergie"`, `uom="percent"` | gen:Attribute | Energy ADE 3.0 has no renewable-share slot. `nrg3:EnergyPerformanceCertificateType` extends `AbstractFeatureWithLifeSpanType` directly (not via CityObject), so the EPC cannot host `gen:*Attribute` children — the BuildingUnit (which descends from CityObject) is the closest container at the same per-VBO scope. Emit verbatim under a measure attribute; the user has flagged this as needed for downstream analysis. |
| `AandeelHernieuwbareEnergieEMGForfaitair` | Same with EMG-Forfaitair | none | Drop | Same Forfaitair-convention reasoning as `PrimaireFossieleEnergieEMGForfaitair`. |

### 5k. Calculated emissions and use (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `BerekendeCO2Emissie` | Calculated CO2 emission (kg/m²·yr) | `nrg3:Energy/co2Equivalent` on the `PrimaireFossieleEnergie` Energy resource (the BENG-2 one). `value` in kg per m² per year, `uom="kg/m2/a"`. The `kg/m2/a` token is introduced by this project for NL-convention CO₂ emissions; see §7 for FZK UOMList relationship. | Native | `co2Equivalent` is a property of `AbstractResource` (line 646), not a standalone feature. Attaching it to BENG-2 (the primary-energy resource) is the conceptually correct place: emissions are downstream of primary fossil energy. |
| `BerekendeEnergieverbruik` | Calculated total annual energy use (kWh/m²·yr) | `nrg3:Energy` resource on BuildingUnit: `type="finalEnergy"`, `endUse="spaceHeating"`, `operationType="demands"`, `referencePeriod="year"`, `amount` uom `kWh/m2/a`, `isAmountNormalized=true`, `normalizationValue` = thermal-zone area. | Native | Distinct from `Energiebehoefte` (net) and `PrimaireFossieleEnergie` (primary): this is the *delivered* final-energy figure. `EnergyTypeValue` includes `finalEnergy`; one more sibling Energy resource. |
| `Temperatuuroverschrijding` | Summer overheating hours (BENG-4) | none today; potential target = `gen:measureAttribute` on the BuildingUnit with uom `h`, OR a future Energy ADE `Zone/comfortIndicator` field | Skip (latent) | No thermal-comfort indicator slot in `AbstractZone` even though the type carries `isCooled` / `isMechanicallyVentilated`. Skipping for now; revisit if thermal-comfort analysis enters the thesis scope. |

### 5l. BENG / Bouwbesluit thresholds (4)

All four thresholds skipped. Reasoning: Energy ADE 3.0 has no native slot for regulatory requirements (the schema models actual values only); committing to a `gen:measureAttribute` encoding for every threshold is generic-attribute clutter for a category of data the thesis does not currently analyse against. Skipping is reversible: each threshold has a clean potential target listed below.

| Column | Meaning | Potential target if revisited | Verdict |
|---|---|---|---|
| `EisEnergiebehoefte` | BENG-1 threshold (kWh/m²·yr) | `gen:measureAttribute name="epOnlineEisEnergiebehoefte"` uom `kWh/m2/a`, OR a future Energy ADE `Resource/threshold` field | Skip (latent) |
| `EisPrimaireFossieleEnergie` | BENG-2 threshold (kWh/m²·yr) | `gen:measureAttribute name="epOnlineEisPrimaireFossieleEnergie"` uom `kWh/m2/a` | Skip (latent) |
| `EisAandeelHernieuwbareEnergie` | BENG-3 threshold (%) | `gen:measureAttribute name="epOnlineEisAandeelHernieuwbareEnergie"` uom `percent` | Skip (latent) |
| `EisTemperatuuroverschrijding` | BENG-4 threshold (h) | `gen:measureAttribute name="epOnlineEisTemperatuuroverschrijding"` uom `h` | Skip (latent) |

## 6. Worked example: one VBO's full XML output

After P1-P3 ship, a residential VBO with a 2024 Detailopname certificate looks like this (XML excerpt; non-load-bearing wrappers elided). Every field shown here is *written*; nothing in this example is a Skip-(latent) or Drop column from §5.

Structural distribution to keep in mind while reading:

- `bldg:yearOfConstruction` (BAG) and `gen:intAttribute name="yearOfConstructionEPOnline"` (EP-online) both live at Building level: a building is constructed once, so year-of-construction is fundamentally a Pand-level fact regardless of which register reports it. Two `nrg3:Metadata` blocks on the Building, one per source, document each value.
- The thermal-zone area (`GebruiksoppervlakteThermischeZone`) rides as a second `nrg3:QualifiedArea` on each BuildingUnit, alongside the BAG `oppervlakte` entry. `BuildingUnit/area` is `[0..*]` so two same-type entries with distinct `source` strings is the documented multi-source pattern (no `nrg3:Zone` wrapper needed).
- The remaining EP-online emissions (`bdgTypeEPOnline`, `epOnlineAandeelHernieuwbareEnergie`, the four `nrg3:Energy` resources) live on each `nrg3:BuildingUnit` because their underlying physical reality is per-VBO. The native `nrg3:bdgType` element substitutes onto Building only, so the per-VBO version rides as `gen:stringAttribute name="bdgTypeEPOnline"` with the same English-mapped value.
- One `nrg3:Metadata` block per BuildingUnit attributes EP-online for the per-VBO emissions on that unit.

```xml
<bldg:Building gml:id="pand_0114100000206140">
  <gml:name>Hoofdkanaal WZ 73</gml:name>

  <!-- Year-of-construction is per-Pand: BAG and EP-online both report a single
       value for the whole building. Two Metadata blocks document each source. -->
  <nrg3:Metadata>
    <nrg3:source>BAG bag:pand.bouwjaar (PDOK WFS v2.0)</nrg3:source>
    <nrg3:qualityDescription>Source for bldg:yearOfConstruction on this Pand.</nrg3:qualityDescription>
  </nrg3:Metadata>
  <nrg3:Metadata>
    <nrg3:source>EP-online Mutatiebestand v4 (RVO)</nrg3:source>
    <nrg3:qualityDescription>Source for gen:intAttribute name="yearOfConstructionEPOnline" on this Pand. Picked from the most-recently-registered EP-online certificate across this Pand's VBOs.</nrg3:qualityDescription>
  </nrg3:Metadata>
  <bldg:yearOfConstruction>1955</bldg:yearOfConstruction>
  <gen:intAttribute name="yearOfConstructionEPOnline">
    <gen:value>1956</gen:value>
  </gen:intAttribute>

  <nrg3:buildingUnit>
    <nrg3:BuildingUnit gml:id="bu_0114010000274521">
      <bldg:address>...xAL...</bldg:address>

      <!-- Two QualifiedArea entries: same type ("netFloorArea"), distinct source.
           BAG oppervlakte and the EP-online thermal-zone area sit side-by-side so
           consumers can compare them directly. -->
      <nrg3:area>
        <nrg3:QualifiedArea>
          <nrg3:type codeSpace="...AreaTypeValue.xml">netFloorArea</nrg3:type>
          <nrg3:source>BAG bag:verblijfsobject.oppervlakte (PDOK WFS v2.0)</nrg3:source>
          <nrg3:value uom="m2">115.0</nrg3:value>
        </nrg3:QualifiedArea>
      </nrg3:area>
      <nrg3:area>
        <nrg3:QualifiedArea>
          <nrg3:type codeSpace="...AreaTypeValue.xml">netFloorArea</nrg3:type>
          <nrg3:source>EP-online Mutatiebestand v4 (RVO)</nrg3:source>
          <nrg3:value uom="m2">112.5</nrg3:value>
        </nrg3:QualifiedArea>
      </nrg3:area>

      <nrg3:energyPerformanceCertificate>
        <nrg3:EnergyPerformanceCertificate>
          <nrg3:type codeSpace="...">EP-online</nrg3:type>
          <nrg3:label>A++</nrg3:label>
          <nrg3:certificationMethod>Detailopname / NTA 8800:2024 (detailopname woningbouw)</nrg3:certificationMethod>
          <core:validFrom>2024-05-14T00:00:00</core:validFrom>
          <core:validTo>2034-05-13T00:00:00</core:validTo>
        </nrg3:EnergyPerformanceCertificate>
      </nrg3:energyPerformanceCertificate>

      <!-- Per-VBO EP-online classification + renewable share. Year-of-construction
           is NOT here (it lives on the Building because Bouwjaar is a Pand-level
           fact). The bdgTypeEPOnline value is the English-mapped Energy ADE
           BuildingTypeValue term; the native nrg3:bdgType element substitutes
           onto Building only, so the per-VBO version uses gen:stringAttribute. -->
      <gen:stringAttribute name="bdgTypeEPOnline">
        <gen:value>singleFamilyHouse</gen:value>
      </gen:stringAttribute>
      <gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie">
        <gen:value uom="percent">42</gen:value>
      </gen:measureAttribute>

      <!-- One Metadata block attributing the EP-online source for the per-VBO
           emissions on this BuildingUnit. -->
      <nrg3:Metadata>
        <nrg3:source>EP-online Mutatiebestand v4 (RVO)</nrg3:source>
        <nrg3:qualityDescription>Source for the EP-online-derived per-VBO emissions on this BuildingUnit (bdgTypeEPOnline, epOnlineAandeelHernieuwbareEnergie, and the nrg3:Energy resources hosted via nrg3:resource). Year of construction (yearOfConstructionEPOnline) is at the Building level: a Pand is constructed once.</nrg3:qualityDescription>
      </nrg3:Metadata>

      <!-- The four nrg3:Energy resources attached directly via <nrg3:resource>
           (substitution on core:_GenericApplicationPropertyOfCityObject, XSD
           line 1366). No xlink, no top-level cityObjectMember workaround. -->

      <nrg3:resource>
        <nrg3:Energy gml:id="energy_bu_0114010000274521_energiebehoefte">
          <gml:description>Energiebehoefte (BENG-1, heating + cooling)</gml:description>
          <nrg3:operationType codeSpace="...ResourceOperationTypeValue.xml">demands</nrg3:operationType>
          <nrg3:referencePeriod codeSpace="...ReferencePeriodValue.xml">year</nrg3:referencePeriod>
          <nrg3:amount uom="kWh/m2/a">28.5</nrg3:amount>
          <nrg3:isAmountNormalized>true</nrg3:isAmountNormalized>
          <nrg3:normalizationValue uom="m2">112.5</nrg3:normalizationValue>
          <nrg3:normalizationParameter>netFloorArea</nrg3:normalizationParameter>
          <nrg3:type codeSpace="...EnergyTypeValue.xml">netEnergy</nrg3:type>
          <nrg3:endUse codeSpace="...EnergyEndUseValue.xml">spaceHeating</nrg3:endUse>
        </nrg3:Energy>
      </nrg3:resource>

      <nrg3:resource>
        <nrg3:Energy>
          <gml:description>Warmtebehoefte (NTA 8800 net heating demand)</gml:description>
          <nrg3:type codeSpace="...">netEnergy</nrg3:type>
          <nrg3:amount uom="kWh/m2/a">25.1</nrg3:amount>
          <!-- ...same envelope as the BENG-1 resource above... -->
        </nrg3:Energy>
      </nrg3:resource>

      <nrg3:resource>
        <nrg3:Energy>
          <gml:description>PrimaireFossieleEnergie (BENG-2)</gml:description>
          <nrg3:type codeSpace="...">primaryEnergy</nrg3:type>
          <nrg3:amount uom="kWh/m2/a">63.0</nrg3:amount>
          <nrg3:co2Equivalent uom="kg/m2/a">14.7</nrg3:co2Equivalent>
          <!-- co2Equivalent rides on the BENG-2 (primary-energy) resource only. -->
        </nrg3:Energy>
      </nrg3:resource>

      <nrg3:resource>
        <nrg3:Energy>
          <gml:description>BerekendeEnergieverbruik (delivered final energy)</gml:description>
          <nrg3:type codeSpace="...">finalEnergy</nrg3:type>
          <nrg3:amount uom="kWh/m2/a">35.4</nrg3:amount>
        </nrg3:Energy>
      </nrg3:resource>
    </nrg3:BuildingUnit>
  </nrg3:buildingUnit>
</bldg:Building>
```

Why the EP-online thermal-zone area sits as a second QualifiedArea on the BuildingUnit rather than inside an `nrg3:Zone` wrapper: `BuildingUnit/area` is `[0..*]` and the QualifiedAttribute multi-source pattern (different `source` strings, same `type`) is the schema's documented way to keep two readings of the same quantity queryable side-by-side. The earlier draft of this mapping wrapped the EP-online area in an `nrg3:Zone` (Building-level, xlink to BuildingUnit) so the Zone could carry `UsageZoneTypeValue="occupied"` plus the area, but the Zone added no information beyond the area itself — the BuildingUnit already exists, every per-m² Energy resource on it already normalises against this same area, and the xlink hop back from Zone to BuildingUnit only existed to recover the per-VBO scope that the Zone wrapper had blurred. Dropping the wrapper keeps the schema-permissible encoding and removes the round-trip.

## 7. uom convention table

uom tokens follow Dutch (NTA 8800 / EP-online) convention. The FZKViewer UOMList ([KITModelViewer_V7.5_Build-3636/Data/UOMList.xml](../KITModelViewer_V7.5_Build-3636/Data/UOMList.xml)) is consulted as **reference** but is known to be incomplete for the NL energy-domain values; the user is in contact with the FZKViewer developers, and the tokens introduced by this integration will be communicated upstream so that subsequent UOMList revisions can pick them up. The pipeline currently emits only three tokens (`m`, `m2`, `deg`); this integration adds:

| Quantity | uom token chosen | FZK UOMList status | Notes |
|---|---|---|---|
| Energy per area, annual basis (BENG-1 / BENG-2 / final-energy / Warmtebehoefte) | `kWh/m2/a` | New for this project. UOMList has `kWh/m2` (line 143, no per-annum) and `MWh/a` (line 35, no per-area); the per-area-per-annum combination is unlisted. | Matches NTA 8800 convention exactly. Mirrors the `MWh/a` / `kWh/m2` pattern already in UOMList, just composed. The `referencePeriod="year"` field on the parent Energy resource is also set, mirroring the convention in [`inputs/owner_occupier_building.json`](../inputs/owner_occupier_building.json) line 169-170 (which pairs `MWh/a` with `referencePeriod="year"`); both belt and braces. |
| Renewable-energy share (%) | `percent` | ✓ Exact match: `PERCENTAGE` id=`percent` (line 182). **Do not use `%` literally**: it is a sign-glyph on UOMList, not an id. | |
| Floor area (m²) | `m2` | ✓ Exact match: `SQUARE_METRE` id=`m2` (line 63) | Already in use. |
| CO₂ emission per area, annual basis | `kg/m2/a` | New for this project. UOMList has `kg`, `g/m3`, `kg/m3`; per-area-mass and per-area-mass-per-annum are unlisted. | Matches NTA 8800 convention for emission reporting. To be communicated to the FZKViewer developers as a candidate UOMList addition. |

The two new tokens (`kWh/m2/a`, `kg/m2/a`) are documented here so a future contributor knows they are deliberate NL-convention extensions, not typos. They are also flagged in §9 as items the FZKViewer team has been asked to consider for the next UOMList revision.

## 8. Privacy and data-quality caveats

| Concern | Decision | Reasoning |
|---|---|---|
| `Certificaathouder` (certifier name) | Drop | Names of certifying inspectors / firms. While EP-online's open licence permits redistribution, the certifier name is not a building-physics signal and adds attack surface for unintended deanonymisation when joined with other registers. |
| `OpBasisVanReferentiegebouw=Ja` | Skip (latent) for now; flag the lossy-fidelity implication in this document so a future revisit knows the stakes | A `Ja` value indicates the cert was computed from a reference-building shortcut, not from in-building measurement. Roughly 20-30% of utility certs carry this flag and their numbers are statistically softer. Currently not emitted because the thesis is not analysing per-cert fidelity; if that changes, `gen:stringAttribute name="epOnlineReferenceBuildingBased"` is the documented fallback (§5d). |
| `Status` lifecycle (`Bestaand` / `Nieuwbouw` / `Verbouw`) | Skip (latent) | A `Verbouw` cert was issued mid-renovation and may not reflect a stable thermal envelope. Currently not filtered or emitted; a downstream consumer can re-derive it from the EP-online CSV if needed. |
| EP-online's per-VBO area disagrees with BAG's `oppervlakte` | Both are emitted; QualifiedArea `source` strings disambiguate | Already the precedent for BAG (see existing pattern in `builders.py:_build_building_unit`). Two same-typed but differently-sourced QualifiedAreas are a feature, not a conflict. |
| BAG `bouwjaar` disagrees with EP-online `Bouwjaar` | Both are emitted as twin `gen:intAttribute` (§5h) | Same explicit-source pattern: a downstream consumer can compare per-Pand and quantify how often the two sources disagree. |

## 9. Rolled-up gap analysis (the "what cannot be modelled" answer)

Honest accounting of where Energy ADE 3.0 beta8 falls short of EP-online's data model. Listed in priority for the BRP / RenoDAT thesis (gaps that affect *load-bearing* energy fields first, then quality / metadata gaps):

1. **No native renewable-share slot.** `AandeelHernieuwbareEnergie` (BENG-3) has no home; the workaround in this mapping is `gen:measureAttribute`. A future Energy ADE revision could add `Building/renewableEnergyFraction` (or treat it as derived from per-source Energy resources, which would require richer per-source breakdowns than EP-online ships).
2. **`EnergyEndUseValue.xml` has no all-uses / total / unspecified entry.** All four EP-online `nrg3:Energy` resources land on `endUse="spaceHeating"`, but two of them — BENG-2 (`PrimaireFossieleEnergie`) and the delivered total (`BerekendeEnergieverbruik`) — are whole-building totals across every end-use, not heating-only. The Dutch source name in each Energy's `description` field disambiguates, but a downstream consumer that filters by `endUse` (the natural Energy ADE query path) sees four heating numbers and misses that two of them are whole-building totals. Same shape applies to `Energiebehoefte` vs `Warmtebehoefte` (the heating + cooling sum and the heating-only number both ride `endUse="spaceHeating"`). A future Energy ADE revision adding `total` / `unspecified` to `EnergyEndUseValue.xml` would close this; until then, consumers must read `description` alongside `endUse`. This is the most thesis-relevant of the gaps because it directly limits machine-readability of the BENG metrics — exactly the BRP question the schema is being tested on.
3. **No native multi-source `yearOfConstruction` in CityGML core.** `bldg:yearOfConstruction` is a CityGML 2.0 core field (not Energy ADE), single-valued (`xs:gYear`). Energy ADE's QualifiedAttribute multi-source pattern (`bdgArea` / `bdgHeight` / `bdgVolume`) is Measure-typed and so cannot be used for a year. Workaround in this mapping: keep `bldg:yearOfConstruction` BAG-authoritative and ride the EP-online value as `gen:intAttribute name="yearOfConstructionEPOnline"` (also at Building level, because year-of-construction is structurally a Pand-level fact), with two `nrg3:Metadata` blocks on the Building documenting each source. Multi-VBO Pands take the most-recently-registered cert's Bouwjaar so the Pand-level value stays single-valued. The cleanest schema-level fix would be a CityGML core extension allowing repeated `yearOfConstruction` values with source attribution, which is out of scope for Energy ADE alone.
4. **FZKViewer UOMList is incomplete for the NL energy domain.** `kWh/m2/a` and `kg/m2/a` are introduced by this project to match NTA 8800 convention. The user is in contact with the FZKViewer developers about adding these tokens upstream; they are listed in §7 so a future UOMList revision can pick them up.
5. **No standalone Emission feature.** Multi-gas GHG accounting (CH₄, N₂O, refrigerants) is impossible; we only get the CO₂-equivalent value on each Energy resource. Acceptable for EP-online (which only ships CO₂-eq) but not for richer LCA data.
6. **`gebruiksdoel` (BAG) and `Gebouwtype` (EP-online) coexist on the same Building.** Both fill `bldg:function`-adjacent slots. The mapping puts BAG on `bldg:function` and EP-online on `nrg3:bdgType` (different codeSpace) so they never collide; if downstream consumers want one canonical, they pick by codeSpace.
7. **No native slots for the deliberately-skipped fields** (Status, OpBasisVanReferentiegebouw, Opnamedatum, Compactheid, Temperatuuroverschrijding, BENG `Eis*` thresholds, Gebouwklasse, Gebouwsubtype, SBICode). Each of these is a candidate for either a `gen:*Attribute` workaround or a future Energy ADE extension; this document records the potential target alongside the verdict, so a later thesis chapter can quote the schema-extension proposals directly from §5.

Each of these is a thesis-relevant finding: they identify where the schema would benefit from extension if the BRP work proceeds beyond the standardisation status quo.

## 10. Resolved: Energy attachment via `nrg3:resource` substitution

Settled (was an open question in the original v0 of this doc): `nrg3:Energy` parents directly under the BuildingUnit via the `nrg3:resource` substitution element at line 1366. No xlink, no top-level `cityObjectMember` workaround, no schema extension.

The XSD evidence:

```xml
<element name="resource"
         substitutionGroup="core:_GenericApplicationPropertyOfCityObject"
         type="nrg3:AbstractResourcePropertyType">
```

`core:_GenericApplicationPropertyOfCityObject` is the substitution group for ADE extensions to `core:AbstractCityObject`. Every CityGML feature class that descends from `AbstractCityObject` (Building, BuildingUnit, Zone, Device, etc.) hosts an `nrg3:resource` slot. That is exactly how the existing per-building input attaches `nrg3:Energy` to a `nrg3:PhotovoltaicCollector` or `nrg3:EVChargingStation`: the device is itself an AbstractCityObject. EP-online metrics are per-VBO (per-BuildingUnit) and so attach the same way, just to a different AbstractCityObject.

**Implementation note:** the existing JSON input loader already handles this via the `parent` field + `attach_child` mechanism. EP-online Energy resources can be authored with `"parent": "<bu_*>"` and the loader resolves the right field (`nrg3:resource` accepts `nrg3:AbstractResourcePropertyType` which wraps `nrg3:Energy`). The city pipeline does not author JSON, but can call the same `attach_child` helper directly from `builders.py`.

## 11. Implementation phases (post-Phase-0)

The integration splits into four PRs after this doc is accepted:

| PR | Scope | Lines of change (rough) | Tests |
|---|---|---|---|
| **P1: Plumbing** | Surface every column on the `EnergyLabel` dataclass + parser. Extend `_COLUMN_ALIASES`. No GML output change. | ~80 in `eponline.py`; column inventory in tests | `test_city_eponline.py`: full-row parse + per-column null-tolerance |
| **P2a: Classification fields** | `gen:stringAttribute name="bdgTypeEPOnline"` on each BuildingUnit (Dutch -> English lookup, § 5e); `certificationMethod` concat for `SoortOpname` (§ 5d). Unmapped Gebouwtype values log a WARNING and are dropped. **No** generic-attribute fallbacks for Gebouwklasse / Gebouwsubtype / SBICode / Status / OpBasisVan / Opnamedatum (all Skip-latent). | ~150 in `builders.py` + lookup module | `test_city_builders.py`: per-branch lookup, unmapped-Gebouwtype failure path, certificationMethod concat |
| **P2b: Energy-flow domain** | Per-VBO thermal-zone area as a second `nrg3:QualifiedArea` on each BuildingUnit (sibling of the BAG `oppervlakte` entry, distinct `source`); four `nrg3:Energy` resources on each BuildingUnit via `nrg3:resource` (Energiebehoefte, Warmtebehoefte, PrimaireFossieleEnergie + co2Equivalent, BerekendeEnergieverbruik); `gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie"` on each BuildingUnit; `gen:intAttribute name="yearOfConstructionEPOnline"` on the Building (Pand-level reduction; § 5h); two `nrg3:Metadata` blocks on the Building (BAG + EP-online for year-of-construction); one `nrg3:Metadata` block per BuildingUnit (EP-online source for per-VBO emissions). Decimal-comma parsing for the numeric CSV columns. **No** BENG thresholds, **no** Forfaitair variants, **no** Compactheid / Temperatuuroverschrijding / Status / OpBasisVan, **no** Gebouwklasse / Gebouwsubtype / SBICode (all Skip-latent per § 5). | ~300 in `builders.py` + `eponline.py` numeric coercion + new `energy_resources.py` helper | New `test_city_energy_resources.py`; XSD validation of full Emmer-Compascuum run |
| **P3: Update reference docs** | Move every "Latent" row in [city_data_sources_overview.md](city_data_sources_overview.md) §6 into the "Used" column. Update `tests/test_city_pipeline.py` fixtures. Refresh [README.md](../README.md) §12.3 ("output shape per building") with the new content. | ~50 across docs | Existing pipeline-invariants suite covers determinism; no new test infra |

## 12. Acceptance criteria for Phase 0

1. Every one of the 42 EP-online columns has exactly one verdict in §5.
2. Every "Native" verdict cites an XSD line number for its target.
3. Every "gen:Attribute" verdict states *why* a native fit does not exist and is justified by an explicit reason for not skipping it (load-bearing for thesis analysis or explicit user request).
4. Every "Skip (latent)" verdict names a potential future target so the field is recoverable without re-investigation.
5. The `nrg3:Energy` parent attachment is resolved (§10) before Phase 2 begins.
6. Every introduced uom token is cross-checked against the FZKViewer UOMList; unmatched NL-convention tokens (`kWh/m2/a`, `kg/m2/a`) are documented in §7 with rationale and flagged for upstream communication to the FZKViewer developers.
7. The thesis-relevant gap analysis (§9) is preserved as a standalone section so a reader of the BRP report can extract the schema-extension findings without reading the full mapping table.
