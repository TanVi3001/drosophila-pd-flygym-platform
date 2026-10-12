"""
Write reviewed record for PLOS004:M into chunk_review.jsonl.
publisher_locator corrected from reviewer-submitted value:
  submitted: paragraph beginning "The negative geotaxis assay was performed..."
  correct  : paragraph beginning "After a ten-minute acclimation period..." (same section)
Both paragraphs confirmed present in snapshot sha256 E609315FD3D15DE93E8C936BB5FD3C749C9B98B23E555C0C1AFF4BA0E7A0D200.
draft_text confirmed VERBATIM_EXACT in snapshot.
"""
import json
from pathlib import Path

p = Path(".workbench/evidence/protocol_evidence_eval_review_20261011_v2/chunk_review.jsonl")
rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

assert len(rows) == 20
idx = next(i for i, r in enumerate(rows) if r["chunk_id"] == "PLOS004:M")
assert idx == 4

updated = {
    "chunk_id": "PLOS004:M",
    "source_id": "PLOS004",
    "source_url": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0041907",
    "snapshot_file": "source_snapshots/PLOS004.html",
    "snapshot_sha256": "E609315FD3D15DE93E8C936BB5FD3C749C9B98B23E555C0C1AFF4BA0E7A0D200",
    "v1_locator": "Materials and Methods, Negative Geotaxis",
    "publisher_locator": (
        "Materials and Methods > Negative Geotaxis; "
        "paragraph beginning \"After a ten-minute acclimation period...\" "
        "\u2014 sentence beginning \"ImageJ particle analysis\""
    ),
    "publisher_locator_verification_note": (
        "Heading 'Negative Geotaxis' confirmed in snapshot. "
        "Needle sentence found in paragraph following acclimation-period paragraph. "
        "Reviewer-submitted locator ('The negative geotaxis assay was performed...') "
        "is paragraph-1 of same section, not the paragraph containing the needle sentence; "
        "corrected to paragraph-2 beginning 'After a ten-minute acclimation period'."
    ),
    "draft_text": (
        "ImageJ particle analysis was then used to determine "
        "the height animals had climbed 4 s post-startle."
    ),
    "text_status": "VERBATIM_EXACT",
    "representation": "VERBATIM",
    "sentence_reviews": [
        {
            "sentence_id": "PLOS004:M-s1",
            "draft_text": (
                "ImageJ particle analysis was then used to determine "
                "the height animals had climbed 4 s post-startle."
            ),
            "publisher_text": (
                "ImageJ particle analysis was then used to determine "
                "the height animals had climbed 4 s post-startle."
            ),
            "classification": ["METHOD", "REPORTED_READOUT"],
            "contains_result": "NO",
            "contains_outcome": "NO",
            "contains_efficacy_conclusion": "NO",
            "provenance": "PUBLISHED_PAPER",
        }
    ],
    "outcome_status": "VERIFIED_NO_OUTCOME",
    "efficacy_conclusion_status": "VERIFIED_NO_EFFICACY_CONCLUSION",
    "review_status": "REVIEWED",
    "reviewer_id": "reviewer_01",
    "reviewed_at": "2026-10-12T11:48:00+07:00",
    "notes": (
        "publisher_locator corrected from reviewer-submitted version: "
        "submitted locator pointed to paragraph-1 of Negative Geotaxis section; "
        "needle is in paragraph-2 beginning 'After a ten-minute acclimation period'. "
        "draft_text confirmed VERBATIM_EXACT against snapshot "
        "sha256 E609315FD3D15DE93E8C936BB5FD3C749C9B98B23E555C0C1AFF4BA0E7A0D200."
    ),
}

rows[idx] = updated

out = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
p.write_text(out, encoding="utf-8")

# Verify round-trip
back = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
assert len(back) == 20
r = back[idx]
assert r["chunk_id"] == "PLOS004:M"
assert r["review_status"] == "REVIEWED"
assert r["text_status"] == "VERBATIM_EXACT"
assert r["outcome_status"] == "VERIFIED_NO_OUTCOME"
assert len(r["sentence_reviews"]) == 1
assert r["sentence_reviews"][0]["publisher_text"] == (
    "ImageJ particle analysis was then used to determine "
    "the height animals had climbed 4 s post-startle."
)

pending = sum(1 for x in back if x["review_status"] == "PENDING")
reviewed = sum(1 for x in back if x["review_status"] == "REVIEWED")

print(f"OK  chunk_id       : {r['chunk_id']}")
print(f"    review_status  : {r['review_status']}")
print(f"    text_status    : {r['text_status']}")
print(f"    outcome_status : {r['outcome_status']}")
print(f"    reviewer_id    : {r['reviewer_id']}")
print(f"    reviewed_at    : {r['reviewed_at']}")
print(f"    publisher_locator: {r['publisher_locator']}")
print(f"    sentence_count : {len(r['sentence_reviews'])}")
print(f"    total rows     : {len(back)}")
print(f"    PENDING        : {pending}")
print(f"    REVIEWED       : {reviewed}")
