#!/usr/bin/env python3
"""Seleciona o ficheiro mais recente de cada familia de tarifas.

Familias suportadas:
- BK
- FCI
- VAN

Regra importante:
Os numeros existentes nos nomes (ex.: 080826, 150826, 300627) podem ser
periodos de vigencia e NAO sao usados para decidir qual e o ficheiro mais
recente. Em repositorios Git, o mtime do filesystem tambem nao e fiavel apos
checkout. Por isso usamos a data do ultimo commit que alterou cada ficheiro.

Se um ficheiro ainda nao tiver historico Git, usamos mtime apenas como fallback.
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


def candidate_for(path: Path) -> Candidate | None:
    family = family_for(path)
    if not family:
        return None
    git_ts = git_last_change(path)
    if git_ts is not None:
        return Candidate(path, family, git_ts, "git_last_change")
    return Candidate(path, family, path.stat().st_mtime, "filesystem_mtime_fallback")


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> int:
    INCOMING.mkdir(parents=True, exist_ok=True)
    SELECTED.mkdir(parents=True, exist_ok=True)

    files = [
        p for p in INCOMING.iterdir()
        if p.is_file() and p.name != ".gitkeep" and p.suffix.lower() in {".xlsx", ".xlsm"}
    ]
    if not files:
        print(f"Nenhum Excel encontrado em {INCOMING}")
        return 1

    candidates = [c for p in files if (c := candidate_for(p)) is not None]
    if not candidates:
        print("Nenhum ficheiro reconhecido como BK, FCI ou VAN.")
        return 1

    latest: dict[str, Candidate] = {}
    for cand in candidates:
        current = latest.get(cand.family)
        if current is None or (cand.effective_ts, cand.path.name) > (current.effective_ts, current.path.name):
            latest[cand.family] = cand

    for existing in SELECTED.iterdir():
        if existing.is_file() and existing.name != ".gitkeep":
            existing.unlink()

    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rule": "latest per family BK/FCI/VAN by last Git change; filename dates ignored",
        "selected": [],
        "available_families": sorted(latest),
    }

    print("\nFicheiros selecionados:")
    for family in ("BK", "FCI", "VAN"):
        cand = latest.get(family)
        if not cand:
            print(f"- {family}: NAO ENCONTRADO")
            continue
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
