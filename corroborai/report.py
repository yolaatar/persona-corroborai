"""Writes the corroboration report: Excel workbook, flat CSV, and a Markdown summary.

Input files are only read. Outputs go to a separate folder, and the input
hashes are recorded before and after the run as evidence that they were not
modified.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from .engine import (
    A_ARBITRER,
    ECART,
    ECART_JUSTIFIE,
    ECART_SYSTEMATIQUE,
    OK,
    V_ANOMALIE,
    V_ANOMALIE_PROBABLE,
    V_A_ARBITRER,
    V_CONFORME,
    V_JUSTIFIE,
    V_SYSTEMATIQUE,
    RowResult,
)
from .loader import DETAIL_FILE, MAPPING_FILE, MOTIF_FILE, SOURCE_FILE, TARGET_FILE, Inputs
from .rules import RULES, SOURCE_COLUMNS_USED

STATUS_LABEL = {
    OK: "OK",
    ECART_JUSTIFIE: "Écart justifié",
    A_ARBITRER: "À arbitrer",
    ECART: "Écart",
    ECART_SYSTEMATIQUE: "Écart systématique",
}

VERDICT_ORDER = [
    V_ANOMALIE,
    V_ANOMALIE_PROBABLE,
    V_A_ARBITRER,
    V_SYSTEMATIQUE,
    V_JUSTIFIE,
    V_CONFORME,
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def input_hashes(root: Path) -> dict[str, str]:
    names = [SOURCE_FILE, TARGET_FILE, MAPPING_FILE, MOTIF_FILE, DETAIL_FILE]
    return {n: sha256(root / n) for n in names}


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def findings_table(results: list[RowResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        for f in r.findings:
            rows.append(
                {
                    "Matricule": _fmt(r.matricule),
                    "Poste": _fmt(r.poste),
                    "Type affectation": _fmt(r.type_affectation),
                    "Règle": f.rule_id,
                    "Champ cible": f.target,
                    "Description (mapping)": f.description,
                    "Référence mapping": f.mapping_ref,
                    "Valeur source": _fmt(f.source_value),
                    "Valeur attendue": _fmt(f.expected),
                    "Valeur cible": _fmt(f.actual),
                    "Statut": STATUS_LABEL.get(f.status, f.status),
                    "Verdict": f.verdict or "",
                    "Confiance": "" if f.confidence is None else f"{f.confidence:.2f}",
                    "Explication": f.explanation,
                    "Preuves": " | ".join(f.evidence),
                }
            )
    return pd.DataFrame(rows)


def verdicts_table(results: list[RowResult], inputs: Inputs) -> pd.DataFrame:
    rows = []
    for r in results:
        bad = sorted({f.target for f in r.findings if f.status in (ECART, A_ARBITRER)})
        justified = sorted({f.target for f in r.findings if f.status == ECART_JUSTIFIE})
        systematic = sorted({f.target for f in r.findings if f.status == ECART_SYSTEMATIQUE})
        rows.append(
            {
                "Matricule": _fmt(r.matricule),
                "Poste": _fmt(r.poste),
                "Code emploi": _fmt(r.code_emploi),
                "Type affectation": _fmt(r.type_affectation),
                "Ligne source": "" if r.source_index is None else int(r.source_index) + 2,
                "Ligne cible": "" if r.target_index is None else int(r.target_index) + 2,
                "Verdict": r.verdict,
                "Écarts à investiguer": ", ".join(bad),
                "Écarts justifiés": ", ".join(justified),
                "Écarts systématiques (non individuels)": ", ".join(systematic),
                "Résumé": r.summary,
            }
        )
    order = {v: i for i, v in enumerate(VERDICT_ORDER)}
    df = pd.DataFrame(rows)
    df["_o"] = df["Verdict"].map(lambda v: order.get(v, 99))
    return df.sort_values(["_o", "Matricule", "Type affectation"]).drop(columns="_o").reset_index(drop=True)


def uncontrolled_fields(inputs: Inputs) -> pd.DataFrame:
    rows = []
    for col in inputs.source.columns:
        if col not in SOURCE_COLUMNS_USED:
            rows.append({"Système": "A - RH", "Champ": col, "Raison": "Hors mapping ou sans règle de corroboration"})
    used_tgt = {r.target for r in RULES} | {"personId"}
    for col in inputs.target.columns:
        if col not in used_tgt:
            rows.append({"Système": "B - Temps", "Champ": col, "Raison": "Hors mapping ou sans source correspondante"})
    return pd.DataFrame(rows)


def summary_counts(results: list[RowResult]) -> pd.DataFrame:
    c = Counter(r.verdict for r in results)
    total = len(results)
    rows = [{"Verdict": v, "Nombre": c.get(v, 0), "Part": f"{c.get(v, 0) / total:.0%}"} for v in VERDICT_ORDER if v in c]
    rows.append({"Verdict": "Total", "Nombre": total, "Part": "100%"})
    return pd.DataFrame(rows)


def write_outputs(results, meta, inputs: Inputs, input_root: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    before = input_hashes(input_root)

    findings = findings_table(results)
    verdicts = verdicts_table(results, inputs)
    counts = summary_counts(results)
    uncontrolled = uncontrolled_fields(inputs)
    systematic_rows = [
        {"Règle": rid, "Lignes en écart": v["fails"], "Lignes évaluées": v["evaluable"]}
        for rid, v in meta["systematic"].items()
    ]
    systematic = pd.DataFrame(systematic_rows)
    anomalies = verdicts[verdicts["Verdict"].isin([V_ANOMALIE, V_ANOMALIE_PROBABLE, V_A_ARBITRER])].copy()

    after = input_hashes(input_root)
    integrity = pd.DataFrame(
        [{"Fichier": k, "SHA-256 avant": before[k], "SHA-256 après": after[k], "Inchangé": before[k] == after[k]} for k in before]
    )
    if not all(before[k] == after[k] for k in before):
        raise RuntimeError("Un fichier d'entrée a changé pendant l'analyse")

    xlsx = out_dir / "rapport_corroboration.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        counts.to_excel(xw, sheet_name="Synthèse", index=False, startrow=1)
        systematic.to_excel(xw, sheet_name="Synthèse", index=False, startrow=len(counts) + 5)
        verdicts.to_excel(xw, sheet_name="Verdicts par ligne", index=False)
        anomalies.to_excel(xw, sheet_name="Anomalies à investiguer", index=False)
        findings.to_excel(xw, sheet_name="Détail des règles", index=False)
        uncontrolled.to_excel(xw, sheet_name="Champs non contrôlés", index=False)
        integrity.to_excel(xw, sheet_name="Intégrité des entrées", index=False)
    _autosize(xlsx)

    findings.to_csv(out_dir / "rapport_corroboration_details.csv", index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    verdicts.to_csv(out_dir / "rapport_corroboration_verdicts.csv", index=False, encoding="utf-8-sig")

    from .viewer import write_viewer

    write_viewer(results, verdicts, findings, out_dir / "index.html")
    (out_dir / "rapport.md").write_text(_markdown(counts, verdicts, findings, systematic, uncontrolled, integrity), encoding="utf-8")
    run_info = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": before,
        "rows_source": int(len(inputs.source)),
        "rows_target": int(len(inputs.target)),
        "verdict_counts": counts[counts["Verdict"] != "Total"].set_index("Verdict")["Nombre"].to_dict(),
        "unmatched_target_indexes": [int(i) for i in meta["unmatched_targets"]],
    }
    (out_dir / "run.json").write_text(json.dumps(run_info, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_info


def _autosize(path: Path) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font

    wb = load_workbook(path)
    for ws in wb.worksheets:
        for cell in ws[1] if ws.title != "Synthèse" else []:
            cell.font = Font(bold=True)
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2" if ws.title != "Synthèse" else None
    wb.save(path)


def _markdown(counts, verdicts, findings, systematic, uncontrolled, integrity) -> str:
    def table(df: pd.DataFrame) -> str:
        if df.empty:
            return "_(aucun)_"
        cols = list(df.columns)
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
        for _, r in df.iterrows():
            lines.append("| " + " | ".join(str(r[c]).replace("|", "/").replace("\n", " ") for c in cols) + " |")
        return "\n".join(lines)

    anomalies = verdicts[verdicts["Verdict"].isin([V_ANOMALIE, V_ANOMALIE_PROBABLE, V_A_ARBITRER])]
    justified = verdicts[verdicts["Verdict"] == V_JUSTIFIE]
    conforme = verdicts[verdicts["Verdict"] == V_CONFORME]
    return f"""# Rapport de corroboration RH / Temps

