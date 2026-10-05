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


def run_optional(name: str) -> None:
    """Corre um passo que nunca deve travar a geracao (ex.: depende de um site externo)."""
    print(f"\n=== {name} (opcional) ===")
    try:
        proc = subprocess.run([sys.executable, str(SCRIPTS / name)], cwd=ROOT, timeout=1500)
        if proc.returncode:
            print(f"Aviso: {name} terminou com codigo {proc.returncode}; continua com os dados existentes.")
    except Exception as exc:  # noqa: BLE001
        print(f"Aviso: {name} falhou ({exc}); continua com os dados existentes.")


def main() -> int:
    # Precos AutoUnion do site publico para a coluna AutoUnion do Rate Shop (public/data/rateshop-autounion-site.json).
    # O ficheiro gerado e publicado no GitHub Pages junto com o resto de public/.
    run_optional("update_autounion_site.py")
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
