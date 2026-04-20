"""Fetch and normalise EP-online energy labels (bulk ``Mutatiebestand`` CSV).

EP-online (RVO) publishes the complete register of Dutch energy labels
as a ZIP-compressed CSV (~1 GB uncompressed, ~5 M rows). The download
URL rotates per vintage, so step 1 is a GET to the ``DownloadInfo``
endpoint (which returns the real download URL plus metadata), step 2
downloads the ZIP and unpacks the single CSV inside. Access requires an
API token sent via the ``Authorization`` header.

The CSV uses Dutch conventions: semicolon separators, YYYYMMDD dates,
Dutch column names. We normalise into :class:`EnergyLabel` records with
snake_case fields that downstream code can join on.

**Filter-on-parse is the fast path.** The city pipeline only cares about
labels that match the VBOs inside a BBOX (usually a few hundred rows out
of 5 M). :func:`fetch_energy_labels` accepts ``wanted_ids`` and
``wanted_keys`` sets and :func:`parse_csv` drops every non-matching row
before materialising a dataclass: no 5 M-row list, no multi-GB pickle,
no O(N) post-scan. Passing no filter falls back to the full parse,
which is what tests and scripts that want the whole register rely on.

:class:`EnergyLabel` is deliberately minimal: only the fields that end
up in the CityGML output (``energieklasse`` → EPC label + colour,
``registratiedatum`` / ``geldig_tot`` → ``validFrom`` / ``validTo``,
``opnamedatum`` → duplicate-row ordering) plus the address keys.
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
from typing import Any

from ..address_key import (
    AddressKey,
    normalise_letter,
    normalise_postcode,
)
from ..address_key import (
    address_key as build_address_key,
)
from ..http import CachedSession

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
}


@dataclass(frozen=True, slots=True)
class EnergyLabel:
    """One EP-online energy-label record, normalised to Python types.

    Intentionally minimal (see module docstring). Every attribute here
    is consumed by :mod:`address_match` (joining to BAG) or
    :mod:`builders` (populating ``nrg3:EnergyPerformanceCertificate``).
    """

    postcode: str
    huisnummer: int
    huisletter: str | None
    toevoeging: str | None
    bag_verblijfsobject_id: str | None
    energieklasse: str | None
    registratiedatum: date | None
    opnamedatum: date | None
    geldig_tot: date | None

    def address_key(self) -> AddressKey:
        """Return the ``(postcode, huisnummer, huisletter, toevoeging)`` tuple.

        Delegates to :func:`citygml_energy.city_builder.address_key.address_key`
        so BAG and EP-online spellings stay in lockstep.
        """
        return build_address_key(self.postcode, self.huisnummer, self.huisletter, self.toevoeging)


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
            return _parse_csv_from_bulk_bytes(raw, wanted_ids=wanted_ids, wanted_keys=wanted_keys)

        with zf.open(csv_names[0]) as binary:
            text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
            return list(
                _iter_labels_from_text(text, wanted_ids=wanted_ids, wanted_keys=wanted_keys)
            )


def _parse_csv_from_bulk_bytes(
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
    BOM was already consumed by :func:`_parse_csv_from_bulk_bytes`.
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
        # Any polars hiccup (schema mismatch, buffer error, malformed CSV)
        # drops us onto the well-tested stdlib path with no user-visible
        # impact. Log once at WARNING so the regression is observable.
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

    # Local aliases for micro-opt in the hot loop.
    norm_postcode = normalise_postcode
    norm_letter = normalise_letter
    split_huisnummer = _split_huisnummer
    parse_ymd = _parse_yyyymmdd

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
