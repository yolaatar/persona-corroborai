"""Arbiter for cases the deterministic rules cannot close alone.

For each ambiguous or disputed finding, gather corroborating evidence from the
other extracts (job-detail history, the same person's other assignments,
contract flags) and produce:
  - a verdict: "ANOMALIE PROBABLE (à valider)" or "À ARBITRER"
  - a confidence score in [0, 1]
  - an explanation and the evidence it rests on

This is evidence-weighted reasoning, not a language model. No data leaves the
machine. An LLM can be plugged in later if the data owner approves it.
"""

from __future__ import annotations

import math

import pandas as pd

from .engine import A_ARBITRER, ECART_JUSTIFIE, V_A_ARBITRER, V_ANOMALIE_PROBABLE, Finding
from .rules import _is_missing

ANOMALY_THRESHOLD = 0.6  # at or above: "ANOMALIE PROBABLE"; below: "À ARBITRER"


def _detail_for_poste(detail: pd.DataFrame, poste) -> pd.DataFrame:
    if _is_missing(poste):
        return detail.iloc[0:0]
    return detail[detail["IdentifiantPoste"] == int(poste)].sort_values("date_effet")


def _mode(values: list[float]):
    values = [v for v in values if not _is_missing(v)]
    if not values:
        return None
    return max(set(values), key=values.count)


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "vide"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def arbitrate(f: Finding, s_idx: int, t_idx: int, source: pd.DataFrame, target: pd.DataFrame, ctx) -> None:
    src = source.loc[s_idx]
    tgt = target.loc[t_idx]
    detail = _detail_for_poste(ctx.detail, src["CodePoste"])
    ft = src.get("EstTempsPlein")
    evidence = [
        f"Poste {_fmt(src['CodePoste'])}, emploi {_fmt(src['CodeEmploi'])}, affectation {src['TypeAffectation']}.",
    ]

    other = target[(target["personId"] == src["Matricule"]) & (target.index != t_idx)]
    if len(other):
        evidence.append(
            "Autres affectations de la personne dans la cible : "
            + "; ".join(f"poste {_fmt(o['positionId'])}, {_fmt(o['weeklyHoursOverride'])} h/sem" for _, o in other.iterrows())
            + "."
        )

    if f.rule_id in ("R20", "R21"):
        _arbitrate_hours(f, src, tgt, detail, ft, evidence)
    elif f.rule_id == "R18":
        _arbitrate_start_date(f, src, tgt, detail, evidence)
    elif f.status == A_ARBITRER:
        f.verdict = V_A_ARBITRER
        f.confidence = 0.3
        f.explanation = f.explanation or "Cas ambigu : la règle seule ne permet pas de conclure."
    f.evidence = evidence + f.evidence


def _arbitrate_hours(f, src, tgt, detail, ft, evidence):
    column = "HeuresSemaineContrat" if f.rule_id == "R20" else "HeuresJourContrat"
    detail_value = _mode(detail[column].tolist()) if len(detail) else None
    src_col = "HeuresNormeHebdo" if f.rule_id == "R20" else "HeuresNormeQuotidienne"
    tgt_value = None if _is_missing(tgt[f.target]) else float(tgt[f.target])
    src_value = None if _is_missing(src[src_col]) else float(src[src_col])
    unit = "h/sem" if f.rule_id == "R20" else "h/jour"
    evidence.append(
        f"Détail de poste : {_fmt(detail_value)} {unit} (colonne {column}); "
        f"temps plein selon la source : {ft}."
    )

    if detail_value is not None and tgt_value == detail_value:
        if src_value is None:
            f.verdict = V_A_ARBITRER
            f.confidence = 0.5
            f.explanation = (
                f"Source vide pour ce champ. La cible reprend {_fmt(tgt_value)} {unit}, valeur du détail de poste "
                "que le mapping n'associe pas à ce champ. Probable valeur par défaut : à confirmer."
            )
        else:
            f.verdict = V_ANOMALIE_PROBABLE
            f.confidence = 0.7
            f.explanation = (
                f"La source indique {_fmt(src_value)} {unit}, la cible reprend {_fmt(tgt_value)} {unit}, valeur du détail "
                "de poste. Le mapping associe ce champ à la source et non au détail : probable valeur par défaut "
                "écrasant l'horaire réel."
            )
        f.evidence.append(f"Cible = détail de poste ({_fmt(detail_value)} {unit}); source = {_fmt(src_value)}.")
        return

    f.verdict = V_A_ARBITRER
    f.confidence = 0.4
    f.explanation = (
        f"Écart d'horaire (source {_fmt(src_value)}, cible {_fmt(tgt_value)} {unit}) qui ne correspond pas au détail "
        "de poste. Vérifier la convention de l'horaire pour ce poste."
    )


def _arbitrate_start_date(f, src, tgt, detail, evidence):
    tgt_date = None if _is_missing(tgt[f.target]) else pd.to_datetime(tgt[f.target]).date()
    src_date = None if _is_missing(src["DateEntréePoste"]) else pd.to_datetime(src["DateEntréePoste"]).date()
    if detail.empty or tgt_date is None:
        return
    last = detail["date_effet"].max()
    evidence.append(
        f"Historique du poste : {len(detail)} effets, de {detail['date_effet'].min()} à {last}."
    )
    if tgt_date == last and tgt_date != src_date:
        # Organisers confirmed (Discord): the source holds the position effective date only,
        # the target holds the transformed rule value. The difference is intended.
        f.status = ECART_JUSTIFIE
        f.confidence = 0.9
        f.explanation = (
            f"Date cible {tgt_date} = dernière date d'effet du détail de poste, valeur issue de la règle de "
            f"transformation du mapping. La source ne porte que la date d'effet du poste ({src_date}). "
            "Écart voulu, confirmé par les organisateurs."
        )
        f.evidence.append("Date cible = règle transformée (détail de poste), confirmée par les organisateurs.")
