#!/usr/bin/env python3
"""Import an existing standalone Rate Shop HTML as the protected template.

Usage:
    python scripts/import_html.py /path/to/ICONIQ_Rate_Shop_DiscoverCars.html

The source is copied to public/index.template.html only after validating that it
contains exactly one `const RATES = ...;` definition. The UI and all other
JavaScript are left untouched by subsequent builds.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "public" / "index.template.html"
PATTERN = re.compile(r"const\s+RATES\s*=\s*\{.*?\};", re.DOTALL)


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python scripts/import_html.py /caminho/para/ICONIQ_Rate_Shop_DiscoverCars.html")
        return 2
    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.is_file():
        print(f"HTML não encontrado: {source}")
        return 1
    html = source.read_text(encoding="utf-8")
    count = len(PATTERN.findall(html))
    if count != 1:
        print(f"Esperava exatamente 1 definição `const RATES = ...;`; encontrei {count}.")
        return 3
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, TARGET)
    print(f"Template importado: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
