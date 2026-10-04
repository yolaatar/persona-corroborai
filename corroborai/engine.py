"""Corroboration engine: matching, rule evaluation, and verdicts.

Pipeline
  1. match each source row (Système A) to one target row (Système B)
  2. evaluate every mapped rule on each matched pair
  3. flag systematic disagreements (same rule failing on most rows)
  4. look for cross-record inversions (two records with each other's values)
  5. send ambiguous findings to the arbiter, then roll up a verdict per row
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .loader import Inputs, fix_mojibake
from .rules import RULES, UNKNOWN, Rule, _is_missing, normalize

# Finding statuses (per field)
OK = "OK"
ECART_JUSTIFIE = "ECART_JUSTIFIE"  # differs only by encoding or presentation
A_ARBITRER = "A_ARBITRER"  # rule cannot decide, or the value is ambiguous
ECART = "ECART"  # differs and the rule is decisive
ECART_SYSTEMATIQUE = "ECART_SYSTEMATIQUE"  # same rule fails on most rows
NON_VERIFIABLE = "NON_VERIFIABLE"

# Row verdicts (rolled up), most severe first
V_ANOMALIE = "ANOMALIE"
V_ANOMALIE_PROBABLE = "ANOMALIE PROBABLE (à valider)"
V_A_ARBITRER = "À ARBITRER"
V_SYSTEMATIQUE = "ÉCART SYSTÉMATIQUE (à confirmer)"
V_JUSTIFIE = "ÉCART JUSTIFIÉ"
V_NON_VERIFIABLE = "NON VÉRIFIABLE"
V_CONFORME = "CONFORME"

SEVERITY_ORDER = [
    V_ANOMALIE,
    V_ANOMALIE_PROBABLE,
    V_A_ARBITRER,
    V_SYSTEMATIQUE,
    V_JUSTIFIE,
    V_NON_VERIFIABLE,
    V_CONFORME,
]

SYSTEMATIC_MIN_ROWS = 5
SYSTEMATIC_RATIO = 0.8


@dataclass
class Finding:
    rule_id: str
    target: str
    description: str
    mapping_ref: str
    status: str
    source_value: object
    expected: object
    actual: object
    explanation: str = ""
    confidence: float | None = None
    verdict: str | None = None  # set by the arbiter for ambiguous findings
    evidence: list[str] = field(default_factory=list)


@dataclass
class RowResult:
    source_index: int | None
    target_index: int | None
    matricule: object
    poste: object
    code_emploi: object
    type_affectation: object
    verdict: str
    findings: list[Finding]
    summary: str = ""


@dataclass
class Context:
    inputs: Inputs
    motif: dict
    detail: pd.DataFrame


def _mapping_ref(rule: Rule, inputs: Inputs) -> str:
    row = inputs.mapping_rows.get(rule.mapping_source) if rule.mapping_source else None
    if row:
        return f"Mapping.xlsx > Mapping > ligne {row} ({rule.description})"
    return f"Mapping.xlsx > Mapping ({rule.description})"


# ---------- matching ----------

def match_rows(source: pd.DataFrame, target: pd.DataFrame) -> tuple[list[tuple[int, int | None]], list[int]]:
    """Return (source_index, target_index or None) for every source row, and the unmatched target indexes.

    Key: matricule + code emploi + date d'effet. If that fails, fall back to
    matricule + code emploi when it identifies one target row.
    """
    used: set[int] = set()
    pairs = []
    tgt_dates = target["assignmentStartDate"].map(lambda v: None if _is_missing(v) else pd.to_datetime(v).date())
    src_dates = source["DateEntréePoste"].map(lambda v: None if _is_missing(v) else pd.to_datetime(v).date())
    for s_idx, s in source.iterrows():
        cands = [
            t_idx
            for t_idx, t in target.iterrows()
            if t_idx not in used
            and t["personId"] == s["Matricule"]
            and t["positionId"] == s["CodeEmploi"]
        ]
        exact = [t for t in cands if tgt_dates[t] == src_dates[s_idx]]
        chosen = None
        if len(exact) == 1:
            chosen = exact[0]
        elif len(cands) == 1:
            chosen = cands[0]
        if chosen is not None:
            used.add(chosen)
        pairs.append((s_idx, chosen))
    return pairs, sorted(set(target.index) - used)


# ---------- field evaluation ----------

def _int_text(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _kind_value(rule: Rule, value):
    try:
        return normalize(rule.kind, value)
    except (ValueError, TypeError):
        return str(value)


def evaluate_field(rule: Rule, src_row: pd.Series, tgt_row: pd.Series, ctx: Context, inputs: Inputs) -> Finding:
    expected = rule.expected(src_row, {"motif": ctx.motif, "detail": ctx.detail})
    raw_actual = tgt_row[rule.target] if rule.target in tgt_row.index else None
    source_value = src_row[rule.mapping_source] if rule.mapping_source and rule.mapping_source in src_row.index else None
    base = dict(
        rule_id=rule.rule_id,
        target=rule.target,
        description=rule.description,
        mapping_ref=_mapping_ref(rule, inputs),
        source_value=None if _is_missing(source_value) else source_value,
        expected=None if _is_missing(expected) else expected,
        actual=None if _is_missing(raw_actual) else raw_actual,
    )

    if expected is UNKNOWN:
        return Finding(
            status=A_ARBITRER,
            explanation="La règle ne peut pas trancher (valeur absente de la table de référence ou combinaison non prévue).",
            **base,
        )

    exp_n = _kind_value(rule, expected) if not _is_missing(expected) else None
    act_fixed = fix_mojibake(raw_actual) if isinstance(raw_actual, str) else raw_actual
    act_n = _kind_value(rule, act_fixed) if not _is_missing(act_fixed) else None

    if exp_n == act_n:
        if isinstance(raw_actual, str) and raw_actual != act_fixed:
            return Finding(
                status=ECART_JUSTIFIE,
                explanation=f"Valeur identique après correction d'encodage ({raw_actual!r} lu comme {act_fixed!r}).",
                **base,
            )
        if (
            rule.conversion
            and not _is_missing(act_fixed)
            and not _is_missing(source_value)
            and str(source_value) != str(act_fixed)
        ):
            return Finding(
                status=ECART_JUSTIFIE,
                explanation=(
                    f"Conversion par table de référence : code source {_int_text(source_value)} → valeur cible {_int_text(act_fixed)} "
                    "(Mapping.xlsx > Jointure - Motif des situations ; Motif de la situation d'emploi.xlsx)."
                ),
                **base,
            )
        return Finding(status=OK, **base)

    if rule.severity == "ambiguous":
        return Finding(status=A_ARBITRER, explanation="Écart sur une valeur que le mapping ne tranche pas seul.", **base)
    return Finding(status=ECART, explanation="Valeur cible différente de la valeur attendue selon la règle.", **base)


def evaluate_row(s_idx, t_idx, source, target, ctx: Context, inputs: Inputs) -> list[Finding]:
    src_row = source.loc[s_idx]
    tgt_row = target.loc[t_idx]
    return [evaluate_field(rule, src_row, tgt_row, ctx, inputs) for rule in RULES]


# ---------- dataset-level passes ----------

def mark_systematic(all_findings: dict[int, list[Finding]]) -> dict[str, dict]:
    """A rule that fails on most rows is a systematic disagreement, not per-row errors."""
    by_rule: dict[str, list[Finding]] = {}
    for fs in all_findings.values():
        for f in fs:
            if f.status in (OK, ECART, ECART_JUSTIFIE):
                by_rule.setdefault(f.rule_id, []).append(f)
    notes = {}
    for rule_id, fs in by_rule.items():
        bad = [f for f in fs if f.status == ECART]
        if len(fs) >= SYSTEMATIC_MIN_ROWS and len(bad) / len(fs) >= SYSTEMATIC_RATIO:
            for f in bad:
                f.status = ECART_SYSTEMATIQUE
                f.explanation = (
                    f"Écart sur {len(bad)}/{len(fs)} lignes évaluables : la même règle échoue presque partout. "
                    "Ce n'est pas une erreur par ligne ; probable effet de génération ou d'anonymisation du jeu, à confirmer."
                )
            notes[rule_id] = {"fails": len(bad), "evaluable": len(fs)}
    return notes


def mark_inversions(all_findings: dict[int, list[Finding]], rows_meta: dict[int, dict]) -> None:
    """Two records whose target values are each other's expected values: a swap."""
    by_rule: dict[str, list[tuple[int, Finding]]] = {}
    for s_idx, fs in all_findings.items():
        for f in fs:
            if f.status == ECART:
                by_rule.setdefault(f.rule_id, []).append((s_idx, f))
    for rule_id, items in by_rule.items():
        for i, (si, fi) in enumerate(items):
            for sj, fj in items[i + 1 :]:
                if fi.actual == fj.expected and fj.actual == fi.expected and fi.actual is not None:
                    other_i = rows_meta[si]["matricule"]
                    other_j = rows_meta[sj]["matricule"]
                    note_i = f"Valeur attendue pour un autre dossier ({other_j}) : probable inversion lors du transfert."
                    note_j = f"Valeur attendue pour un autre dossier ({other_i}) : probable inversion lors du transfert."
                    fi.evidence.append(note_i)
                    fj.evidence.append(note_j)
                    fi.explanation = f"{fi.explanation} {note_i}".strip()
                    fj.explanation = f"{fj.explanation} {note_j}".strip()


