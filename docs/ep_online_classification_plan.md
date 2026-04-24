# EP-online classification fields — integration plan

**Status:** plan, not implementation. Companion document to
[`docs/city_data_sources_overview.md`](city_data_sources_overview.md) §5.

EP-online's Mutatiebestand CSV carries several **building
classification** fields that are currently dropped by the pipeline.
They are worth wiring up because:

1. They carry **genuinely distinct information** that neither BAG nor
   3DBAG provide (the building's role in the energy-calculation
   taxonomy, not just its legal class).
2. They are **Dutch-government open data** (RVO publishes them under
   `EP_ONLINE_API_KEY`), so they fit the pipeline's data-source policy.
3. The target CityGML / Energy ADE slots are **already in the bindings**
   — no schema changes, no ADE authoring.

This plan is kept separate from the main overview so that integrating
it is a discrete, reviewable change rather than a drive-by addition.

## Fields in scope

All observed in the production EP-online CSV (v20260401, 42 columns).
The first example value shown is from a real row.

| CSV column | Example | What it is |
|---|---|---|
| `SoortOpname` | `"Basisopname"`, `"Detailopname"` | Inspection type. "Basis" = quick assessment, "Detail" = full energy survey. Affects the precision of every downstream metric. |
| `Berekeningstype` | `"NTA 8800:2024 (basisopname woningbouw)"` | NTA-8800 variant used for the calculation. **Already wired** (→ `nrg3:EnergyPerformanceCertificate/certificationMethod`). Listed here for completeness; the remaining fields sit alongside it. |
| `Gebouwklasse` | `"W"`, `"U"` | Top-level class: **W**oning (residential) vs **U**tiliteitsgebouw (utility/commercial). |
| `Gebouwtype` | `"Rijwoning hoek"`, `"Kantoorgebouw"`, `"Vrijstaande woning"` | Specific building type within the class, per RVO's NTA-8800 typology. |
| `Gebouwsubtype` | occasional | Further qualifier (e.g. apartment-in-portiekflat). Rarely populated. |
| `Certificaathouder` | `"Energielabel Deskundige"`, `"EP Registratie"` | Who issued the label (certifier name, not an individual). |
| `Status` | `"Bestaand"`, `"Nieuwbouw"`, `"Verbouw"` | Lifecycle state at the time of inspection. |
| `OpBasisVanReferentiegebouw` | `"Ja"`, `"Nee"` | Whether the calculation used a reference-building shortcut (applies to some utility buildings). |
| `SBICode` | occasional, utility only | Economic-activity code (e.g. `"8710"` for nursing homes). |

## Target slots

### A. Fields with a clean native Energy ADE target

**`Gebouwklasse` (W / U) → `nrg3:bdg_type`**

`bdg_type` is a `CodeType` list on Building with its own codespace
[`BuildingTypeValue.xml`](../Energy_ADE-3.0beta8/xsd/codelists/BuildingTypeValue.xml).
The Energy ADE vocabulary uses English terms (`singleFamilyHouse`,
`multiFamilyHouse`, `office`, `commercial`, …), not the Dutch W/U
distinction. Two options:

* **Map the Dutch code to the Energy ADE term via `Gebouwtype`.** A
  small lookup table maps `"Rijwoning hoek"` → `multiFamilyHouse`,
  `"Vrijstaande woning"` → `singleFamilyHouse`, `"Kantoorgebouw"` →
  `office`, etc. Preferred: keeps the output in the Energy ADE
  vocabulary, so a non-Dutch consumer can read it.
* **Emit the raw Dutch value with an RVO codespace.** Document the
  NTA-8800 codelist URL as `codeSpace` and write
  `"Rijwoning hoek"` verbatim. Simpler, but loses the
  interoperability that SIG3D codespaces buy us.

The first option is the correct senior-dev call. Building the lookup
table is straightforward (RVO publishes the canonical list of
`Gebouwtype` values); the pipeline falls back to the second option
(raw value + RVO codespace) for any `Gebouwtype` not in the map, so
no information is ever silently dropped.

**`Status` (`Bestaand` / `Nieuwbouw` / `Verbouw`) → `bldg:class`**

SIG3D's CityGML 2.0 building class codelist
[`_AbstractBuilding_class.xml`](https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_class.xml)
uses numeric codes (1000 = residential, 1010 = commercial, …); it is
**not** a lifecycle enumeration, so `bldg:class` is the wrong slot.

