# Post-held-out paper survival gate

Do not choose a path until the comparator protocol is owner-approved and the one-time evaluation has completed. The held-out result is a legitimate endpoint, not a tuning set.

| Outcome | Manuscript path | Required interpretation |
|---|---|---|
| Frozen Workbench ranking shows a meaningful, stable advantage over approved comparators under predeclared metrics/denominator | `GO_SUBMISSION` candidate: framework + ranking performance + reproducibility | State exact metric, uncertainty and limitations; still no biological efficacy claim. |
| Ranking is approximately equal to effect-only | `PIVOT_MANUSCRIPT` candidate: reproducible workflow + evidence/capability constraints + auditability | No ranking-superiority claim; explain that this benchmark's gates were non-discriminative. |
| Ranking is materially weaker or unstable | Test whether the software/methods contribution remains coherent and sufficiently evidenced; otherwise `PIVOT_NEW_STUDY` | Preserve and report the negative result; never retune and relabel these same cases held-out. |

## Go / pivot / stop decision table

| Dimension | GO signal | Pivot signal | Stop/current-paper signal |
|---|---|---|---|
| Novelty | Focused related-work review identifies a clear unmet workflow need beyond existing simulators/provenance tools. | Contribution is useful integration but narrower than the initial framing. | No defensible distinction after direct comparison. |
| Method coherence | Question, StudySpec, gates, score, QC and outputs form one reproducible contract. | Some components remain software-only and are reframed as such. | Claims depend on unsupported mappings or inconsistent endpoints. |
| Development evidence | Frozen analysis is reproducible and transparently reported. | Ranking uplift is weak; methods/workflow remains central. | Development artifacts cannot be verified or conflict materially. |
| Held-out evidence | Approved comparator set, common denominator and stable predeclared endpoint support the claim. | Similar/weaker ranking, but workflow claim remains independently supported. | Evaluation invalid/leaked or result defeats the only substantive claim. |
| Reproducibility | Independent operator passes, or an explicitly limited owner-only record is accepted. | Independent run unavailable; narrow the reproducibility claim. | Provenance/artifact discrepancies remain unresolved. |
| Scientific/claim support | External case review and labels/assay scope support the stated retrospective interpretation. | Restrict to computational workflow and published-label agreement. | Biological or disease claim is essential but unsupported. |
| Completeness/release | Methods, figures, data/software availability and clean tagged release are complete. | Minor noncritical items remain and are transparently listed. | Core artifacts unavailable or irreproducible. |

Final decision vocabulary: `GO_SUBMISSION`, `PIVOT_MANUSCRIPT`, `PIVOT_NEW_STUDY`, `STOP_CURRENT_PAPER`. Current state: `POST_HELDOUT_DECISION_PENDING`.
