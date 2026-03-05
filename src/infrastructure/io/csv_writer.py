# finanzmanager/infrastructure/io/csv_writer.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def write_dicts_to_csv(
    path: str | Path,
    rows: Iterable[dict],
    *,
    fieldnames: list[str],
    delimiter: str = ";",
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
