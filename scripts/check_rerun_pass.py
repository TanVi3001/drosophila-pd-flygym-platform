import json
from pathlib import Path

for f in sorted(Path("results/brain_driven/rerun_20260825").glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    py = d["baseline"].get("python_version", "?")
    mj = d["baseline"].get("mujoco_version", "?")
    print(f"{f.stem:42} overall_pass={d['overall_pass']} python={py} mujoco={mj}")
