"""
scripts/_write_plos017_review.py

Write REVIEWED records for PLOS017:C, PLOS017:H, PLOS017:M, PLOS017:N
into chunk_review.jsonl.
All 4 outcome decisions are human-verified: VERIFIED_NO_OUTCOME.
"""

import html as html_module
import json
import re
from pathlib import Path

JSONL  = Path(".workbench/evidence/protocol_evidence_eval_review_20261011_v2/chunk_review.jsonl")
CORPUS = Path(".workbench/evidence/protocol_evidence_eval_draft_20261010_v1/corpus/corpus_draft.jsonl")
SNAP_F = Path(".workbench/evidence/protocol_evidence_eval_draft_20261011_v2/source_snapshots/PLOS017.html")

URL  = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0177710"
SHA  = "0F5706612DBC9F4D5504A330791C40662DD36CAC7C78F5208A2FB49AB03005FD"
SNAP = "../protocol_evidence_eval_draft_20261011_v2/source_snapshots/PLOS017.html"
RA   = "2026-10-12T12:55:00+07:00"
RV   = "reviewer_01"

TARGET = {"PLOS017:C", "PLOS017:H", "PLOS017:M", "PLOS017:N"}
drafts = {}
for ln in CORPUS.read_text(encoding="utf-8").splitlines():
    if not ln.strip():
        continue
    c = json.loads(ln)
    if c["chunk_id"] in TARGET:
        drafts[c["chunk_id"]] = c["text"]
assert set(drafts) == TARGET

raw  = SNAP_F.read_text(encoding="utf-8", errors="replace")
s    = re.sub(r"(?is)<script.*?</script>", " ", raw)
s    = re.sub(r"(?is)<style.*?</style>", " ", s)
s    = re.sub(r"(?s)<[^>]+>", " ", s)
text = html_module.unescape(" ".join(s.split()))

# ── publisher segment extractor ───────────────────────────────────────────────
ANCHORS = {
    "PLOS017:C": "Flies were reared in a light-dark controlled incubator on a",
    "PLOS017:H": "I hypothesized that developmental nicotine exposure would have similar effects",
    "PLOS017:M": "A negative geotaxis assay was used to determine nicotine sensitivity",
    "PLOS017:N": "The developmental drug exposure protocol was adapted from McClure et",
}
# Publisher segments: locate anchor, then extend to the natural paragraph/section end.
# Boundaries confirmed via _verify_plos017_deep.py output.
PUB_ENDS = {
    "PLOS017:C": "collection two days before the behavioral assay.",
    "PLOS017:H": "mediated by D \u03b1 7 .",
    "PLOS017:M": "Grubbs\u2019 test was used to exclude outliers.",
    "PLOS017:N": "during metamorphosis, for the Pupa stage (P).",
}

def get_pub_segment(cid: str) -> str:
    anchor = ANCHORS[cid]
    end_marker = PUB_ENDS[cid]
    idx = text.find(anchor)
    assert idx >= 0, f"Anchor not found for {cid}"
    end_idx = text.find(end_marker, idx)
    assert end_idx >= 0, f"End marker not found for {cid}"
    return text[idx: end_idx + len(end_marker)]

pub = {cid: get_pub_segment(cid) for cid in TARGET}
for cid, seg in pub.items():
    print(f"  pub_segment {cid}: {len(seg)} chars  OK")

# ── sentence splitter ────────────────────────────────────────────────────────
def split_sents(txt: str) -> list:
    return [p.strip() for p in re.split(r"(?<=\.)\s+(?=[A-Z\u201c\u2018I])", txt.strip()) if p.strip()]

def make_sr(sid, dt, cls):
    return {
        "sentence_id": sid, "draft_text": dt, "classification": cls,
        "contains_result": "NO", "contains_outcome": "NO",
        "contains_efficacy_conclusion": "NO", "provenance": "PUBLISHED_PAPER",
    }

# ── build sentence_reviews per chunk ─────────────────────────────────────────
C_sents = split_sents(drafts["PLOS017:C"])
C_sr    = [make_sr(f"PLOS017:C-s{i+1}", t, ["METHOD", "CONTEXT"]) for i, t in enumerate(C_sents)]

