#!/usr/bin/env python3
"""Inject public/data/rates.json into the standalone Rate Shop HTML.

Supports const/let/var RATES and replaces the full object using balanced-brace
parsing, avoiding brittle regex matching on a large nested JSON object.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "public" / "index.template.html"
RATES_JSON = ROOT / "public" / "data" / "rates.json"
OUTPUT = ROOT / "public" / "index.html"

DECL = re.compile(r"\b(const|let|var)\s+RATES\s*=\s*")


def find_rates_span(text: str):
    matches = list(DECL.finditer(text))
    if len(matches) != 1:
        return None, f"Foram encontradas {len(matches)} declarações RATES; esperado: 1."

    m = matches[0]
    i = m.end()

    while i < len(text) and text[i].isspace():
        i += 1

    if i >= len(text) or text[i] != "{":
        return None, "A declaração RATES existe, mas não começa por um objeto `{...}`."

    start_obj = i
    depth = 0
    in_string = False
    quote = ""
    escape = False

    for j in range(start_obj, len(text)):
        ch = text[j]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            continue

        if ch in ("'", '"', "`"):
            in_string = True
            quote = ch
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                k = j + 1
                while k < len(text) and text[k].isspace():
                    k += 1
                if k < len(text) and text[k] == ";":
                    k += 1
                return (m.start(), k, m.group(1)), None

    return None, "Não foi possível encontrar o fim do objeto RATES."


def main() -> int:
    if not TEMPLATE.exists():
        print(f"Template não encontrado: {TEMPLATE}")
        return 1
    if not RATES_JSON.exists():
        print(f"Dados não encontrados: {RATES_JSON}")
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    rates = json.loads(RATES_JSON.read_text(encoding="utf-8"))

    span, error = find_rates_span(html)
    if error:
        print(error)
        print("Procura no public/index.template.html por `RATES =` e confirma que existe uma única declaração.")
        return 2

    start, end, keyword = span
    replacement = (
        f"{keyword} RATES = "
        + json.dumps(rates, ensure_ascii=False, separators=(",", ":"))
        + ";"
    )

    updated = html[:start] + replacement + html[end:]
    OUTPUT.write_text(updated, encoding="utf-8")

    print(f"HTML gerado: {OUTPUT}")
    print(f"Declaração RATES substituída com sucesso ({keyword}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
