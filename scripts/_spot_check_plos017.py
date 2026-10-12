import json
from pathlib import Path

back = [json.loads(x) for x in Path('.workbench/evidence/protocol_evidence_eval_review_20261011_v2/chunk_review.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]

for cid in ['PLOS017:C','PLOS017:H','PLOS017:M','PLOS017:N']:
    r = next(x for x in back if x['chunk_id']==cid)
    srs = r['sentence_reviews']
    bad = [s for s in srs if s['contains_result']!='NO' or s['contains_outcome']!='NO' or s['contains_efficacy_conclusion']!='NO']
    print(f"{cid}:")
    print(f"  sentences={len(srs)}  bad_flags={len(bad)}")
    print(f"  classification[0]={srs[0]['classification']}")
    print(f"  pub_seg_len={len(r['publisher_segment_exact'])} chars")
    print(f"  pub_loc={r['publisher_locator'][:80]}")
    print(f"  notes={r['notes'][:80]}")
    print()

print('REVIEWED=', sum(1 for r in back if r['review_status']=='REVIEWED'))
print('PENDING =', sum(1 for r in back if r['review_status']=='PENDING'))
