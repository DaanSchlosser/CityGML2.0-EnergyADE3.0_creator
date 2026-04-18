"""Fetch and normalise EP-online energy labels (bulk ``Mutatiebestand`` CSV).

EP-online (RVO) publishes the complete register of Dutch energy labels
as a ZIP-compressed CSV. The download URL rotates; step 1 is a GET to
the ``DownloadInfo`` endpoint (which returns the real download URL
plus metadata), step 2 downloads the ZIP and unpacks the single CSV
inside. Access requires an API token sent via the
``Authorization`` header.

The CSV uses Dutch conventions — semicolon separators, comma decimal
points, YYYYMMDD dates, Dutch column names. We normalise into a list
of :class:`EnergyLabel` records with snake_case fields that downstream
code can join on.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import pickle
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..http import CachedSession

DOWNLOAD_INFO_URL = (
    "https://public.ep-online.nl/api/v5/Mutatiebestand/DownloadInfo"
    "?fileType=csv&xmlVersion=4"
)

_HUISNUMMER_RE = re.compile(
    r"^\s*(\d{1,5})\s*[- ]*\s*([A-Za-z])?\s*[- ]*\s*([A-Za-z0-9]{1,4})?\s*$"
)


@dataclass(frozen=True)
class EnergyLabel:
    """One EP-online energy-label record, normalised to Python types."""

    postcode: str
    huisnummer: int
    huisletter: str | None
    toevoeging: str | None
    bag_verblijfsobject_id: str | None
    energieklasse: str | None
    registratiedatum: date | None
    opnamedatum: date | None
    geldig_tot: date | None
    energieindex: float | None
    primaire_fossiele_energie: float | None
    aandeel_hernieuwbare_energie: float | None
    berekende_co2_emissie: float | None
    gebouwtype: str | None
    gebouwsubtype: str | None
    gebruiksoppervlakte_thermische_zone: float | None
    compactheid: float | None
    raw: dict[str, str]

    def address_key(self) -> tuple[str, int, str | None, str | None]:
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


def fetch_energy_labels(session: CachedSession, *, api_key: str) -> list[EnergyLabel]:
    """Return every label in the current EP-online mutation file.

    Fetches the ZIP (cached), unpacks the single CSV inside, and
    normalises every row. Rows without a parseable ``(postcode,
    huisnummer)`` are skipped — they are malformed in the source data
    and cannot be matched to a BAG address.

    **Cache note**: the ZIP body and the parsed label list are both cached
    indefinitely on disk. Delete ``<cache_dir>/ep_online_bundle.*.bin``
    (and the matching ``ep_online_parsed.*.pkl``) to force a full refresh
    when a new EP-online vintage is published.
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

    # Use a pickle cache for parsed labels keyed by download URL so that
    # subsequent runs skip the expensive 5M-row CSV parse entirely.
    url_digest = hashlib.sha256(str(download_url).encode()).hexdigest()[:16]
    parsed_cache = session.cache_dir / f"ep_online_parsed.{url_digest}.pkl"
    if session.use_cache and parsed_cache.exists():
        return pickle.loads(parsed_cache.read_bytes())

    # The ZIP itself is cached keyed by "ep_online_bundle" so a new vintage
    # (new URL) automatically triggers a fresh download.
    zip_bytes = session.get_bytes(
        str(download_url),
        cache_key="ep_online_bundle",
    )
    csv_text = _extract_csv_from_zip(zip_bytes)
    labels = parse_csv(csv_text)

    if session.use_cache:
        parsed_cache.write_bytes(pickle.dumps(labels, protocol=pickle.HIGHEST_PROTOCOL))

    return labels


def parse_csv(csv_text: str) -> list[EnergyLabel]:
    """Parse the raw EP-online CSV into :class:`EnergyLabel` records.

    Exposed separately so tests can construct their own fixture CSV
    without going near the network layer.
    """
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
    rows: list[EnergyLabel] = []
    for raw_row in reader:
        # csv.DictReader assigns None as the key for overflow columns (more
        # values than headers). Skip those entries to avoid downstream errors.
        row = {
            k.strip(): (v.strip() if v else "")
            for k, v in raw_row.items()
            if k is not None
        }
        parsed = _row_to_label(row)
        if parsed is not None:
            rows.append(parsed)
    return rows


# ---------------------------------------------------------------------------
# Row → EnergyLabel
# ---------------------------------------------------------------------------


def _row_to_label(row: dict[str, str]) -> EnergyLabel | None:
    postcode = _normalise_postcode(row.get("Postcode", ""))
    if not postcode:
        return None

    huisnummer_raw = row.get("Huisnummer", "").strip()
    huisletter_raw = row.get("Huisletter", "").strip() or None
    toevoeging_raw = row.get("Huisnummertoevoeging", "").strip() or None
    huisnummer, huisletter, toevoeging = _split_huisnummer(
        huisnummer_raw, huisletter_raw, toevoeging_raw
    )
    if huisnummer is None:
        return None

    bag_vbo_raw = row.get("BAGVerblijfsobjectID", "").strip()
    return EnergyLabel(
        postcode=postcode,
        huisnummer=huisnummer,
        huisletter=huisletter,
        toevoeging=toevoeging,
        bag_verblijfsobject_id=bag_vbo_raw or None,
        energieklasse=_optional(row.get("Energieklasse")),
        registratiedatum=_parse_yyyymmdd(row.get("Registratiedatum", "")),
        opnamedatum=_parse_yyyymmdd(row.get("Opnamedatum", "")),
        geldig_tot=_parse_yyyymmdd(row.get("GeldigTot", "")),
        # Column names from EP-online v5 CSV (as of 2026-04):
        energieindex=_parse_dutch_float(row.get("EnergieIndex", "") or row.get("Energieindex", "")),
        primaire_fossiele_energie=_parse_dutch_float(
            row.get("PrimaireFossieleEnergie", "") or row.get("Energiebehoefte", "")
        ),
        aandeel_hernieuwbare_energie=_parse_dutch_float(
            row.get("AandeelHernieuwbareEnergie", "")
        ),
        berekende_co2_emissie=_parse_dutch_float(
            row.get("BerekendeCO2Emissie", "") or row.get("BerekendeCo2Emissie", "")
        ),
        gebouwtype=_optional(row.get("Gebouwtype") or row.get("GebouwType")),
        gebouwsubtype=_optional(row.get("GebouwSubtype") or row.get("Gebouwsubtype")),
        gebruiksoppervlakte_thermische_zone=_parse_dutch_float(
            row.get("GebruiksoppervlakteThermischeZone", "")
            or row.get("GebruiksoppervlaktethermischeZone", "")
            or row.get("GebruiksOppervlakteThermischeZone", "")
        ),
        compactheid=_parse_dutch_float(row.get("Compactheid", "")),
        raw=row,
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


def _parse_dutch_float(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _optional(raw: Any) -> str | None:
    if raw in (None, ""):
        return None
    return str(raw).strip() or None


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
