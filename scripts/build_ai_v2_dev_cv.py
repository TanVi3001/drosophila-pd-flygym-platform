"""Generate the fixed five-fold manifest from the development-only allowlist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from drosophila_pd.ai_v2.cv import make_development_cv


PINNED_REGISTRY_SHA256 = "8743feba5149f78d96238e9ee3bfacbc1d7dd8a33960b6a5eaf6bda77d8fdedb"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved", type=Path, default=Path("configs/ai_v2/approved_development_ids_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("configs/ai_v2/development_cv_5fold_v1.json"))
    args = parser.parse_args()
    approved = json.loads(args.approved.read_text(encoding="utf-8"))
    ids = tuple(approved["case_ids"])
    if approved["schema_version"] != "ai-v2-approved-development-ids-v1" or approved["case_count"] != 74 or len(ids) != 74 or approved["source_registry_sha256"] != PINNED_REGISTRY_SHA256:
        raise ValueError("approved development source must contain exactly 74 IDs")
    cv = make_development_cv(ids, approved_ids=frozenset(ids))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cv.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"DEVELOPMENT_CV_READY cases={len(ids)} folds={len(cv.folds)} membership_sha256={cv.membership_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
