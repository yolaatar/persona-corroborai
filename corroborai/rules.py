"""Deterministic business rules, one per mapped target field.

Each rule states how the expected target value is derived from the source
extract, following Mapping.xlsx. A rule returns:
  - a value: the expected target value
  - UNKNOWN: the rule cannot decide (for example, a status code absent from the
    motif table). Routed to the arbitration step.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Callable

import pandas as pd



class _Sentinel:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return self.name


UNKNOWN = _Sentinel("UNKNOWN")

# Contract type from the employee category (Mapping.xlsx, "Type d'employé").
# EMPTP_CD is the source CatégorieEmploi column. Permanent and full-time flags
# only matter for the "V" category.
CONTRACT_BY_CATEGORY = {
    "T": "KELH",
    "O": "WHX",
    "M": "CEGQ",
    "R": "CNZC",
    "J": "RMQ",
    "Z": "JAW",
    "Q": "TRSY",
}
CONTRACT_V = {
    (True, True): "JWN",  # PERM=1, FT=1
    (True, False): "XFLR",  # PERM=1, FT=0
}

# Access-processing codes ("Code de traitement des accès"), from the
# "Règles situation d'emploi" sheet.
ACCESS_ACTIVE = {0, 1}
ACCESS_ABSENT = {2, 3, 6, 7}


def _is_missing(value) -> bool:
    if value is None or value is pd.NaT:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _yes_no(value) -> bool | None:
    if _is_missing(value):
        return None
    return str(value).strip().lower() in {"oui", "1", "true", "yes"}


def normalize(kind: str, value):
    """Make two values comparable. Returns None for missing values."""
    if _is_missing(value):
        return None
    if kind == "date":
        return pd.to_datetime(value).date()
    if kind == "number":
        return float(value)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "oui", "1"}
        return bool(value)
    if kind == "code":
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, int):
            return str(value)
        return str(value).strip()
    # text
    return str(value).strip()


@dataclass(frozen=True)
class Rule:
    rule_id: str
    target: str  # target column in Système B
    kind: str  # date | number | bool | code | text
    mapping_source: str  # source column that anchors the mapping row ("" if derived)
    description: str
    expected: Callable  # (src_row, ctx) -> value | UNKNOWN
    # Severity when the value differs: "anomaly" (real error) or
    # "ambiguous" (needs arbitration).
    severity: str = "anomaly"
    # Set when the rule is known to disagree on every row (see engine).
    systemic_note: str = ""
    # True when the rule converts a source code through a reference table. A
    # value that differs from the raw source code is then a documented,
    # justified difference, not an error.
    conversion: bool = False


# ---------- expected-value functions ----------

def _given(row, ctx):
    return row["PrénomUsuel"]


def _surname(row, ctx):
    return row["NomFamille"]


def _onboard(row, ctx):
    return row["DateEmbaucheRécente"]


def _email(row, ctx):
    # Rule: first letter of first name + last name + last 3 digits of the
    # employee code + "@loto-quebec.com", accents removed.
    local = f"{row['PrénomUsuel'][:1]}{row['NomFamille']}{str(int(row['Matricule']))[-3:]}"
    return f"{_strip_accents(local)}@loto-quebec.com"


def _site_id(row, ctx):
    return row["CodeSite"]


def _site_name(row, ctx):
    return row["LibelléSite"]


def _division_id(row, ctx):
    return row["CodeDirection"]


def _division_code(row, ctx):
    return row["CodeImputation"]


def _division_name(row, ctx):
    return f"{int(row['CodeDirection']):05d}-{row['LibelléDirection']}"


def _position_id(row, ctx):
    return row["CodeEmploi"]


def _position_name(row, ctx):
    return f"{int(row['CodeEmploi'])}-{row['IntituléEmploi']}"


def _pay_grade(row, ctx):
    return row["ÉchelleSalariale"]


def _contract(row, ctx):
    category = str(row["CatégorieEmploi"]).strip()
    if category == "V":
        perm = _yes_no(row["EstPermanent"])
        ft = _yes_no(row["EstTempsPlein"])
        return CONTRACT_V.get((perm, ft), UNKNOWN)
    return CONTRACT_BY_CATEGORY.get(category, UNKNOWN)


def _access_status(row) -> str | None:
    code = row["CodeSuspensionAccès"]
    if _is_missing(code):
        return None
    code = int(code)
    if code in ACCESS_ACTIVE:
        return "Actif"
    if code in ACCESS_ABSENT:
        return "Absence complète"
    return None


def _detailed_status(row, ctx):
    status = _access_status(row)
    return UNKNOWN if status is None else status


def _expected_return(row, ctx):
    if _access_status(row) == "Absence complète":
        return row["DateRetourAnticipée"]
    return None


def _status_reason(row, ctx):
    if _access_status(row) != "Absence complète":
        return None
    entry = ctx["motif"].get(int(row["CodeRaisonStatut"]))
    return UNKNOWN if entry is None else entry["remphor"]


def _is_primary(row, ctx):
    return {"P": True, "A": False, "S": False}.get(str(row["TypeAffectation"]).strip(), UNKNOWN)


def _is_temporary(row, ctx):
    return {"P": False, "A": True, "S": False}.get(str(row["TypeAffectation"]).strip(), UNKNOWN)


def _assign_start(row, ctx):
    return row["DateEntréePoste"]


def _assign_end(row, ctx):
    return row["DateSortiePoste"]


def _weekly_hours(row, ctx):
    return row["HeuresNormeHebdo"]


def _daily_hours(row, ctx):
    return row["HeuresNormeQuotidienne"]


RULES: tuple[Rule, ...] = (
    Rule("R01", "givenName", "text", "PrénomUsuel", "Prénom de l'employé", _given),
    Rule("R02", "surname", "text", "NomFamille", "Nom de l'employé", _surname),
    Rule(
        "R03",
        "contactEmail",
        "text",
        "",
        "Courriel : initiale du prénom + nom + 3 derniers chiffres du code, sans accents",
        _email,
    ),
    Rule("R04", "onboardDate", "date", "DateEmbaucheRécente", "Date d'embauche", _onboard),
    Rule("R05", "siteId", "code", "CodeSite", "Code d'emplacement", _site_id),
    Rule("R06", "siteCode", "code", "CodeSite", "Code d'emplacement", _site_id),
    Rule("R07", "siteName", "text", "LibelléSite", "Emplacement", _site_name),
    Rule("R08", "divisionId", "code", "CodeDirection", "Département", _division_id),
    Rule("R09", "divisionCode", "code", "CodeImputation", "Code de département", _division_code),
    Rule(
        "R10",
        "divisionName",
        "text",
        "LibelléDirection",
        "Concaténation unité adm. (5 car.) + '-' + libellé",
        _division_name,
    ),
    Rule("R11", "positionId", "code", "CodeEmploi", "Id du rôle", _position_id),
    Rule("R12", "positionCode", "code", "CodeEmploi", "Code du rôle", _position_id),
    Rule(
        "R13",
        "positionName",
        "text",
        "IntituléEmploi",
        "Concaténation code emploi + '-' + libellé emploi",
        _position_name,
        systemic_note="Préfixe numérique différent du code emploi sur l'ensemble des lignes",
    ),
    Rule("R14", "payGradeId", "code", "ÉchelleSalariale", "Niveau du groupe de rémunération", _pay_grade),
    Rule(
        "R15",
        "contractTypeCode",
        "code",
        "CatégorieEmploi",
        "Type d'employé (CatégorieEmploi + PERM_IND + FT_IND)",
        _contract,
    ),
    Rule(
        "R16",
        "isPrimaryAssignment",
        "bool",
        "TypeAffectation",
        "Type d'affectation : P = primaire",
        _is_primary,
    ),
    Rule(
        "R17",
        "isTemporaryAssignment",
        "bool",
        "TypeAffectation",
        "Type d'affectation : A = temporaire",
        _is_temporary,
    ),
    Rule("R18", "assignmentStartDate", "date", "DateEntréePoste", "Date d'effet du poste", _assign_start),
    Rule("R19", "assignmentEndDate", "date", "DateSortiePoste", "Date d'expiration du poste", _assign_end),
    Rule(
        "R20",
        "weeklyHoursOverride",
        "number",
        "HeuresNormeHebdo",
        "Nombre d'heures par semaine du poste",
        _weekly_hours,
        severity="ambiguous",
    ),
    Rule(
        "R21",
        "dailyHoursOverride",
        "number",
        "HeuresNormeQuotidienne",
        "Nombre d'heures par jour du poste",
        _daily_hours,
        severity="ambiguous",
    ),
    Rule(
        "R22",
        "detailedStatus",
        "text",
        "CodeSuspensionAccès",
        "Situation d'emploi selon le code de traitement des accès",
        _detailed_status,
    ),
    Rule(
        "R23",
        "expectedReturnDate",
        "date",
        "DateRetourAnticipée",
        "Date de retour prévue (seulement en absence complète)",
        _expected_return,
    ),
    Rule(
        "R24",
        "statusReasonCode",
        "code",
        "CodeRaisonStatut",
        "Code de situation d'emploi Remphor (table des motifs)",
        _status_reason,
        conversion=True,
    ),
)

RULES_BY_ID = {r.rule_id: r for r in RULES}

# Source columns read by the rules (directly or through a derived value).
SOURCE_COLUMNS_USED = frozenset(
    {
        "Matricule",
        "PrénomUsuel",
        "NomFamille",
        "DateEmbaucheRécente",
        "CodeSite",
        "LibelléSite",
        "CodeDirection",
        "LibelléDirection",
        "CodeImputation",
        "CodeEmploi",
        "IntituléEmploi",
        "ÉchelleSalariale",
        "CatégorieEmploi",
        "EstPermanent",
        "EstTempsPlein",
        "TypeAffectation",
        "DateEntréePoste",
        "DateSortiePoste",
        "HeuresNormeHebdo",
        "HeuresNormeQuotidienne",
        "CodeSuspensionAccès",
        "DateRetourAnticipée",
        "CodeRaisonStatut",
        "CodePoste",  # join key to the job-detail extract
    }
)
