"""Writes a self-contained HTML viewer (no server, no external script) next to the report."""

from __future__ import annotations

import json

import pandas as pd

from .engine import RowResult


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return v


# Real issues first; dataset-level systematic findings last.
STATUS_RANK = {"Écart": 0, "À arbitrer": 1, "Écart justifié": 2, "Écart systématique": 3}


def write_viewer(results: list[RowResult], verdicts: pd.DataFrame, findings: pd.DataFrame, out_path) -> None:
    rows = []
    for _, v in verdicts.iterrows():
        key = (str(v["Matricule"]), str(v["Type affectation"]), str(v["Poste"]))
        fs = findings[(findings["Matricule"] == v["Matricule"]) & (findings["Type affectation"] == v["Type affectation"]) & (findings["Poste"] == v["Poste"])]
        rows.append(
            {
                "id": "|".join(key),
                "matricule": str(v["Matricule"]),
                "type": str(v["Type affectation"]),
                "poste": str(v["Poste"]),
                "verdict": v["Verdict"],
                "resume": v["Résumé"],
                "matched": str(v["Ligne cible"]) != "",
                "fields": sorted(
                    (
                        {k: _clean(val) for k, val in f.items()}
                        for f in fs.to_dict(orient="records")
                        if f["Statut"] != "OK"
                    ),
                    key=lambda f: STATUS_RANK.get(f["Statut"], 9),
                ),
            }
        )
    payload = json.dumps(rows, ensure_ascii=False)
    out_path.write_text(TEMPLATE.replace("__DATA__", payload.replace("</", "<\\/")), encoding="utf-8")


