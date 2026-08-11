#!/usr/bin/env python3
"""Sincroniza automaticamente as tarifas mais recentes do SharePoint.

Fonte oficial:
- SharePoint drive TARIFAS
- pasta Comercial/Brokers/Rates/Tarifas/files 2027

Seleciona sempre o ficheiro .xlsx/.xlsm com lastModifiedDateTime mais recente
por familia BK, FCI e VAN. Os numeros existentes no nome do ficheiro nao sao
usados para decidir qual e o mais recente.

Credenciais obrigatorias no ambiente:
- MS_TENANT_ID
- MS_CLIENT_ID
- MS_CLIENT_SECRET

Variaveis opcionais:
- SHAREPOINT_DRIVE_ID
- SHAREPOINT_FOLDER_PATH
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "data" / "incoming"
SYNC_MANIFEST = ROOT / "sharepoint_sync_manifest.json"

DEFAULT_DRIVE_ID = "b!xwmEBgEH00ujiRgMsJd2Yv53BYWpg_FEgcR3FtNZmn4HGYIuutM5S5XGcFz-a35B"
DEFAULT_FOLDER_PATH = "Comercial/Brokers/Rates/Tarifas/files 2027"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Variavel obrigatoria {name} nao configurada. "
            "Configure os GitHub Actions Secrets antes de publicar."
        )
    return value


def request_json(url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} em {url}: {detail[:800]}") from exc


def get_token() -> str:
    tenant = require_env("MS_TENANT_ID")
    client_id = require_env("MS_CLIENT_ID")
    client_secret = require_env("MS_CLIENT_SECRET")
    token_url = f"https://login.microsoftonline.com/{urllib.parse.quote(tenant)}/oauth2/v2.0/token"
    form = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode("ascii")
    payload = request_json(
        token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=form,
    )
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("Microsoft Graph nao devolveu access_token.")
    return token


def graph_json(path_or_url: str, token: str) -> dict[str, Any]:
    url = path_or_url if path_or_url.startswith("https://") else GRAPH_ROOT + path_or_url
    return request_json(url, headers={"Authorization": f"Bearer {token}"})


def family_for(name: str) -> str | None:
    upper = name.upper()
    if not upper.endswith((".XLSX", ".XLSM")):
        return None
    if "COMMERCIAL_VAN" in upper or "VAN" in upper:
        return "VAN"
    if "FCI" in upper:
        return "FCI"
    if "BK" in upper:
        return "BK"
    return None


def parse_graph_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def list_folder_files(token: str, drive_id: str, folder_path: str) -> list[dict[str, Any]]:
    encoded_path = urllib.parse.quote(folder_path.strip("/"), safe="/")
    url = (
        f"{GRAPH_ROOT}/drives/{urllib.parse.quote(drive_id, safe='')}/root:/"
        f"{encoded_path}:/children?$top=999&$select=id,name,lastModifiedDateTime,file,size,webUrl"
    )
    items: list[dict[str, Any]] = []
    while url:
        payload = graph_json(url, token)
        items.extend(payload.get("value", []))
        url = str(payload.get("@odata.nextLink") or "")
    return [item for item in items if item.get("file")]


def choose_latest(files: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in files:
        family = family_for(str(item.get("name") or ""))
        if not family:
            continue
        modified = str(item.get("lastModifiedDateTime") or "")
        if not modified:
            continue
        current = latest.get(family)
        if current is None:
            latest[family] = item
            continue
        cur_dt = parse_graph_datetime(str(current["lastModifiedDateTime"]))
        new_dt = parse_graph_datetime(modified)
        if (new_dt, str(item.get("name") or "")) > (cur_dt, str(current.get("name") or "")):
            latest[family] = item
    missing = [family for family in ("BK", "FCI", "VAN") if family not in latest]
    if missing:
        raise RuntimeError("Familias em falta no SharePoint: " + ", ".join(missing))
    return latest


def download_file(token: str, drive_id: str, item_id: str, destination: Path) -> None:
    url = f"{GRAPH_ROOT}/drives/{urllib.parse.quote(drive_id, safe='')}/items/{urllib.parse.quote(item_id, safe='')}/content"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp, destination.open("wb") as out:
            shutil.copyfileobj(resp, out)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Falha a descarregar {destination.name}: HTTP {exc.code}: {detail[:500]}") from exc
    if destination.stat().st_size == 0:
        raise RuntimeError(f"Download vazio: {destination.name}")


def clear_runtime_incoming() -> None:
    INCOMING.mkdir(parents=True, exist_ok=True)
    for path in INCOMING.iterdir():
        if path.is_file() and path.name != ".gitkeep" and path.suffix.lower() in {".xlsx", ".xlsm"}:
            path.unlink()


def main() -> int:
    try:
        token = get_token()
        drive_id = os.environ.get("SHAREPOINT_DRIVE_ID", DEFAULT_DRIVE_ID).strip() or DEFAULT_DRIVE_ID
        folder_path = os.environ.get("SHAREPOINT_FOLDER_PATH", DEFAULT_FOLDER_PATH).strip() or DEFAULT_FOLDER_PATH

        files = list_folder_files(token, drive_id, folder_path)
        latest = choose_latest(files)

        # Remove tarifas antigas apenas no workspace do Action. Estes ficheiros nao sao
        # adicionados ao commit; em cada execucao voltam a ser obtidos do SharePoint.
        clear_runtime_incoming()

        manifest: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "Microsoft SharePoint via Microsoft Graph",
            "drive_id": drive_id,
            "folder_path": folder_path,
            "selection_rule": "latest lastModifiedDateTime per family; filename dates ignored",
            "selected": [],
        }

        print("Ficheiros SharePoint selecionados:")
        for family in ("BK", "FCI", "VAN"):
            item = latest[family]
            name = str(item["name"])
            destination = INCOMING / name
            download_file(token, drive_id, str(item["id"]), destination)
            rec = {
                "family": family,
                "filename": name,
                "item_id": str(item["id"]),
                "lastModifiedDateTime": str(item["lastModifiedDateTime"]),
                "size": item.get("size"),
                "webUrl": item.get("webUrl"),
                "downloaded_to": str(destination.relative_to(ROOT)),
            }
            manifest["selected"].append(rec)
            print(f"- {family}: {name} | {item['lastModifiedDateTime']}")

        SYNC_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Manifesto SharePoint criado: {SYNC_MANIFEST}")
        return 0
    except Exception as exc:
        print(f"SINCRONIZACAO SHAREPOINT FALHOU: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
