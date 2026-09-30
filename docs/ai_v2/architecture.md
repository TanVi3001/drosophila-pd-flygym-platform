# AI V2 architecture — PROPOSED / DEVELOPMENT

AI V2 is an experimental software path based at source commit `b48edd0d027eb89d6351c1fc70d8b93320faa60c`. It does not modify the V1 Workbench score, comparator, split or evaluation artifacts. The seven replaceable interfaces live in `src/drosophila_pd/ai_v2/components.py`: `EvidenceRetriever`, `StudySpecGenerator`, `GraphEncoder`, `FeatureFusion`, `RankingHead`, `UncertaintyEstimator` and `AIV2ExperimentRunner`.

The development flow is: approved offline evidence → draft Workbench `StudySpec` → graph metadata and vector → four-family features (LIF effect, graph, uncertainty, QC/provenance) → ranking prediction → development-fold metrics and manifest. The AI-produced StudySpec stays `DRAFT`; human approval is a separate V1 gate. `pipeline.py` composes the interfaces for one case. No large graph model, web retrieval, training algorithm or external evaluation is implemented.

`RankingPrediction` serializes only case ID, score, uncertainty, model/config identity and optional probability. Label access occurs through `DevelopmentDataAccess`, and only development labels may enter development metrics. Synthetic fixtures exercise this path without biological claims.

Scientific state: `AI_V2_STATUS = DEVELOPMENT_ONLY`. Neither a synthetic test nor five-fold development CV establishes external predictive or biological validity.
