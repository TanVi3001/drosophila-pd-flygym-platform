"""Read-only analysis utilities for imported rollout and frozen reports."""

from .rollout_analysis import AnalysisResult, LoadedRollout, analyze_rollout, compute_metrics, load_rollout
from .memory_safe import analyze_memory_safe_rollout

from .evidence_synthesis import (
    EvidenceSynthesisConfig,
    EvidenceValidationError,
    build_synthesis,
    generate_figures,
    generate_tables,
    load_evidence_reports,
    load_synthesis_config,
    run_evidence_synthesis,
    validate_frozen_evidence,
)

__all__ = [
    "AnalysisResult",
    "LoadedRollout",
    "analyze_rollout",
    "analyze_memory_safe_rollout",
    "compute_metrics",
    "load_rollout",
    "EvidenceSynthesisConfig",
    "EvidenceValidationError",
    "build_synthesis",
    "generate_figures",
    "generate_tables",
    "load_evidence_reports",
    "load_synthesis_config",
    "run_evidence_synthesis",
    "validate_frozen_evidence",
]
