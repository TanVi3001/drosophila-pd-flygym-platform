#!/usr/bin/env python
"""Create reproducible manuscript tables and figures from frozen artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def _load_scores(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _metric_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "rewire_effect_only": "Rewire effect only",
        "rewire_plus_uncertainty": "Rewire + uncertainty",
        "full_workbench_locked": "Full Workbench",
        "random_reference": "Random reference",
    }
    rows = []
    for name in labels:
        values = report["primary_metrics"][name]
        rows.append(
            {
                "system": name,
                "label": labels[name],
                "average_precision": float(values["average_precision"]),
                "precision_at_5": float(values["precision_at_k"]),
                "coverage": float(values["coverage"]),
            }
        )
    return rows


def _write_tables(out: Path, rows: list[dict[str, Any]]) -> None:
    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    fields = ["system", "label", "average_precision", "precision_at_5", "coverage"]
    with (tables / "development_ablation.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Development ablation table",
        "",
        "| System | Average precision | Precision@5 | Coverage |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {row['label']} | {row['average_precision']:.3f} | {row['precision_at_5']:.3f} | {row['coverage']:.3f} |"
        for row in rows
    )
    (tables / "development_ablation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tables / "limitations.md").write_text(
        "# Current manuscript limitations\n\n"
        "| Limitation | Meaning for the claim |\n"
        "| --- | --- |\n"
        "| Retrospective public labels | Does not establish prospective utility. |\n"
        "| Evidence/capability gates constant | Their ranking contribution is not identifiable in this registry. |\n"
        "| One computational run per case | Does not quantify biological or simulation uncertainty fully. |\n"
        "| MN9 readout only | Not a whole-animal behavior or wet-lab validation. |\n"
        "| Second operator pending | Independent reproducibility claim is not yet eligible. |\n",
        encoding="utf-8",
    )


def _make_ablation_figure(out: Path, rows: list[dict[str, Any]]) -> None:
    labels = [row["label"] for row in rows]
    x = list(range(len(rows)))
    colors = ["#2f6f8f", "#b76d3c", "#4d8b67", "#7d7d7d"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), constrained_layout=True)
    for axis, key, title in (
        (axes[0], "average_precision", "Average precision"),
        (axes[1], "precision_at_5", "Precision@5"),
    ):
        values = [row[key] for row in rows]
        bars = axis.bar(x, values, color=colors, width=0.68)
        axis.set_ylim(0, 1)
        axis.set_ylabel("Score")
        axis.set_title(title)
        axis.set_xticks(x, labels, rotation=25, ha="right")
        axis.grid(axis="y", alpha=0.25)
        for bar, value in zip(bars, values):
            axis.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    fig.suptitle("Development-only Workbench ablation (n=74)")
    fig.savefig(out / "figures" / "development_ablation.png", dpi=300)
    plt.close(fig)


def _make_distribution_figure(out: Path, score_rows: list[dict[str, Any]]) -> None:
    values = [float(row["score_hz"]) for row in score_rows]
    zero_count = sum(value == 0.0 for value in values)
    nonzero = [value for value in values if value > 0]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2), constrained_layout=True)
    axes[0].bar(["Zero score", "Non-zero score"], [zero_count, len(nonzero)], color=["#8b8b8b", "#2f6f8f"])
    axes[0].set_ylabel("Cases")
    axes[0].set_title(f"Frozen rewire scores (n={len(values)})")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].text(0, zero_count + 1, str(zero_count), ha="center")
    axes[0].text(1, len(nonzero) + 1, str(len(nonzero)), ha="center")
    if nonzero:
        bins = min(8, max(3, len(nonzero)))
        axes[1].hist(nonzero, bins=bins, color="#4d8b67", edgecolor="#234b38")
    axes[1].set_xlabel("Rewire score (Hz)")
    axes[1].set_ylabel("Non-zero cases")
    axes[1].set_title("Distribution among active scores")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Frozen degree-preserving-rewire readout")
    fig.savefig(out / "figures" / "rewire_score_distribution.png", dpi=300)
    plt.close(fig)


def _make_pipeline_figure(out: Path) -> None:
    fig, axis = plt.subplots(figsize=(13, 3.2))
    axis.set_xlim(0, 13)
    axis.set_ylim(0, 3)
    axis.axis("off")
    boxes = [
        (0.3, "Protocol +\nhypothesis", "#d8e8f0"),
        (2.9, "Evidence +\ncapability gate", "#dcebdc"),
        (5.5, "StudySpec +\nprovenance", "#eee2c6"),
        (8.1, "LIF simulation +\nQC + uncertainty", "#ead7e8"),
        (10.7, "Rank candidates\nfor wet-lab", "#f1d8ce"),
    ]
    for index, (x, label, color) in enumerate(boxes):
        patch = FancyBboxPatch((x, 1.05), 1.8, 0.9, boxstyle="round,pad=0.04,rounding_size=0.08", facecolor=color, edgecolor="#555555", linewidth=1.0)
        axis.add_patch(patch)
        axis.text(x + 0.9, 1.5, label, ha="center", va="center", fontsize=10)
        if index < len(boxes) - 1:
            axis.annotate("", xy=(boxes[index + 1][0] - 0.1, 1.5), xytext=(x + 1.9, 1.5), arrowprops={"arrowstyle": "->", "color": "#555555", "lw": 1.4})
    axis.text(6.5, 2.55, "Fly Research Workbench computational prioritization pipeline", ha="center", va="center", fontsize=13, fontweight="bold")
    axis.text(6.5, 0.35, "AI assists reading and interpretation; it does not invent biological mappings or replace wet-lab validation.", ha="center", va="center", fontsize=9, color="#555555")
    fig.savefig(out / "figures" / "workbench_pipeline.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def build(*, ablation_path: Path, freeze_scores_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "figures").mkdir(exist_ok=True)
    report = _load_json(ablation_path)
    score_rows = _load_scores(freeze_scores_path)
    rows = _metric_rows(report)
    _write_tables(output_root, rows)
    _make_ablation_figure(output_root, rows)
    _make_distribution_figure(output_root, score_rows)
    _make_pipeline_figure(output_root)
    manifest = {
        "status": "CREATED",
        "source_ablation": str(ablation_path),
        "source_frozen_scores": str(freeze_scores_path),
        "outputs": [
            "figures/workbench_pipeline.png",
            "figures/development_ablation.png",
            "figures/rewire_score_distribution.png",
            "tables/development_ablation.csv",
            "tables/development_ablation.md",
            "tables/limitations.md",
        ],
        "scientific_scope": "Manuscript support artifacts; development-only ablation and frozen computational score distribution.",
    }
    (output_root / "manuscript_figure_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ablation", type=Path, required=True)
    parser.add_argument("--freeze-scores", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        ablation_path=args.ablation.resolve(),
        freeze_scores_path=args.freeze_scores.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
