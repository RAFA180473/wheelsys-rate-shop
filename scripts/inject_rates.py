#!/usr/bin/env python3
"""Inject rates and selected-source metadata into the standalone Rate Shop HTML."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "public" / "index.template.html"
RATES_JSON = ROOT / "public" / "data" / "rates.json"
MANIFEST = ROOT / "selection_manifest.json"
OUTPUT = ROOT / "public" / "index.html"

DECL = re.compile(r"\b(const|let|var)\s+RATES\s*=\s*")
SELECT_RE = re.compile(r'(<select\s+id=["\']fileFilterSel["\'][^>]*>.*?</select>)', re.I | re.S)
OLD_META_BOX_RE = re.compile(r'<div\s+id=["\']rateSourceMeta["\'][^>]*>.*?</div>', re.I | re.S)
OLD_META_SCRIPT_RE = re.compile(
    r'<script>\s*// Source metadata injected automatically from selection_manifest\.json.*?</script>',
    re.I | re.S,
)
OLD_META_CSS_RE = re.compile(
    r'/\* source-version badge injected by build \*/.*?#rateSourceFile\{[^}]*\}\s*',
    re.I | re.S,
)


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


def fmt_date(value: str | None) -> str:
    if not value:
        return "data não disponível"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return value[:10]


def source_metadata() -> dict[str, dict[str, str]]:
    meta = {
        key: {"filename": "", "date": "", "method": "", "status": "missing"}
        for key in ("BK", "FCI", "VAN")
    }
    if not MANIFEST.exists():
        return meta

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for rec in data.get("selected", []):
        family = str(rec.get("family") or "").upper()
        source = str(rec.get("source") or rec.get("selected") or "")
        name = Path(source).name

        if family not in meta:
            low = name.lower()
            family = "VAN" if "van" in low else "FCI" if "fci" in low else "BK" if "bk" in low else ""
        if family not in meta:
            continue

        effective = rec.get("effective_datetime") or rec.get("effective_date")
        meta[family] = {
            "filename": name,
            "date": fmt_date(effective),
            "method": str(rec.get("selection_method") or ""),
            "status": "ok",
        }
    return meta


def clean_previous_injection(html: str) -> str:
    # A template may have been copied from a previously generated index.html.
    # Remove previously injected UI/script/CSS so stale metadata cannot survive.
    html = OLD_META_SCRIPT_RE.sub("", html)
    html = OLD_META_BOX_RE.sub("", html)
    html = OLD_META_CSS_RE.sub("", html)
    return html


def ensure_van_support(html: str) -> str:
    # Add VAN to the operational WORK/ORIG structures used by the page.
    html = html.replace("['BK','FCI'].forEach(fk=>", "['BK','FCI','VAN'].forEach(fk=>")

    # Add VAN option to the existing tariff selector if it is not already present.
    m = SELECT_RE.search(html)
    if m and 'value="VAN"' not in m.group(1) and "value='VAN'" not in m.group(1):
        updated_select = re.sub(
            r'</select>\s*$',
            '<option value="VAN">RateGroup Commercial VAN</option></select>',
            m.group(1),
            flags=re.I,
        )
        html = html[:m.start()] + updated_select + html[m.end():]
    return html


def inject_source_ui(html: str, meta: dict[str, dict[str, str]]) -> str:
    if not SELECT_RE.search(html):
        print("AVISO: seletor #fileFilterSel não encontrado; metadados de versão não foram mostrados.")
        return html

    box = '''\n<div id="rateSourceMeta" class="rate-source-meta" aria-live="polite">\n  <span id="rateSourceDot" class="rate-source-dot"></span>\n  <span><b>Última versão usada:</b> <span id="rateSourceFile"></span><br>\n  <span class="rate-source-sub"><b>Data detetada:</b> <span id="rateSourceDate"></span></span></span>\n</div>'''
    html = SELECT_RE.sub(lambda m: m.group(1) + box, html, count=1)

    css = '''\n/* source-version badge injected by build */\n.rate-source-meta{display:flex;gap:8px;align-items:flex-start;margin-top:7px;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--mist-100);font-size:11px;line-height:1.35;color:var(--navy-700)}\n.rate-source-dot{width:9px;height:9px;border-radius:50%;background:var(--up);margin-top:3px;flex:0 0 9px;box-shadow:0 0 0 3px rgba(0,168,136,.10)}\n.rate-source-meta.missing .rate-source-dot{background:var(--coral-500);box-shadow:0 0 0 3px rgba(217,97,79,.10)}\n.rate-source-sub{color:var(--steel-500)}\n#rateSourceFile{font-family:'IBM Plex Mono',monospace;word-break:break-all}\n'''
    if "</style>" in html:
        html = html.replace("</style>", css + "</style>", 1)

    script = f'''\n<script>\n// Source metadata injected automatically from selection_manifest.json\nconst RATE_SOURCE_META = {json.dumps(meta, ensure_ascii=False, separators=(",", ":"))};\n(function(){{\n  const sel = document.getElementById('fileFilterSel');\n  const box = document.getElementById('rateSourceMeta');\n  const fileEl = document.getElementById('rateSourceFile');\n  const dateEl = document.getElementById('rateSourceDate');\n  if(!sel || !box || !fileEl || !dateEl) return;\n  const baseLabels = {{\n    BK:'RateGroup BK (CDW)',\n    FCI:'RateGroup BK FCI (CDW + FCI)',\n    VAN:'RateGroup Commercial VAN'\n  }};\n  Array.from(sel.options).forEach(opt=>{{\n    const m = RATE_SOURCE_META[opt.value];\n    opt.textContent = baseLabels[opt.value] || opt.textContent;\n    if(m && m.status === 'ok' && m.date) opt.textContent += ' — ficheiro ' + m.date;\n  }});\n  function refreshSourceVersion(){{\n    const m = RATE_SOURCE_META[sel.value] || {{status:'missing',filename:'',date:''}};\n    const ok = m.status === 'ok';\n    box.classList.toggle('missing', !ok);\n    fileEl.textContent = ok ? m.filename : 'ficheiro não identificado';\n    dateEl.textContent = ok ? m.date : 'não disponível';\n    box.title = ok && m.method ? 'Seleção: ' + m.method : '';\n  }}\n  sel.addEventListener('change', refreshSourceVersion);\n  refreshSourceVersion();\n}})();\n</script>\n'''
    if "</body>" in html:
        html = html.replace("</body>", script + "</body>", 1)
    else:
        html += script
    return html


def main() -> int:
    if not TEMPLATE.exists():
        print(f"Template não encontrado: {TEMPLATE}")
        return 1
    if not RATES_JSON.exists():
        print(f"Dados não encontrados: {RATES_JSON}")
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    html = clean_previous_injection(html)
    html = ensure_van_support(html)

    rates = json.loads(RATES_JSON.read_text(encoding="utf-8"))
    span, error = find_rates_span(html)
    if error:
        print(error)
        return 2

    start, end, keyword = span
    replacement = f"{keyword} RATES = " + json.dumps(rates, ensure_ascii=False, separators=(",", ":")) + ";"
    updated = html[:start] + replacement + html[end:]
    updated = inject_source_ui(updated, source_metadata())
    OUTPUT.write_text(updated, encoding="utf-8")

    print(f"HTML gerado: {OUTPUT}")
    print(f"Declaração RATES substituída com sucesso ({keyword}).")
    print("Versão dos ficheiros BK/FCI/VAN adicionada ao seletor de tarifa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
