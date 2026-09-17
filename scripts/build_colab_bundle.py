"""Build a Linux-safe lean Colab bundle zip for the body-side pipeline."""

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "_colab_bundle" / "drosophila-pd-flygym"
OUT = ROOT / f"drosophila_pd_colab_bundle.zip"

COPY_DIRS = ["src", "scripts", "configs", "tests", "notebooks"]
COPY_FILES = ["pyproject.toml", "README.md"]
COPY_MAP = {
    "data/bridge_scales": "data/bridge_scales",
    "datasets/experimental_locomotion_db.json": "datasets/experimental_locomotion_db.json",
}
EXCLUDE_PARTS = {"__pycache__", ".egg-info", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

if STAGING.exists():
    shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)

for name in COPY_DIRS:
    shutil.copytree(ROOT / name, STAGING / name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
for name in COPY_FILES:
    shutil.copy2(ROOT / name, STAGING / name)
for src_rel, dst_rel in COPY_MAP.items():
    src = ROOT / src_rel
    dst = STAGING / dst_rel
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

if OUT.exists():
    OUT.unlink()

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(STAGING.rglob("*")):
        if any(part in EXCLUDE_PARTS for part in path.parts):
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        if path.is_file():
            arcname = path.relative_to(STAGING.parent).as_posix()
            zf.write(path, arcname)
            count += 1

shutil.rmtree(STAGING.parent)
print(f"wrote {OUT.name}: {count} files, "
      f"{OUT.stat().st_size / 1024 / 1024:.2f} MB")
