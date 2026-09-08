"""Bounded-memory scalar analysis for the Gate24 long-rollout profile."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .rollout_analysis import AnalysisResult


PRIMARY_METRIC = "median_planar_speed_mm_s"
SECONDARY_METRIC = "distance_traveled_mm"


def analyze_memory_safe_rollout(
    dataset: str | Path,
    output_dir: str | Path | None = None,
    *,
    chunk_size: int = 8192,
) -> AnalysisResult:
    """Derive scalar metrics directly from NPZ without parsing frame JSON.

    The locked median-speed and distance formulas are retained.  This report
    deliberately omits per-frame JSON timeseries and figures, which are
    optional post-processing for the primary Gate24 validation profile.
    """

    root = Path(dataset).expanduser().resolve()
    if root.is_file():
        root = root.parent
    npz_path = root / "rollout.npz"
    if not npz_path.is_file():
        raise FileNotFoundError(f"Memory-safe rollout.npz not found: {npz_path}")
    metadata = _read_metadata(root)
    with np.load(npz_path, allow_pickle=False) as archive:
        positions = _first_array(archive, ("thorax", "thorax_positions", "positions"))
        time_s = _first_array(archive, ("timestamp_s", "time_s", "timestamps_s"))
        if positions is None or time_s is None:
            raise ValueError("rollout.npz requires thorax and timestamp/time arrays")
        positions = np.asarray(positions, dtype=float)
        time_s = np.asarray(time_s, dtype=float).reshape(-1)
        _validate_inputs(positions, time_s)
        frame_count = int(positions.shape[0])
        speed = np.empty(frame_count - 1, dtype=float)
        distance = 0.0
        for start in range(0, frame_count - 1, max(int(chunk_size), 1)):
            stop = min(start + max(int(chunk_size), 1), frame_count - 1)
            deltas = positions[start + 1 : stop + 1, :2] - positions[start:stop, :2]
            step_distance = np.linalg.norm(deltas, axis=1)
            speed[start:stop] = step_distance / np.diff(time_s[start : stop + 1])
            distance += float(np.sum(step_distance))

    median_speed = float(np.median(speed))
    displacement = float(np.linalg.norm(positions[-1, :2] - positions[0, :2]))
    duration = float(time_s[-1] - time_s[0]) if frame_count > 1 else 0.0
    timestep = float(np.median(np.diff(time_s))) if frame_count > 1 else float(metadata.get("timestep_s", 1.0))
    metrics = {
        "analysis_version": 1,
        "analysis_mode": "MEMORY_SAFE_SCALAR_SUMMARY",
        "dataset_id": str(metadata.get("dataset_id", root.name)),
        "source_files": [npz_path.name],
        "frame_count": frame_count,
        "duration_s": duration,
        "timestep_s": timestep,
        "primary_metric": PRIMARY_METRIC,
        "secondary_metric": SECONDARY_METRIC,
        "scalar_metrics": {
            PRIMARY_METRIC: median_speed,
            SECONDARY_METRIC: distance,
            "walking_speed_mm_s": float(np.sum(speed) / frame_count),
            "walking_speed_max_mm_s": float(np.max(speed)) if speed.size else 0.0,
            "total_distance_mm": distance,
            "thorax_displacement_xy_mm": displacement,
        },
        PRIMARY_METRIC: median_speed,
        SECONDARY_METRIC: distance,
        "thorax_displacement_xy_mm": displacement,
        "timeseries_exported": False,
        "optional_postprocess": "SKIPPED_OPTIONAL_POSTPROCESS",
        "scientific_scope": (
            "Computational scalar metrics derived directly from rollout.npz; "
            "not biological validation or a clinical Parkinson's disease measure."
        ),
    }
    output = Path(output_dir or root).expanduser().resolve()
    metrics_dir = output / "metrics"
    report_dir = output / "report"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    csv_path = metrics_dir / "metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("metric", "value"))
        writer.writeheader()
        writer.writerows(
            {"metric": key, "value": value}
            for key, value in metrics["scalar_metrics"].items()
        )
    summary_path = report_dir / "summary.md"
    summary_path.write_text(
        "# Memory-safe rollout analysis\n\n"
        f"- Dataset: `{metrics['dataset_id']}`\n"
        f"- Frames: `{frame_count}`\n"
        f"- Duration (s): `{duration:.6g}`\n"
        f"- Median planar speed (mm/s): `{median_speed:.6g}`\n"
        f"- Distance traveled (mm): `{distance:.6g}`\n\n"
        "Full-frame JSON, viewer pose and optional biomarker post-processing "
        "were intentionally skipped for the Gate24 primary profile.\n",
        encoding="utf-8",
    )
    return AnalysisResult(
        metrics=metrics,
        output_dir=output,
        files={"metrics_json": metrics_path, "metrics_csv": csv_path, "summary": summary_path},
    )


def _read_metadata(root: Path) -> dict[str, Any]:
    for name in ("metadata.json", "rollout_index.json"):
        path = root / name
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                metadata = value.get("metadata")
                return dict(metadata) if isinstance(metadata, dict) else value
    return {}


def _first_array(archive: Any, names: tuple[str, ...]) -> np.ndarray | None:
    for name in names:
        if name in archive.files:
            return np.asarray(archive[name])
    return None


def _validate_inputs(positions: np.ndarray, time_s: np.ndarray) -> None:
    if positions.ndim != 2 or positions.shape[1] < 2 or positions.shape[0] < 2:
        raise ValueError("thorax positions must have shape (frame_count >= 2, >= 2)")
    if time_s.shape[0] != positions.shape[0]:
        raise ValueError("timestamps and thorax frame counts must match")
    if not np.isfinite(positions).all() or not np.isfinite(time_s).all():
        raise ValueError("thorax positions and timestamps must be finite")
    if not np.all(np.diff(time_s) > 0):
        raise ValueError("timestamps must be strictly increasing")


__all__ = ["analyze_memory_safe_rollout", "PRIMARY_METRIC", "SECONDARY_METRIC"]
