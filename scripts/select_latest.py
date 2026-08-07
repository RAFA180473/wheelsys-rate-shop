#!/usr/bin/env python3
"""Select the newest SharePoint file for each logical file family.

Priority:
1. Date embedded in filename.
2. Filesystem modification time when no filename date is available.

Selected files are copied from data/incoming to data/selected and a JSON
manifest is written at repository root.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "data" / "incoming"
SELECTED = ROOT / "data" / "selected"
MANIFEST = ROOT / "selection_manifest.json"

DATE_PATTERNS = [
    (re.compile(r"(?<!\d)(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](20\d{2})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)"), "dmy2"),
]


@dataclass(frozen=True)
class Candidate:
    path: Path
    family: str
    effective_date: datetime
    method: str


def extract_date(name: str) -> tuple[Optional[datetime], Optional[re.Match[str]]]:
    stem = Path(name).stem
    for pattern, order in DATE_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        try:
            a, b, c = (int(x) for x in match.groups())
            if order == "ymd":
                dt = datetime(a, b, c)
            elif order == "dmy":
                dt = datetime(c, b, a)
            else:
                dt = datetime(2000 + c, b, a)
            return dt, match
        except ValueError:
            continue
    return None, None


def normalize_family(path: Path, date_match: Optional[re.Match[str]]) -> str:
    stem = path.stem
    if date_match:
        stem = stem[: date_match.start()] + stem[date_match.end() :]
    stem = re.sub(r"[-_. ]+", "_", stem).strip("_").lower()
    return f"{stem}{path.suffix.lower()}"


def candidate_for(path: Path) -> Candidate:
    filename_date, match = extract_date(path.name)
    if filename_date is not None:
        effective = filename_date
        method = "filename_date"
    else:
        effective = datetime.fromtimestamp(path.stat().st_mtime)
        method = "modified_time"
    return Candidate(
        path=path,
        family=normalize_family(path, match),
        effective_date=effective,
        method=method,
    )


def main() -> int:
    INCOMING.mkdir(parents=True, exist_ok=True)
    SELECTED.mkdir(parents=True, exist_ok=True)

    files = [p for p in INCOMING.iterdir() if p.is_file() and p.name != ".gitkeep"]
    if not files:
        print(f"Nenhum ficheiro encontrado em {INCOMING}")
        return 1

    candidates = [candidate_for(path) for path in files]
    latest: dict[str, Candidate] = {}

    for cand in candidates:
        current = latest.get(cand.family)
        if current is None or (cand.effective_date, cand.path.name) > (
            current.effective_date,
            current.path.name,
        ):
            latest[cand.family] = cand

    for existing in SELECTED.iterdir():
        if existing.is_file() and existing.name != ".gitkeep":
            existing.unlink()

    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rule": "latest file per family; filename date first, modified time fallback",
        "selected": [],
    }

    print("\nFicheiros selecionados:")
    for family, cand in sorted(latest.items()):
        destination = SELECTED / cand.path.name
        shutil.copy2(cand.path, destination)
        record = {
            "family": family,
            "source": str(cand.path.relative_to(ROOT)),
            "selected": str(destination.relative_to(ROOT)),
            "effective_date": cand.effective_date.isoformat(timespec="seconds"),
            "selection_method": cand.method,
        }
        manifest["selected"].append(record)
        print(
            f"- {family}: {cand.path.name} "
            f"[{cand.effective_date.date()} | {cand.method}]"
        )

    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nManifesto criado: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
