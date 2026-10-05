#!/usr/bin/env python3
"""Atualiza public/data/rateshop-autounion-site.json com precos do site publico da AutoUnion.

Usado pela coluna "AutoUnion" do Rate Shop. Para cada estacao (Lisboa/Porto/Faro) pede uma cotacao
de 7 dias (11:00) a API publica /api/v1/rental/quote: diaria para os proximos DAILY_DAYS dias e,
a partir dai, ao sabado ate ao fim do ano seguinte. Guarda totalRate (total 7 dias) por codigo de grupo.

Nunca falha o workflow: se o site nao responder (ex.: bloqueio a pedidos de servidor), mantem o
ficheiro existente e apenas remove datas passadas.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data" / "rateshop-autounion-site.json"
API = "https://autounionrentacar.com/api/v1/rental/quote"
LOCATIONS = {
    "Lisboa": "13335d02-2f7e-4cdf-a257-a30188df79b8",
    "Porto": "1f8ba899-41d1-4843-8f6a-84882a2d9a63",
    "Faro": "578f4610-71ef-4b88-8a7a-e8f1965e6775",
}
DAILY_DAYS = 90
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://autounionrentacar.com",
    "Referer": "https://autounionrentacar.com/pt-PT/landing",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36",
}


def quote(guid: str, d: date) -> dict[str, float] | None:
    body = json.dumps({
        "pickupLocationCode": guid, "dropoffLocationCode": guid,
        "dateFrom": d.isoformat(), "timeFrom": "11:00",
        "dateTo": (d + timedelta(days=7)).isoformat(), "timeTo": "11:00",
    }).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(API, data=body, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            groups = (data.get("data") or {}).get("groups") or []
            if groups:
                return {g["code"]: float(g["totalRate"]) for g in groups if g.get("totalRate") is not None}
        except Exception as exc:  # noqa: BLE001
            print(f"  aviso {d} tentativa {attempt + 1}: {exc}")
        time.sleep(0.8 * (attempt + 1))
    return None


def target_dates(today: date) -> list[date]:
    dates = [today + timedelta(days=i) for i in range(1, DAILY_DAYS + 1)]
    d = today + timedelta(days=DAILY_DAYS + 1)
    while d.weekday() != 5:  # sabado
        d += timedelta(days=1)
    end = date(today.year + 1, 12, 31)
    while d <= end:
        dates.append(d)
        d += timedelta(days=7)
    return dates


def main() -> int:
    today = date.today()
    existing = {}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            existing = {}
    locations = existing.get("locations") or {}

    # Teste rapido: se o site nao responder ao primeiro pedido, nao insiste.
    probe = quote(LOCATIONS["Lisboa"], today + timedelta(days=7))
    ok = 0
    if probe is None:
        print("Site AutoUnion sem resposta a pedidos do servidor; mantem-se o ficheiro existente.")
    else:
        for loc, guid in LOCATIONS.items():
            by_code = locations.setdefault(loc, {})
            for d in target_dates(today):
                res = quote(guid, d)
                if res is None:
                    continue
                ok += 1
                for code, val in res.items():
                    by_code.setdefault(code, {})[d.isoformat()] = val
                time.sleep(0.15)
        print(f"Cotacoes obtidas: {ok}")

    # Remove datas passadas
    cutoff = today.isoformat()
    for loc in locations.values():
        for code in list(loc):
            loc[code] = {k: v for k, v in sorted(loc[code].items()) if k >= cutoff}
            if not loc[code]:
                del loc[code]

    if ok or not OUT.exists():
        existing["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds") if ok else existing.get("generatedAt")
    existing.update({
        "schemaVersion": 1,
        "source": "AutoUnion Rent A Car - site publico (autounionrentacar.com), API /api/v1/rental/quote, 7 dias 11:00",
        "locationCodes": LOCATIONS,
        "locations": locations,
    })
    OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
