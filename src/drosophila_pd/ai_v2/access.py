"""Single data entry point for AI V2 development reads."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from dataclasses import dataclass
from typing import Mapping


class AccessClass(StrEnum):
    PUBLIC_UNLABELED = "PUBLIC_UNLABELED"
    DEVELOPMENT_INPUT = "DEVELOPMENT_INPUT"
    DEVELOPMENT_LABEL = "DEVELOPMENT_LABEL"
    INTERNAL_HELDOUT_INPUT = "INTERNAL_HELDOUT_INPUT"
    INTERNAL_HELDOUT_LABEL = "INTERNAL_HELDOUT_LABEL"
    EXTERNAL_VALIDATION_INPUT = "EXTERNAL_VALIDATION_INPUT"
    EXTERNAL_VALIDATION_LABEL = "EXTERNAL_VALIDATION_LABEL"


class DataAccessDenied(PermissionError):
    pass


ALLOWED_DEV = frozenset({AccessClass.PUBLIC_UNLABELED, AccessClass.DEVELOPMENT_INPUT, AccessClass.DEVELOPMENT_LABEL})
SENSITIVE_PARTS = frozenset({"heldout", "held_out", "validation_labels_sealed", "curator_vault", "external_validation_label", "internal_heldout_label"})
MIXED_BENCHMARK_FILES = frozenset({"shiu_public_benchmark_v2.json", "shiu_v2_flywire630_mapping.csv", "development_score_table.csv"})


@dataclass(frozen=True)
class DevelopmentLabels:
    values: Mapping[str, int]
    source_class: AccessClass

    def __post_init__(self) -> None:
        if self.source_class is not AccessClass.DEVELOPMENT_LABEL or not self.values or any(value not in (0, 1) for value in self.values.values()):
            raise ValueError("only binary development labels are accepted")


class DevelopmentDataAccess:
    def __init__(self, roots: dict[AccessClass, Path], approved_files: dict[AccessClass, frozenset[Path]], audit_path: Path) -> None:
        self.roots = {AccessClass(key): Path(value).resolve(strict=True) for key, value in roots.items() if AccessClass(key) in ALLOWED_DEV}
        self.approved_files = {AccessClass(key): frozenset(Path(item).resolve(strict=True) for item in values) for key, values in approved_files.items() if AccessClass(key) in ALLOWED_DEV}
        self.audit_path = Path(audit_path)

    def _event(self, access_class: str, decision: str, reason: str) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"timestamp_utc": datetime.now(UTC).isoformat(), "class": access_class, "decision": decision, "reason": reason}, sort_keys=True) + "\n")

    def read_bytes(self, access_class: AccessClass | str, path: Path) -> bytes:
        name = str(access_class)
        try:
            category = AccessClass(access_class)
        except ValueError:
            self._event(name, "DENY", "unknown_class")
            raise DataAccessDenied("unknown access class") from None
        if category not in ALLOWED_DEV or category not in self.roots:
            self._event(category.value, "DENY", "class_not_available_in_development")
            raise DataAccessDenied("data class is forbidden in development")
        candidate = Path(path)
        if any(part.casefold() in SENSITIVE_PARTS for part in candidate.parts) or candidate.name.casefold() in MIXED_BENCHMARK_FILES:
            self._event(category.value, "DENY", "sensitive_path")
            raise DataAccessDenied("sensitive path is forbidden")
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(self.roots[category])
            if not resolved.is_file():
                raise ValueError("not a file")
        except (OSError, ValueError):
            self._event(category.value, "DENY", "outside_approved_root")
            raise DataAccessDenied("path is outside the approved class root") from None
        if any(part.casefold() in SENSITIVE_PARTS for part in resolved.parts) or resolved.name.casefold() in MIXED_BENCHMARK_FILES:
            self._event(category.value, "DENY", "sensitive_resolved_path")
            raise DataAccessDenied("sensitive path is forbidden")
        if resolved not in self.approved_files.get(category, frozenset()):
            self._event(category.value, "DENY", "file_not_approved")
            raise DataAccessDenied("file is not on the development allowlist")
        data = resolved.read_bytes()
        self._event(category.value, "ALLOW", "approved_root")
        return data

    def load_development_labels(self, path: Path, *, approved_ids: frozenset[str]) -> DevelopmentLabels:
        raw = json.loads(self.read_bytes(AccessClass.DEVELOPMENT_LABEL, path))
        if not isinstance(raw, dict) or set(raw) != approved_ids:
            raise DataAccessDenied("label IDs must equal the approved development set")
        return DevelopmentLabels(raw, AccessClass.DEVELOPMENT_LABEL)
