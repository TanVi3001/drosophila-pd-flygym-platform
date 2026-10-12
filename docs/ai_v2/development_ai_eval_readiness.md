# AI V2 development corpus and evaluation readiness

**Status: PREPARATION DRAFT — NOT APPROVED; no real-provider evaluation has been run.**

## What was prepared

For the current distinction between the preserved software-policy questions
and the new synthetic protocol-extraction references, see
[evaluation_task_split.md](evaluation_task_split.md). The original snapshot
hashes and readiness statements below describe the earlier preparation state;
they are not a live status report. Use the local versioned index and the runtime
readiness endpoint for exact current identities. No real-provider evaluation is
reported by the split/reference-preparation work.

The local, Git-ignored directory `.workbench/evidence/` now contains:

- `rag_development_corpus_draft.jsonl`: a small software-behavior corpus paraphrased from the AI V2 architecture, RAG contract, and staging instructions.
- `ai_v2_development_questions_rubric_draft.json`: 12 candidate development questions with reference fields and evidence-chunk IDs.

The draft corpus SHA-256 is `4ec7ad33737986f90e9db2eb22462e9eda1a774f4270a3aa0fc298d99b266bd8`. This identifies these exact bytes; it is an integrity fingerprint, not an approval.
The paired draft rubric SHA-256 is `7e5561575dcaf2a164f6fac183962631163bc009ec7fdadabbec6814bb230200`, likewise only an integrity fingerprint.

This is deliberately an **internal software-knowledge pilot**, not a scientific-literature corpus. It tests whether an assistant can accurately explain the implemented workflow, human gates, local retrieval, provider-consent gate, abstention, citation filtering, secret handling, and synthetic-demo boundary. It contains no benchmark score table, experimental label, phenotype, or held-out material. It does not test neuron biology or the validity of biological mappings.

The files are named and stored as drafts. They do not satisfy the runtime's approved-manifest contract and must not be passed off as an approved scientific corpus. The rubric also contains no model outputs; it is a proposed reference set, not evaluation results.

## Why no real-provider metric is reported

The repository has no owner-approved corpus, human-approved reference answers, completed privacy/provider decision, or configured provider credentials. The draft pack intentionally sets reviewer IDs empty and all sharing flags false. The manifest utility records human attestations; it cannot itself determine whether content is outcome-free, appropriate to share, or scientifically correct. I did not create a manifest or simulate approvals.

Metrics remain `NOT_MEASURED`: retrieval Recall@K/Precision@K, citation precision, required-field accuracy, missing-field F1, coverage, schema-valid rate, unsupported-claim rate, and provider reliability. Do not interpret this preparation audit as model-performance evaluation.

The proposed comparison systems are `manual_template`, `llm_no_retrieval`, and `llm_rag`. The proposed retrieval cutoff is `k=5`, matching the current RAG runtime default; it is distinct from the Workbench benchmark's P@5 and is not frozen by this draft. Claim support must be labeled by people, not another model.

## Human review and activation gates

There are two explicitly different review modes:

- **Owner-reviewed demo:** one named project owner reviews the corpus, answerability decisions, gold fields, citations, and claim annotations. The evaluator can calculate descriptive metrics but labels them `MEASURED_OWNER_REVIEWED_DEMO_NOT_INDEPENDENT`. This is suitable for a personal/internal demo, not independent reproduction or publication-grade validation.
- **Approved development evaluation:** at least two distinct human reviewers remain required. Owner-demo mode does not relax this rule or upgrade its claims.

Before making an owner-reviewed demo bundle:

1. The owner checks each corpus chunk against its cited source section and inspects for outcome-bearing or restricted material.
2. The owner reviews every answer, gold field, evidence citation, and unanswerable question; record the real reviewer identifier and corrections before freezing hashes.
3. Decide whether evaluation is local-only or a named external provider may receive corpus excerpts and protocol text. For external use, record exact provider/model/endpoint and review retention/training/privacy terms. Keep credentials in environment secrets; never paste them into the repository or chat.
4. Freeze the question set, rubric, retrieval `k`, prompt version, provider identity, and exact file hashes. Then create a new versioned manifest using `scripts/create_rag_manifest.py` and a correctly labeled evaluation bundle using `scripts/evaluate_ai_v2_assistant.py`.
5. Retain outputs for all three comparators and the owner's claim annotations. Report denominators and abstentions, preserving the non-independent demo label.

For the separate two-reviewer mode, both reviewers inspect independently and reconcile disagreements before freezing. Do not change the mode label to make a demo look stronger.

Until those gates are met, keep provider calls off and do not describe this draft as validated AI quality. The 32 held-out cases remain untouched and `HELDOUT_STATUS = LOCKED_NOT_RUN`.
