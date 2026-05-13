"""Fetch and normalise EP-online energy labels (bulk ``Mutatiebestand`` CSV).

EP-online (RVO) publishes the complete register of Dutch energy labels
as a ZIP-compressed CSV (~1 GB uncompressed, ~5 M rows). The download
URL rotates per vintage, so step 1 is a GET to the ``DownloadInfo``
endpoint (which returns the real download URL plus metadata), step 2
downloads the ZIP and unpacks the single CSV inside. Access requires an
API token sent via the ``Authorization`` header.

The CSV uses Dutch conventions: semicolon separators, YYYYMMDD dates,
Dutch decimal commas, Dutch column names. We normalise into
:class:`EnergyLabel` records with snake_case fields that downstream code
can join on.

**Filter-on-parse is the fast path.** The city pipeline only cares about
labels that match the VBOs inside a BBOX (usually a few hundred rows out
of 5 M). :func:`fetch_energy_labels` accepts ``wanted_ids`` and
``wanted_keys`` sets and :func:`parse_csv` drops every non-matching row
before materialising a dataclass: no 5 M-row list, no multi-GB pickle,
no O(N) post-scan. Passing no filter falls back to the full parse,
which is what tests and scripts that want the whole register rely on.

:class:`EnergyLabel` carries the columns that end up in the CityGML
output, both directly (``energieklasse`` → EPC label, dates → validFrom /
validTo, ``berekeningstype`` / ``soort_opname`` → ``certificationMethod``,
``gebouwtype`` → ``nrg3:bdgType`` on Building (Dutch verbatim, RVO
codespace), ``gebouwsubtype`` → ``gen:stringAttribute
name="bdgSubtypeEPOnline"`` on each BuildingUnit, the energy-flow
numerics → ``nrg3:Energy`` resources) and indirectly (``opnamedatum``
is the address-match tiebreaker). Skip-(latent) columns from
[`docs/mapping_city.md`](../../../docs/mapping_city.md) § 6.5
are deliberately not surfaced; adding them later is a one-line change to
:data:`_COLUMN_ALIASES` and the dataclass.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from ..address_key import (
    AddressKey,
    normalise_letter,
    normalise_postcode,
)
from ..address_key import (
    address_key as build_address_key,
)
from ..http import CachedSession

# Calculation-regime classification of the ``Berekeningstype`` column.
# Determines the unit and field-availability of the energy-flow numerics
# downstream; see :meth:`EnergyLabel.calculation_regime` and § 6.3 of
# docs/mapping_city.md for the empirical evidence and the
# per-regime emission rules.
CalculationRegime = Literal["nta8800", "legacy_total", "unknown"]

DOWNLOAD_INFO_URL = (
    "https://public.ep-online.nl/api/v5/Mutatiebestand/DownloadInfo?fileType=csv&xmlVersion=4"
)


_HUISNUMMER_RE = re.compile(
    r"^\s*(\d{1,5})\s*[- ]*\s*([A-Za-z])?\s*[- ]*\s*([A-Za-z0-9]{1,4})?\s*$"
)

# Required CSV columns. ``DictReader`` was ~2x slower than a positional
# ``csv.reader`` on the 5 M-row file: we pay the column-name lookup once
# per header and then index every row by integer. Aliases accommodate
# EP-online version drift.
#
# Logical names group into three buckets:
#
# * Address keys + VBO id used for joining BAG ↔ EP-online.
# * Identifying / certifying metadata that lands on
#   ``nrg3:EnergyPerformanceCertificate`` directly (``energieklasse``,
#   the three dates, ``berekeningstype``, ``soort_opname``).
# * Building-physics / energy-flow numerics that drive the
#   ``nrg3:Energy`` resources built in
#   :mod:`citygml_energy.city_builder.energy_resources`, plus the
#   per-VBO thermal-zone ``nrg3:QualifiedArea`` they normalise against.
#   NL convention is semicolon separators with comma decimal markers
#   (``28,5`` not ``28.5``); :func:`parse_decimal` normalises that.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "postcode": ("Postcode",),
    "huisnummer": ("Huisnummer",),
    "huisletter": ("Huisletter",),
    "toevoeging": ("Huisnummertoevoeging",),
    "bag_vbo_id": ("BAGVerblijfsobjectID",),
    "energieklasse": ("Energieklasse",),
    "registratiedatum": ("Registratiedatum",),
    "opnamedatum": ("Opnamedatum",),
    "geldig_tot": ("GeldigTot",),
    # Berekeningstype = the NTA-8800 variant used for the EPC calculation,
    # e.g. "NTA 8800:2024 (detailopname utiliteitsbouw)". Carried through to
    # ``nrg3:EnergyPerformanceCertificate/certificationMethod`` so the
    # provenance of the label is legible to downstream tools.
    "berekeningstype": ("Berekeningstype",),
    # SoortOpname = the inspection rigour ("Basisopname" / "Detailopname").
    # Concatenated into ``certificationMethod`` alongside Berekeningstype.
    "soort_opname": ("SoortOpname",),
    # Gebouwtype = RVO NTA-8800 building-type taxonomy (e.g. "Rijwoning hoek").
    # Carried verbatim into ``nrg3:bdgType`` on the Building, with
    # ``@codeSpace`` pointing at the EP-online publication that defines the
    # vocabulary (see :data:`citygml_energy.namespaces.CS_RVO_GEBOUWTYPE`).
    # No translation: Energy ADE 3.0's ``BuildingTypeValue.xml`` codelist is
    # too coarse for the NTA-8800 typology and the round-trip through it
    # would silently merge "Hoekwoning" / "Tussenwoning" / "2-onder-1-kap"
    # under a single ``singleFamilyHouse`` member.
    "gebouwtype": ("Gebouwtype",),
    # Gebouwsubtype = RVO secondary qualifier (e.g. "appartement-portiekflat",
    # "rijwoning-tussen"). Per-VBO because two VBOs in one Pand can carry
    # different subtypes (mixed-use, partial conversion). Lands as
    # ``gen:stringAttribute name="bdgSubtypeEPOnline"`` on each BuildingUnit:
    # there is no native ``nrg3:bdgSubtype`` element in EnergyADE 3.0, and
    # the value is a Dutch RVO term so the EP-online suffix flags the
    # vocabulary source.
    "gebouwsubtype": ("Gebouwsubtype",),
    # Bouwjaar = EP-online's recorded year of construction. Frequently
    # disagrees with BAG; both are emitted under explicit source-named
    # generic attributes (see § 5h of the mapping doc).
    "bouwjaar": ("Bouwjaar",),
    # Thermal-zone floor area: the denominator that every per-m² energy
    # metric below is normalised against. Lands as a second
    # ``nrg3:QualifiedArea`` on the BuildingUnit (sibling of the BAG
    # ``oppervlakte`` entry, same ``netFloorArea`` type, distinct
    # ``source``); see ``builders/building.py``.
    "gebruiksoppervlakte_thermische_zone": ("GebruiksoppervlakteThermischeZone",),
    # Energy-flow metrics → ``nrg3:Energy`` resources. NL convention is
    # kWh/m²·jaar; the parent Energy carries ``referencePeriod="year"`` and
    # the uom is ``kWh/m2/a`` (see § 7 of the mapping doc).
    "energiebehoefte": ("Energiebehoefte",),
    "warmtebehoefte": ("Warmtebehoefte",),
    "primaire_fossiele_energie": ("PrimaireFossieleEnergie",),
    "berekende_energieverbruik": ("BerekendeEnergieverbruik",),
    # CO₂ emission per m² per year → ``co2Equivalent`` on the BENG-2 Energy
    # resource (uom ``kg/m2/a``).
    "berekende_co2_emissie": ("BerekendeCO2Emissie",),
    # Renewable-energy share (BENG-3, %). No native Energy ADE slot; lives
    # as a ``gen:measureAttribute`` on the EPC.
    "aandeel_hernieuwbare_energie": ("AandeelHernieuwbareEnergie",),
}


@dataclass(frozen=True, slots=True)
class EnergyLabel:
    """One EP-online energy-label record, normalised to Python types.

    Surfaces every column that
    [`docs/ep_online_data_model_mapping.md`](../../../docs/ep_online_data_model_mapping.md)
    classifies as ``Native`` / ``Native (derived)`` / ``gen:Attribute`` (i.e.
    everything that ends up in the GML output, plus the address keys used
    for joining). Skip-(latent) and Drop columns are deliberately not
    represented here; reviving any of them is a one-line addition.

    All energy-flow numerics (``energiebehoefte`` … ``berekende_co2_emissie``)
    are stored as :class:`float` after :func:`parse_decimal` has handled
    the Dutch comma decimal marker.
    """

    # --- address keys + VBO id (join inputs) -------------------------------
    postcode: str
    huisnummer: int
    huisletter: str | None
    toevoeging: str | None
    bag_verblijfsobject_id: str | None
    # --- identifying / certifying metadata --------------------------------
    energieklasse: str | None
    registratiedatum: date | None
    opnamedatum: date | None
    geldig_tot: date | None
    # ``berekeningstype`` and every field below default to ``None`` so
    # callers that construct EnergyLabel fixtures (tests, one-off scripts)
    # do not have to enumerate them. The CSV parser always populates the
    # ones the production header carries, so the defaults only appear on
    # hand-built instances and on minimal-header CSVs (e.g. the
    # backward-compat fixtures in :mod:`tests.test_city_eponline`).
    berekeningstype: str | None = None
    soort_opname: str | None = None
    # --- building classification + physics --------------------------------
    gebouwtype: str | None = None
    gebouwsubtype: str | None = None
    bouwjaar: int | None = None
    gebruiksoppervlakte_thermische_zone: float | None = None
    # --- energy-flow metrics (NL convention: kWh/m²·jaar; CO₂ as kg/m²·jaar)
    energiebehoefte: float | None = None
    warmtebehoefte: float | None = None
    primaire_fossiele_energie: float | None = None
    berekende_energieverbruik: float | None = None
    berekende_co2_emissie: float | None = None
    # Renewable-energy share (BENG-3): an integer percentage in the source CSV
    # but stored as float so the pipeline never has to choose between
    # rounding and a `gen:intAttribute`/`gen:measureAttribute` mismatch.
    aandeel_hernieuwbare_energie: float | None = None

    def address_key(self) -> AddressKey:
        """Return the ``(postcode, huisnummer, huisletter, toevoeging)`` tuple.

        Delegates to :func:`citygml_energy.city_builder.address_key.address_key`
        so BAG and EP-online spellings stay in lockstep.
        """
        return build_address_key(self.postcode, self.huisnummer, self.huisletter, self.toevoeging)

    def calculation_regime(self) -> CalculationRegime:
        """Return the calculation regime identified from ``berekeningstype``.

        Three regimes occur in production EP-online data (v20260401 vintage,
        empirical counts across the full 5.12 M-row register):

        * ``nta8800`` (~3.28 M certs, 64%): NTA 8800:2018-2024 family. All
          four BENG metrics (``Energiebehoefte``, ``Warmtebehoefte``,
          ``PrimaireFossieleEnergie``, ``BerekendeEnergieverbruik``) are
          reported in **kWh/(m²·yr)**; ``BerekendeCO2Emissie`` in
          **kg/(m²·yr)**, populated for ~99.99% of rows.
          ``GebruiksoppervlakteThermischeZone`` populated 100%.
        * ``legacy_total`` (~2.84 M certs, 55%): pre-NTA-8800 methods —
          "Rekenmethodiek Definitief Energielabel" (NEN 7120 lineage),
          "Nader Voorschrift", and ISSO 75.3 / 82.3 inspections. Only
          ``BerekendeEnergieverbruik`` is populated, in **MJ per year
          (TOTAL annual primary fossil energy, NOT per-m²)**.
          ``GebruiksoppervlakteThermischeZone`` is empty 100%.
          ``BerekendeCO2Emissie`` is a method-level placeholder ``0,00``
          for the Definitief Energielabel branch (99.997% zero across
          1.44 M rows) and is genuinely populated in **kg/yr (total)**
          for the Nader Voorschrift / ISSO branch — see
          :meth:`co2_is_placeholder` for the per-row decision.
        * ``unknown``: any ``Berekeningstype`` this code has not seen,
          including the empty / null case.

        The empirical magnitude evidence (median 150 kWh/(m²·yr) for
        NTA 8800 vs. median ~93 000 MJ/yr for Definitief Energielabel
        v1.2) is documented with the 5.12 M-row distribution table in
        § 5i of the EP-online mapping doc, alongside the unit derivation.
        """
        method = (self.berekeningstype or "").strip()
        if not method:
            return "unknown"
        if "NTA 8800" in method:
            return "nta8800"
        legacy_markers = (
            "Definitief Energielabel",
            "Nader Voorschrift",
            "ISSO75",
            "ISSO 75",
            "ISSO82",
            "ISSO 82",
        )
        if any(marker in method for marker in legacy_markers):
            return "legacy_total"
        return "unknown"

    def co2_is_placeholder(self) -> bool:
        """True when ``BerekendeCO2Emissie`` is a method-level placeholder, not data.

        The legacy "Rekenmethodiek Definitief Energielabel" branch records
        ``0,00`` for every certificate (1 438 399 zero values out of
        1 438 444 rows in the v20260401 vintage; 99.997%). This method
        does not compute CO₂; the field is structural padding so the row
        still has 42 columns. Emitting that ``0`` as ``co2Equivalent``
        downstream would mislead consumers into treating it as a measured
        value.

        Other legacy methods (Nader Voorschrift, ISSO 75.3 / 82.3) DO
        compute CO₂ and report it in **kg/yr (total)**, with normal
        distribution; their zeros are real (~0.1% of rows). NTA 8800
        certs also report CO₂ as data with vanishingly rare zeros (381
        out of 3.28 M = 0.01%).

        Decision rule: treat the ``0,00`` as placeholder *only* for the
        Definitief Energielabel branch, where the empirical signal is
        unambiguous.
        """
        return "Definitief Energielabel" in (self.berekeningstype or "")


# ---------------------------------------------------------------------------
# Public fetch + parse
# ---------------------------------------------------------------------------


def fetch_energy_labels(
    session: CachedSession,
    *,
    api_key: str,
    wanted_ids: Iterable[str] | None = None,
    wanted_keys: Iterable[AddressKey] | None = None,
) -> list[EnergyLabel]:
    """Return the EP-online labels from the current mutation file.

    Fetches the ZIP (cached by ``"ep_online_bundle"``), unpacks the single
    CSV inside, and normalises every matching row. Rows without a
    parseable ``(postcode, huisnummer)`` are skipped.

    When *wanted_ids* or *wanted_keys* is given, every CSV row that
    fails both membership tests is dropped before any dataclass is
    allocated: this is what makes 5 M-row parses affordable in the
    city pipeline. Pass ``None`` (the default) to parse every row; this
    is the path used by tests and scripts that want the full register.

    Streams the CSV directly from the zip entry (no intermediate
    gigabyte-string + splitlines), so peak memory is bounded by the
    ``TextIOWrapper`` buffer rather than the uncompressed CSV size.

    The ZIP body is cached indefinitely; there is deliberately no
    parsed-label pickle. A pickle for 5 M labels is half a gig on disk
    and tens of seconds of load time per run; filter-on-parse beats both
    reading the pickle and rewriting it on URL rotation.
    """
    # DownloadInfo is intentionally NOT cached: the download URL rotates with
    # each vintage publication. Caching it would serve stale URLs indefinitely.
    meta_raw = session.get_bytes(
        DOWNLOAD_INFO_URL,
        headers={"Authorization": api_key},
    )
    meta = json.loads(meta_raw.decode("utf-8"))
    download_url = meta.get("downloadUrl") or meta.get("DownloadUrl")
    if not download_url:
        raise ValueError("EP-online DownloadInfo response is missing downloadUrl")

    zip_bytes = session.get_bytes(
        str(download_url),
        cache_key="ep_online_bundle",
    )
    return _parse_csv_from_zip(zip_bytes, wanted_ids=wanted_ids, wanted_keys=wanted_keys)


def parse_csv(
    csv_text: str,
    *,
    wanted_ids: Iterable[str] | None = None,
    wanted_keys: Iterable[AddressKey] | None = None,
) -> list[EnergyLabel]:
    """Parse the raw EP-online CSV into :class:`EnergyLabel` records.

    When *wanted_ids* or *wanted_keys* is given, rows that match neither
    filter are discarded before any parsing work beyond reading the
    positional cells required to test membership. This is much cheaper
    than constructing the dataclass and filtering afterward because the
    CSV contains ~5 M rows and typical callers want ~10³.

    Uses a positional :func:`csv.reader` (not :class:`csv.DictReader`)
    with column indices resolved once from the header row: ``DictReader``
    allocates a dict per row, which alone accounted for >50% of the parse
    time on the production CSV.
    """
    return list(
        _iter_labels_from_text(
            io.StringIO(csv_text),
            wanted_ids=wanted_ids,
            wanted_keys=wanted_keys,
        )
    )


def _parse_csv_from_zip(
    zip_bytes: bytes,
    *,
    wanted_ids: Iterable[str] | None,
    wanted_keys: Iterable[AddressKey] | None,
) -> list[EnergyLabel]:
    """Stream the single CSV inside *zip_bytes* through the row iterator.

    The EP-online mutation CSV is ~1 GB uncompressed; decoding it to a
    Python ``str`` and then calling ``splitlines()`` materialises 3-4 GB
    peak. Wrapping the zip entry in a :class:`io.TextIOWrapper` lets
    :func:`csv.reader` consume the stream line-by-line with a bounded
    buffer, so memory stays flat and we skip the ``splitlines`` call
    (~3 s on the production CSV).

    When ``polars`` is installed **and** a key filter is active, a
    Rust-backed columnar path is attempted first: polars loads the CSV
    into Arrow arrays, filters rows where the normalised ``Postcode``
    column is in the wanted set (SIMD, sub-second on the full 5 M-row
    file), and emits the survivors as Python tuples that still flow
    through :func:`_iter_matching_rows` for the final huisnummer parse
    + composite-key check. Any unexpected polars behaviour falls back
    transparently to the stdlib streaming path, so the optional
    ``[city-fast]`` extra is purely additive.
    """
    # Optional polars fast-path, gated off by default. The Python
    # streaming + byte-level prefilter beats polars on this shape because
    # polars must materialise the full 5 M-row CSV into Arrow before
    # filtering, whereas the streaming path rejects a non-matching
    # postcode with a single ``str.find``. Opt in with
    # ``CITYGML_ENERGY_EPONLINE_POLARS=1`` for experimentation if future
    # filter logic grows beyond a postcode-membership test.
    if wanted_keys is not None and os.environ.get("CITYGML_ENERGY_EPONLINE_POLARS") == "1":
        polars_labels = _try_parse_with_polars(
            zip_bytes, wanted_ids=wanted_ids, wanted_keys=wanted_keys
        )
        if polars_labels is not None:
            return polars_labels

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("EP-online ZIP does not contain a .csv file")

        # Bulk-decompress + BytesIO line iteration is materially faster
        # than streaming ``TextIOWrapper`` on the production ZIP because
        # ``zipfile.ZipExtFile``'s line iteration is poorly buffered; the
        # one-off uncompressed-CSV allocation (single-process) is
        # tolerable. Only applies when a key filter is active; the
        # unfiltered branch that tests rely on keeps the streaming-text
        # path.
        if wanted_keys is not None:
            raw = zf.read(csv_names[0])
            return parse_csv_from_bulk_bytes(raw, wanted_ids=wanted_ids, wanted_keys=wanted_keys)

        with zf.open(csv_names[0]) as binary:
            text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
            return list(
                _iter_labels_from_text(text, wanted_ids=wanted_ids, wanted_keys=wanted_keys)
            )


def parse_csv_from_bulk_bytes(
    raw: bytes,
    *,
    wanted_ids: Iterable[str] | None,
    wanted_keys: Iterable[AddressKey],
) -> list[EnergyLabel]:
    """Parse fully-decompressed CSV bytes with a bytes-level postcode prefilter.

    The unfiltered path still streams via :func:`_iter_labels_from_text`
    so test suites (which never hit this function) keep their existing
    contract.
    """
    bom_offset = 3 if raw.startswith(b"\xef\xbb\xbf") else 0

    # Locate the first header line (``Postcode`` + ``Huisnummer``) by
    # scanning raw bytes. The preamble is small (a handful of metadata
    # lines) so the extra cost is negligible.
    offset = bom_offset
    n = len(raw)
    header: list[str] | None = None
    while offset < n:
        line_end = raw.find(b"\n", offset)
        line = raw[offset : line_end if line_end >= 0 else n]
        if b"Postcode" in line and b"Huisnummer" in line:
            header = next(csv.reader([line.decode("utf-8")], delimiter=";"))
            offset = line_end + 1 if line_end >= 0 else n
            break
        if line_end < 0:
            return []
        offset = line_end + 1

    if header is None:
        return []

    idx = _resolve_column_indices(header)
    id_set = frozenset(wanted_ids) if wanted_ids is not None else None
    key_set = frozenset(wanted_keys)
    postcode_bytes_set: frozenset[bytes] = frozenset(k[0].encode("ascii") for k in key_set)

    # Seek rather than slice: ``raw[offset:]`` would copy ~1.5 GB.
    body = io.BytesIO(raw)
    body.seek(offset)
    filtered_text = _filter_bulk_bytes_by_postcode(
        body, postcode_bytes_set, postcode_col_idx=idx["postcode"]
    )
    reader = csv.reader(filtered_text, delimiter=";")
    return list(_iter_matching_rows(reader, idx, id_set=id_set, key_set=key_set))


def _filter_bulk_bytes_by_postcode(
    buf: io.BytesIO,
    postcode_bytes_set: frozenset[bytes],
    *,
    postcode_col_idx: int,
) -> Iterable[str]:
    """Yield decoded CSV lines whose Postcode column is in *postcode_bytes_set*.

    The EP-online CSV puts ``Postcode`` at column 12 (after
    ``Registratiedatum;Opnamedatum;GeldigTot;…``), not column 0, so
    this prefilter must seek past the preceding semicolon-separated
    fields before reading the postcode. Reading only those bytes, and
    skipping the full :func:`csv.reader` parse for non-matching rows,
    is the entire point of the bulk path on the 5 M-row file.

    Hot loop; locals bound up front so the body avoids ``LOAD_GLOBAL``
    per iteration. Decodes as ``utf-8`` (not ``utf-8-sig``) because the
    BOM was already consumed by :func:`parse_csv_from_bulk_bytes`.
    """
    readline = buf.readline
    set_contains = postcode_bytes_set.__contains__
    sep_byte = b";"
    while True:
        line = readline()
        if not line:
            return
        # Walk to the start of the Postcode field by skipping `postcode_col_idx`
        # semicolons, then read up to the next one.
        start = 0
        for _ in range(postcode_col_idx):
            sep = line.find(sep_byte, start)
            if sep < 0:
                start = -1
                break
            start = sep + 1
        if start < 0:
            continue
        end = line.find(sep_byte, start)
        if end < 0:
            continue
        pc = line[start:end]
        if b" " in pc:
            pc = pc.replace(b" ", b"")
        pc = pc.strip().upper()
        if set_contains(pc):
            yield line.decode("utf-8")


def _try_parse_with_polars(
    zip_bytes: bytes,
    *,
    wanted_ids: Iterable[str] | None,
    wanted_keys: Iterable[AddressKey],
) -> list[EnergyLabel] | None:
    """Attempt a polars-backed columnar parse; return ``None`` to fall back.

    Routes the coarse postcode filter through polars (Rust/SIMD columnar
    scan); surviving rows still flow through :func:`_iter_matching_rows`
    so the huisnummer regex, composite-key test, and :class:`EnergyLabel`
    construction live in one place. Any ``ImportError``, runtime
    exception, or malformed input silently falls through to the stdlib
    path.
    """
    try:
        import polars as pl
    except ImportError:
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                return None
            raw = zf.read(csv_names[0])

        # Strip any UTF-8 BOM; locate the first data header row.
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        header_offset = _find_header_offset(raw)
        if header_offset is None:
            return None

        # Count the preamble lines so polars can skip them at read time.
        preamble = raw[:header_offset]
        skip_rows = preamble.count(b"\n")

        df = pl.read_csv(
            io.BytesIO(raw),
            separator=";",
            has_header=True,
            skip_rows=skip_rows,
            infer_schema_length=0,  # keep every column as Utf8; we parse later
            # Truncate malformed oversize rows rather than abort the parse.
            truncate_ragged_lines=True,
        )

        if "Postcode" not in df.columns:
            return None

        postcodes = list({k[0] for k in wanted_keys})
        # Columnar postcode filter: normalise then membership-test with
        # Rust-level string ops across all rows at once.
        filtered = df.filter(
            pl.col("Postcode").str.replace_all(" ", "").str.to_uppercase().is_in(postcodes)
        )
        if filtered.height == 0:
            return []

        header_cols = df.columns
        idx = _resolve_column_indices(header_cols)
        id_set = frozenset(wanted_ids) if wanted_ids is not None else None
        key_set = frozenset(wanted_keys)

        # ``rows()`` returns a list of tuples of Utf8 values (or None for
        # missing cells). ``_iter_matching_rows`` already tolerates short
        # rows via ``0 <= i < row_len``; we coerce None → "" to match the
        # csv-reader contract exactly.
        def _normalise_row(row: tuple[Any, ...]) -> list[str]:
            return ["" if v is None else v for v in row]

        rows = (_normalise_row(r) for r in filtered.iter_rows())
        return list(_iter_matching_rows(rows, idx, id_set=id_set, key_set=key_set))
    except Exception as exc:
        # Any polars hiccup (schema mismatch, buffer error, malformed CSV,
        # an ArrowError from a future polars version) drops us onto the
        # well-tested stdlib path with no user-visible impact. Bare
        # ``Exception`` is deliberate here: the only alternative is to
        # hard-import ``polars.exceptions.PolarsError``, which couples
        # this module to an optional dep just to match a catch clause.
        # KeyboardInterrupt / SystemExit are BaseException and still
        # propagate, which is the only hard correctness requirement.
        logging.getLogger(__name__).warning(
            "polars EP-online parse failed (%s); falling back to csv.reader",
            exc,
        )
        return None


def _find_header_offset(raw: bytes) -> int | None:
    """Return the byte offset of the first row containing ``Postcode`` + ``Huisnummer``.

    Finds the start of the line so :func:`polars.read_csv` can use
    ``skip_rows`` to jump straight to the header. Returns ``None`` on a
    pathological feed with no detectable header.
    """
    pos = 0
    needles = (b"Postcode", b"Huisnummer")
    while True:
        line_end = raw.find(b"\n", pos)
        if line_end < 0:
            line = raw[pos:]
        else:
            line = raw[pos:line_end]
        if all(n in line for n in needles):
            return pos
        if line_end < 0:
            return None
        pos = line_end + 1


def _iter_labels_from_text(
    text: Iterable[str],
    *,
    wanted_ids: Iterable[str] | None,
    wanted_keys: Iterable[AddressKey] | None,
) -> Iterable[EnergyLabel]:
    """Yield :class:`EnergyLabel` rows from a line-iterable *text* source.

    Walks the CSV with :func:`csv.reader`, skips any metadata preamble
    by scanning for the first row containing both ``Postcode`` and
    ``Huisnummer``, then delegates to :func:`_iter_matching_rows`. Works
    identically for an in-memory :class:`io.StringIO` (via
    :func:`parse_csv`) and for a streaming :class:`io.TextIOWrapper`
    around a zip entry (via :func:`_parse_csv_from_zip`).

    When *wanted_keys* is supplied, a **line-level postcode prefilter**
    runs ahead of :func:`csv.reader`: we extract the raw first field
    (EP-online always writes postcode as column 1 without quoting),
    normalise it cheaply, and drop lines whose postcode isn't wanted
    before paying the csv-tokenise cost. On the production 5 M-row file
    this cuts csv-parsing work by ~99 %. The id-only match path (BAG
    VBO-ID column) still works for rows whose postcode *is* in the
    wanted set; id-only matches on rows with a mismatched postcode are
    dropped by the prefilter, which is a documented narrowing of
    semantics that does not affect any real-world BAG-derived filter
    set (the city pipeline supplies both ``wanted_ids`` and
    ``wanted_keys`` from the same VBO list, so their postcodes agree).
    """
    line_iter = iter(text)
    header: list[str] | None = None
    for line in line_iter:
        # Cheap preamble skip: header row always contains ``Postcode`` and
        # ``Huisnummer`` as whole cells (surrounded by ``;`` or line edges).
        # Substring check avoids csv-tokenising each preamble line.
        if "Postcode" in line and "Huisnummer" in line:
            header = next(csv.reader([line], delimiter=";"))
            break
    if header is None:
        return

    idx = _resolve_column_indices(header)
    id_set = frozenset(wanted_ids) if wanted_ids is not None else None
    key_set = frozenset(wanted_keys) if wanted_keys is not None else None

    if key_set is not None:
        postcode_set = frozenset(k[0] for k in key_set)
        filtered_lines = _filter_lines_by_postcode(line_iter, postcode_set)
        reader = csv.reader(filtered_lines, delimiter=";")
    else:
        reader = csv.reader(line_iter, delimiter=";")

    yield from _iter_matching_rows(reader, idx, id_set=id_set, key_set=key_set)


def _filter_lines_by_postcode(
    lines: Iterable[str],
    postcode_set: frozenset[str],
) -> Iterable[str]:
    """Yield only lines whose first semicolon-delimited field is a wanted postcode.

    Runs before :func:`csv.reader`, so postcode-rejected lines cost one
    ``str.find`` + one ``str.upper`` + one set lookup, with no tokenisation
    and no Python-object allocation for the row cells.

    Normalisation matches :func:`citygml_energy.city_builder.address_key.normalise_postcode`
    (uppercase + internal whitespace stripped). EP-online never quotes
    its postcode column, so the raw slice before the first ``;`` is
    equivalent to the csv-parsed cell.
    """
    for line in lines:
        sep = line.find(";")
        if sep < 0:
            continue
        first = line[:sep]
        # Fast path: most EP-online postcodes are already tight-uppercase.
        if " " in first:
            first = first.replace(" ", "")
        # Strip tolerates stray trailing BOM/whitespace on malformed feeds.
        pc = first.strip().upper()
        if pc in postcode_set:
            yield line


# ---------------------------------------------------------------------------
# Row → EnergyLabel
# ---------------------------------------------------------------------------


def _resolve_column_indices(header: list[str]) -> dict[str, int]:
    """Map each required logical name → its positional index in *header*.

    Raises :class:`KeyError` if postcode/huisnummer are missing (we
    cannot match anything without them); other columns are silently
    assigned ``-1`` so :func:`_row_to_label` treats them as absent.
    """
    normalised = {h.strip(): i for i, h in enumerate(header)}
    resolved: dict[str, int] = {}
    for logical, aliases in _COLUMN_ALIASES.items():
        idx = next((normalised[a] for a in aliases if a in normalised), -1)
        if idx == -1 and logical in ("postcode", "huisnummer"):
            raise KeyError(
                f"EP-online CSV is missing the {aliases!r} column; "
                f"cannot match labels to addresses."
            )
        resolved[logical] = idx
    return resolved


def _iter_matching_rows(
    reader: Iterable[list[str]],
    idx: dict[str, int],
    *,
    id_set: frozenset[str] | None,
    key_set: frozenset[AddressKey] | None,
) -> Iterable[EnergyLabel]:
    """Yield only the :class:`EnergyLabel` rows matching one of the filters.

    Hot loop across the 5 M-row production CSV; work is deferred past
    the cheapest possible rejection test:

    1. **Postcode early-prune.** When *key_set* is active, derive a
       postcode-only projection up front; rows whose postcode isn't in
       it cannot match by key and are rejected after one
       :func:`normalise_postcode` call. When *id_set* is also active
       we still admit rows that might match by BAG-id after a cheap
       ``.strip()`` test.
    2. **Huisnummer parse** (regex), only for surviving rows.
    3. **Full filter match** (id then key), only for parsed rows.

    Column indices and ``frozenset`` / normaliser callables are bound
    as locals because attribute lookup dominates the inner loop.
    """
    unfiltered = id_set is None and key_set is None

    # Postcode-only projection of the wanted keys, used to reject rows
    # with an irrelevant postcode before any huisnummer/toevoeging work.
    postcode_set: frozenset[str] | None = (
        frozenset(k[0] for k in key_set) if key_set is not None else None
    )

    # Pull index lookups out of the hot loop.
    i_pc = idx["postcode"]
    i_nr = idx["huisnummer"]
    i_hl = idx["huisletter"]
    i_tv = idx["toevoeging"]
    i_vbo = idx["bag_vbo_id"]
    i_klas = idx["energieklasse"]
    i_reg = idx["registratiedatum"]
    i_opn = idx["opnamedatum"]
    i_geld = idx["geldig_tot"]
    i_berek = idx["berekeningstype"]
    i_opname = idx["soort_opname"]
    i_gtype = idx["gebouwtype"]
    i_gsubtype = idx["gebouwsubtype"]
    i_bouw = idx["bouwjaar"]
    i_floor = idx["gebruiksoppervlakte_thermische_zone"]
    i_e_demand = idx["energiebehoefte"]
    i_heat_demand = idx["warmtebehoefte"]
    i_primary = idx["primaire_fossiele_energie"]
    i_final = idx["berekende_energieverbruik"]
    i_co2 = idx["berekende_co2_emissie"]
    i_renewable = idx["aandeel_hernieuwbare_energie"]

    # Local aliases for micro-opt in the hot loop.
    norm_postcode = normalise_postcode
    norm_letter = normalise_letter
    split_huisnummer = _split_huisnummer
    parse_ymd = _parse_yyyymmdd
    parse_int = _parse_int_or_none
    parse_dec = parse_decimal

    for row in reader:
        row_len = len(row)
        postcode_raw = row[i_pc] if 0 <= i_pc < row_len else ""
        postcode = norm_postcode(postcode_raw)
        if not postcode:
            continue

        # Early prune: if the postcode cannot match any wanted key,
        # only a BAG-id match could save this row. That test is a single
        # strip + set lookup, cheap compared to the huisnummer regex.
        if postcode_set is not None and postcode not in postcode_set:
            if id_set is None:
                continue
            bag_id_raw = row[i_vbo] if 0 <= i_vbo < row_len else ""
            bag_id_stripped = bag_id_raw.strip()
            if not bag_id_stripped or bag_id_stripped not in id_set:
                continue
            # BAG-id match: fall through to full parse (rare).

        huisnummer_raw = row[i_nr] if 0 <= i_nr < row_len else ""
        huisletter_raw = (row[i_hl].strip() if 0 <= i_hl < row_len else "") or None
        toevoeging_raw = (row[i_tv].strip() if 0 <= i_tv < row_len else "") or None
        huisnummer, huisletter, toevoeging = split_huisnummer(
            huisnummer_raw, huisletter_raw, toevoeging_raw
        )
        if huisnummer is None:
            continue

        bag_id = (row[i_vbo].strip() if 0 <= i_vbo < row_len else "") or None

        if not unfiltered:
            hit_id = id_set is not None and bag_id is not None and bag_id in id_set
            if not hit_id:
                candidate_key: AddressKey = (
                    postcode,
                    huisnummer,
                    norm_letter(huisletter),
                    norm_letter(toevoeging),
                )
                if key_set is None or candidate_key not in key_set:
                    continue

        yield EnergyLabel(
            postcode=postcode,
            huisnummer=huisnummer,
            huisletter=huisletter,
            toevoeging=toevoeging,
            bag_verblijfsobject_id=bag_id,
            energieklasse=(row[i_klas].strip() if 0 <= i_klas < row_len else "") or None,
            registratiedatum=parse_ymd(row[i_reg] if 0 <= i_reg < row_len else ""),
            opnamedatum=parse_ymd(row[i_opn] if 0 <= i_opn < row_len else ""),
            geldig_tot=parse_ymd(row[i_geld] if 0 <= i_geld < row_len else ""),
            berekeningstype=(row[i_berek].strip() if 0 <= i_berek < row_len else "") or None,
            soort_opname=(row[i_opname].strip() if 0 <= i_opname < row_len else "") or None,
            gebouwtype=(row[i_gtype].strip() if 0 <= i_gtype < row_len else "") or None,
            gebouwsubtype=(row[i_gsubtype].strip() if 0 <= i_gsubtype < row_len else "") or None,
            bouwjaar=parse_int(row[i_bouw] if 0 <= i_bouw < row_len else ""),
            gebruiksoppervlakte_thermische_zone=parse_dec(
                row[i_floor] if 0 <= i_floor < row_len else ""
            ),
            energiebehoefte=parse_dec(row[i_e_demand] if 0 <= i_e_demand < row_len else ""),
            warmtebehoefte=parse_dec(row[i_heat_demand] if 0 <= i_heat_demand < row_len else ""),
            primaire_fossiele_energie=parse_dec(row[i_primary] if 0 <= i_primary < row_len else ""),
            berekende_energieverbruik=parse_dec(row[i_final] if 0 <= i_final < row_len else ""),
            berekende_co2_emissie=parse_dec(row[i_co2] if 0 <= i_co2 < row_len else ""),
            aandeel_hernieuwbare_energie=parse_dec(
                row[i_renewable] if 0 <= i_renewable < row_len else ""
            ),
        )


# ---------------------------------------------------------------------------
# Low-level normalisation helpers
# ---------------------------------------------------------------------------


def _split_huisnummer(
    huisnummer_raw: str,
    huisletter_raw: str | None,
    toevoeging_raw: str | None,
) -> tuple[int | None, str | None, str | None]:
    """Parse EP-online's sometimes-composite huisnummer into three fields.

    The source mixes styles: "42", "42A", "42 AB", "2-3B", "2 bis" all
    appear. We use a single regex plus a heuristic that treats a "double
    letter" as a ``toevoeging`` when ``huisletter`` is still unset.
    """
    if not huisnummer_raw:
        return None, None, None
    match = _HUISNUMMER_RE.match(huisnummer_raw)
    if match is None:
        return None, None, None
    number = int(match.group(1))
    tail_letter = match.group(2)
    tail_toevoeging = match.group(3)

    # Prefer explicit columns when the source provides them.
    huisletter = huisletter_raw or (tail_letter.upper() if tail_letter else None)
    toevoeging = toevoeging_raw or (tail_toevoeging.upper() if tail_toevoeging else None)
    return number, huisletter, toevoeging


def _parse_yyyymmdd(raw: str) -> date | None:
    text = (raw or "").strip()
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _parse_int_or_none(raw: str) -> int | None:
    """Parse an EP-online integer column; tolerate empty / malformed cells."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_decimal(raw: str) -> float | None:
    """Parse a Dutch-decimal numeric cell (e.g. ``"28,5"``) to ``float``.

    EP-online's CSV is semicolon-separated and uses the Dutch comma
    decimal marker for every numeric column. The thousands separator
    (``"."``) is irrelevant in practice for the energy-domain columns
    (Energiebehoefte, primary energy, CO₂ emission, renewable share are
    all in 0-1000 range), but the implementation strips it defensively
    anyway in case a future vintage adds wider quantities.

    Empty / whitespace-only / unparseable cells return ``None`` rather
    than raising, mirroring :func:`_parse_yyyymmdd` and the rest of this
    module's "tolerate-then-skip" stance toward malformed cells.
    """
    text = (raw or "").strip()
    if not text:
        return None
    # Strip the Dutch thousands separator, then swap the decimal comma.
    text = text.replace(".", "").replace(",", ".") if "," in text else text
    try:
        return float(text)
    except ValueError:
        return None