def roll_up(findings: list[Finding], matched: bool) -> str:
    if not matched:
        return V_ANOMALIE
    verdicts: set[str] = set()
    for f in findings:
        if f.status == ECART:
            verdicts.add(V_ANOMALIE)
        elif f.status == A_ARBITRER:
            verdicts.add(f.verdict or V_A_ARBITRER)
        # ECART_SYSTEMATIQUE is a dataset-level finding: it does not make an
        # individual record wrong, so it is reported in the summary only.
        elif f.status == ECART_JUSTIFIE:
            verdicts.add(V_JUSTIFIE)
        elif f.status == NON_VERIFIABLE:
            verdicts.add(V_NON_VERIFIABLE)
    for v in SEVERITY_ORDER:
        if v in verdicts:
            return v
    return V_CONFORME


def run_engine(inputs: Inputs) -> tuple[list[RowResult], dict]:
    from .arbitre import arbitrate  # local import avoids a cycle

    ctx = Context(inputs=inputs, motif=inputs.motif, detail=inputs.detail)
    source, target = inputs.source, inputs.target
    pairs, unmatched_targets = match_rows(source, target)

    all_findings: dict[int, list[Finding]] = {}
    rows_meta: dict[int, dict] = {}
    for s_idx, t_idx in pairs:
        s = source.loc[s_idx]
        rows_meta[s_idx] = dict(
            matricule=s["Matricule"],
            poste=s["CodePoste"],
            code_emploi=s["CodeEmploi"],
            type_affectation=s["TypeAffectation"],
            target_index=t_idx,
        )
        if t_idx is None:
            all_findings[s_idx] = []
        else:
            all_findings[s_idx] = evaluate_row(s_idx, t_idx, source, target, ctx, inputs)

    systematic = mark_systematic(all_findings)
    mark_inversions(all_findings, rows_meta)

    results = []
    for s_idx, t_idx in pairs:
        meta = rows_meta[s_idx]
        fs = all_findings[s_idx]
        if t_idx is not None:
            for f in fs:
                if f.status == A_ARBITRER or f.status == ECART:
                    arbitrate(f, s_idx, t_idx, source, target, ctx)
        verdict = roll_up(fs, matched=t_idx is not None)
        summary = _summary(verdict, fs, t_idx is not None, meta)
        results.append(
            RowResult(
                source_index=s_idx,
                target_index=t_idx,
                matricule=meta["matricule"],
                poste=meta["poste"],
                code_emploi=meta["code_emploi"],
                type_affectation=meta["type_affectation"],
                verdict=verdict,
                findings=fs,
                summary=summary,
            )
        )

    for t_idx in unmatched_targets:
        t = target.loc[t_idx]
        results.append(
            RowResult(
                source_index=None,
                target_index=t_idx,
                matricule=t["personId"],
                poste=None,
                code_emploi=t["positionId"],
                type_affectation=None,
                verdict=V_ANOMALIE,
                findings=[],
                summary="Enregistrement présent dans la cible sans équivalent dans la source.",
            )
        )

    meta_info = {"systematic": systematic, "unmatched_targets": unmatched_targets}
    return results, meta_info


def _summary(verdict, fs, matched, meta) -> str:
    if not matched:
        return (
            f"Affectation {meta['type_affectation']} (poste {meta['poste']}) absente de la cible. "
            "Aucune règle de filtrage dans le mapping ne l'exclut."
        )
    bad = [f.target for f in fs if f.status in (ECART, A_ARBITRER)]
    justified = [f.target for f in fs if f.status == ECART_JUSTIFIE]
    systematic = [f.target for f in fs if f.status == ECART_SYSTEMATIQUE]
    parts = []
    if bad:
        parts.append("écarts : " + ", ".join(sorted(set(bad))))
    if systematic:
        parts.append("systématique : " + ", ".join(sorted(set(systematic))))
    if justified:
        parts.append("justifié : " + ", ".join(sorted(set(justified))))
    return "; ".join(parts) if parts else "Tous les champs mappés concordent."
