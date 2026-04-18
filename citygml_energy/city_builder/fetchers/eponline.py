"""Fetch and normalise EP-online energy labels (bulk ``Mutatiebestand`` CSV).

EP-online (RVO) publishes the complete register of Dutch energy labels
as a ZIP-compressed CSV (~1 GB uncompressed, ~5 M rows). The download
URL rotates per vintage, so step 1 is a GET to the ``DownloadInfo``
endpoint (which returns the real download URL plus metadata), step 2
downloads the ZIP and unpacks the single CSV inside. Access requires an
API token sent via the ``Authorization`` header.

The CSV uses Dutch conventions — semicolon separators, YYYYMMDD dates,
Dutch column names. We normalise into :class:`EnergyLabel` records with
snake_case fields that downstream code can join on.

**Filter-on-parse is the fast path.** The city pipeline only cares about
labels that match the VBOs inside a BBOX (usually a few hundred rows out
of 5 M). :func:`fetch_energy_labels` accepts ``wanted_ids`` and
``wanted_keys`` sets and :func:`parse_csv` drops every non-matching row
before materialising a dataclass — no 5 M-row list, no multi-GB pickle,
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
import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..http import CachedSession

DOWNLOAD_INFO_URL = (
    "https://public.ep-online.nl/api/v5/Mutatiebestand/DownloadInfo"
    "?fileType=csv&xmlVersion=4"
)

AddressKey = tuple[str, int, str | None, str | None]


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

    Intentionally minimal — see module docstring. Every attribute here
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

        The postcode is normalised to all-uppercase without internal
        whitespace so BAG and EP-online spellings match.
        """
        return (
            _normalise_postcode(self.postcode),
            self.huisnummer,
            _normalise_letter_or_toevoeging(self.huisletter),
            _normalise_letter_or_toevoeging(self.toevoeging),
        )


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
    allocated — this is what makes 5 M-row parses affordable in the
    city pipeline. Pass ``None`` (the default) to parse every row; this
    is the path used by tests and scripts that want the full register.

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
    csv_text = _extract_csv_from_zip(zip_bytes)
    return parse_csv(csv_text, wanted_ids=wanted_ids, wanted_keys=wanted_keys)


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
    reader = csv.reader(io.StringIO(csv_text), delimiter=";")
    try:
        header = next(reader)
    except StopIteration:
        return []

    idx = _resolve_column_indices(header)
    id_set = frozenset(wanted_ids) if wanted_ids is not None else None
    key_set = frozenset(wanted_keys) if wanted_keys is not None else None

    return [
        label
        for label in _iter_matching_rows(reader, idx, id_set=id_set, key_set=key_set)
    ]


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
                f"EP-online CSV is missing the {aliases!r} column — "
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

    Hot loop — written for speed. We pull the column indices into locals
    (attribute lookup on a dict is cheaper in a hot loop when the dict
    itself is a module-level reference, but locals beat both), test the
    cheap ``bag_verblijfsobject_id`` membership first when an id filter
    is active, and only fall through to the composite address-key test
    on a miss. If *both* filters are ``None``, we short-circuit the
    membership check entirely and emit every parseable row.
    """
    unfiltered = id_set is None and key_set is None

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

    for row in reader:
        row_len = len(row)
        postcode_raw = row[i_pc] if 0 <= i_pc < row_len else ""
        postcode = _normalise_postcode(postcode_raw)
        if not postcode:
            continue

        huisnummer_raw = row[i_nr] if 0 <= i_nr < row_len else ""
        huisletter_raw = (row[i_hl].strip() if 0 <= i_hl < row_len else "") or None
        toevoeging_raw = (row[i_tv].strip() if 0 <= i_tv < row_len else "") or None
        huisnummer, huisletter, toevoeging = _split_huisnummer(
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
                    _normalise_letter_or_toevoeging(huisletter),
                    _normalise_letter_or_toevoeging(toevoeging),
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
            registratiedatum=_parse_yyyymmdd(
                row[i_reg] if 0 <= i_reg < row_len else ""
            ),
            opnamedatum=_parse_yyyymmdd(
                row[i_opn] if 0 <= i_opn < row_len else ""
            ),
            geldig_tot=_parse_yyyymmdd(
                row[i_geld] if 0 <= i_geld < row_len else ""
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
    appear. The reference ``VdB_Optoppen_lokaal`` implementation uses a
    single regex plus a heuristic that treats a "double letter" as a
    ``toevoeging`` when ``huisletter`` is still unset.
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
    toevoeging = toevoeging_raw or (
        tail_toevoeging.upper() if tail_toevoeging else None
    )
    return number, huisletter, toevoeging


def _normalise_postcode(raw: Any) -> str:
    if raw is None:
        return ""
    return "".join(str(raw).split()).upper()


def _normalise_letter_or_toevoeging(raw: str | None) -> str | None:
    if raw is None:
        return None
    trimmed = raw.strip().upper()
    return trimmed or None


def _parse_yyyymmdd(raw: str) -> date | None:
    text = (raw or "").strip()
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _extract_csv_from_zip(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("EP-online ZIP does not contain a .csv file")
        with zf.open(csv_names[0]) as handle:
            text = handle.read().decode("utf-8-sig")

    # The EP-online Mutatiebestand CSV starts with metadata rows such as:
    #   PublicatieDatum;01-04-2026
    #   LaatstVerwerkteMutatievolgnummer;19345219
    # before the actual column header row.  Find the header by looking for
    # the first row that contains both "Postcode" and "Huisnummer" as
    # semicolon-delimited fields, then return only from that row onward.
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        parts = {p.strip() for p in line.split(";")}
        if "Postcode" in parts and "Huisnummer" in parts:
            return "".join(lines[i:])

    return text  # fallback — no preamble detected, parse as-is
