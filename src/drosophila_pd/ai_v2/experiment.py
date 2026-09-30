"""Development-only fold runner and provenance manifest; no model training."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

from .contracts import RankingPrediction
from .contracts import SHA256
from .access import DevelopmentLabels
from .cv import DevelopmentCV, canonical_hash
from .metrics import METRIC_INTERPRETATION, average_precision, coverage, precision_at_k, recall_at_k


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class DevelopmentExperiment:
    cv: DevelopmentCV
    source_commit: str
    worktree_state: str
    model_id: str
    model_config: dict[str, object]
    input_artifact_hashes: dict[str, str]
    feature_set: tuple[str, ...]
    random_seed: int
    output_root: Path

    def __post_init__(self) -> None:
        if not self.source_commit or self.worktree_state not in {"clean", "dirty"} or not self.model_id:
            raise ValueError("source commit, worktree state and model identity are required")
        if not self.feature_set or not self.input_artifact_hashes or any(not SHA256.fullmatch(value) for value in self.input_artifact_hashes.values()):
            raise ValueError("feature set and input artifact SHA-256 values are required")
        if not Path(self.output_root).exists() or not Path(self.output_root).is_dir():
            raise ValueError("a dedicated existing development output root is required")

    def run_fold(self, *, fold: int, labels: DevelopmentLabels, predict: Callable[[str], RankingPrediction], output_dir: Path, k: int = 5) -> dict[str, object]:
        train_ids, validation_ids = self.cv.train_validation(fold)
        if not isinstance(labels, DevelopmentLabels) or set(labels.values) != set(self.cv.case_ids):
            raise ValueError("labels must cover exactly the approved development set")
        if k < 1 or k > len(validation_ids):
            raise ValueError("K must fit validation fold")
        predictions = [predict(case_id) for case_id in validation_ids]
        if any(not isinstance(item, RankingPrediction) or item.case_id != case_id or item.model_id != self.model_id or item.config_sha256 != canonical_hash(self.model_config) for item, case_id in zip(predictions, validation_ids)):
            raise ValueError("prediction identity or config mismatch")
        scores = {item.case_id: item.score for item in predictions}
        fold_labels = {case: labels.values[case] for case in validation_ids}
        metrics = {"average_precision": average_precision(fold_labels, scores), "precision_at_k": precision_at_k(fold_labels, scores, k), "recall_at_k": recall_at_k(fold_labels, scores, k), "coverage": coverage(set(validation_ids), set(scores))}
        output_dir = Path(output_dir)
        if output_dir.resolve().parent != Path(self.output_root).resolve():
            raise ValueError("output must be an immediate child of the development output root")
        output_dir.mkdir(parents=True, exist_ok=False)
        payload = [item.as_dict() for item in predictions]
        predictions_path = output_dir / "predictions.json"
        predictions_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        manifest = {"schema_version": "ai-v2-dev-experiment-v1", "experiment_id": f"{self.model_id}-fold-{fold}-{self.random_seed}", "timestamp_utc": datetime.now(UTC).isoformat(), "partition": "DEVELOPMENT", "source_commit": self.source_commit, "worktree_state": self.worktree_state, "development_split_sha256": self.cv.split_sha256, "fold_membership_sha256": self.cv.membership_sha256, "fold": fold, "train_case_count": len(train_ids), "validation_case_count": len(validation_ids), "model_id": self.model_id, "model_config": self.model_config, "random_seed": self.random_seed, "input_artifact_hashes": self.input_artifact_hashes, "feature_set": list(self.feature_set), "metrics_requested": list(metrics), "metric_interpretation": METRIC_INTERPRETATION, "metrics": metrics, "output_hashes": {"predictions.json": sha256_file(predictions_path)}}
        (output_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return manifest
