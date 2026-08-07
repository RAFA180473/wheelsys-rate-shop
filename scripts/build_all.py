#!/usr/bin/env python3
"""Run the complete local update pipeline."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(name: str) -> None:
    print(f"\n=== {name} ===")
    proc = subprocess.run([sys.executable, str(SCRIPTS / name)], cwd=ROOT)
    if proc.returncode:
        raise SystemExit(proc.returncode)


def main() -> int:
    run("select_latest.py")
    run("build_rates.py")
    template = ROOT / "public" / "index.template.html"
    if not template.exists():
        print("\nERRO: falta public/index.template.html.")
        print("Importa primeiro o HTML real com: python scripts/import_html.py /caminho/ficheiro.html")
        return 2
    run("inject_rates.py")
    run("validate_build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
