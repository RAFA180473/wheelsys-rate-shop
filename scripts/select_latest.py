#!/usr/bin/env python3
"""Seleciona a tarifa mais recente por familia BK/FCI/VAN.

Quando sharepoint_sync_manifest.json existe, ele e a fonte oficial para a data
de modificacao e para o ficheiro selecionado. Caso contrario, mantem fallback
para historico Git/mtime, util em execucoes locais antigas.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "data" / "incoming"
SELECTED = ROOT / "data" / "selected"
MANIFEST = ROOT / "selection_manifest.json"
SP_MANIFEST = ROOT / "sharepoint_sync_manifest.json"


@dataclass(frozen=True)
class Candidate:
    path: Path
    family: str
    effective_ts: float
    method: str


def family_for(path: Path) -> str | None:
    name = path.stem.upper()
    if "COMMERCIAL_VAN" in name or "VAN" in name:
        return "VAN"
    if "FCI" in name:
        return "FCI"
    if "BK" in name:
        return "BK"
    return None


def git_last_change(path: Path) -> float | None:
    rel = path.relative_to(ROOT)
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(rel)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        text = proc.stdout.strip()
        return float(text) if text else None
    except Exception:
        return None


def parse_iso(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def sharepoint_candidates() -> list[Candidate]:
    if not SP_MANIFEST.exists():
        return []
    data = json.loads(SP_MANIFEST.read_text(encoding="utf-8"))
    result: list[Candidate] = []
    for rec in data.get("selected", []):
        family = str(rec.get("family") or "").upper()
        filename = str(rec.get("filename") or "")
        modified = str(rec.get("lastModifiedDateTime") or "")
        if family not in {"BK", "FCI", "VAN"} or not filename or not modified:
            continue
        path = INCOMING / filename
        if not path.exists():
            raise RuntimeError(f"Ficheiro do manifesto SharePoint nao existe em incoming: {filename}")
        result.append(Candidate(path, family, parse_iso(modified), "sharepoint_lastModifiedDateTime"))
    return result


def fallback_candidates() -> list[Candidate]:
    result: list[Candidate] = []
    for path in INCOMING.iterdir():
        if not path.is_file() or path.name == ".gitkeep" or path.suffix.lower() not in {".xlsx", ".xlsm"}:
            continue
        family = family_for(path)
        if not family:
            continue
        git_ts = git_last_change(path)
        if git_ts is not None:
            result.append(Candidate(path, family, git_ts, "git_last_change"))
        else:
            result.append(Candidate(path, family, path.stat().st_mtime, "filesystem_mtime_fallback"))
    return result


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> int:
    INCOMING.mkdir(parents=True, exist_ok=True)
    SELECTED.mkdir(parents=True, exist_ok=True)

    candidates = sharepoint_candidates() or fallback_candidates()
    if not candidates:
        print(f"Nenhum Excel BK/FCI/VAN encontrado em {INCOMING}")
        return 1

    latest: dict[str, Candidate] = {}
    for cand in candidates:
        current = latest.get(cand.family)
        if current is None or (cand.effective_ts, cand.path.name) > (current.effective_ts, current.path.name):
            latest[cand.family] = cand

    missing = [family for family in ("BK", "FCI", "VAN") if family not in latest]
    if missing:
        print("Familias em falta: " + ", ".join(missing))
        return 1

    for existing in SELECTED.iterdir():
        if existing.is_file() and existing.name != ".gitkeep":
            existing.unlink()

    rule = (
        "latest per family BK/FCI/VAN by SharePoint lastModifiedDateTime"
        if SP_MANIFEST.exists()
        else "latest per family BK/FCI/VAN by Git change; filename dates ignored"
    )
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rule": rule,
        "selected": [],
        "available_families": sorted(latest),
    }

    print("\nFicheiros selecionados:")
    for family in ("BK", "FCI", "VAN"):
        cand = latest[family]
        destination = SELECTED / cand.path.name
        shutil.copy2(cand.path, destination)
        manifest["selected"].append({
            "family": family,
            "source": str(cand.path.relative_to(ROOT)),
            "selected": str(destination.relative_to(ROOT)),
            "effective_datetime": iso(cand.effective_ts),
            "selection_method": cand.method,
        })
        print(f"- {family}: {cand.path.name} [{iso(cand.effective_ts)} | {cand.method}]")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nManifesto criado: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
