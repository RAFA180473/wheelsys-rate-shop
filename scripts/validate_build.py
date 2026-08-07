#!/usr/bin/env python3
"""Validate generated rates and standalone HTML before publication."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATES = ROOT / "public" / "data" / "rates.json"
HTML = ROOT / "public" / "index.html"
BUILD_MANIFEST = ROOT / "build_manifest.json"

DECL = re.compile(r"\b(?:const|let|var)\s+RATES\s*=\s*\{")


def main() -> int:
    errors: list[str] = []

    if not RATES.exists():
        errors.append("public/data/rates.json não existe")
    else:
        data = json.loads(RATES.read_text(encoding="utf-8"))
        for tariff in ("BK", "FCI"):
            if tariff not in data:
                errors.append(f"Tarifário {tariff} em falta")
                continue
            total = sum(len(data[tariff].get(loc, [])) for loc in ("Lisboa", "Porto", "Faro"))
            if total == 0:
                errors.append(f"Tarifário {tariff} não tem linhas")

        for tariff in ("BK", "FCI"):
            for loc in ("Lisboa", "Porto", "Faro"):
                if tariff in data and loc not in data[tariff]:
                    errors.append(f"Localização {loc} em falta em {tariff}")

    if HTML.exists():
        html = HTML.read_text(encoding="utf-8")
        count = len(DECL.findall(html))
        if count != 1:
            errors.append(f"public/index.html tem {count} declarações RATES (esperado: 1)")

        for marker in ("Painel de Ajuste de Tarifas", "btnExport", "XLSX"):
            if marker not in html:
                errors.append(f"Marcador funcional ausente no HTML: {marker}")
    else:
        errors.append("public/index.html não existe")

    if BUILD_MANIFEST.exists():
        manifest = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
        if manifest.get("warnings"):
            print(f"AVISO: {len(manifest['warnings'])} aviso(s) no build_manifest.json")

    if errors:
        print("VALIDAÇÃO FALHOU:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("VALIDAÇÃO OK: BK + FCI presentes, Lisboa/Porto/Faro estruturados e HTML íntegro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
