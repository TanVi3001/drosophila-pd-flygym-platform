"""Verify CCR and G sentences against snapshot before writing review records."""
import html, re
from pathlib import Path

raw = Path(".workbench/evidence/protocol_evidence_eval_draft_20261011_v2/source_snapshots/PLOS004.html").read_text(encoding="utf-8", errors="replace")

def visible(s):
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html.unescape(" ".join(s.split()))

text = visible(raw)

ccr_sentences = [
    ("CCR-s1", "Each day a new group of infected and control flies were transferred to clean glass vials (20 flies per vial) without anesthesia around noon and placed in melting ice in a bucket for three hours to induce chill coma."),
    ("CCR-s2", "Prior to beginning the assay, flies were moved from the vials to individual wells of a 48 well plate while being kept on ice."),
    ("CCR-s3", "A timer was started once the plates were moved from the ice to a bench at room temperature and flies were considered recovered when they were able to stand."),
    ("CCR-s4", "Each fly was checked by eye for recovery once a minute for the first 60 minutes, and every five minutes for the remaining 90-minute period."),
    ("CCR-s5", "Data is expressed as the percentage of flies that have stood by each time point."),
]

g_sentences = [
    ("G-s1", "After a ten-minute acclimation period, the frame was tapped three times and climbing was captured with time-lapse photographs taken once per second post startle."),
    ("G-s2", "Flies were then transferred without anesthesia back into their rearing vial."),
]

all_ok = True
for sid, s in ccr_sentences + g_sentences:
    found = s in text
    status = "EXACT" if found else "NOT_FOUND"
    print(f"{sid}: {status}")
    if not found:
        all_ok = False

print()
print("CCR_HEADING_Chill_Coma_Recovery:", "Chill Coma Recovery" in text)
print("CCR_LOCATOR_PARA_start:", "Each day a new group of infected" in text)
print("G_LOCATOR_PARA_start:", "After a ten-minute acclimation period" in text)
print()
print("ALL_SENTENCES_EXACT:", all_ok)
