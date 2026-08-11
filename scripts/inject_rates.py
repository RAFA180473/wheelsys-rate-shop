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
RATE_SHOP_OUTPUT = ROOT / "public" / "rate-shop.html"

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


def ensure_adjustment_panel_updates(html: str) -> str:
    """Apply the commercial/station UX to the adjustment panel only."""
    if "const ADJUSTMENT_GROUP_DESCRIPTIONS" in html:
        return html

    html = html.replace(
        "Localizações a visualizar <span",
        "Estações a visualizar <span",
        1,
    )
    html = html.replace(
        '<div class="panel comp-panel">',
        '<div class="panel comp-panel" hidden aria-hidden="true">',
        1,
    )
    html = html.replace(
        '<span class="tag">ICONIQ &middot; Broker Rates &middot; Wheelsys export</span>',
        '<span class="tag">ICONIQ &middot; Broker Rates &middot; Wheelsys export</span>\n  <a class="page-nav" href="rate-shop.html">Rate Shop Concorrência →</a>',
        1,
    )
    navigation_css = """
.page-nav{margin-left:auto;padding:9px 14px;border:1px solid rgba(255,255,255,.28);border-radius:6px;background:var(--teal-500);color:#fff;text-decoration:none;font-size:12px;font-weight:700;white-space:nowrap;}
.page-nav:hover{background:var(--teal-400);color:var(--navy-950);}
.group-segment-label{flex-basis:100%;margin-top:4px;padding:4px 6px;border-left:3px solid var(--teal-500);background:var(--mist-100);color:var(--navy-700);font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.35px;}
.segment-cell{min-width:105px;background:#e9f2f4!important;color:var(--navy-700);font-weight:750;text-transform:uppercase;font-size:9.5px;letter-spacing:.25px;}
.segment-filter-card{border:1px solid var(--line);border-radius:6px;background:#fff;padding:5px;}
.segment-filter-checklist{border:0!important;max-height:94px!important;padding:0!important;gap:3px!important;}
.segment-filter-actions{display:flex;gap:4px;margin-top:5px;}
.segment-filter-actions button{border:1px solid var(--line);border-radius:10px;background:var(--mist-100);color:var(--steel-500);font-size:9.5px;padding:2px 7px;cursor:pointer;}
.gridfilter .checklist,#bulkGroups{gap:3px;padding:5px;border-radius:7px;background:#fbfcfd;}
.gridfilter .checklist label,#bulkGroups label,.segment-filter-checklist label{padding:3px 6px;font-size:10.5px;border:1px solid transparent;border-radius:5px;line-height:1.2;}
.gridfilter .checklist label.checked,#bulkGroups label.checked,.segment-filter-checklist label.checked{border-color:rgba(31,163,148,.3);}
.segment-tone-0{--seg-soft:#f2fbf8;--seg-strong:#d9f2eb;--seg-accent:#2f9e87;}
.segment-tone-1{--seg-soft:#fff6f7;--seg-strong:#f9e1e5;--seg-accent:#c96b7d;}
.segment-tone-2{--seg-soft:#fff9ed;--seg-strong:#f8ebc9;--seg-accent:#c99425;}
.segment-tone-3{--seg-soft:#f3f8ff;--seg-strong:#dceafb;--seg-accent:#4f83bd;}
.segment-tone-4{--seg-soft:#f7f4ff;--seg-strong:#e8def9;--seg-accent:#8063b5;}
.segment-tone-5{--seg-soft:#f0fafc;--seg-strong:#d8eef3;--seg-accent:#3d94a5;}
.segment-tone-6{--seg-soft:#f4faef;--seg-strong:#e1efd5;--seg-accent:#6f9d49;}
.segment-tone-7{--seg-soft:#fff7ef;--seg-strong:#f7e4d0;--seg-accent:#bf7a35;}
.segment-tone-8{--seg-soft:#faf8f2;--seg-strong:#eee7d7;--seg-accent:#9a7b3f;}
.segment-tone-9{--seg-soft:#f3f5ff;--seg-strong:#dfe4f8;--seg-accent:#6074b3;}
.segment-tone-10{--seg-soft:#fff4fb;--seg-strong:#f4deec;--seg-accent:#ae6495;}
.segment-tone-11{--seg-soft:#f8f3fb;--seg-strong:#e9dcf0;--seg-accent:#8d63a4;}
.segment-tone-12{--seg-soft:#f5f7f8;--seg-strong:#e1e7ea;--seg-accent:#607681;}
tbody tr[class*="segment-tone-"]{background:var(--seg-soft);}
tbody tr[class*="segment-tone-"] td.group-cell,tbody tr[class*="segment-tone-"] td.segment-cell{background:var(--seg-strong)!important;}
tbody tr[class*="segment-tone-"] td.group-cell{border-left:4px solid var(--seg-accent);}
.group-segment-label[class*="segment-tone-"]{background:var(--seg-strong);border-left-color:var(--seg-accent);}
@media(max-width:760px){.topbar{flex-wrap:wrap}.page-nav{margin-left:0}}
"""
    html = html.replace("</style>", navigation_css + "</style>", 1)
    html = html.replace(
        '<label for="bulkFrom">Período de</label>',
        '<label for="bulkFrom">Período pickup de</label>',
        1,
    )
    html = html.replace(
        '<label for="segFilterSel">Segmento</label>\n      <select id="segFilterSel"></select>',
        '<label>Segmentos a visualizar <span style="font-weight:400;text-transform:none;letter-spacing:0;">(um ou vários)</span></label>\n      <div class="segment-filter-card">\n        <div class="checklist segment-filter-checklist" id="segFilterSel"></div>\n        <div class="segment-filter-actions"><button type="button" id="segFilterAll">Todos</button><button type="button" id="segFilterNone">Nenhum</button></div>\n      </div>',
        1,
    )
    html = html.replace("let segFilter = 'Todos';", "let segFilter = new Set();\nlet segFilterInitialized = false;", 1)
    html = html.replace(
        '<input type="date" id="bulkFrom">',
        '<input type="date" id="bulkFrom" readonly aria-readonly="true">',
        1,
    )
    html = html.replace(
        '<input type="date" id="bulkTo">',
        '<input type="date" id="bulkTo" readonly aria-readonly="true">',
        1,
    )
    html = html.replace(
        'Só são afetados os períodos já existentes que estejam totalmente dentro deste intervalo — os restantes mantêm o preço atual.',
        'Intervalo ligado automaticamente ao Período (pickup) selecionado no topo.',
        1,
    )
    html = html.replace(
        '<div class="quickrange">\n        <button type="button" data-from=',
        '<div class="quickrange" style="display:none;" aria-hidden="true">\n        <button type="button" data-from=',
        1,
    )

    commercial_config = """
const ADJUSTMENT_GROUP_DESCRIPTIONS = {
  VANS:'VW Caddy Cargo',
  VANM:'VW Transporter Cargo',
  VANL:'VW Crafter Cargo 9900 L'
};
Object.assign(SEGMENTS, {
  VANS:'Veículos comerciais',
  VANM:'Veículos comerciais',
  VANL:'Veículos comerciais',
  VCXL:'Veículos comerciais'
});
const TARIFF_LABELS = {BK:'RateGroup BK', FCI:'RateGroup BK FCI', VAN:'RateGroup Commercial VAN'};
const EXPORT_FILE_LABELS = {BK:'BK', FCI:'BK_FCI', VAN:'Commercial_VAN'};
const SEGMENT_TONE_INDEX = {
  'Economy':0,'Cabrio':1,'Economy SUV':2,'Compact':3,'Intermediate':4,
  'SUV Inter.':5,'SUV Compact':6,'Passenger Van':7,'Luxury':8,
  'SUV Premium':9,'Special':10,'Cabrio Elite':11,'Veículos comerciais':12
};
function segmentToneClass(segment){
  const index = Object.prototype.hasOwnProperty.call(SEGMENT_TONE_INDEX, segment)
    ? SEGMENT_TONE_INDEX[segment]
    : 12;
  return `segment-tone-${index}`;
}
"""
    html = re.sub(
        r"(const SEGMENTS = \{.*?\};)",
        lambda m: m.group(1) + commercial_config,
        html,
        count=1,
        flags=re.S,
    )

    html = html.replace(
        """function populateSegFilterSel(){
  const sel = document.getElementById('segFilterSel');
  const segs = Array.from(new Set(Object.values(SEGMENTS))).sort();
  sel.innerHTML = '<option value="Todos">Todos os segmentos</option>' + segs.map(s=>`<option value="${s}">${s}</option>`).join('');
  sel.value = segFilter;
}""",
        """function segmentOrderOf(fileKey){
  const order = [];
  groupsOf(fileKey).forEach(g=>{
    const segment = SEGMENTS[g];
    if(segment && !order.includes(segment)) order.push(segment);
  });
  return order;
}
function populateSegFilterSel(){
  const box = document.getElementById('segFilterSel');
  const segs = segmentOrderOf(currentFile);
  if(!segFilterInitialized){
    segFilter = new Set(segs);
    segFilterInitialized = true;
  } else {
    segFilter = new Set(Array.from(segFilter).filter(s=>segs.includes(s)));
    if(segFilter.size === 0) segFilter = new Set(segs);
  }
  box.innerHTML = '';
  segs.forEach(segment=>{
    const lab = document.createElement('label');
    const checked = segFilter.has(segment);
    if(checked) lab.className = 'checked';
    lab.innerHTML = `<input type="checkbox" value="${segment}" ${checked?'checked':''}> ${segment}`;
    box.appendChild(lab);
    const cb = lab.querySelector('input');
    cb.addEventListener('change', ()=>{
      if(cb.checked) segFilter.add(segment); else segFilter.delete(segment);
      lab.classList.toggle('checked', cb.checked);
      onFilterChange();
    });
  });
}""",
        1,
    )
    html = html.replace(
        """function groupsOfFiltered(fileKey, loc){
  const list = groupsOf(fileKey, loc);
  if(!segFilter || segFilter==='Todos') return list;
  return list.filter(g=>(SEGMENTS[g]||'')===segFilter);
}""",
        """function groupsOfFiltered(fileKey, loc){
  const list = groupsOf(fileKey, loc);
  const filtered = list.filter(g=>segFilter.has(SEGMENTS[g]||''));
  const segmentOrder = segmentOrderOf(fileKey);
  const groupOrder = new Map(list.map((g,index)=>[g,index]));
  return filtered.slice().sort((a,b)=>{
    const bySegment = segmentOrder.indexOf(SEGMENTS[a]) - segmentOrder.indexOf(SEGMENTS[b]);
    return bySegment || groupOrder.get(a) - groupOrder.get(b);
  });
}""",
        1,
    )
    html = html.replace(
        """function populateGridGroupFilter(){
  const box = document.getElementById('gridGroupFilter');
  box.innerHTML = '';
  const groups = groupsOfFiltered(currentFile);
  gridGroupFilter = new Set(groups.length ? [groups[0]] : []);
  activeGroup = groups.length ? groups[0] : null;
  groups.forEach((g,i)=>{
    const lab = document.createElement('label');
    if(i===0) lab.className = 'checked';
    lab.innerHTML = `<input type="checkbox" value="${g}" ${i===0?'checked':''}> ${g}`;
    box.appendChild(lab);
    const cb = lab.querySelector('input');""",
        """function populateGridGroupFilter(){
  const box = document.getElementById('gridGroupFilter');
  box.innerHTML = '';
  const groups = groupsOfFiltered(currentFile);
  const availableSegments = new Set(groupsOf(currentFile).map(g=>SEGMENTS[g]).filter(Boolean));
  const autoSelectAllGroups = segFilter.size < availableSegments.size;
  gridGroupFilter = new Set(autoSelectAllGroups ? groups : (groups.length ? [groups[0]] : []));
  activeGroup = groups.length ? groups[0] : null;
  let previousSegment = null;
  groups.forEach(g=>{
    const segment = SEGMENTS[g] || 'Outro';
    if(segment !== previousSegment){
      const heading = document.createElement('div');
      heading.className = `group-segment-label ${segmentToneClass(segment)}`;
      heading.textContent = segment;
      box.appendChild(heading);
      previousSegment = segment;
    }
    const lab = document.createElement('label');
    const isChecked = gridGroupFilter.has(g);
    if(isChecked) lab.className = 'checked';
    lab.innerHTML = `<input type="checkbox" value="${g}" ${isChecked?'checked':''}> ${g}`;
    box.appendChild(lab);
    const cb = lab.querySelector('input');""",
        1,
    )

    html = html.replace(
        "let model = v.desc.replace(",
        "let model = (ADJUSTMENT_GROUP_DESCRIPTIONS[g] || v.desc).replace(",
        1,
    )
    html = html.replace(
        """      } else {
        gridGroupFilter.delete(g);
        if(activeGroup === g) activeGroup = null;
      }
      const pg = primaryGroup();""",
        """      } else {
        gridGroupFilter.delete(g);
        if(activeGroup === g) activeGroup = null;
      }
      syncBulkGroupCheckboxes();
      const pg = primaryGroup();""",
        1,
    )
    html = html.replace(
        """  activeGroup = groupsOf(currentFile).find(g=>gridGroupFilter.has(g)) || null;
  const pg = primaryGroup();""",
        """  activeGroup = groupsOfFiltered(currentFile).find(g=>gridGroupFilter.has(g)) || null;
  syncBulkGroupCheckboxes();
  const pg = primaryGroup();""",
        1,
    )
    html = html.replace(
        """  gridGroupFilter.clear();
  activeGroup = null;
  refreshAll();""",
        """  gridGroupFilter.clear();
  activeGroup = null;
  syncBulkGroupCheckboxes();
  refreshAll();""",
        1,
    )
    html = html.replace(
        """      gridGroupFilter = new Set([g]);
      activeGroup = g;
      syncGridGroupFilterCheckboxes();""",
        """      gridGroupFilter = new Set([g]);
      activeGroup = g;
      syncGridGroupFilterCheckboxes();
      syncBulkGroupCheckboxes();""",
        1,
    )
    html = html.replace(
        """// ---- bulk group checklist ----
function populateBulkGroups(){
  const box = document.getElementById('bulkGroups');
  box.innerHTML = '';
  groupsOfFiltered(currentFile).forEach(g=>{
    const lab = document.createElement('label');
    lab.innerHTML = `<input type="checkbox" value="${g}"> ${g}`;
    box.appendChild(lab);
    const cb = lab.querySelector('input');
    cb.addEventListener('change', ()=>{ lab.classList.toggle('checked', cb.checked); refreshBulkPreview(); });
  });
}
document.getElementById('bulkGroupsAll').addEventListener('click', ()=>{
  document.querySelectorAll('#bulkGroups input').forEach(cb=>{ cb.checked=true; cb.parentElement.classList.add('checked'); });
  refreshBulkPreview();
});
document.getElementById('bulkGroupsNone').addEventListener('click', ()=>{
  document.querySelectorAll('#bulkGroups input').forEach(cb=>{ cb.checked=false; cb.parentElement.classList.remove('checked'); });
  refreshBulkPreview();
});""",
        """// ---- bulk group checklist ----
function populateBulkGroups(){
  const box = document.getElementById('bulkGroups');
  box.innerHTML = '';
  groupsOfFiltered(currentFile).forEach(g=>{
    const lab = document.createElement('label');
    const isChecked = gridGroupFilter.has(g);
    if(isChecked) lab.className = 'checked';
    lab.innerHTML = `<input type="checkbox" value="${g}" ${isChecked?'checked':''}> ${g}`;
    box.appendChild(lab);
    const cb = lab.querySelector('input');
    cb.addEventListener('change', ()=>{
      if(cb.checked){
        gridGroupFilter.add(g);
        activeGroup = g;
      } else {
        gridGroupFilter.delete(g);
        if(activeGroup === g) activeGroup = null;
      }
      lab.classList.toggle('checked', cb.checked);
      syncGridGroupFilterCheckboxes();
      const pg = primaryGroup();
      if(pg){ updateGroupDesc(pg); populatePeriodSelect(pg); }
      refreshAll();
      refreshBulkPreview();
    });
  });
}
function syncBulkGroupCheckboxes(){
  document.querySelectorAll('#bulkGroups label').forEach(lab=>{
    const cb = lab.querySelector('input');
    const on = gridGroupFilter.has(cb.value);
    cb.checked = on;
    lab.classList.toggle('checked', on);
  });
}
document.getElementById('bulkGroupsAll').addEventListener('click', ()=>{
  document.querySelectorAll('#bulkGroups input').forEach(cb=>{
    cb.checked = true;
    cb.parentElement.classList.add('checked');
    gridGroupFilter.add(cb.value);
  });
  activeGroup = groupsOfFiltered(currentFile).find(g=>gridGroupFilter.has(g)) || null;
  syncGridGroupFilterCheckboxes();
  const pg = primaryGroup();
  if(pg){ updateGroupDesc(pg); populatePeriodSelect(pg); }
  refreshAll();
  refreshBulkPreview();
});
document.getElementById('bulkGroupsNone').addEventListener('click', ()=>{
  document.querySelectorAll('#bulkGroups input').forEach(cb=>{
    cb.checked = false;
    cb.parentElement.classList.remove('checked');
    gridGroupFilter.delete(cb.value);
  });
  activeGroup = null;
  syncGridGroupFilterCheckboxes();
  refreshAll();
  refreshBulkPreview();
});""",
        1,
    )
    html = html.replace(
        "const v = VGROUPS[group];\n  document.getElementById('grpDesc').textContent = v ? (`Grupo ${group} — ${v.desc} · SIPP ${v.sipp}`) : '';",
        "const v = VGROUPS[group];\n  const desc = v ? (ADJUSTMENT_GROUP_DESCRIPTIONS[group] || v.desc) : '';\n  document.getElementById('grpDesc').textContent = v ? (`Grupo ${group} — ${desc} · SIPP ${v.sipp}`) : '';",
        1,
    )
    html = html.replace(
        "const locLabel = locs.length ? locs.join(', ') : 'nenhuma localização selecionada';\n  document.getElementById('gridTitle').textContent = 'Todos os grupos — período ' + pStart + ' a ' + pEnd + ' (' + (currentFile==='BK'?'RateGroup BK':'RateGroup BK FCI') + ' · ' + locLabel + ')';",
        "const locLabel = locs.length ? locs.join(', ') : 'nenhuma estação selecionada';\n  document.getElementById('gridTitle').textContent = 'Todos os grupos — período ' + pStart + ' a ' + pEnd + ' (' + TARIFF_LABELS[currentFile] + ' · ' + locLabel + ')';",
        1,
    )
    html = html.replace(
        """if(cb !== 'p7'){
    cascadeBtn.disabled = true;
    cascadeBtn.style.opacity = 0.45;
    cascadeBtn.style.cursor = 'not-allowed';
    cascadeNote.textContent = 'A cascata só está disponível quando o cost break selecionado é "7 dias" (a base). Para outros cost breaks, o ajuste aplica-se sempre só a essa célula.';
  } else {
    cascadeBtn.disabled = false;
    cascadeBtn.style.opacity = 1;
    cascadeBtn.style.cursor = 'pointer';
    cascadeNote.textContent = 'A cascata segue os rácios do ficheiro original (1d=155%, 2d=120%, 3d=115%, 4-6d=110%, 7d=base, 8-13d=90%, 14-29d=85%, 30+=igual a 4-6d) e só se aplica quando ajustas o cost break "7 dias".';
  }""",
        """if(currentFile === 'VAN'){
    applyMode = 'only';
    cascadeBtn.disabled = true;
    cascadeBtn.style.opacity = 0.45;
    cascadeBtn.style.cursor = 'not-allowed';
    cascadeBtn.classList.remove('sel','inc');
    onlyBtn.classList.add('sel','inc');
    cascadeNote.textContent = 'A tarifa Commercial VAN não utiliza cascata. O ajuste aplica-se apenas ao cost break selecionado.';
  } else if(cb !== 'p7'){
    cascadeBtn.disabled = true;
    cascadeBtn.style.opacity = 0.45;
    cascadeBtn.style.cursor = 'not-allowed';
    cascadeNote.textContent = 'A cascata só está disponível quando o cost break selecionado é "7 dias" (a base). Para outros cost breaks, o ajuste aplica-se sempre só a essa célula.';
  } else {
    cascadeBtn.disabled = false;
    cascadeBtn.style.opacity = 1;
    cascadeBtn.style.cursor = 'pointer';
    cascadeNote.textContent = 'A cascata segue os rácios do ficheiro original (1d=155%, 2d=120%, 3d=115%, 4-6d=110%, 7d=base, 8-13d=90%, 14-29d=85%, 30+=igual a 4-6d) e só se aplica quando ajustas o cost break "7 dias".';
  }""",
        1,
    )
    html = html.replace(
        "<th>Grupo</th><th>Localização</th>",
        "<th>Grupo</th><th>Segmento</th><th>Estação</th>",
        2,
    )
    html = html.replace("<th>Localização</th>", "<th>Estação</th>", 1)
    html = html.replace(
        "const groups = groupsOf(currentFile).filter(g=>gridGroupFilter.has(g));",
        "const groups = groupsOfFiltered(currentFile).filter(g=>gridGroupFilter.has(g));",
        1,
    )
    html = html.replace(
        "if(isSelRow) tr.className='selected-row';",
        "tr.className = `${isSelRow ? 'selected-row ' : ''}${segmentToneClass(SEGMENTS[g] || 'Outro')}`;",
        1,
    )
    html = html.replace(
        """if(idx===0){
        tds += `<td class="group-cell" rowspan="${rowsForGroup.length}">${groupLabel(g)}</td>`;
      }""",
        """if(idx===0){
        tds += `<td class="group-cell" rowspan="${rowsForGroup.length}">${groupLabel(g)}</td>`;
        tds += `<td class="segment-cell" rowspan="${rowsForGroup.length}">${SEGMENTS[g] || 'Outro'}</td>`;
      }""",
        1,
    )
    html = html.replace(
        "selectedLocations = new Set([loc]);\n      syncLocFilterCheckboxes();\n      refreshAll();",
        "selectedLocations = new Set([loc]);\n      syncLocFilterCheckboxes();\n      adjustLocations = new Set(selectedLocations);\n      syncAdjustLocCheckboxes();\n      refreshBulkPreview();\n      refreshAll();",
        1,
    )
    html = html.replace(
        "lab.classList.toggle('checked', cb.checked);\n      onFilterChange();",
        "lab.classList.toggle('checked', cb.checked);\n      adjustLocations = new Set(selectedLocations);\n      syncAdjustLocCheckboxes();\n      refreshBulkPreview();\n      onFilterChange();",
        1,
    )
    html = html.replace(
        """document.getElementById('segFilterSel').addEventListener('change', e=>{
  segFilter = e.target.value;
  onFilterChange();
});""",
        """function syncAdjustLocCheckboxes(){
  document.querySelectorAll('#adjustLocChecklist label').forEach(lab=>{
    const cb = lab.querySelector('input');
    const on = adjustLocations.has(cb.value);
    cb.checked = on;
    lab.classList.toggle('checked', on);
  });
}
document.getElementById('segFilterAll').addEventListener('click', ()=>{
  document.querySelectorAll('#segFilterSel input').forEach(cb=>segFilter.add(cb.value));
  populateSegFilterSel();
  onFilterChange();
});
document.getElementById('segFilterNone').addEventListener('click', ()=>{
  segFilter.clear();
  document.querySelectorAll('#segFilterSel label').forEach(lab=>{
    const cb = lab.querySelector('input');
    cb.checked = false;
    lab.classList.remove('checked');
  });
  onFilterChange();
});""",
        1,
    )
    html = html.replace(
        "currentFile==='BK'?'BK':'BK_FCI'",
        "EXPORT_FILE_LABELS[currentFile]",
        1,
    )
    html = html.replace(
        "applyMode === 'cascade' && cb === 'p7'",
        "applyMode === 'cascade' && currentFile !== 'VAN' && cb === 'p7'",
    )
    html = html.replace(
        "// ---- mode tabs ----",
        """function syncBulkPeriodFromPickup(){
  const periodSelect = document.getElementById('perSel');
  const bulkFrom = document.getElementById('bulkFrom');
  const bulkTo = document.getElementById('bulkTo');
  if(!periodSelect || !bulkFrom || !bulkTo || !periodSelect.value) return;
  const [pickupStart, pickupEnd] = periodSelect.value.split('|');
  if(!pickupStart || !pickupEnd) return;
  bulkFrom.value = toISO(pickupStart);
  bulkTo.value = toISO(pickupEnd);
  if(typeof refreshBulkPreview === 'function') refreshBulkPreview();
}

// ---- mode tabs ----""",
        1,
    )
    html = html.replace(
        """document.getElementById('perSel').addEventListener('change', ()=>{
  refreshAll();
  syncRateShopDatesFromPeriod();
});""",
        """document.getElementById('perSel').addEventListener('change', ()=>{
  refreshAll();
  syncBulkPeriodFromPickup();
  syncRateShopDatesFromPeriod();
});""",
        1,
    )
    html = html.replace(
        """  populateBulkGroups();
  populateBulkCostbreaks();
  refreshBulkPreview();
});

// ---- date helpers""",
        """  populateBulkGroups();
  populateBulkCostbreaks();
  syncBulkPeriodFromPickup();
  refreshBulkPreview();
});

// ---- date helpers""",
        1,
    )
    html = html.replace(
        """    populateBulkGroups();
    populateBulkCostbreaks();
    refreshBulkPreview();
  }
}""",
        """    populateBulkGroups();
    populateBulkCostbreaks();
    syncBulkPeriodFromPickup();
    refreshBulkPreview();
  }
}""",
        1,
    )
    html = html.replace(
        """document.getElementById('fileFilterSel').addEventListener('change', e=>{
  currentFile = e.target.value;
  onFilterChange();
});""",
        """document.getElementById('fileFilterSel').addEventListener('change', e=>{
  currentFile = e.target.value;
  populateSegFilterSel();
  onFilterChange();
});""",
        1,
    )
    # Obsolete call raised a ReferenceError whenever a top-panel filter changed.
    html = html.replace("  populateCompGroupSelect();\n", "", 1)
    return html


