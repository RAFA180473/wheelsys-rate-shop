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
SELECTION_MANIFEST = ROOT / "selection_manifest.json"

DECL = re.compile(r"\b(?:const|let|var)\s+RATES\s*=\s*")


def extract_rates_object(html: str):
    matches = list(DECL.finditer(html))
    if len(matches) != 1:
        raise ValueError(f"public/index.html tem {len(matches)} declarações RATES (esperado: 1)")
    m = matches[0]
    i = m.end()
    while i < len(html) and html[i].isspace():
        i += 1
    if i >= len(html) or html[i] != "{":
        raise ValueError("Declaração RATES não começa por objeto JSON")

    start = i
    depth = 0
    in_string = False
    quote = ""
    escape = False
    for j in range(start, len(html)):
        ch = html[j]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            continue
        if ch in ('"', "'", "`"):
            in_string = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start:j + 1])
    raise ValueError("Não foi possível extrair RATES do HTML")


def main() -> int:
    errors: list[str] = []
    data = None

    if not RATES.exists():
        errors.append("public/data/rates.json não existe")
    else:
        data = json.loads(RATES.read_text(encoding="utf-8"))
        for tariff in ("BK", "FCI", "VAN"):
            if tariff not in data:
                errors.append(f"Tarifário {tariff} em falta")
                continue
            total = sum(len(data[tariff].get(loc, [])) for loc in ("Lisboa", "Porto", "Faro"))
            if total == 0:
                errors.append(f"Tarifário {tariff} não tem linhas")
            for loc in ("Lisboa", "Porto", "Faro"):
                if loc not in data[tariff]:
                    errors.append(f"Localização {loc} em falta em {tariff}")

    if HTML.exists():
        html = HTML.read_text(encoding="utf-8")
        try:
            html_rates = extract_rates_object(html)
            if data is not None and html_rates != data:
                errors.append("RATES embutido em public/index.html não é igual a public/data/rates.json")
        except Exception as exc:
            errors.append(str(exc))

        for marker in (
            "Painel de Ajuste de Tarifas",
            "btnExport",
            "XLSX",
            "Estações a visualizar",
            "Veículos comerciais",
            "VW Caddy Cargo",
            "VW Transporter Cargo",
            "VW Crafter Cargo 9900 L",
            "syncAdjustLocCheckboxes",
            "RateGroup Commercial VAN",
        ):
            if marker not in html:
                errors.append(f"Marcador funcional ausente no HTML: {marker}")

        if html.count('id="rateSourceMeta"') != 1:
            errors.append("public/index.html deve ter exatamente 1 bloco rateSourceMeta")

        if 'value="VAN"' not in html and "value='VAN'" not in html:
            errors.append("Opção VAN não encontrada no seletor de tarifa")
    else:
        errors.append("public/index.html não existe")

    if SELECTION_MANIFEST.exists():
        selection = json.loads(SELECTION_MANIFEST.read_text(encoding="utf-8"))
        families = {str(x.get("family") or "").upper() for x in selection.get("selected", [])}
        for tariff in ("BK", "FCI", "VAN"):
            if tariff not in families:
                errors.append(f"selection_manifest.json não selecionou {tariff}")
    else:
        errors.append("selection_manifest.json não existe")

    if BUILD_MANIFEST.exists():
        manifest = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
        built = {str(x.get("tariff") or "").upper() for x in manifest.get("sources", [])}
        for tariff in ("BK", "FCI", "VAN"):
            if tariff not in built:
                errors.append(f"build_manifest.json não contém fonte {tariff}")
        if manifest.get("warnings"):
            print(f"AVISO: {len(manifest['warnings'])} aviso(s) no build_manifest.json")
    else:
        errors.append("build_manifest.json não existe")

    if errors:
        print("VALIDAÇÃO FALHOU:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("VALIDAÇÃO OK: BK + FCI + VAN presentes e HTML sincronizado com rates.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
