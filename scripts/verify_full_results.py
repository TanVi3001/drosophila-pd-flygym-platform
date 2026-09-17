"""Full pipeline results verification script."""
import json
import pathlib
import sys

ROOT = pathlib.Path("drosophila_pd_full_results")
BD   = ROOT / "brain_driven" / "colab_run_final"
VAL  = ROOT / "validation"

MODELS = ["pink1", "parkin", "lrrk2", "dj1", "complexI", "pink1_age25", "pink1_parkin_OE_age25"]

print("=" * 72)
print("  KIEM TRA FULL PIPELINE RESULTS")
print("=" * 72)

all_pass = True

# --- CHECK 1: 7 file JSON ---
print("\n[CHECK 1] 7 file JSON mo phong brain_driven (colab_run_final):")
for m in MODELS:
    f = BD / f"{m}_locomotion.json"
    if not f.is_file():
        print(f"  FAIL  {m}: KHONG TIM THAY FILE")
        all_pass = False
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    op      = data.get("overall_pass", False)
    scalars = data.get("comparison", {}).get("scalars", {})
    speed   = scalars.get("mean_planar_speed_mm_s", {})
    yaw     = scalars.get("heading_yaw_change_rad", {})
    duty    = scalars.get("walking_duty_cycle", {})

    gap3_ok = all(k in scalars for k in ["walking_duty_cycle", "pause_bout_count", "cumulative_turning_rad"])
    pert    = data.get("perturbation", {})
    bio_ok  = pert.get("biological_mechanism") is not None

    status   = "OK  " if op else "WARN"
    g3_tag   = "GAP3:OK" if gap3_ok else "GAP3:MISSING"
    bio_tag  = "GAP1:OK" if bio_ok else "GAP1:MISSING"
    sp_pct   = f"{speed.get('relative_delta', 0)*100:+.1f}%" if speed else "N/A"
    yaw_pct  = f"{yaw.get('relative_delta', 0)*100:+.1f}%"   if yaw   else "N/A"
    duty_val = f"{duty.get('perturbed', 0):.3f}"              if duty   else "N/A"

    print(f"  {status} {m:25}  speed{sp_pct:>7}  yaw{yaw_pct:>7}  duty={duty_val}  [{g3_tag}] [{bio_tag}]")
    if not op:
        all_pass = False

# --- CHECK 2: Validation report (GAP 4) ---
print()
print("[CHECK 2] Literature Quantitative Validation (GAP 4):")
jf  = VAL / "literature_quantitative_validation.json"
mdf = VAL / "literature_quantitative_matrix.md"
if not jf.is_file():
    print("  FAIL  literature_quantitative_validation.json: KHONG TON TAI")
    all_pass = False
else:
    evals = json.loads(jf.read_text(encoding="utf-8"))
    concordant = sum(1 for e in evals if "CONCORDANCE" in e.get("concordance", ""))
    print(f"  OK    literature_quantitative_validation.json: {len(evals)} entries, {concordant}/{len(evals)} concordant")
    for e in evals:
        c   = e.get("concordance", "?")
        tag = "OK  " if "CONCORDANCE" in c else "WARN"
        lit = e["empirical"]["relative_delta_pct"]
        sim = e["simulation"]["relative_delta_pct"]
        print(f"    {tag} {e['model']:25}  lit={lit:>8}  sim={sim:>8}  {c}")

if not mdf.is_file():
    print("  FAIL  literature_quantitative_matrix.md: KHONG TON TAI")
    all_pass = False
else:
    print(f"  OK    literature_quantitative_matrix.md: {mdf.stat().st_size:,} bytes")

# --- CHECK 3: pink1_age25 vs pink1_parkin_OE_age25 (Rescue distinct) ---
print()
print("[CHECK 3] Phan biet pink1_age25 (benh) vs pink1_parkin_OE_age25 (rescue) [GAP 1]:")
f25 = BD / "pink1_age25_locomotion.json"
fOE = BD / "pink1_parkin_OE_age25_locomotion.json"
d25 = json.loads(f25.read_text(encoding="utf-8"))
dOE = json.loads(fOE.read_text(encoding="utf-8"))
sp25    = d25["comparison"]["scalars"]["mean_planar_speed_mm_s"]["perturbed"]
spOE    = dOE["comparison"]["scalars"]["mean_planar_speed_mm_s"]["perturbed"]
motor25 = d25.get("perturbation", {}).get("parameters", {}).get("motor_scale", "?")
motorOE = dOE.get("perturbation", {}).get("parameters", {}).get("motor_scale", "?")
print(f"  pink1_age25          : speed={sp25:.4f} mm/s  motor_scale={motor25}")
print(f"  pink1_parkin_OE_age25: speed={spOE:.4f} mm/s  motor_scale={motorOE}")
if abs(sp25 - spOE) < 0.001:
    print("  WARN  Hai model GIONG NHAU => Rescue chua duoc phan biet (can chay lai tren Colab)")
    all_pass = False
else:
    diff_pct = (spOE - sp25) / max(abs(sp25), 1e-9) * 100
    print(f"  OK    Rescue (OE) khac benh (age25): {diff_pct:+.1f}%")

# --- CHECK 4: GAP 3 metrics sample values ---
print()
print("[CHECK 4] Kiem tra chi tiet GAP 3 metrics (Bouts, Pauses, Asymmetry):")
for m in ["pink1", "pink1_age25", "pink1_parkin_OE_age25"]:
    f = BD / f"{m}_locomotion.json"
    data    = json.loads(f.read_text(encoding="utf-8"))
    scalars = data.get("comparison", {}).get("scalars", {})
    duty  = scalars.get("walking_duty_cycle", {})
    pause = scalars.get("pause_bout_count", {})
    asym  = scalars.get("left_right_asymmetry", {})
    cum_t = scalars.get("cumulative_turning_rad", {})
    print(f"  {m:25}  duty_delta={duty.get('relative_delta', 0)*100:+.1f}%  "
          f"pause_count_perturbed={pause.get('perturbed', 'N/A')}  "
          f"asymmetry_perturbed={asym.get('perturbed', 0):.4f}  "
          f"cumturn_delta={cum_t.get('relative_delta', 0)*100:+.1f}%")

# --- FINAL SUMMARY ---
print()
print("=" * 72)
n_ok = sum(1 for m in MODELS if (BD / f"{m}_locomotion.json").is_file() and
           json.loads((BD / f"{m}_locomotion.json").read_text(encoding="utf-8")).get("overall_pass", False))
print(f"  Models OK         : {n_ok}/{len(MODELS)}")
if jf.is_file():
    evals = json.loads(jf.read_text(encoding="utf-8"))
    c_ok  = sum(1 for e in evals if "CONCORDANCE" in e.get("concordance",""))
    print(f"  Literature Match  : {c_ok}/{len(evals)} HIGH/MODERATE CONCORDANCE")
print()
if all_pass:
    print("  >>> TONG KET: PASS - Du dieu kien bao cao khoa hoc")
else:
    print("  >>> TONG KET: CO VAN DE - Xem chi tiet tung CHECK o tren")
print("=" * 72)
sys.exit(0 if all_pass else 1)
