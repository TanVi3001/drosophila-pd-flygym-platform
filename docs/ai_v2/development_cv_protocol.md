# AI V2 development CV — PROPOSED / DEVELOPMENT

The source is the 74 development ID list from the frozen Shiu registry. `configs/ai_v2/approved_development_ids_v1.json` records the source registry SHA-256 and IDs without labels. `configs/ai_v2/development_cv_5fold_v1.json` records five deterministic folds, seed `20260930`, split hash and fold-membership hash. Run `python scripts/build_ai_v2_dev_cv.py` with `PYTHONPATH=src` to regenerate. `load_cv()` verifies both hashes and the complete approved ID allowlist. This is a subdivision of 74 DEV cases; the original 74/32 partition is untouched.

Each fold trains/selects settings on its training IDs and validates on its validation IDs. No preprocessing, feature selection, architecture selection or threshold selection may use the fold's validation labels before prediction. Compare candidate settings by development-fold metrics only, with a fixed selection rule documented before running models. Five folds are a framework default, not evidence that a model has been trained or validated.

The frozen 32-case set has an integrity incident and remains `LOCKED_NOT_RUN`; its pristine status is unavailable. No external outcome data may influence AI V2 selection.
