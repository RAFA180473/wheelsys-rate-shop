#!/usr/bin/env python3
"""Converte o Excel de periodos/eventos (uma folha por estacao) em data/periods/periods.json.

Colunas esperadas a partir da linha 3: Inicio, Fim, Semana / periodo, Feriados e ferias,
Eventos locais, Ref. ano anterior, KPIs ano anterior.

Uso: python scripts/import_periods.py [caminho.xlsx]
Sem argumento usa o .xlsx mais recente em data/periods/.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
PERIODS_DIR = ROOT / "data" / "periods"
OUT = PERIODS_DIR / "periods.json"
EXTRA = PERIODS_DIR / "periods_extra.json"
SHEET_TO_LOCATION = {"lisbon": "Lisboa", "lisboa": "Lisboa", "porto": "Porto", "faro": "Faro"}
FIELDS = ("hol", "evt", "ref", "kpi")


def clean(value) -> str:
    return "" if value is None else str(value).strip()


def main() -> int:
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        files = sorted((f for f in PERIODS_DIR.glob("*.xlsx")), key=lambda p: p.stat().st_mtime)
        if not files:
            print(f"Nenhum .xlsx em {PERIODS_DIR}")
            return 1
        src = files[-1]

    wb = load_workbook(src, data_only=True)
    periods: list[dict[str, str]] = []
    info: dict[str, dict[str, dict[str, str]]] = {}
    for ws in wb:
        loc = SHEET_TO_LOCATION.get(ws.title.strip().lower())
        if not loc:
            print(f"Folha ignorada: {ws.title}")
            continue
        loc_periods = []
        info[loc] = {}
        for row in ws.iter_rows(min_row=3, max_col=7, values_only=True):
            start, end = row[0], row[1]
            if not isinstance(start, datetime) or not isinstance(end, datetime):
                continue
            key = f"{start:%d/%m/%Y}|{end:%d/%m/%Y}"
            loc_periods.append({"start": f"{start:%d/%m/%Y}", "end": f"{end:%d/%m/%Y}", "label": clean(row[2])})
            entry = {f: clean(row[3 + i]) for i, f in enumerate(FIELDS)}
            info[loc][key] = {k: v for k, v in entry.items() if v}
        if not periods:
            periods = loc_periods
        elif [(p["start"], p["end"]) for p in periods] != [(p["start"], p["end"]) for p in loc_periods]:
            print(f"ERRO: os periodos da folha {ws.title} nao coincidem com os da primeira folha.")
            return 2

    # Periodos adicionais fora do Excel (ex.: dezembro do ano anterior), sem feriados/eventos associados.
    if EXTRA.exists():
        extra = json.loads(EXTRA.read_text(encoding="utf-8")).get("periods", [])
        periods = sorted(extra + periods, key=lambda p: datetime.strptime(p["start"], "%d/%m/%Y"))

    # Os periodos tem de ser contiguos e sem sobreposicao.
    prev_end = None
    for p in periods:
        s = datetime.strptime(p["start"], "%d/%m/%Y")
        e = datetime.strptime(p["end"], "%d/%m/%Y")
        if e < s or (prev_end is not None and (s - prev_end).days != 1):
            print(f"ERRO: periodo nao contiguo: {p}")
            return 2
        prev_end = e

    OUT.write_text(json.dumps({"source": src.name, "periods": periods, "info": info}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Criado {OUT}: {len(periods)} periodos, estacoes: {', '.join(info)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
