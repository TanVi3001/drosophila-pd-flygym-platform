#!/usr/bin/env python
"""Run reviewer-approved Shiu v2 mappings through the rewired LIF graph.

The mapping CSV is intentionally a gate.  A row is runnable only when two
reviewers have approved exact FlyWire-630 IDs, assay comparability is YES, and
the row contains both MN9 readouts plus a declared intervention input set.
Scores are the arithmetic mean of the left/right MN9 rates at the benchmark's
50 Hz stimulus. Pending, ambiguous, or unassessable rows remain visible and
never become negative scores.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/workbench/shiu_public_benchmark_v2.json"
DEFAULT_MAPPING = ROOT / "configs/workbench/shiu_v2_flywire630_mapping.csv"
DEFAULT_NEURAL_REPO = ROOT.parent / "drosophila-pd-neural-disease"
DEFAULT_NEURAL_PYTHON = ROOT.parent / ".venvs" / "baseline-2024-312" / "Scripts" / "python.exe"
DEFAULT_LIF_SCRIPT = DEFAULT_NEURAL_REPO / "scripts/run_lif_condition.py"
DEFAULT_MODEL_ROOT = ROOT.parent / "external/Drosophila_brain_model"
DEFAULT_CONNECTIVITY = DEFAULT_MODEL_ROOT / "results/workbench_graph_nulls/flywire630_v1/graph_null_630_seed20260922_r01.parquet"
DEFAULT_ANNOTATION = DEFAULT_NEURAL_REPO / "annotations/flywire630_shiu_table3_upstream.csv"
SHIU_V2_READOUT_IDS = ("720575940645521262", "720575940660219265")
SHIU_V2_SCORE_RATE_HZ = 50.0
SCHEMA_VERSION = "shiu-v2-rewired-lif-batch-v1"
REQUIRED_MAPPING_FIELDS = (
    "case_id",
    "cell_type",
    "source_section",
    "source_excel_row",
    "reference_label",
    "intervention",
    "mapping_status",
    "assay_comparable",
    "input_ids_json",
    "silence_ids_json",
    "readout_ids_json",
    "reviewer_1",
    "reviewer_2",
    "reviewer_1_decision",
    "reviewer_2_decision",
    "review_decision",
    "notes",
)
REVIEW_DECISIONS = {"PENDING", "APPROVED", "REJECTED", "NEEDS_REVISION"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip()).strip("._") or "case"


def _normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _id_list(raw: str, *, field: str, case_id: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{case_id}: {field} must be valid JSON") from exc
    if not isinstance(value, list):
        raise ValueError(f"{case_id}: {field} must be a JSON list")
    result: list[str] = []
    for item in value:
        if isinstance(item, bool):
            raise ValueError(f"{case_id}: {field} contains a boolean")
        text = str(item).strip()
        if not text.isdigit():
            raise ValueError(f"{case_id}: {field} contains a non-decimal neuron ID")
        if text not in result:
            result.append(text)
    return result


def _protocol_cases(path: Path) -> dict[str, Mapping[str, Any]]:
    protocol = _load_json(path)
    cases = protocol.get("cases")
    if not isinstance(cases, list):
        raise ValueError("protocol cases must be a list")
    result: dict[str, Mapping[str, Any]] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("protocol case must be an object")
        case_id = str(case.get("case_id", "")).strip()
        if not case_id or case_id in result:
            raise ValueError(f"invalid or duplicate protocol case ID: {case_id!r}")
        result[case_id] = case
    return result


def _read_mapping(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_MAPPING_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"mapping CSV is missing columns: {missing}")
        return [{key: str(value or "").strip() for key, value in row.items()} for row in reader]


def validate_mapping(protocol_path: Path, mapping_path: Path) -> dict[str, Any]:
    expected = _protocol_cases(protocol_path)
    rows = _read_mapping(mapping_path)
    by_id: dict[str, dict[str, str]] = {}
    duplicate_ids: list[str] = []
    invalid: list[dict[str, Any]] = []
    for row in rows:
        case_id = row.get("case_id", "")
        if case_id in by_id:
            duplicate_ids.append(case_id)
            continue
        by_id[case_id] = row
        case = expected.get(case_id)
        if case is None:
            invalid.append({"case_id": case_id, "reason": "unknown_case_id"})
            continue
        metadata = case.get("metadata", {})
        expected_type = str(metadata.get("cell_type", "")) if isinstance(metadata, Mapping) else ""
        if _normalized_label(row.get("cell_type", "")) != _normalized_label(expected_type):
            invalid.append({"case_id": case_id, "reason": "cell_type_mismatch"})
        for field in ("input_ids_json", "silence_ids_json", "readout_ids_json"):
            try:
                row[field + "_parsed"] = _id_list(row.get(field, ""), field=field, case_id=case_id)
            except ValueError as exc:
                invalid.append({"case_id": case_id, "reason": str(exc)})
        status = row.get("mapping_status", "").upper()
        comparable = row.get("assay_comparable", "").upper()
        reviewer_1_decision = row.get("reviewer_1_decision", "").upper()
        reviewer_2_decision = row.get("reviewer_2_decision", "").upper()
        decision = row.get("review_decision", "").upper()
        if status not in {"PENDING", "APPROVED", "UNASSESSABLE", "REJECTED"}:
            invalid.append({"case_id": case_id, "reason": "invalid_mapping_status"})
        if comparable not in {"PENDING", "YES", "NO"}:
            invalid.append({"case_id": case_id, "reason": "invalid_assay_comparable"})
        for field, value in (
            ("reviewer_1_decision", reviewer_1_decision),
            ("reviewer_2_decision", reviewer_2_decision),
            ("review_decision", decision),
        ):
            if value not in REVIEW_DECISIONS:
                invalid.append({"case_id": case_id, "reason": f"invalid_{field}"})
        if status == "APPROVED":
            if comparable != "YES" or decision != "APPROVED":
                invalid.append({"case_id": case_id, "reason": "approved_row_lacks_review_signoff"})
            if not row.get("reviewer_1") or not row.get("reviewer_2"):
                invalid.append({"case_id": case_id, "reason": "approved_row_requires_two_reviewers"})
            if reviewer_1_decision != "APPROVED" or reviewer_2_decision != "APPROVED":
                invalid.append({"case_id": case_id, "reason": "approved_row_requires_two_reviewer_decisions"})
            input_ids = row.get("input_ids_json_parsed", [])
            silence_ids = row.get("silence_ids_json_parsed", [])
            readout_ids = row.get("readout_ids_json_parsed", [])
            if tuple(sorted(readout_ids)) != tuple(sorted(SHIU_V2_READOUT_IDS)):
                invalid.append(
                    {
                        "case_id": case_id,
                        "reason": "shiu_v2_requires_mn9_left_and_right_readout_ids",
                    }
                )
            intervention = row.get("intervention", "").lower()
            if intervention == "activation" and (not input_ids or silence_ids):
                invalid.append({"case_id": case_id, "reason": "activation_requires_input_ids_only"})
            elif intervention == "outgoing_synapse_block" and (not silence_ids or input_ids):
                invalid.append({"case_id": case_id, "reason": "silencing_requires_silence_ids_only"})
            elif intervention not in {"activation", "outgoing_synapse_block"}:
                invalid.append({"case_id": case_id, "reason": "unsupported_intervention"})
    missing_ids = sorted(set(expected) - set(by_id))
    extra_ids = sorted(set(by_id) - set(expected))
    pending_ids = sorted(case_id for case_id, row in by_id.items() if row.get("mapping_status", "").upper() == "PENDING")
    unassessable_ids = sorted(case_id for case_id, row in by_id.items() if row.get("mapping_status", "").upper() == "UNASSESSABLE")
    approved_ids = sorted(case_id for case_id, row in by_id.items() if row.get("mapping_status", "").upper() == "APPROVED")
    complete = not (missing_ids or extra_ids or duplicate_ids or invalid or pending_ids or unassessable_ids)
    return {
        "status": "READY" if complete else "BLOCKED",
        "protocol_case_count": len(expected),
        "mapping_row_count": len(rows),
        "approved_case_ids": approved_ids,
        "pending_case_ids": pending_ids,
        "unassessable_case_ids": unassessable_ids,
        "missing_case_ids": missing_ids,
        "unknown_case_ids": extra_ids,
        "duplicate_case_ids": sorted(set(duplicate_ids)),
        "invalid_rows": invalid,
        "mapping_sha256": _sha256(mapping_path),
        "protocol_sha256": _sha256(protocol_path),
        "scientific_scope": "Mapping gate only; names are never converted to neuron IDs by inference.",
        "rows": by_id,
    }


def _metric_rate(metrics_path: Path, readout_ids: Sequence[str]) -> dict[str, Any]:
    document = _load_json(metrics_path)
    metrics = document.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError(f"metrics document has no metrics object: {metrics_path}")
    rates = metrics.get("readout_rates_hz")
    if not isinstance(rates, Mapping):
        raise ValueError(f"metrics has no readout_rates_hz object: {metrics_path}")
    values: dict[str, float] = {}
    for readout_id in readout_ids:
        if readout_id not in rates:
            raise ValueError(f"readout {readout_id} is missing from metrics: {metrics_path}")
        value = float(rates[readout_id])
        if value != value or abs(value) == float("inf"):
            raise ValueError(f"readout {readout_id} is not finite: {metrics_path}")
        values[readout_id] = value
    if not values:
        raise ValueError(f"at least one readout is required: {metrics_path}")
    return {
        "readout_rates_hz": values,
        "readout_rate_hz": sum(values.values()) / len(values),
    }


def _run_lif(
    *,
    args: argparse.Namespace,
    case_id: str,
    label: str,
    input_ids: Sequence[str],
    silence_ids: Sequence[str],
    readout_ids: Sequence[str],
    output: Path,
) -> dict[str, Any]:
    command = [
        str(args.neural_python.resolve()),
        str(args.lif_script.resolve()),
        "--model-root", str(args.model_root.resolve()),
        "--completeness", str((args.model_root / "2023_03_23_completeness_630_final.csv").resolve()),
        "--connectivity", str(args.connectivity.resolve()),
        "--condition-label", f"{case_id}_{label}",
        "--exp-name", f"{case_id}_{label}",
        "--seed", str(args.seed),
        "--trials", str(args.trials),
        "--duration-s", str(args.duration_s),
        "--stimulus-rate-hz", str(args.stimulus_rate_hz),
        "--id-namespace", "flywire_root_id",
        "--dataset-id", "flywire-630-2023-03-23",
        "--output", str(output.resolve()),
    ]
    if args.annotation_file is not None:
        command.extend(("--annotation-file", str(args.annotation_file.resolve())))
    for value in input_ids:
        command.extend(("--input-id", value))
    for value in silence_ids:
        command.extend(("--silence-id", value))
    for readout_id in readout_ids:
        command.extend(("--readout-id", readout_id))
    completed = subprocess.run(
        command,
        cwd=args.neural_repo.resolve(),
        capture_output=True,
        text=True,
        check=False,
    )
    (output / "launcher.stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    (output / "launcher.stderr.log").write_text(completed.stderr or "", encoding="utf-8")
    status_path = output / "status.json"
    status = _load_json(status_path) if status_path.is_file() else {"status": "FAILED"}
    metrics_path = output / "metrics.json"
    if completed.returncode != 0 or status.get("status") != "PASS" or not metrics_path.is_file():
        return {
            "status": "FAILED",
            "return_code": completed.returncode,
            "output": str(output),
            "status_document": status,
        }
    return {
        "status": "PASS",
        "output": str(output),
        "metrics": str(metrics_path),
        **_metric_rate(metrics_path, readout_ids),
    }


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = args.protocol.resolve()
    mapping_path = args.mapping.resolve()
    validation = validate_mapping(protocol_path, mapping_path)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "protocol": str(protocol_path),
        "mapping": str(mapping_path),
        "connectivity": str(args.connectivity.resolve()),
        "validation": {key: value for key, value in validation.items() if key != "rows"},
        "scores": {},
        "case_results": {},
        "score_contract": {
            "readout_ids": list(SHIU_V2_READOUT_IDS),
            "aggregation": "arithmetic_mean_hz",
            "stimulus_rate_hz": SHIU_V2_SCORE_RATE_HZ,
        },
        "scientific_scope": (
            "Rewired LIF score preparation only. Scores are computational readouts, "
            "not biological validation or causal evidence."
        ),
    }
    if validation["status"] != "READY" and not args.allow_partial:
        result["status"] = "BLOCKED_MAPPING_REQUIRED"
        return result
    if args.dry_run:
        result["status"] = "READY_TO_RUN" if validation["status"] == "READY" else "PARTIAL_MAPPING"
        return result

    args.output_root.mkdir(parents=True, exist_ok=True)
    for case_id in validation["approved_case_ids"]:
        row = validation["rows"][case_id]
        readout_ids = row["readout_ids_json_parsed"]
        case_root = args.output_root / _safe_component(case_id)
        control = _run_lif(
            args=args,
            case_id=case_id,
            label="control",
            input_ids=[],
            silence_ids=[],
            readout_ids=readout_ids,
            output=case_root / "control",
        )
        condition = _run_lif(
            args=args,
            case_id=case_id,
            label="condition",
            input_ids=row["input_ids_json_parsed"],
            silence_ids=row["silence_ids_json_parsed"],
            readout_ids=readout_ids,
            output=case_root / "condition",
        )
        case_result: dict[str, Any] = {
            "cell_type": row["cell_type"],
            "readout_ids": readout_ids,
            "control": control,
            "condition": condition,
        }
        if control.get("status") == "PASS" and condition.get("status") == "PASS":
            score = float(condition["readout_rate_hz"])
            case_result["score"] = score
            case_result["delta_hz"] = score - float(control["readout_rate_hz"])
            result["scores"][case_id] = score
        result["case_results"][case_id] = case_result
    all_approved_succeeded = len(result["scores"]) == len(validation["approved_case_ids"])
    result["status"] = (
        "COMPLETE"
        if validation["status"] == "READY" and all_approved_succeeded
        else "PARTIAL_RUN"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--connectivity", type=Path, default=DEFAULT_CONNECTIVITY)
    parser.add_argument("--neural-repo", type=Path, default=DEFAULT_NEURAL_REPO)
    parser.add_argument("--neural-python", type=Path, default=DEFAULT_NEURAL_PYTHON)
    parser.add_argument("--lif-script", type=Path, default=DEFAULT_LIF_SCRIPT)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--annotation-file", type=Path, default=DEFAULT_ANNOTATION)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--duration-s", type=float, default=1.0)
    parser.add_argument("--stimulus-rate-hz", type=float, default=SHIU_V2_SCORE_RATE_HZ)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.protocol.is_file() or not args.mapping.is_file():
        parser.error("protocol and mapping files must exist")
    result = run_batch(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve()), "score_count": len(result["scores"])}, indent=2))
    return 0 if result["status"] in {"COMPLETE", "READY_TO_RUN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
