"""Run label-blind topology/aggregation audit; never invokes a model."""

from __future__ import annotations

import json
from pathlib import Path

from drosophila_pd.ai_v2.access import AccessClass, DevelopmentDataAccess
from drosophila_pd.ai_v2.graph_data import GraphCaseInputs, build_graph_projection
from drosophila_pd.ai_v2.representation_audit import audit_representation
from drosophila_pd.ai_v2.task1b_audit import GRAPH_SHA256, hash_bytes, compact_json


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/ai_v2_dev/graph_representation_diagnostic_v1.json"


def main() -> int:
    manifest = json.loads((ROOT / "data/ai_v2_dev/sanitized_manifest_v1.json").read_text(encoding="utf-8"))
    mapping_path = ROOT / "data/ai_v2_dev/development_mapping_v1.json"
    if hash_bytes(mapping_path.read_bytes()) != manifest["artifacts"]["data/ai_v2_dev/development_mapping_v1.json"]:
        raise ValueError("sanitized mapping hash mismatch")
    config = json.loads((ROOT / "configs/ai_v2/graphsage_dev_search_v1.json").read_text(encoding="utf-8"))
    graph_path = Path(config["graph_source"])
    access = DevelopmentDataAccess(
        {AccessClass.DEVELOPMENT_INPUT: mapping_path.parent, AccessClass.PUBLIC_UNLABELED: graph_path.parent},
        {AccessClass.DEVELOPMENT_INPUT: frozenset({mapping_path}), AccessClass.PUBLIC_UNLABELED: frozenset({graph_path})},
        OUTPUT.parent / "access_audit.jsonl",
    )
    mapping = json.loads(access.read_bytes(AccessClass.DEVELOPMENT_INPUT, mapping_path))
    approved = json.loads((ROOT / "configs/ai_v2/approved_development_ids_v1.json").read_text(encoding="utf-8"))
    ids = tuple(sorted(approved["case_ids"]))
    rows = {item["case_id"]: item for item in mapping["mappings"]}
    if len(rows) != 74 or set(rows) != set(ids):
        raise ValueError("mapping is not the approved 74-case development subset")
    inputs = GraphCaseInputs(ids, tuple(tuple(int(node) for node in rows[case]["target_ids"]) for case in ids), mapping["source_sha256"])
    graph = build_graph_projection(access, connectivity_path=graph_path, expected_graph_sha256=GRAPH_SHA256, cases=inputs)
    old = json.loads((ROOT / "configs/ai_v2/development_cv_5fold_v1.json").read_text(encoding="utf-8"))
    new = json.loads((ROOT / "configs/ai_v2/development_cv_stratified_5fold_v2.json").read_text(encoding="utf-8"))
    report = audit_representation(graph, old["folds"], new["folds"], graph_path=access.authorize_path(AccessClass.PUBLIC_UNLABELED, graph_path))
    if OUTPUT.exists():
        raise FileExistsError("representation diagnostic already exists")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(compact_json(report))
    print(json.dumps({"status": "LABEL_BLIND_GRAPH_AUDIT_COMPLETE", "output": str(OUTPUT), "case_count": report["case_count"], "unique_target_count": report["unique_mapped_target_neurons"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
