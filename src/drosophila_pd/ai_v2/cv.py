"""Deterministic folds constrained by an explicit development-only allowlist."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class DevelopmentCV:
    case_ids: tuple[str, ...]
    folds: tuple[tuple[str, ...], ...]
    seed: int
    split_sha256: str
    membership_sha256: str

    def __post_init__(self) -> None:
        if len(self.case_ids) != len(set(self.case_ids)) or not self.case_ids:
            raise ValueError("development IDs must be unique and nonempty")
        if len(self.folds) < 2 or any(not fold for fold in self.folds):
            raise ValueError("at least two nonempty folds required")
        flattened = [item for fold in self.folds for item in fold]
        if len(flattened) != len(self.case_ids) or set(flattened) != set(self.case_ids):
            raise ValueError("folds must partition development IDs exactly")
        if self.split_sha256 != canonical_hash(list(sorted(self.case_ids))):
            raise ValueError("development split hash mismatch")
        if self.membership_sha256 != canonical_hash([list(fold) for fold in self.folds]):
            raise ValueError("fold membership hash mismatch")

    def train_validation(self, fold: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
        validation = self.folds[fold]
        return tuple(case for case in self.case_ids if case not in set(validation)), validation

    def as_dict(self) -> dict[str, object]:
        return {"schema_version": "ai-v2-dev-cv-v1", "partition": "DEVELOPMENT", "seed": self.seed, "case_count": len(self.case_ids), "case_ids": list(self.case_ids), "folds": [list(fold) for fold in self.folds], "development_split_sha256": self.split_sha256, "fold_membership_sha256": self.membership_sha256}


def make_development_cv(case_ids: tuple[str, ...], *, approved_ids: frozenset[str], seed: int = 20260930, n_folds: int = 5) -> DevelopmentCV:
    if not case_ids or len(case_ids) != len(set(case_ids)) or set(case_ids) != approved_ids:
        raise ValueError("CV input must equal the approved development partition")
    if n_folds < 2 or n_folds > len(case_ids):
        raise ValueError("invalid fold count")
    ordered = sorted(case_ids)
    shuffled = ordered.copy()
    random.Random(seed).shuffle(shuffled)
    folds = tuple(tuple(sorted(shuffled[index::n_folds])) for index in range(n_folds))
    return DevelopmentCV(tuple(ordered), folds, seed, canonical_hash(ordered), canonical_hash([list(fold) for fold in folds]))


def load_cv(path: Path, approved_ids: frozenset[str]) -> DevelopmentCV:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("partition") != "DEVELOPMENT" or raw.get("schema_version") != "ai-v2-dev-cv-v1":
        raise ValueError("not a development CV manifest")
    ids = tuple(raw["case_ids"])
    if set(ids) != approved_ids or len(ids) != len(approved_ids) or raw["case_count"] != len(ids):
        raise ValueError("CV manifest differs from approved development IDs")
    return DevelopmentCV(ids, tuple(tuple(fold) for fold in raw["folds"]), raw["seed"], raw["development_split_sha256"], raw["fold_membership_sha256"])
