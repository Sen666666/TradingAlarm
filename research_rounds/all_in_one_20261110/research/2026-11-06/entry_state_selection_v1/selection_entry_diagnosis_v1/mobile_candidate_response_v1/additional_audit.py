
from pathlib import Path
import json,gzip,hashlib
from collections import Counter
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/mobile_candidate_response_v1')
P=O.parents[1]/'account_comparison_continuous_v1/run_1200000/pair'
def read(p):return json.loads(Path(p).read_text())
raw=pd.read_parquet(O/'RAW_EMPTY_MOBILE_OPPORTUNITIES.parquet');c=pd.read_parquet(O/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet')
keys=set(zip(c.account,c.day,c.sid));missing=raw[raw.industry_active&~raw.pending];closewhy={}
h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');days=[str(pd.Timestamp(d).date())for d in h['dates']];prev=dict(zip(days[1:],days[:-1]))
open_results=Counter();unmatched_industry=[]
for line in gzip.open(P/'funding.jsonl.gz','rt'):
 r=json.loads(line)
 if r.get('role')!='mobile':continue
 day=r['at'][:10]
 if '15:10' in r['at']:closewhy[(r['account'],day,r['sid'])]=r['result']
 else:
  key=(r['account'],prev[day],r['sid'])
  if key in keys:
   open_results[r['result']]+=1
   if r['result']=='industry_invalidated':unmatched_industry.append(key)
reasons=Counter(closewhy.get((r.account,r.day,r.sid),'UNEXPLAINED')for r in missing.itertuples())
assert reasons.get('UNEXPLAINED',0)==0
assert not unmatched_industry
u=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sm={r['symbol']:r for r in read(u/'STOCK_MANIFEST.json')}
rm={r['series_id']:r for r in read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json')['series']}
checked=[];bad=[]
for sid in sorted(set(c.sid)):
 paths=[(sm[sid]['refs']['facts'],sm[sid]['output_sha256'][sm[sid]['refs']['facts']]),(rm[sid]['raw']['path'],rm[sid]['raw']['sha256'])]
 for p,expected in paths:
  actual=hashlib.sha256(Path(p).read_bytes()).hexdigest();checked.append(dict(sid=sid,path=p,expected=expected,actual=actual,passed=actual==expected))
  if actual!=expected:bad.append(p)
assert not bad,bad[:5]
pd.DataFrame(checked).to_csv(O/'NATIVE_SOURCE_HASH_AUDIT.csv',index=False)
# Analysis-only common complete dates. Never affects queues or membership.
sel=pd.read_parquet(O/'SEALED_SAME_K_SELECTIONS.parquet');rows=[]
for(a,y),g in sel.groupby(['account','year']):
 for H in [5,20]:
  count=g.groupby(['day','strategy']).agg(k=('sid','size'),complete=('complete'+str(H),'sum'),ret=('ret'+str(H),'mean'))
  good=count.k.eq(count.complete).unstack('strategy').fillna(False).all(axis=1)
  ret=count.ret.unstack('strategy');r=ret[good]
  rows.append(dict(account=a,year=y,horizon=H,common_complete_dates=len(r),original=r.ORIGINAL_PVR.mean(),response=r.MOBILE_RESPONSE.mean(),response_minus_original=(r.MOBILE_RESPONSE-r.ORIGINAL_PVR).mean(),daily_positive_difference=(r.MOBILE_RESPONSE>r.ORIGINAL_PVR).mean()))
pd.DataFrame(rows).to_csv(O/'MATCHED_COMPLETE_DATE_CHECK.csv',index=False)
unknown=c.assign(PVR_known=np.isfinite(c.original_PVR)).groupby(['account','year']).PVR_known.agg(['sum','count'])
sc=pd.read_parquet(O/'CANDIDATE_SCORES.parquet')
known=sc.groupby(['account','year']).agg(candidate_count=('sid','size'),model_known=('model_known','sum'),mean_sector_dates=('sector_training_dates','mean'),median_sector_dates=('sector_training_dates','median'))
known.to_csv(O/'MODEL_KNOWLEDGE_BY_YEAR.csv')
out=dict(missing_pending_active_sector=len(missing),missing_pending_reasons=dict(reasons),included_next_open_outcomes=dict(open_results),included_industry_invalidated=0,source_files_checked=len(checked),source_hash_failures=0,passed=True)
(O/'ADDITIONAL_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out));print(pd.DataFrame(rows).to_string(index=False));print(known.to_string())
