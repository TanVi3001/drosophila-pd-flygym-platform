import json
import sys
from pathlib import Path


def load(model, run_dir):
    p = Path("results/brain_driven") / (run_dir / f"{model}_locomotion.json")
    return json.loads(p.read_text(encoding="utf-8"))["comparison"]["scalars"]


def main() -> int:
    models = [
        "pink1", "pink1_age25", "pink1_parkin_OE_age25",
        "parkin", "dj1", "lrrk2", "complexI",
    ]
    rerun_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("rerun_20260825")
    print(f"{'model':26} {'metric':34} {'dataset_delta':>16} {'rerun_delta':>16} {'abs_diff':>12}")
    for model in models:
        try:
            old = load(model, Path("."))
            new = load(model, rerun_dir)
        except FileNotFoundError as exc:
            print(f"{model:26} MISSING: {exc.filename}")
            continue
        for key in old:
            v = old[key]["absolute_delta"]
            n = new[key]["absolute_delta"]
            diff = abs(n - v)
            flag = "" if diff < 1e-9 else ("  ~" if diff < 1e-3 else "  DIFF")
            print(f"{model:26} {key:34} {v:>16.10g} {n:>16.10g} {diff:>12.3e}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