Ce rapport est généré par `run.py`. Les fichiers d'entrée n'ont pas été modifiés (empreintes SHA-256 ci-dessous).

## Synthèse

{table(counts)}

## Écarts systématiques (à confirmer, pas des erreurs par ligne)

Une règle qui échoue sur presque toutes les lignes indique un effet de génération ou d'anonymisation du jeu, pas une erreur par dossier.

{table(systematic)}

## Anomalies à investiguer

{table(anomalies[["Matricule", "Poste", "Type affectation", "Verdict", "Écarts à investiguer", "Résumé"]])}

Le détail par champ, avec la référence au mapping, la valeur attendue et la preuve, est dans `rapport_corroboration_details.csv` et dans l'onglet *Détail des règles* du classeur Excel.

## Écarts justifiés (conversion par table ou encodage)

{table(justified[["Matricule", "Poste", "Type affectation", "Résumé"]])}

## Cas conformes

{table(conforme[["Matricule", "Poste", "Type affectation"]])}

## Démonstration des trois types de cas

{_demo(verdicts, findings)}

## Champs non contrôlés

Champs présents dans les extractions mais absents du mapping, donc non corroborés. Le mapping est la seule référence.

{table(uncontrolled)}

## Intégrité des entrées

{table(integrity)}
"""


def _demo(verdicts: pd.DataFrame, findings: pd.DataFrame) -> str:
    """One conforming record, one justified deviation, one real anomaly, with their field evidence."""
    picks = []
    conf = verdicts[verdicts["Verdict"] == V_CONFORME]
    just = verdicts[verdicts["Verdict"] == V_JUSTIFIE]
    anom = verdicts[verdicts["Verdict"] == V_ANOMALIE]
    if not conf.empty:
        picks.append(("1. Cas conforme", conf.iloc[0]))
    if not just.empty:
        picks.append(("2. Écart justifié", just.iloc[0]))
    if not anom.empty:
        # prefer an anomaly with cross-record evidence (a swap) when there is one
        swap = findings[findings["Explication"].str.contains("inversion", na=False)]
        chosen = anom.iloc[0]
        if not swap.empty:
            hit = anom[(anom["Matricule"] == swap.iloc[0]["Matricule"]) & (anom["Type affectation"] == swap.iloc[0]["Type affectation"])]
            if not hit.empty:
                chosen = hit.iloc[0]
        picks.append(("3. Vraie anomalie", chosen))

    out = []
    for label, row in picks:
        out.append(f"### {label} : matricule {row['Matricule']}, affectation {row['Type affectation']}, poste {row['Poste']}")
        out.append(f"Verdict : **{row['Verdict']}**. {row['Résumé']}")
        sub = findings[(findings["Matricule"] == row["Matricule"]) & (findings["Type affectation"] == row["Type affectation"])]
        sub = sub[sub["Statut"].isin(["Écart", "Écart justifié", "À arbitrer"])]
        if sub.empty:
            out.append("Tous les champs contrôlés concordent. Le seul écart restant est systématique (voir ci-dessus).")
        else:
            out.append("")
            out.append(_md_table(sub[["Règle", "Champ cible", "Valeur attendue", "Valeur cible", "Statut", "Explication", "Référence mapping"]]))
        out.append("")
    return "\n".join(out) if out else "_(aucun cas)_"


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]).replace("|", "/").replace("\n", " ") for c in cols) + " |")
    return "\n".join(lines)
