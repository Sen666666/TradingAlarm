"""Freeze three actual PVR samples before reading their execution prices.
The preserved first freeze mistakenly used H1 ranks; no price was read then.
"""
from pathlib import Path
import gzip,hashlib,json,math
import pandas as pd

O=Path(__file__).resolve().parent;R=O.parent
opp=R/'market_gross_admission_native_v1/full-long-v1/pair/opportunities.jsonl.gz'
mp=R/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json'
days={'2024-09-24':'2024-09-25','2024-09-25':'2024-09-26','2024-09-26':'2024-09-27'}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows={d:[] for d in days}
with gzip.open(opp,'rt') as f:
    for line in f:
        r=json.loads(line)
        if r['day'] in rows and 'mobile' in r['roles'] and r['mobile_Q'] is True and r['CP1_id']:
            rows[r['day']].append(r)
m=json.loads(mp.read_text());entries={r['symbol']:r for r in m['entries']}
sources={str(opp):sha(opp),str(mp):sha(mp)}
scores={}
for sid in sorted({r['sid'] for group in rows.values() for r in group}):
    p=mp.parent/'scores'/f'{sid}.parquet';h=sha(p)
    assert h==entries[sid]['output_sha256'];sources[str(p)]=h
    f=pd.read_parquet(p,columns=['score'])
    for d in days:
        if pd.Timestamp(d) in f.index:
            v=float(f.loc[pd.Timestamp(d),'score'])
            if math.isfinite(v):scores[sid,d]=v
samples=[];full=[]
for d,group in rows.items():
    known=[dict(r,PVR_score=scores[r['sid'],d]) for r in group if (r['sid'],d) in scores]
    assert len(known)==len(group),'unknown PVR changes selection; stop instead of silently choosing available scores'
    ordered=sorted(known,key=lambda r:(-r['PVR_score'],r['sid']))
    samples.append(dict(ordered[0],next_OPEN=days[d],fixed_sample_order=1))
    full.extend(ordered)
out=dict(selection_frozen_before_sample_price_read=True,selection='Highest existing original frozen PVR_score among original retained fresh mobile roles, exact float score descending then sid; all PVR known',
    correction='THREE_FIXED_SAMPLES_FREEZE.json preserved as wrong H1-rank interpretation; H1 is not PVR. No sample price or future return was read before this corrected freeze.',
    candidate_counts={d:len(group) for d,group in rows.items()},samples=samples,sources=sources,
    accounts_constructed=0,indicators_recomputed=0)
p=O/'THREE_TRUE_PVR_SAMPLES_FREEZE.json';assert not p.exists();p.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
(O/'ALL_THREE_DAYS_FRESH_MOBILE_PVR_ORDER.json').write_text(json.dumps(full,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'selected':samples,'candidate_counts':out['candidate_counts'],'score_files':len(scores)//3,'freeze_SHA256':sha(p)},ensure_ascii=False,indent=2))
