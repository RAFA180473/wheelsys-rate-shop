#!/usr/bin/env python3
"""Inject public/data/rates.json into the current standalone Rate Shop HTML.

Put the current HTML at public/index.template.html. This script replaces only
`const RATES = ...;` and writes public/index.html, preserving the rest of UI/JS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "public" / "index.template.html"
RATES_JSON = ROOT / "public" / "data" / "rates.json"
OUTPUT = ROOT / "public" / "index.html"

PATTERN = re.compile(r"const\s+RATES\s*=\s*\{.*?\};", re.DOTALL)


def main() -> int:
    if not TEMPLATE.exists():
        print(f"Template não encontrado: {TEMPLATE}")
        return 1
    if not RATES_JSON.exists():
        print(f"Dados não encontrados: {RATES_JSON}")
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    rates = json.loads(RATES_JSON.read_text(encoding="utf-8"))
    replacement = "const RATES = " + json.dumps(rates, ensure_ascii=False, separators=(",", ":")) + ";"

    updated, count = PATTERN.subn(replacement, html, count=1)
    if count != 1:
        print("Não foi possível localizar exatamente uma definição `const RATES = {...};`.")
        return 2
    OUTPUT.write_text(updated, encoding="utf-8")
    print(f"HTML gerado: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