H_sr = [make_sr("PLOS017:H-s1", drafts["PLOS017:H"], ["HYPOTHESIS"])]

M_sents = split_sents(drafts["PLOS017:M"])
M_sr    = [make_sr(f"PLOS017:M-s{i+1}", t, ["METHOD", "REPORTED_READOUT"]) for i, t in enumerate(M_sents)]

N_sents = split_sents(drafts["PLOS017:N"])
N_sr    = [make_sr(f"PLOS017:N-s{i+1}", t, ["METHOD", "CONTEXT"]) for i, t in enumerate(N_sents)]

# ── normalization notes per chunk ────────────────────────────────────────────
NORM = {
    "PLOS017:C": [
        "w^{1118} in draft = w 1118 in snapshot (superscript HTML artifact)",
        "wB in draft = ( w B) in snapshot (superscript/italic HTML spacing)",
        "D\u03b17 in draft = D \u03b1 7 in snapshot (superscript HTML spacing)",
        "P\u0394EY6/P\u0394EY5 in draft = P \u0394 EY6/P \u0394 EY5 in snapshot (HTML spacing)",
        "CO2 in draft = CO 2 in snapshot (superscript HTML artifact)",
        "Citation [29] stripped in draft; present as [ 29 ] in snapshot",
    ],
    "PLOS017:H": [
        "D\u03b17 in draft = D \u03b1 7 in snapshot (superscript HTML spacing)",
        "Citation period spacing: 'D \u03b1 7 .' in snapshot (HTML space before period) vs 'D\u03b17.' in draft",
        "BOUNDARY: 'I found that...' begins immediately after draft segment in snapshot and is NOT in draft text",
    ],
    "PLOS017:M": [
        "Citation [ 39 ] in snapshot vs [39] in draft (HTML spacing artifact)",
        "2.5 \u03bcl — spacing/encoding normalized from HTML",
        "w B strain in snapshot vs wB in draft (superscript HTML spacing)",
        "Grubbs\u2019 (right single quotation mark) in snapshot vs Grubbs' (apostrophe) in draft",
    ],
    "PLOS017:N": [
        "Citations [ 23 ] and [ 42 ] in snapshot vs [23] and [42] in draft (HTML spacing artifact)",
        "1 st to 3 rd in snapshot vs 1st to 3rd in draft (superscript ordinal HTML artifact)",
    ],
}

NOTES = {
    "PLOS017:C": (
        "HTML normalization applied (w^{1118} -> w 1118, D\u03b17 -> D \u03b1 7, "
        "CO2 -> CO 2, [29] stripped). "
        "Boundary confirmed: 'findings shown here' appears in preceding Introduction context, "
        "completely outside this Methods draft boundary. contains_outcome = NO."
    ),
    "PLOS017:H": (
        "HTML normalization applied (D\u03b17 -> D \u03b1 7). "
        "Boundary confirmed: 'I found that...' is in subsequent text outside the boundary. "
        "The phrase 'similar effects' in the draft refers strictly to a literature-based hypothesis, "
        "not an observation. contains_outcome = NO."
    ),
    "PLOS017:M": (
        "HTML normalization applied (spacing around citations and units). "
        "The phrase 'percent impairment' in the text defines a readout metric/calculation, "
        "not an efficacy claim or biological result. contains_outcome = NO."
    ),
    "PLOS017:N": (
        "HTML normalization applied (superscript spacing, citation spacing). "
        "The phrase 'results across experiments' refers to procedural consistency and QC of the "
        "nicotine concentrations, not a biological outcome or result. contains_outcome = NO."
    ),
}

# ── publisher locators ────────────────────────────────────────────────────────
PUB_LOC = {
    "PLOS017:C": (
        "Materials and Methods > Drosophila strains and culture; "
        'paragraph beginning "Flies were reared in a light-dark controlled incubator..."'
    ),
    "PLOS017:H": (
        "Introduction > aim/hypothesis paragraph; "
        'sentence beginning "I hypothesized that developmental nicotine exposure..."'
    ),
    "PLOS017:M": (
        "Materials and Methods > Nicotine sensitivity assay; "
        'paragraph beginning "A negative geotaxis assay was used to determine nicotine sensitivity..."'
    ),
    "PLOS017:N": (
        "Materials and Methods > Nicotine exposure; "
        'paragraph beginning "The developmental drug exposure protocol was adapted from McClure et al...."'
    ),
}

