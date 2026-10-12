"""
scripts/_verify_plos017_deep.py

Verify chunks PLOS017:C, PLOS017:H, PLOS017:M, PLOS017:N against
.workbench/evidence/protocol_evidence_eval_draft_20261011_v2/source_snapshots/PLOS017.html

Requirements:
1. Strip HTML tags to get clean text.
2. Check exact substring match for each draft text.
3. If not found exactly, try first-10-words anchor to locate the segment.
4. Print the exact publisher segment found (same length as draft text, or anchor window).
5. Print 500 chars of context BEFORE and AFTER the found segment.
6. Scan the surrounding context (outside draft text) for outcome-adjacent keywords;
   print any that are found with their immediate context.
"""

import html as html_module
import json
import re
from pathlib import Path

# ── helpers ──────────────────────────────────────────────────────────────────

SNAP = Path(
    ".workbench/evidence/protocol_evidence_eval_draft_20261011_v2"
    "/source_snapshots/PLOS017.html"
)
CORPUS = Path(
    ".workbench/evidence/protocol_evidence_eval_draft_20261010_v1"
    "/corpus/corpus_draft.jsonl"
)

OUTCOME_KEYWORDS = [
    "show", "result", "increase", "decrease", "reduce", "significant",
    "impair", "restore", "compare", "reveal",
]

CONTEXT_CHARS = 500
KEYWORD_WINDOW = 80   # chars each side when reporting a keyword hit


def strip_html(raw: str) -> str:
    """Remove scripts, styles, tags; decode entities; collapse whitespace."""
    s = re.sub(r"(?is)<script.*?</script>", " ", raw)
    s = re.sub(r"(?is)<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html_module.unescape(" ".join(s.split()))


def first_n_words(text: str, n: int = 10) -> str:
    return " ".join(text.split()[:n])


def scan_keywords(surrounding: str, draft: str) -> list[tuple[str, str]]:
    """
    Find outcome_keywords in `surrounding` that are NOT inside `draft`.
    Returns list of (keyword, snippet) tuples.
    """
    hits = []
    surrounding_lower = surrounding.lower()
    draft_lower = draft.lower()
    for kw in OUTCOME_KEYWORDS:
        start = 0
        while True:
            idx = surrounding_lower.find(kw, start)
            if idx == -1:
                break
            # Extract the window for this hit
            snippet = surrounding[max(0, idx - KEYWORD_WINDOW): idx + len(kw) + KEYWORD_WINDOW]
            # Only report if keyword is not inside the draft text itself
            if kw not in draft_lower:
                hits.append((kw, snippet.strip()))
            start = idx + 1
    return hits


def verify_chunk(chunk_id: str, draft: str, text: str) -> None:
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"CHUNK: {chunk_id}")
    print(sep)

    # 1. Exact match
    exact = draft in text
    print(f"  exact_match          : {'YES' if exact else 'NO'}")

    # 2. Anchor: first 10 words
    anchor = first_n_words(draft, 10)
    anchor_idx = text.find(anchor)
    print(f"  anchor_10w_found     : {'YES' if anchor_idx >= 0 else 'NO'}")
    print(f"  anchor               : {repr(anchor)}")

    if anchor_idx < 0:
        # Try first 6 words as fallback
        anchor6 = first_n_words(draft, 6)
        anchor_idx = text.find(anchor6)
        print(f"  anchor_6w_found      : {'YES' if anchor_idx >= 0 else 'NO'}")
        print(f"  anchor_6w            : {repr(anchor6)}")
        if anchor_idx < 0:
            print("  STATUS               : NOT_FOUND — cannot locate segment in snapshot")
            return

    seg_start = anchor_idx
    seg_end   = anchor_idx + len(draft)

    # 3. Publisher segment (same length window as draft)
    pub_segment = text[seg_start:seg_end]
    print(f"\n  --- PUBLISHER SEGMENT (draft-length window from anchor) ---")
    print(f"  {repr(pub_segment)}")

    # 4. Context BEFORE
    before = text[max(0, seg_start - CONTEXT_CHARS): seg_start]
    print(f"\n  --- CONTEXT BEFORE ({CONTEXT_CHARS} chars) ---")
    print(f"  {repr(before)}")

    # 5. Context AFTER
    after = text[seg_end: seg_end + CONTEXT_CHARS]
    print(f"\n  --- CONTEXT AFTER ({CONTEXT_CHARS} chars) ---")
    print(f"  {repr(after)}")

    # 6. Keyword scan in surrounding (before + after), excluding draft itself
    surrounding = before + after
    hits = scan_keywords(surrounding, draft)
    print(f"\n  --- OUTCOME-ADJACENT KEYWORD SCAN (surrounding only, not in draft) ---")
    if hits:
        seen_kw = set()
        for kw, snippet in hits:
            if kw not in seen_kw:
                print(f"  KEYWORD '{kw}' FOUND IN SURROUNDING:")
                print(f"    ...{snippet}...")
                seen_kw.add(kw)
    else:
        print("  No outcome-adjacent keywords found in surrounding context.")

    # Also note any keywords present inside draft text itself
    draft_kw_hits = [kw for kw in OUTCOME_KEYWORDS if kw in draft.lower()]
    if draft_kw_hits:
        print(f"\n  NOTE: keyword(s) also present INSIDE draft text: {draft_kw_hits}")
        print("  These require sentence-level classification by reviewer.")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    raw  = SNAP.read_text(encoding="utf-8", errors="replace")
    text = strip_html(raw)

    target_ids = {"PLOS017:C", "PLOS017:H", "PLOS017:M", "PLOS017:N"}
    chunks = {
        c["chunk_id"]: c["text"]
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for c in [json.loads(line)]
        if c["chunk_id"] in target_ids
    }

    print(f"Snapshot : {SNAP}")
    print(f"Snapshot size (visible chars): {len(text):,}")
    print(f"Chunks to verify: {sorted(chunks.keys())}")

    for cid in sorted(chunks.keys()):
        verify_chunk(cid, chunks[cid], text)

    print(f"\n{'=' * 72}")
    print("DONE")


if __name__ == "__main__":
    main()
