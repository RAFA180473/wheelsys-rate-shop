#!/usr/bin/env python3
"""Inject rates, source metadata and Rate Shop navigation into the standalone HTML."""
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
OLD_META_SCRIPT_RE = re.compile(r'<script>\s*// Source metadata injected automatically from selection_manifest\.json.*?</script>', re.I | re.S)
OLD_SYNC_SCRIPT_RE = re.compile(r'<script>\s*// Wheelsys location/station sync and Rate Shop page mode.*?</script>', re.I | re.S)
OLD_META_CSS_RE = re.compile(r'/\* source-version badge injected by build \*/.*?#rateSourceFile\{[^}]*\}\s*', re.I | re.S)
OLD_NAV_CSS_RE = re.compile(r'/\* Rate Shop navigation injected by build \*/.*?\.rate-shop-standalone-back:hover\{[^}]*\}\s*', re.I | re.S)


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
    meta = {key: {"filename": "", "date": "", "method": "", "status": "missing"} for key in ("BK", "FCI", "VAN")}
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
    html = OLD_META_SCRIPT_RE.sub("", html)
    html = OLD_SYNC_SCRIPT_RE.sub("", html)
    html = OLD_META_BOX_RE.sub("", html)
    html = OLD_META_CSS_RE.sub("", html)
    html = OLD_NAV_CSS_RE.sub("", html)
    return html


def ensure_van_support(html: str) -> str:
    html = html.replace("['BK','FCI'].forEach(fk=>", "['BK','FCI','VAN'].forEach(fk=>")
    m = SELECT_RE.search(html)
    if m and 'value="VAN"' not in m.group(1) and "value='VAN'" not in m.group(1):
        updated_select = re.sub(r'</select>\s*$', '<option value="VAN">RateGroup Commercial VAN</option></select>', m.group(1), flags=re.I)
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
    script = f'''\n<script>\n// Source metadata injected automatically from selection_manifest.json\nconst RATE_SOURCE_META = {json.dumps(meta, ensure_ascii=False, separators=(",", ":"))};\n(function(){{\n  const sel = document.getElementById('fileFilterSel');\n  const box = document.getElementById('rateSourceMeta');\n  const fileEl = document.getElementById('rateSourceFile');\n  const dateEl = document.getElementById('rateSourceDate');\n  if(!sel || !box || !fileEl || !dateEl) return;\n  const baseLabels = {{BK:'RateGroup BK (CDW)',FCI:'RateGroup BK FCI (CDW + FCI)',VAN:'RateGroup Commercial VAN'}};\n  Array.from(sel.options).forEach(opt=>{{\n    const m = RATE_SOURCE_META[opt.value];\n    opt.textContent = baseLabels[opt.value] || opt.textContent;\n    if(m && m.status === 'ok' && m.date) opt.textContent += ' — ficheiro ' + m.date;\n  }});\n  function refreshSourceVersion(){{\n    const m = RATE_SOURCE_META[sel.value] || {{status:'missing',filename:'',date:''}};\n    const ok = m.status === 'ok';\n    box.classList.toggle('missing', !ok);\n    fileEl.textContent = ok ? m.filename : 'ficheiro não identificado';\n    dateEl.textContent = ok ? m.date : 'não disponível';\n    box.title = ok && m.method ? 'Seleção: ' + m.method : '';\n  }}\n  sel.addEventListener('change', refreshSourceVersion);\n  refreshSourceVersion();\n}})();\n</script>\n'''
    return html.replace("</body>", script + "</body>", 1) if "</body>" in html else html + script