TEMPLATE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CorroborAI : rapport de corroboration</title>
<style>
:root{--bg:#f7f7f5;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#e2e1dc;
--red:#b3261e;--amb:#b26a00;--blue:#1f5fa8;--grn:#2e7d4f;--gry:#6b6b66}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#161615;--fg:#eceae4;--mut:#9b9a93;--card:#1f1f1d;--line:#34332f;--red:#ff8a80;--amb:#ffb74d;--blue:#8ab4f8;--grn:#81c995;--gry:#9b9a93}}
:root[data-theme="dark"]{--bg:#161615;--fg:#eceae4;--mut:#9b9a93;--card:#1f1f1d;--line:#34332f;--red:#ff8a80;--amb:#ffb74d;--blue:#8ab4f8;--grn:#81c995;--gry:#9b9a93}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:20px 24px 8px}h1{font-size:20px;margin:0 0 4px}header p{margin:0;color:var(--mut)}
.wrap{padding:8px 24px 40px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:16px}
@media (max-width:860px){.wrap{grid-template-columns:minmax(0,1fr);padding:8px 16px 32px}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.chip{border:1px solid var(--line);background:none;color:var(--fg);border-radius:999px;padding:4px 10px;cursor:pointer;font:inherit}
.chip[aria-pressed="true"]{background:var(--fg);color:var(--bg)}
input[type=search]{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg);font:inherit;margin-bottom:10px}
.list{max-height:70vh;overflow:auto}
.row{display:flex;justify-content:space-between;gap:8px;padding:9px 8px;border-radius:8px;cursor:pointer;border:1px solid transparent}
.row:hover{background:var(--bg)}.row[aria-selected="true"]{border-color:var(--line);background:var(--bg)}
.tag{font-size:12px;font-weight:600;white-space:nowrap}
.v-ANOMALIE{color:var(--red)}.v-PROB{color:var(--amb)}.v-ARB{color:var(--amb)}.v-JUST{color:var(--blue)}.v-CONF{color:var(--grn)}.v-SYS{color:var(--gry)}
.muted{color:var(--mut)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;vertical-align:top;padding:7px 6px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600}
.exp{font-family:ui-monospace,Menlo,monospace;font-size:12px;word-break:break-all}
.note{margin:10px 0;padding:10px;border-left:3px solid var(--line);background:var(--bg);border-radius:6px}
.tablewrap{overflow-x:auto}
</style></head>
<body>
<header><h1>CorroborAI : rapport de corroboration RH / Temps</h1>
<p>Lecture seule des extractions. Chaque verdict renvoie à la règle du mapping et à la preuve. Les écarts systématiques sont signalés au niveau du jeu, pas par dossier.</p></header>
<div class="wrap">
  <section class="card">
    <div class="chips" id="chips"></div>
    <input type="search" id="q" placeholder="Filtrer par matricule, champ, verdict…" aria-label="Filtrer">
    <div class="list" id="list" role="listbox"></div>
  </section>
  <section class="card" id="detail" aria-live="polite"></section>
</div>
<script>
const DATA = __DATA__;
const ORDER = ["ANOMALIE","ANOMALIE PROBABLE (à valider)","À ARBITRER","ÉCART JUSTIFIÉ","CONFORME"];
const CLS = {"ANOMALIE":"v-ANOMALIE","ANOMALIE PROBABLE (à valider)":"v-PROB","À ARBITRER":"v-ARB","ÉCART JUSTIFIÉ":"v-JUST","CONFORME":"v-CONF"};
let active = null, sel = null, q = "";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function counts(){ const c={}; DATA.forEach(d=>c[d.verdict]=(c[d.verdict]||0)+1); return c; }
function chips(){
  const c = counts(); const el = document.getElementById("chips");
  el.innerHTML = "";
  const all = mk("Tous ("+DATA.length+")", null); el.appendChild(all);
  ORDER.filter(v=>c[v]).forEach(v=>el.appendChild(mk(v+" ("+c[v]+")", v)));
  function mk(label, v){ const b=document.createElement("button"); b.className="chip"; b.textContent=label; b.setAttribute("aria-pressed", String(active===v)); b.onclick=()=>{active=v;render();chips();}; return b; }
}
function list(){
  const items = DATA.filter(d => (!active || d.verdict===active) && (!q || (d.matricule+" "+d.verdict+" "+d.resume+" "+d.fields.map(f=>f["Champ cible"]).join(" ")).toLowerCase().includes(q)))
    .sort((a,b)=> ORDER.indexOf(a.verdict)-ORDER.indexOf(b.verdict) || a.matricule.localeCompare(b.matricule));
  const el = document.getElementById("list");
  el.innerHTML = items.map(d=>`<div class="row" role="option" tabindex="0" aria-selected="${sel===d.id}" data-id="${esc(d.id)}">
     <span><strong>${esc(d.matricule)}</strong> <span class="muted">· ${esc(d.type)} · poste ${esc(d.poste)}</span><br><span class="muted">${esc(d.resume)}</span></span>
     <span class="tag ${CLS[d.verdict]||""}">${esc(d.verdict)}</span></div>`).join("") || '<p class="muted">Aucun dossier.</p>';
  el.querySelectorAll(".row").forEach(r=>{ r.onclick=()=>{sel=r.dataset.id;render();}; r.onkeydown=e=>{if(e.key==="Enter"){sel=r.dataset.id;render();}}; });
}
function detail(){
  const d = DATA.find(x=>x.id===sel) || DATA.find(x=>x.verdict==="ANOMALIE") || DATA[0];
  if(!d){ document.getElementById("detail").innerHTML="<p class='muted'>Aucune donnée.</p>"; return; }
  sel = d.id;
  const rows = d.fields.map(f=>`<tr><td>${esc(f["Règle"])}</td><td>${esc(f["Champ cible"])}</td>
     <td class="exp">${esc(f["Valeur attendue"])}</td><td class="exp">${esc(f["Valeur cible"])}</td>
     <td>${esc(f["Statut"])}${f["Verdict"]?` <span class="tag ${CLS[f["Verdict"]]||""}">${esc(f["Verdict"])}</span>`:""}
     ${f["Confiance"]?`<br><span class="muted">confiance ${esc(f["Confiance"])}</span>`:""}</td>
     <td>${esc(f["Explication"])}${f["Preuves"]?`<br><span class="muted">${esc(f["Preuves"])}</span>`:""}
     <br><span class="muted">${esc(f["Référence mapping"])}</span></td></tr>`).join("");
  document.getElementById("detail").innerHTML = `
    <h2 style="margin:0 0 4px;font-size:17px">${esc(d.matricule)} · affectation ${esc(d.type)} · poste ${esc(d.poste)}</h2>
    <p class="tag ${CLS[d.verdict]||""}" style="margin:0 0 8px">${esc(d.verdict)}</p>
    <p class="muted" style="margin:0 0 10px">${esc(d.resume)}</p>
    ${rows ? `<div class="tablewrap"><table><thead><tr><th>Règle</th><th>Champ</th><th>Attendu</th><th>Cible</th><th>Statut</th><th>Justification et preuves</th></tr></thead><tbody>${rows}</tbody></table></div>`
           : `<div class="note">${d.matched ? "Tous les champs contrôlés concordent." : "Aucun enregistrement cible à comparer."}</div>`}`;
}
function render(){ list(); detail(); }
document.getElementById("q").addEventListener("input", e=>{ q=e.target.value.toLowerCase(); list(); });
chips(); render();
</script></body></html>
"""