def build_rate_shop_page(html: str) -> str:
    """Derive the standalone Rate Shop page while preserving its existing logic."""
    page = html.replace("<body>", '<body class="rate-shop-page">', 1)
    page = page.replace(
        "<title>Painel de Ajuste de Tarifas</title>",
        "<title>Rate Shop Concorrência</title>",
        1,
    )
    page = page.replace(
        "<h1>Painel de Ajuste de Tarifas</h1>",
        "<h1>Rate Shop Concorrência</h1>",
        1,
    )
    page = page.replace(
        '<a class="page-nav" href="rate-shop.html">Rate Shop Concorrência →</a>',
        '<a class="page-nav" href="index.html">← Painel de Ajuste de Tarifas</a>',
        1,
    )
    page = page.replace(
        '<div class="panel comp-panel" hidden aria-hidden="true">',
        '<div class="panel comp-panel">',
        1,
    )
    standalone_css = """
.rate-shop-page .filterbox{display:none!important;}
.rate-shop-page .layout{display:block;}
.rate-shop-page .layout>div:first-child{display:none!important;}
.rate-shop-page .layout>div:nth-child(2)>.grid-wrap{display:none!important;}
.rate-shop-page .layout>div:nth-child(2)>.comp-panel{display:block!important;margin-top:0;}
"""
    page = page.replace("</style>", standalone_css + "</style>", 1)
    return page


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
    html = ensure_adjustment_panel_updates(html)

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
    RATE_SHOP_OUTPUT.write_text(build_rate_shop_page(updated), encoding="utf-8")

    print(f"HTML gerado: {OUTPUT}")
    print(f"Rate Shop gerado: {RATE_SHOP_OUTPUT}")
    print(f"Declaração RATES substituída com sucesso ({keyword}).")
    print("Versão dos ficheiros BK/FCI/VAN adicionada ao seletor de tarifa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