The right target is **`nrg3:bdg_ownership_type`** (no, that's
ownership), or a new generic attribute. Realistically, Status is a
lifecycle signal and there is no dedicated native field. **Emit as
`gen:stringAttribute name="epOnlineStatus"`** with codespace-less
values; document the three-state enum in the code comment.

### B. Fields that become `nrg3:EnergyPerformanceCertificate` metadata

**`SoortOpname` → append to `nrg3:EnergyPerformanceCertificate/certificationMethod`**

The EPC `certificationMethod` is already populated with
`Berekeningstype`. Concatenating `SoortOpname` in front (e.g.
`"Basisopname — NTA 8800:2024 (basisopname woningbouw)"`) keeps the
two values together as a single human-readable string. Downstream
tools that need the structured value can still split on the `—`.

Alternative: add a second `gen:stringAttribute name="epOnlineSoortOpname"`.
Keeps them structured but bloats the output. Concatenation is the
senior-dev call.

**`Certificaathouder` → `nrg3:EnergyPerformanceCertificate/certificationMethod` or a new attribute**

The certificate issuer is a generic party, not a method. Best target
is a generic attribute: `gen:stringAttribute name="epOnlineCertificaathouder"`.
Low-value; consider implementing only if a downstream consumer asks.

**`OpBasisVanReferentiegebouw` → `gen:stringAttribute` on the EPC**

A boolean-string ("Ja"/"Nee"). Convert to `gen:stringAttribute
name="epOnlineReferenceBuildingBased"` with values `"true"`/`"false"`.
Low-frequency; worth emitting only when set.

### C. Fields without a clean target

**`Gebouwtype`, `Gebouwsubtype`** (beyond the lookup mapping described above)

When the lookup table handles them into `nrg3:bdg_type`, both
columns are consumed. When the mapping falls through (e.g. a
Gebouwtype value RVO added after our lookup table was frozen), emit
the raw Dutch term as `gen:stringAttribute name="epOnlineGebouwtype"`
/ `"epOnlineGebouwsubtype"` with the RVO codespace documented in the
implementation comment.

**`SBICode`**

Applies only to utility buildings. Map straight to
`gen:stringAttribute name="sbiCode"`; an RVO-scoped codespace is
overkill for a code that is already an ISO-registered SBI number.

## Implementation phases

The integration naturally splits into three PRs:

1. **Plumbing.** Extend `_COLUMN_ALIASES` + `EnergyLabel` in
   [`eponline.py`](../citygml_energy/city_builder/fetchers/eponline.py)
   with the new optional fields. Add `None` defaults so existing test
   fixtures continue to work. ~20-line change.

2. **Energy-ADE-native mappings.** Ship the `Gebouwtype` → `nrg3:bdg_type`
   lookup (small dict in [`builders.py`](../citygml_energy/city_builder/builders.py)),
   the `certificationMethod` concatenation, and the raw-fallback code path.
   Add focused tests covering each branch of the lookup table.

3. **Generic-attribute fallbacks.** `SoortOpname` /
   `Certificaathouder` / `OpBasisVanReferentiegebouw` / `SBICode` as
   `gen:*Attribute`s. Each is small and independent.

## Non-goals

- **Energy-metric numerics** (`Energiebehoefte`, `PrimaireFossieleEnergie`,
  `BerekendeCO2Emissie`, `GebruiksoppervlakteThermischeZone`, …) are
  a separate PR. Those need decimal-comma CSV parsing, dedicated
  `nrg3:EnergyDemand` / `nrg3:ThermalZone` bindings, and uom
  conventions that this classification-fields plan does not touch.

- **Date / lifecycle fields beyond `validFrom` / `validTo`** —
  already sufficient for the existing EPC emission.

- **SIG3D `bldg:class` codelist mapping** — as discussed above, it
  does not match any EP-online column semantically and should be
  left unset.

## Acceptance criteria

When this plan is implemented:

1. `nrg3:bdg_type` appears on every Building whose VBOs were
   EP-online-matched with a known `Gebouwtype`.
2. Unknown Gebouwtypes round-trip as `gen:stringAttribute` without
   data loss.
3. `certificationMethod` carries both `SoortOpname` and
   `Berekeningstype` in a single string.
4. The generated GML remains XSD-valid (`tools/validate_xsd.py`).
5. `docs/city_data_sources_overview.md` §5 is updated: these fields
   move from the "latent" column into the "used" column.