def inject_location_station_sync_and_navigation(html: str) -> str:
    css = '''\n/* Rate Shop navigation injected by build */\n.rate-shop-open-btn{position:fixed;right:18px;bottom:18px;z-index:99999;padding:10px 15px;border-radius:9px;background:#0b365d;color:#fff;text-decoration:none;font-weight:700;box-shadow:0 5px 18px rgba(0,0,0,.22)}\n.rate-shop-open-btn:hover{filter:brightness(1.08)}\n.rate-shop-standalone-back{position:fixed;left:16px;top:12px;z-index:100000;padding:8px 12px;border-radius:8px;background:#0b365d;color:#fff;text-decoration:none;font-weight:700;box-shadow:0 4px 14px rgba(0,0,0,.18)}\n.rate-shop-standalone-back:hover{filter:brightness(1.08)}\n'''
    if "</style>" in html:
        html = html.replace("</style>", css + "</style>", 1)

    script = r'''
<script>
// Wheelsys location/station sync and Rate Shop page mode
(function(){
  const norm=s=>(s||'').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  const LOCS={
    lisboa:['lisboa','lis','lxa'],
    porto:['porto','opo','opt'],
    faro:['faro','fao']
  };
  const locFromText=s=>{
    const t=norm(s);
    for(const [loc,hints] of Object.entries(LOCS)) if(hints.some(h=>t===h||t.includes(h))) return loc;
    return '';
  };

  function findLocationSelect(){
    const sels=[...document.querySelectorAll('select')].filter(s=>s.id!=='fileFilterSel');
    let best=null,bestScore=0;
    for(const s of sels){
      const key=norm((s.id||'')+' '+(s.name||'')+' '+[...s.options].map(o=>o.textContent).join(' '));
      let score=0;
      if(key.includes('local')) score+=4;
      if(key.includes('location')) score+=4;
      if(key.includes('lisboa')) score+=2;
      if(key.includes('porto')) score+=2;
      if(key.includes('faro')) score+=2;
      if(score>bestScore){best=s;bestScore=score;}
    }
    return bestScore>=4?best:null;
  }

  function stationArea(){
    const nodes=[...document.querySelectorAll('label,legend,h1,h2,h3,h4,h5,div,span')];
    const title=nodes.find(n=>{const t=norm(n.textContent);return t==='estacoes a ajustar'||t.includes('estacoes a ajustar');});
    if(!title) return null;
    return title.closest('fieldset,.card,.panel,.control-group,.form-group,section,div') || title.parentElement;
  }

  function itemLocation(el){
    let text='';
    if(el.tagName==='OPTION') text=(el.textContent||'')+' '+(el.value||'');
    else {
      const id=el.id;
      const label=id?document.querySelector('label[for="'+CSS.escape(id)+'"]'):null;
      text=(label?label.textContent:'')+' '+(el.value||'')+' '+(el.getAttribute('data-location')||'');
      if(!label && el.parentElement) text+=' '+el.parentElement.textContent;
    }
    return locFromText(text);
  }

  function applyStationLocation(loc){
    if(!loc) return;
    const area=stationArea();
    if(!area) return;
    const controls=[...area.querySelectorAll('option,input[type="checkbox"],input[type="radio"]')];
    controls.forEach(el=>{
      const own=itemLocation(el);
      if(!own) return; // do not touch generic/all-station controls
      const match=own===loc;
      if(el.tagName==='OPTION'){
        el.hidden=!match;
        el.disabled=!match;
        if(!match && el.selected) el.selected=false;
      }else{
        el.disabled=!match;
        if(!match && el.checked) el.checked=false;
        const label=el.id?document.querySelector('label[for="'+CSS.escape(el.id)+'"]'):null;
        const wrap=label||el.closest('label')||el.parentElement;
        if(wrap) wrap.style.display=match?'':'none';
      }
    });
    area.setAttribute('data-synced-location',loc);
  }

  function syncFromLocationControl(){
    const s=findLocationSelect();
    if(!s) return;
    const opt=s.options[s.selectedIndex];
    applyStationLocation(locFromText((opt?opt.textContent:'')+' '+s.value));
  }

  document.addEventListener('change',e=>{
    const s=findLocationSelect();
    if(s && e.target===s) setTimeout(syncFromLocationControl,0);
  });
  document.addEventListener('click',e=>{
    const b=e.target.closest('button,[data-location],a');
    if(!b) return;
    const loc=locFromText((b.getAttribute('data-location')||'')+' '+b.textContent);
    if(loc) setTimeout(()=>applyStationLocation(loc),0);
  });
  setTimeout(syncFromLocationControl,100);

  const params=new URLSearchParams(location.search);
  const standalone=params.get('rateshop')==='1';
  if(!standalone){
    if(!document.getElementById('openRateShopPage')){
      const a=document.createElement('a');
      a.id='openRateShopPage'; a.className='rate-shop-open-btn'; a.href='rate-shop.html'; a.textContent='Rate Shop';
      document.body.appendChild(a);
    }
    return;
  }

  function isolateRateShop(){
    const headings=[...document.querySelectorAll('h1,h2,h3,h4,h5,[role="heading"]')];
    let h=headings.find(x=>norm(x.textContent)==='rate shop') || headings.find(x=>norm(x.textContent).includes('rate shop'));
    if(!h){
      const all=[...document.querySelectorAll('div,section,article')];
      h=all.find(x=>norm(x.textContent).startsWith('rate shop'));
    }
    if(!h) return;
    let target=h.closest('section,article,[id*="rate" i],[class*="rate-shop" i],[class*="rateshop" i],.card,.panel') || h.parentElement;
    if(!target) return;
    let node=target;
    while(node && node!==document.body){
      const parent=node.parentElement;
      if(!parent) break;
      [...parent.children].forEach(ch=>{if(ch!==node && ch.tagName!=='SCRIPT' && ch.tagName!=='STYLE') ch.style.display='none';});
      node=parent;
    }
    document.body.style.paddingTop='52px';
    const back=document.createElement('a');
    back.className='rate-shop-standalone-back'; back.href='index.html'; back.textContent='← Página principal';
    document.body.appendChild(back);
    target.scrollIntoView({block:'start'});
  }
  setTimeout(isolateRateShop,250);
})();
</script>
'''
    return html.replace("</body>", script + "</body>", 1) if "</body>" in html else html + script


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
    updated = inject_location_station_sync_and_navigation(updated)
    OUTPUT.write_text(updated, encoding="utf-8")
    print(f"HTML gerado: {OUTPUT}")
    print("Tarifas BK/FCI/VAN, sincronização localização/estações e navegação Rate Shop atualizadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
