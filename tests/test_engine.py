"""Regression tests on the official extracts.

Each case below was checked by hand against Mapping.xlsx and the extracts.
Set CORROBORAI_DATA to the folder holding the extracts, or place them in
../corroborai-participants (the default).
"""

import os
from pathlib import Path

import pytest

from corroborai.engine import run_engine
from corroborai.loader import fix_mojibake, load_inputs
from corroborai.rules import normalize

DATA = Path(os.environ.get("CORROBORAI_DATA", Path(__file__).resolve().parents[2] / "corroborai-participants"))
pytestmark = pytest.mark.skipif(not (DATA / "Employe_Source_Anonymise_VF.xlsx").exists(), reason="extracts not available")


@pytest.fixture(scope="module")
def results():
    inputs = load_inputs(DATA)
    res, meta = run_engine(inputs)
    return res, meta


def _row(results, matricule, type_aff):
    res, _ = results
    hits = [r for r in res if str(r.matricule) == str(matricule) and r.type_affectation == type_aff]
    assert len(hits) == 1, f"{matricule}/{type_aff}"
    return hits[0]


def test_matching_counts(results):
    res, meta = results
    assert len(res) == 23  # 23 source rows
    assert meta["unmatched_targets"] == []
    assert sum(1 for r in res if r.target_index is None) == 1  # the temporary assignment


def test_conforming_record(results):
    assert _row(results, 1545850, "P").verdict == "CONFORME"


def test_justified_deviation_encoding_and_status_conversion(results):
    row = _row(results, 7603160, "P")
    assert row.verdict == "ÉCART JUSTIFIÉ"
    statuses = {f.rule_id: f.status for f in row.findings}
    assert statuses["R22"] == "ECART_JUSTIFIE"  # mojibake
    assert statuses["R24"] == "ECART_JUSTIFIE"  # 807 -> 170 via the motif table


def test_real_anomaly_swap_is_explained(results):
    row = _row(results, 2762457, "P")
    assert row.verdict == "ANOMALIE"
    finding = next(f for f in row.findings if f.rule_id == "R15")
    assert finding.status == "ECART"
    assert "4625374" in finding.explanation  # the swapped record


def test_missing_temporary_assignment_is_anomaly(results):
    row = _row(results, 1545850, "A")
    assert row.verdict == "ANOMALIE"
    assert row.target_index is None


def test_start_date_is_intended_transformation(results):
    # Organisers confirmed (Discord): the target date is the transformed rule value, not an error.
    row = _row(results, 9989151, "P")
    finding = next(f for f in row.findings if f.rule_id == "R18")
    assert finding.status == "ECART_JUSTIFIE"
    assert "dernière date d'effet" in finding.explanation
    assert row.verdict == "ÉCART JUSTIFIÉ"


def test_hours_default_is_probable_anomaly(results):
    row = _row(results, 2911996, "P")
    assert row.verdict == "ANOMALIE PROBABLE (à valider)"
    finding = next(f for f in row.findings if f.rule_id == "R20")
    assert finding.confidence == pytest.approx(0.7)


def test_missing_source_hours_goes_to_arbitration(results):
    row = _row(results, 3712987, "P")
    finding = next(f for f in row.findings if f.rule_id == "R20")
    assert finding.verdict == "À ARBITRER"


def test_systematic_rules_detected(results):
    _, meta = results
    assert "R13" in meta["systematic"]  # position label prefix


def test_email_anonymisation_is_documented_not_anomaly(results):
    row = _row(results, 1545850, "P")
    finding = next(f for f in row.findings if f.rule_id == "R03")
    assert finding.status == "ECART_SYSTEMATIQUE"
    assert "anonymisation" in finding.explanation
    assert row.verdict == "CONFORME"


def test_optional_prefix_is_accepted():
    from corroborai.engine import _evaluate_email

    f = _evaluate_email("PNom1545850850@loto-quebec.com", "dev-08-v2_PNom1545850850@loto-quebec.com", {
        "rule_id": "R03", "target": "contactEmail", "description": "", "mapping_ref": "",
        "source_value": None, "expected": None, "actual": None})
    assert f.status == "OK"


def test_mojibake_repair():
    assert fix_mojibake("Absence complÃ¨te") == "Absence complète"
    assert normalize("text", "Actif") == "Actif"


def test_inputs_not_modified(tmp_path):
    from corroborai.report import input_hashes

    before = input_hashes(DATA)
    inputs = load_inputs(DATA)
    run_engine(inputs)
    assert input_hashes(DATA) == before
