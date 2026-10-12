"""
Deep verification for PLOS004:C and PLOS004:H.
PLOS004:C: draft has 'CO2'; snapshot has 'CO 2' (space from <sup>2</sup> rendering).
PLOS004:H: need to confirm exact boundary of hypothesis sentence vs surrounding outcome language.
"""
import html, re
from pathlib import Path

raw = Path(".workbench/evidence/protocol_evidence_eval_draft_20261011_v2/source_snapshots/PLOS004.html").read_text(encoding="utf-8", errors="replace")

def visible(s):
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html.unescape(" ".join(s.split()))

text = visible(raw)

# ── PLOS004:C deep check ─────────────────────────────────────────────────────
print("=== PLOS004:C ===")
# Draft text uses 'CO2' — snapshot renders as 'CO 2' after stripping <sup>
c_draft      = "Careful attention was paid to injection volumes, time on CO2 and recovery periods being equivalent for both infected and PBS injected control animals as such stresses could affect performance on behavioral assays."
c_normalized = c_draft.replace("CO2", "CO 2")
c_normalized_noref = re.sub(r'\s*\[\d+\]\s*(?:–\s*\[\d+\])?', '', c_normalized).strip()

print(f"  draft exact              : {'EXACT' if c_draft in text else 'NOT_FOUND'}")
print(f"  CO2->CO 2 normalized     : {'EXACT' if c_normalized in text else 'NOT_FOUND'}")
print(f"  normalized + no citation : {'EXACT' if c_normalized_noref in text else 'NOT_FOUND'}")

# Show the exact publisher segment containing the sentence
idx = text.find("Careful attention was paid to injection volumes")
if idx >= 0:
    segment = text[idx:idx+350]
    print(f"\n  PUBLISHER_SEGMENT:\n  {repr(segment)}")

# Check what citation appears in the publisher text
print(f"\n  citation [30] present near sentence: {'[30]' in text[idx:idx+350] if idx>=0 else 'N/A'}")

# ── PLOS004:H deep check ─────────────────────────────────────────────────────
print("\n=== PLOS004:H ===")
h_draft = (
    "We hypothesized that these metrics could also be used to assess health "
    "during infection because D. melanogaster shows an age-related up-regulation "
    "of inflammatory genes and expression patterns that characterize aging and "
    "the induction of an immune response in these animals are related [18]."
)
h_normalized_noref = re.sub(r'\s*\[18\]', '', h_draft).strip()
print(f"  draft exact              : {'EXACT' if h_draft in text else 'NOT_FOUND'}")
print(f"  without [18] citation    : {'EXACT' if h_normalized_noref in text else 'NOT_FOUND'}")

# Show full publisher segment including surrounding sentences
idx_h = text.find("We hypothesized that these metrics could also be used")
if idx_h >= 0:
    segment_h = text[max(0,idx_h-500):idx_h+600]
    print(f"\n  PUBLISHER_SEGMENT (500 chars before + 600 after):\n  {repr(segment_h)}")

# Check specific outcome/result phrases in SURROUNDING text (not draft)
surrounding = text[max(0,idx_h-500):idx_h+600] if idx_h >= 0 else ""
outcome_in_surrounding = [
    "we report on", "report on assays", "measures of natural declines",
    "wasting and loss of circadian rhythms", "reported to occur",
    "infection in flies",
]
print("\n  Outcome/result phrases in SURROUNDING context (not in draft itself):")
for phrase in outcome_in_surrounding:
    print(f"    [{phrase}]: {'FOUND_IN_SURROUNDING' if phrase.lower() in surrounding.lower() else 'NOT_FOUND'}")

# Confirm: are those phrases IN the draft text itself?
print("\n  Are those phrases IN the H draft text itself?")
for phrase in outcome_in_surrounding:
    print(f"    [{phrase}]: {'IN_DRAFT' if phrase.lower() in h_draft.lower() else 'NOT_IN_DRAFT'}")
