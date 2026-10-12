import json
from pathlib import Path

p = Path('.workbench/evidence/protocol_evidence_eval_review_20261011_v2/chunk_review.jsonl')
rows = [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
assert len(rows) == 20

SHA = "E609315FD3D15DE93E8C936BB5FD3C749C9B98B23E555C0C1AFF4BA0E7A0D200"
URL = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0041907"
SNAP = "source_snapshots/PLOS004.html"

# ── PLOS004:C ────────────────────────────────────────────────────────────────
idx_c = next(i for i, r in enumerate(rows) if r['chunk_id'] == 'PLOS004:C')
rows[idx_c] = {
    "chunk_id": "PLOS004:C",
    "source_id": "PLOS004",
    "source_url": URL,
    "snapshot_file": SNAP,
    "snapshot_sha256": SHA,
    "v1_locator": "Materials and Methods, infection/recovery conditions, line 193",
    "publisher_locator": (
        "Materials and Methods > infection/recovery conditions; "
        'sentence beginning "Careful attention was paid to injection volumes..."'
    ),
    "publisher_segment_exact": (
        "Careful attention was paid to injection volumes, time on CO 2 and recovery periods "
        "being equivalent for both infected and PBS injected control animals as such stresses "
        "could affect performance on behavioral assays [30] \u2013 [32] ."
    ),
    "draft_text": (
        "Careful attention was paid to injection volumes, time on CO2 and recovery periods "
        "being equivalent for both infected and PBS injected control animals as such stresses "
        "could affect performance on behavioral assays."
    ),
    "text_status": "VERBATIM_WITH_HTML_NORMALIZATION",
    "representation": "VERBATIM",
    "normalization_notes": [
        "CO2 in draft = CO 2 in snapshot (HTML superscript <sup>2</sup> stripped to space)",
        "Citation [30]\u2013[32] present in publisher text; absent in draft (stripped at extraction)",
    ],
    "sentence_reviews": [
        {
            "sentence_id": "PLOS004:C-s1",
            "draft_text": (
                "Careful attention was paid to injection volumes, time on CO2 and recovery periods "
                "being equivalent for both infected and PBS injected control animals as such stresses "
                "could affect performance on behavioral assays."
            ),
            "publisher_text": (
                "Careful attention was paid to injection volumes, time on CO 2 and recovery periods "
                "being equivalent for both infected and PBS injected control animals as such stresses "
                "could affect performance on behavioral assays [30] \u2013 [32] ."
            ),
            "classification": ["METHOD", "CONTROL"],
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
    "reviewed_at": "2026-10-12T12:10:00+07:00",
    "notes": (
        "Difference from VERBATIM_EXACT: "
        "(1) HTML superscript renders CO2 as CO 2 in snapshot; "
        "(2) citation [30]-[32] stripped in draft. "
        "Content is identical. No outcome or result language in sentence."
    ),
}

# ── PLOS004:H ────────────────────────────────────────────────────────────────
idx_h = next(i for i, r in enumerate(rows) if r['chunk_id'] == 'PLOS004:H')
rows[idx_h] = {
    "chunk_id": "PLOS004:H",
    "source_id": "PLOS004",
    "source_url": URL,
    "snapshot_file": SNAP,
    "snapshot_sha256": SHA,
    "v1_locator": "Introduction, lines 149-150",
    "publisher_locator": (
        "Introduction; "
        'paragraph beginning "We hypothesized that these metrics could also be used..."'
    ),
    "publisher_segment_exact": (
        "We hypothesized that these metrics could also be used to assess health during infection "
        "because D. melanogaster shows an age-related up-regulation of inflammatory genes and "
        "expression patterns that characterize aging and the induction of an immune response in "
        "these animals are related [18] ."
    ),
    "draft_text": (
        "We hypothesized that these metrics could also be used to assess health during infection "
        "because D. melanogaster shows an age-related up-regulation of inflammatory genes and "
        "expression patterns that characterize aging and the induction of an immune response in "
        "these animals are related [18]."
    ),
    "text_status": "VERBATIM_WITH_HTML_NORMALIZATION",
    "representation": "VERBATIM",
    "normalization_notes": [
        "Publisher has '[18] .' (space before period); draft has '[18].' \u2014 HTML artifact only",
        (
            "IMPORTANT: Surrounding paragraph contains outcome/result language "
            "('Here we report on assays...', "
            "'wasting and loss of circadian rhythms reported to occur during infection...') "
            "but these phrases are NOT in the draft text. Boundary confirmed."
        ),
    ],
    "sentence_reviews": [
        {
            "sentence_id": "PLOS004:H-s1",
            "draft_text": (
                "We hypothesized that these metrics could also be used to assess health during "
                "infection because D. melanogaster shows an age-related up-regulation of "
                "inflammatory genes and expression patterns that characterize aging and the "
                "induction of an immune response in these animals are related [18]."
            ),
            "publisher_text": (
                "We hypothesized that these metrics could also be used to assess health during "
                "infection because D. melanogaster shows an age-related up-regulation of "
                "inflammatory genes and expression patterns that characterize aging and the "
                "induction of an immune response in these animals are related [18] ."
            ),
            "classification": ["HYPOTHESIS", "RATIONALE"],
            "contains_result": "NO",
            "contains_outcome": "NO",
            "contains_efficacy_conclusion": "NO",
            "provenance": "PUBLISHED_PAPER",
            "outcome_boundary_note": (
                "Sentence states group's hypothesis ('We hypothesized that... could be used'). "
                "Does not assert that metrics were shown to work or that any effect was observed. "
                "Surrounding paragraph contains 'Here we report on assays...' and "
                "'wasting and loss of circadian rhythms reported...' "
                "\u2014 these are NOT within the draft text boundary."
            ),
        }
    ],
    "outcome_status": "VERIFIED_NO_OUTCOME",
    "efficacy_conclusion_status": "VERIFIED_NO_EFFICACY_CONCLUSION",
    "review_status": "REVIEWED",
    "reviewer_id": "reviewer_01",
    "reviewed_at": "2026-10-12T12:10:00+07:00",
    "notes": (
        "Hypothesis statement only. Surrounding Introduction paragraph contains "
        "outcome/result language but those sentences are outside the draft text boundary. "
        "Confirmed by publisher segment extraction. "
        "Difference from VERBATIM_EXACT: space artifact in citation rendering '[18] .' vs '[18].'."
    ),
}

# ── Write & verify ────────────────────────────────────────────────────────────
out = '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n'
p.write_text(out, encoding='utf-8')

back = [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
assert len(back) == 20

for cid, n_sent in [('PLOS004:C', 1), ('PLOS004:H', 1)]:
    r = next(x for x in back if x['chunk_id'] == cid)
    assert r['review_status'] == 'REVIEWED'
    assert r['text_status'] == 'VERBATIM_WITH_HTML_NORMALIZATION'
    assert r['outcome_status'] == 'VERIFIED_NO_OUTCOME'
    assert len(r['sentence_reviews']) == n_sent
    assert 'publisher_segment_exact' in r
    assert 'normalization_notes' in r
    print(f"OK  {cid}")
    print(f"    review_status          : {r['review_status']}")
    print(f"    text_status            : {r['text_status']}")
    print(f"    outcome_status         : {r['outcome_status']}")
    print(f"    sentence_count         : {len(r['sentence_reviews'])}")
    print(f"    normalization_notes[0] : {r['normalization_notes'][0]}")
    print(f"    reviewer_id            : {r['reviewer_id']}")
    print(f"    reviewed_at            : {r['reviewed_at']}")
    print()

reviewed = sum(1 for x in back if x['review_status'] == 'REVIEWED')
pending  = sum(1 for x in back if x['review_status'] == 'PENDING')
print(f"total={len(back)}  REVIEWED={reviewed}  PENDING={pending}")

