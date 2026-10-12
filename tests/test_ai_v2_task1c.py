"""Contract tests for the preregistered DEV-only Task 1C runner inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drosophila_pd.ai_v2.access import AccessClass, DataAccessDenied, DevelopmentDataAccess
from drosophila_pd.ai_v2.task1c import (
    decide_task1c,
    load_task1c_cv,
    load_task1c_development_labels,
    sha256_bytes,
)


def _source(tmp_path: Path, *, evaluated_ids: list[str] | None = None):
    ids = [f"shiu_table3_row_{index:03d}" for index in range(2, 76)]
    rows_ids = evaluated_ids or ids
    source = tmp_path / "development_ablation.json"
    payload = {
        "evaluation_split": "development",
        "comparison": {
            "systems": {
                "rewire_effect_only": {
                    "evaluated_cases": [
                        {"case_id": case_id, "reference_label": "positive" if index < 10 else "negative"}
                        for index, case_id in enumerate(rows_ids)
                    ]
                }
            }
        },
        "score_table": [{"case_id": "NON_DEV_SENTINEL", "score": 999}],
    }
    source.write_text(json.dumps(payload), encoding="utf-8")
    access = DevelopmentDataAccess(
        {AccessClass.DEVELOPMENT_LABEL: tmp_path},
        {AccessClass.DEVELOPMENT_LABEL: frozenset({source})},
        tmp_path / "audit.jsonl",
    )
    return tuple(ids), source, access


def test_task1c_cv_is_exact_registered_development_split() -> None:
    root = Path(__file__).resolve().parents[1]
    approved = frozenset(json.loads((root / "configs/ai_v2/approved_development_ids_v1.json").read_text())["case_ids"])
    cv = load_task1c_cv(root / "configs/ai_v2/development_cv_stratified_5fold_v2.json", approved_ids=approved)
    assert len(cv.case_ids) == 74
    assert len(cv.folds) == 5
    assert cv.membership_sha256 == "bddbe5a7a51a0610c4d6b82aaf27ac7e6fd10cf892eb0c824ec2dcd3f95fccfd"


def test_development_label_projection_returns_only_approved_dev_labels(tmp_path: Path) -> None:
    ids, source, access = _source(tmp_path)
    labels = load_task1c_development_labels(
        access,
        path=source,
        expected_sha256=sha256_bytes(source.read_bytes()),
        approved_ids=frozenset(ids),
    )
    assert set(labels.values) == set(ids)
    assert len(labels.values) == 74
    assert sum(labels.values.values()) == 10
    assert "NON_DEV_SENTINEL" not in labels.values


def test_task1c_rejects_non_dev_case_and_duplicate_id(tmp_path: Path) -> None:
    ids, source, access = _source(tmp_path, evaluated_ids=[*([f"shiu_table3_row_{index:03d}" for index in range(2, 75)]), "NON_DEV_SENTINEL"])
    with pytest.raises(DataAccessDenied, match="approved 74-case partition"):
        load_task1c_development_labels(
            access,
            path=source,
            expected_sha256=sha256_bytes(source.read_bytes()),
            approved_ids=frozenset(ids),
        )


def _rows(*, b4_ap: list[float], b4_p5: list[float], b3_ap: list[float] | None = None, b3_p5: list[float] | None = None):
    rows = []
    for fold in range(5):
        values = {
            "B0_effect": (0.50, 0.20),
            "B1_structural": (0.48, 0.20),
            "B2_effect_structural": (0.55, 0.20),
            "B3_graphsage": ((b3_ap or [0.50] * 5)[fold], (b3_p5 or [0.20] * 5)[fold]),
            "B4_effect_graphsage": (b4_ap[fold], b4_p5[fold]),
        }
        for system, (ap, p5) in values.items():
            rows.append({"fold": fold, "system": system, "average_precision": ap, "precision_at_5": p5})
    return rows


def test_task1c_preregistered_robust_decision_requires_every_gate() -> None:
    robust = decide_task1c(_rows(b4_ap=[0.65, 0.65, 0.65, 0.65, 0.50], b4_p5=[0.40, 0.20, 0.20, 0.20, 0.20]))
    assert robust["decision"] == "GRAPH_SIGNAL_ROBUST"
    assert robust["delta_p_at_5_b4_vs_b0"] == pytest.approx(0.04)
    weak = decide_task1c(_rows(b4_ap=[0.50] * 5, b4_p5=[0.20] * 5, b3_ap=[0.50] * 5, b3_p5=[0.40, 0.20, 0.20, 0.20, 0.20]))
    assert weak["decision"] == "GRAPH_SIGNAL_STILL_WEAK"
    unsupported = decide_task1c(_rows(b4_ap=[0.50] * 5, b4_p5=[0.20] * 5))
    assert unsupported["decision"] == "GRAPH_SIGNAL_UNSUPPORTED"


def test_task1c_decision_rejects_incomplete_fold_table() -> None:
    with pytest.raises(ValueError, match="exactly five fold rows"):
        decide_task1c(_rows(b4_ap=[0.50] * 5, b4_p5=[0.20] * 5)[:-1])
