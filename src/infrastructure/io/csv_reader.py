# infrastructure/io/csv_reader.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _detect_delimiter(sample: str) -> str:
    """
    Robust delimiter detection for common German/Excel exports.
    Prefers ';' in ambiguous cases.
    """
    # Take first non-empty line
    lines = [ln for ln in sample.splitlines() if ln.strip()]
    if not lines:
        return ";"
    line = lines[0]

    candidates = [";", ",", "\t", "|"]
    counts = {c: line.count(c) for c in candidates}
    best = max(counts, key=counts.get)

    # If all are zero, try csv.Sniffer (can still fail)
    if counts[best] == 0:
        try:
            return csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
        except Exception:
            return ";"

    # Prefer ';' if tie
    max_count = counts[best]
    tied = [c for c, n in counts.items() if n == max_count]
    if ";" in tied:
        return ";"
    return best


def read_csv_dicts(
    path: str | Path,
    delimiter: str | None = None,
    encoding: str = "utf-8-sig",
) -> list[dict[str, str]]:
    """
    Reads a CSV file into list[dict]. Handles BOM, trims headers, and supports auto delimiter detection.

    - If delimiter is None: tries to detect ; , TAB | (best effort)
    - Returns values as raw strings (no parsing here).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    # Read a small sample for delimiter detection
    raw = p.read_text(encoding=encoding, errors="replace")
    if delimiter is None:
        delimiter = _detect_delimiter(raw[:4096])

    rows: list[dict[str, str]] = []
    with p.open("r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            return []

        # Normalize headers (strip + remove BOM)
        fieldnames = [(fn or "").replace("\ufeff", "").strip() for fn in reader.fieldnames]
        reader.fieldnames = fieldnames

        for r in reader:
            if r is None:
                continue
            cleaned: dict[str, str] = {}
            for k, v in r.items():
                kk = (k or "").replace("\ufeff", "").strip()
                vv = "" if v is None else str(v).strip()
                cleaned[kk] = vv

            # skip fully empty lines
            if any(v for v in cleaned.values()):
                rows.append(cleaned)

    return rows


def write_csv_dicts(
    path: str | Path,
    rows: list[dict[str, Any]],
    delimiter: str = ";",
    encoding: str = "utf-8-sig",
) -> None:
    """
    Writes list[dict] to CSV. Uses union of all keys as header.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    keys: list[str] = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    with p.open("w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, delimiter=delimiter)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in keys})