V1_LOC = {
    "PLOS017:C": "Materials and Methods, Drosophila strains and culture, lines 156-158",
    "PLOS017:H": "Introduction, aim/hypothesis paragraph, line 150",
    "PLOS017:M": "Materials and Methods, Nicotine sensitivity assay, lines 168-171",
    "PLOS017:N": "Materials and Methods, Nicotine exposure, lines 159-163",
}

SR_MAP = {"PLOS017:C": C_sr, "PLOS017:H": H_sr, "PLOS017:M": M_sr, "PLOS017:N": N_sr}

# ── assemble + write ──────────────────────────────────────────────────────────
rows = [json.loads(x) for x in JSONL.read_text(encoding="utf-8").splitlines() if x.strip()]
assert len(rows) == 20

def get_idx(cid): return next(i for i, r in enumerate(rows) if r["chunk_id"] == cid)

for cid in sorted(TARGET):
    rows[get_idx(cid)] = {
        "chunk_id": cid, "source_id": "PLOS017",
        "source_url": URL, "snapshot_file": SNAP, "snapshot_sha256": SHA,
        "v1_locator": V1_LOC[cid],
        "publisher_locator": PUB_LOC[cid],
        "publisher_segment_exact": pub[cid],
        "draft_text": drafts[cid],
        "text_status": "VERBATIM_WITH_HTML_NORMALIZATION",
        "representation": "VERBATIM",
        "normalization_notes": NORM[cid],
        "sentence_reviews": SR_MAP[cid],
        "outcome_status": "VERIFIED_NO_OUTCOME",
        "efficacy_conclusion_status": "VERIFIED_NO_EFFICACY_CONCLUSION",
        "review_status": "REVIEWED",
        "reviewer_id": RV, "reviewed_at": RA,
        "notes": NOTES[cid],
    }

out = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
JSONL.write_text(out, encoding="utf-8")

# ── round-trip assert + report ────────────────────────────────────────────────
back = [json.loads(x) for x in JSONL.read_text(encoding="utf-8").splitlines() if x.strip()]
assert len(back) == 20

for cid in sorted(TARGET):
    r = next(x for x in back if x["chunk_id"] == cid)
    assert r["review_status"] == "REVIEWED",              f"{cid} review_status wrong"
    assert r["text_status"] == "VERBATIM_WITH_HTML_NORMALIZATION", f"{cid} text_status wrong"
    assert r["outcome_status"] == "VERIFIED_NO_OUTCOME",  f"{cid} outcome_status wrong"
    assert r["efficacy_conclusion_status"] == "VERIFIED_NO_EFFICACY_CONCLUSION"
    assert len(r["sentence_reviews"]) > 0,                f"{cid} no sentence_reviews"
    assert "publisher_segment_exact" in r
    assert "normalization_notes" in r
    for sr in r["sentence_reviews"]:
        assert sr["contains_result"] == "NO"
        assert sr["contains_outcome"] == "NO"
        assert sr["contains_efficacy_conclusion"] == "NO"
    print(f"OK  {cid}")
    print(f"    review_status    : {r['review_status']}")
    print(f"    text_status      : {r['text_status']}")
    print(f"    outcome_status   : {r['outcome_status']}")
    print(f"    sentence_count   : {len(r['sentence_reviews'])}")
    print(f"    norm_notes_count : {len(r['normalization_notes'])}")
    print(f"    pub_seg_len      : {len(r['publisher_segment_exact'])} chars")
    print(f"    reviewed_at      : {r['reviewed_at']}")
    print()

reviewed = sum(1 for x in back if x["review_status"] == "REVIEWED")
pending  = sum(1 for x in back if x["review_status"] == "PENDING")
print(f"total={len(back)}  REVIEWED={reviewed}  PENDING={pending}")



