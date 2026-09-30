"""Create sanitized DEV-only artifacts and a post-Task-1 stratified CV manifest."""

from __future__ import annotations

import json
import argparse
from pathlib import Path

from drosophila_pd.ai_v2.access import AccessClass, DevelopmentDataAccess
from drosophila_pd.ai_v2.task1b_audit import (
    DEV_ABLATION_SHA256,
    GRAPH_SHA256,
    MAPPING_SHA256,
    TASK1_CONFIG_SHA256,
    TASK1_FOLD_SHA256,
    compact_json,
    hash_bytes,
    sanitize_development_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/ai_v2_dev"
CV_OUT = ROOT / "configs/ai_v2/development_cv_stratified_5fold_v2.json"
TASK1_CONFIG = ROOT / "configs/ai_v2/graphsage_dev_search_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace-generated-artifacts", action="store_true", help="refresh only the three explicit Task 1B generated outputs")
    args = parser.parse_args()
    if hash_bytes(TASK1_CONFIG.read_bytes()) != TASK1_CONFIG_SHA256:
        raise ValueError("Task 1 config hash mismatch")
    config = json.loads(TASK1_CONFIG.read_text(encoding="utf-8"))
    if config["graph_source_sha256"] != GRAPH_SHA256 or config["mapping_source_sha256"] != MAPPING_SHA256:
        raise ValueError("Task 1 input identity mismatch")
    ids = tuple(json.loads((ROOT / "configs/ai_v2/approved_development_ids_v1.json").read_text(encoding="utf-8"))["case_ids"])
    dev_path = Path(config["development_artifact"])
    mapping_path = ROOT / config["mapping_source"]
    audit_path = ROOT / "results/ai_v2_dev/task1b_audit/access_audit.jsonl"
    access = DevelopmentDataAccess(
        {AccessClass.DEVELOPMENT_LABEL: dev_path.parent, AccessClass.DEVELOPMENT_INPUT: mapping_path.parent},
        {AccessClass.DEVELOPMENT_LABEL: frozenset({dev_path}), AccessClass.DEVELOPMENT_INPUT: frozenset({mapping_path})},
        audit_path,
    )
    effects, mapping, cv, original_folds = sanitize_development_inputs(access, approved_ids=ids, dev_ablation_path=dev_path, mapping_path=mapping_path, original_cv_path=ROOT / "configs/ai_v2/development_cv_5fold_v1.json")
    targets = {
        OUT / "development_effect_features_v1.json": compact_json(effects),
        OUT / "development_mapping_v1.json": compact_json(mapping),
        CV_OUT: compact_json(cv),
    }
    if any(path.exists() for path in targets) and not args.replace_generated_artifacts:
        raise FileExistsError("sanitized or CV artifact already exists; refusing to overwrite")
    for path in targets:
        if path.exists() and (not path.is_file() or path.parent.resolve() not in {OUT.resolve(), CV_OUT.parent.resolve()}):
            raise ValueError("refusing to replace unexpected output target")
    OUT.mkdir(parents=True, exist_ok=True)
    CV_OUT.parent.mkdir(parents=True, exist_ok=True)
    for path, payload in targets.items():
        path.write_bytes(payload)
    manifest = {"schema_version": "ai-v2-task1b-sanitized-input-manifest-v1", "partition": "DEVELOPMENT", "case_count": 74, "created_after_task1_results": True, "task1_config_sha256": TASK1_CONFIG_SHA256, "task1_fold_membership_sha256": TASK1_FOLD_SHA256, "graph_source_sha256": GRAPH_SHA256, "development_source_sha256": DEV_ABLATION_SHA256, "mapping_source_sha256": MAPPING_SHA256, "artifacts": {path.relative_to(ROOT).as_posix(): hash_bytes(payload) for path, payload in targets.items()}, "original_fold_class_counts": original_folds, "task1c_executed": False}
    (OUT / "sanitized_manifest_v1.json").write_bytes(compact_json(manifest))
    print(json.dumps({"status": "TASK1B_INPUTS_CREATED", "case_count": 74, "new_cv_membership_sha256": cv["fold_membership_sha256"], "files": manifest["artifacts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
