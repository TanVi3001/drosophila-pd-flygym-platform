# Paper figure plan and held-out template

1. **Figure 1 — Workbench architecture.** Research question → Evidence gate → Capability gate → StudySpec → Approval → Simulation → RunManifest/provenance → QC → multi-metric analysis → prioritization → human decision. Mark unsupported/requires-review and failure branches explicitly; AI does not approve biological mappings.
2. **Figure 2 — Benchmark design.** 106 source rows split into 74 development and 32 held-out. Show development ablation and calibration on the left; a visible freeze boundary; held-out locked/not run on the right. Do not print held-out case IDs or labels.
3. **Figure 3 — Development ablation.** Plot AP and P@5 in separate panels with the actual four development systems. Values: effect-only 0.659/0.80; rewire+uncertainty 0.626/0.80; full Workbench 0.626/0.80; random 0.248/0.40. Use zero-based axes and visibly label `DEVELOPMENT`; avoid suggesting tiny differences are robust.
4. **Figure 4 — Reproducibility/provenance.** Frozen public inputs/checksums + source revisions → run manifest → completed reference/replica → controlled failed/QC reference/replica → verifier. Label owner reproduction as same-operator; second-operator remains pending until evidence exists.
5. **Figure 5 — Held-out result template.** The template code is `scripts/render_heldout_figure_template.py`; it only renders placeholders and accepts no outcome input. Required visible label: `PENDING ONE-TIME HELD-OUT EXECUTION`. Populate only after the approved guarded execution and independently verify output hashes.

The older `docs/figure_plan.md` describes the historical locomotion/disease track and is not the figure plan for this Workbench paper.
