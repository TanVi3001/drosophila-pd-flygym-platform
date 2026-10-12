"""Verify PLOS004:C and PLOS004:H sentences against snapshot."""
import html, re
from pathlib import Path

raw = Path(".workbench/evidence/protocol_evidence_eval_draft_20261011_v2/source_snapshots/PLOS004.html").read_text(encoding="utf-8", errors="replace")

def visible(s):
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html.unescape(" ".join(s.split()))

text = visible(raw)

# ── PLOS004:C ────────────────────────────────────────────────────────────────
c_draft = (
    "Careful attention was paid to injection volumes, time on CO2 and recovery periods "
    "being equivalent for both infected and PBS injected control animals as such stresses "
    "could affect performance on behavioral assays."
)

# Try full sentence
c_found_full = c_draft in text
print(f"PLOS004:C  full_sentence  : {'EXACT' if c_found_full else 'NOT_FOUND'}")

# Try shorter anchors
anchors_c = [
    "Careful attention was paid to injection volumes",
    "time on CO2 and recovery periods",
    "PBS injected control animals",
    "stresses could affect performance on behavioral assays",
    "CO2 and recovery periods being equivalent",
]
for a in anchors_c:
    print(f"  anchor [{a[:50]}]: {'FOUND' if a in text else 'NOT_FOUND'}")

# Show context if any anchor found
for a in anchors_c:
    idx = text.find(a)
    if idx >= 0:
        print(f"\n  CONTEXT around [{a[:40]}]:")
        print(repr(text[max(0, idx-300):idx+300]))
        break

# ── PLOS004:H ────────────────────────────────────────────────────────────────
print("\n" + "="*70)
h_draft = (
    "We hypothesized that these metrics could also be used to assess health "
    "during infection because D. melanogaster shows an age-related up-regulation "
    "of inflammatory genes and expression patterns that characterize aging and "
    "the induction of an immune response in these animals are related [18]."
)

h_found_full = h_draft in text
print(f"PLOS004:H  full_sentence  : {'EXACT' if h_found_full else 'NOT_FOUND'}")

anchors_h = [
    "We hypothesized that these metrics could also be used",
    "assess health during infection",
    "age-related up-regulation of inflammatory genes",
    "characterize aging and the induction of an immune response",
    "immune response in these animals are related",
]
for a in anchors_h:
    print(f"  anchor [{a[:55]}]: {'FOUND' if a in text else 'NOT_FOUND'}")

# Show context around hypothesis sentence
for a in anchors_h:
    idx = text.find(a)
    if idx >= 0:
        print(f"\n  CONTEXT around [{a[:40]}]:")
        print(repr(text[max(0, idx-400):idx+400]))
        break

# ── Outcome language scan for H ──────────────────────────────────────────────
print("\n" + "="*70)
print("Outcome / result / efficacy language scan in PLOS004:H draft text:")
outcome_triggers = [
    "showed", "demonstrated", "revealed", "found that", "resulted in",
    "improved", "declined", "reduced", "increased", "significantly",
    "effect", "impact", "confirmed", "validated", "reliable",
    "successful", "restored", "impaired",
]
for t in outcome_triggers:
    if t.lower() in h_draft.lower():
        print(f"  TRIGGER_FOUND: '{t}'")
print("  (no further triggers)" if not any(t.lower() in h_draft.lower() for t in outcome_triggers) else "")
