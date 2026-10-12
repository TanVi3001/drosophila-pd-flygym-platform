"""
Write reviewed records for PLOS004:CCR and PLOS004:G into chunk_review.jsonl.
All sentences pre-verified EXACT against snapshot
sha256 E609315FD3D15DE93E8C936BB5FD3C749C9B98B23E555C0C1AFF4BA0E7A0D200
by scripts/_verify_plos004_ccr_g.py.
Locators confirmed:
  CCR: heading 'Chill Coma Recovery' present; para begins 'Each day a new group...'
  G  : heading 'Negative Geotaxis' present; para begins 'After a ten-minute acclimation period...'
"""
import json
from pathlib import Path

p = Path(".workbench/evidence/protocol_evidence_eval_review_20261011_v2/chunk_review.jsonl")
rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
assert len(rows) == 20

SHA = "E609315FD3D15DE93E8C936BB5FD3C749C9B98B23E555C0C1AFF4BA0E7A0D200"
NOTE = f"All sentences verified EXACT against snapshot sha256 {SHA} by scripts/_verify_plos004_ccr_g.py."
URL = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0041907"
SNAP = "source_snapshots/PLOS004.html"

def make_sentence(sid, text, classification, provenance="PUBLISHED_PAPER"):
    return {
        "sentence_id": sid,
        "draft_text": text,
        "publisher_text": text,
        "classification": classification,
        "contains_result": "NO",
        "contains_outcome": "NO",
        "contains_efficacy_conclusion": "NO",
        "provenance": provenance,
    }

def make_record(chunk_id, v1_loc, pub_loc, draft, sentences, ts):
    return {
        "chunk_id": chunk_id,
        "source_id": "PLOS004",
        "source_url": URL,
        "snapshot_file": SNAP,
        "snapshot_sha256": SHA,
        "v1_locator": v1_loc,
        "publisher_locator": pub_loc,
        "draft_text": draft,
        "text_status": "VERBATIM_EXACT",
        "representation": "VERBATIM",
        "sentence_reviews": sentences,
        "outcome_status": "VERIFIED_NO_OUTCOME",
        "efficacy_conclusion_status": "VERIFIED_NO_EFFICACY_CONCLUSION",
        "review_status": "REVIEWED",
        "reviewer_id": "reviewer_01",
        "reviewed_at": ts,
        "notes": NOTE,
    }

# ── PLOS004:CCR ──────────────────────────────────────────────────────────────
ccr_draft = (
    "Each day a new group of infected and control flies were transferred to clean glass vials "
    "(20 flies per vial) without anesthesia around noon and placed in melting ice in a bucket "
    "for three hours to induce chill coma. "
    "Prior to beginning the assay, flies were moved from the vials to individual wells of a "
    "48 well plate while being kept on ice. "
    "A timer was started once the plates were moved from the ice to a bench at room temperature "
    "and flies were considered recovered when they were able to stand. "
    "Each fly was checked by eye for recovery once a minute for the first 60 minutes, and every "
    "five minutes for the remaining 90-minute period. "
    "Data is expressed as the percentage of flies that have stood by each time point."
)
ccr_sentences = [
    make_sentence("PLOS004:CCR-s1",
        "Each day a new group of infected and control flies were transferred to clean glass vials "
        "(20 flies per vial) without anesthesia around noon and placed in melting ice in a bucket "
        "for three hours to induce chill coma.", ["METHOD"]),
    make_sentence("PLOS004:CCR-s2",
        "Prior to beginning the assay, flies were moved from the vials to individual wells of a "
        "48 well plate while being kept on ice.", ["METHOD"]),
    make_sentence("PLOS004:CCR-s3",
        "A timer was started once the plates were moved from the ice to a bench at room temperature "
        "and flies were considered recovered when they were able to stand.", ["METHOD", "REPORTED_READOUT"]),
    make_sentence("PLOS004:CCR-s4",
        "Each fly was checked by eye for recovery once a minute for the first 60 minutes, "
        "and every five minutes for the remaining 90-minute period.", ["METHOD"]),
    make_sentence("PLOS004:CCR-s5",
        "Data is expressed as the percentage of flies that have stood by each time point.", ["REPORTED_READOUT"]),
]
idx_ccr = next(i for i, r in enumerate(rows) if r["chunk_id"] == "PLOS004:CCR")
rows[idx_ccr] = make_record(
    "PLOS004:CCR",
    "Materials and Methods, Chill Coma Recovery, lines 204-205",
    'Materials and Methods > Chill Coma Recovery; paragraph beginning "Each day a new group of infected..."',
    ccr_draft, ccr_sentences, "2026-10-12T11:58:00+07:00",
)

# ── PLOS004:G ────────────────────────────────────────────────────────────────
g_draft = (
    "After a ten-minute acclimation period, the frame was tapped three times and climbing was "
    "captured with time-lapse photographs taken once per second post startle. "
    "Flies were then transferred without anesthesia back into their rearing vial."
)
g_sentences = [
    make_sentence("PLOS004:G-s1",
        "After a ten-minute acclimation period, the frame was tapped three times and climbing was "
        "captured with time-lapse photographs taken once per second post startle.", ["METHOD"]),
    make_sentence("PLOS004:G-s2",
        "Flies were then transferred without anesthesia back into their rearing vial.", ["METHOD"]),
]
idx_g = next(i for i, r in enumerate(rows) if r["chunk_id"] == "PLOS004:G")
rows[idx_g] = make_record(
    "PLOS004:G",
    "Materials and Methods, Negative Geotaxis, lines 209-210",
    'Materials and Methods > Negative Geotaxis; paragraph beginning "After a ten-minute acclimation period..."',
    g_draft, g_sentences, "2026-10-12T11:58:00+07:00",
)

# ── Write & verify ────────────────────────────────────────────────────────────
out = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
p.write_text(out, encoding="utf-8")

back = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
assert len(back) == 20

for cid, n_sent in [("PLOS004:CCR", 5), ("PLOS004:G", 2)]:
    r = next(x for x in back if x["chunk_id"] == cid)
    assert r["review_status"] == "REVIEWED"
    assert r["text_status"] == "VERBATIM_EXACT"
    assert r["outcome_status"] == "VERIFIED_NO_OUTCOME"
    assert len(r["sentence_reviews"]) == n_sent
    print(f"OK  {cid}  sentences={len(r['sentence_reviews'])}  status={r['review_status']}")

pending  = sum(1 for x in back if x["review_status"] == "PENDING")
reviewed = sum(1 for x in back if x["review_status"] == "REVIEWED")
print(f"\ntotal={len(back)}  REVIEWED={reviewed}  PENDING={pending}")
