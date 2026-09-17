"""Verify the Colab bundle zip structure and key files."""

import zipfile
from pathlib import Path

zf = zipfile.ZipFile("drosophila_pd_colab_bundle.zip")
names = zf.namelist()
print("entries:", len(names))

required = [
    "drosophila-pd-flygym/pyproject.toml",
    "drosophila-pd-flygym/scripts/run_brain_driven_experiment.py",
    "drosophila-pd-flygym/scripts/compare_brain_driven_rerun.py",
    "drosophila-pd-flygym/data/bridge_scales/pink1_bridge_scales.json",
    "drosophila-pd-flygym/configs/experiments/healthy_baseline.yaml",
    "drosophila-pd-flygym/src/drosophila_pd/perturbations/brain_driven.py",
    "drosophila-pd-flygym/notebooks/colab/11_Bridge_Scales_Generation.ipynb",
    "drosophila-pd-flygym/datasets/experimental_locomotion_db.json",
]
ok = True
for r in required:
    hit = r in names
    ok &= hit
    print(("OK  " if hit else "MISS"), r)

bad_sep = [n for n in names if "\\" in n]
print("backslash entries:", len(bad_sep))
junk = [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".pyo"))]
print("junk entries:", len(junk))
scales = sorted(n for n in names if "/bridge_scales/" in n and n.endswith(".json"))
print("bridge_scales files:", len(scales))
sys_ok = ok and not bad_sep and not junk and len(scales) == 7
print("RESULT:", "PASS" if sys_ok else "FAIL")
