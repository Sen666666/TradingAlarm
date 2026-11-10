
from pathlib import Path
import json,gzip,hashlib,time
from collections import Counter,defaultdict
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/mobile_candidate_response_v1')
R=O.parents[1]/'account_comparison_continuous_v1'
P=R/'run_1200000/pair';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p):return json.loads(Path(p).read_text())
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
start=time.monotonic()
im=read(U/'INDUSTRY_MANIFEST.json');sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')}
sector={}
for r in im:
 f=pd.read_parquet(r['refs']['state']);f=f[(f.day>='2022-01-01')&(f.day<='2026-05-15')]
 for q in f.to_dict('records'):sector[(r['series'],q['day'])]=q
accounts={a:json.load(gzip.open(P/(a+'.json.gz'),'rt'))for a in ['PVR','E31']}
pending={};firstfills={};daily_held={};stats=Counter()
for a,x in accounts.items():
 for d in x['decisions']:
  for i in d['intents']:
   if i['role']=='mobile':pending[(a,d['at'][:10],i['sid'])]=i
 for l in x['layers']:
  if l['kind']=='add':firstfills[(a,l['signal_at'][:10],l['sid'])]=True
for line in gzip.open(P/'daily.jsonl.gz','rt'):
 d=json.loads(line);daily_held[(d['account'],d['at'][:10])]=set(d['positions'])
raw=[];pmap={}
for line in gzip.open(P/'opportunities.jsonl.gz','rt'):
 d=json.loads(line);stats['opportunity_rows']+=1
 if d['held']or 'mobile'not in d['roles']:continue
 stats['empty_mobile_role_rows']+=1
 if d['barriers']:
  for b in d['barriers']:stats['barrier_'+b]+=1
  continue
 assert d['mobile_Q']is True and d['CP1_id']
 key=(d['account'],d['day'],d['sid'])
 assert d['sid']not in daily_held[(d['account'],d['day'])]
 st=sector[(d['sector'],d['day'])];active=bool(st['E0_valid']and pd.notna(st['attempt_id'])and st['stage']>0)
 i=pending.get(key);r=dict(d,industry_active=active,industry_stage=int(st['stage']),industry_attempt=str(st['attempt_id'])if pd.notna(st['attempt_id'])else None,pending=i is not None)
 if i:
  assert d['CP1_id']==i['CP1_id']and i['cap']>0 and not i.get('size_reject')
  r.update(original_PVR=i['PVR_score'],original_priority_rank=i['priority_rank'],original_H1=i['score'],original_H1_rank=i['original_H1_rank'],cap=i['cap'],budget=i['budget'],floor=i['floor'],epoch=str(i['epoch']))
 raw.append(r);pmap[key]=r
raw=pd.DataFrame(raw)
# Actual per-account source facts/CP receipt check, no indicator runs.
eligible=raw[raw.industry_active&raw.pending].copy();check=[]
for no,(sid,idx)in enumerate(eligible.groupby('sid').groups.items()):
 f=pd.read_parquet(sm[sid]['refs']['facts']);cp=pd.read_parquet(sm[sid]['refs']['CP1']);days=pd.DatetimeIndex(eligible.loc[idx,'day'])
 for name,z in [('i_target',f.i_target),('e0_ready',f.e0_ready),('g_ready',f.g_ready),('cp_receipt',cp.receipt)]:
  eligible.loc[idx,'verified_'+name]=z.reindex(days).to_numpy()
 if(no+1)%400==0:print('CHECKED_STOCKS',no+1,flush=True)
assert eligible.verified_i_target.eq(1).all()
assert eligible.verified_e0_ready.eq(1).all()
assert eligible.verified_g_ready.eq(True).all()
assert eligible.verified_cp_receipt.eq(True).all()
assert not eligible.duplicated(['account','sid','day']).any()
# Each CP identifier must identify one observation day/stock across the two accounts.
cpdays=eligible.groupby('CP1_id').agg(day_count=('day','nunique'),sid_count=('sid','nunique'));assert cpdays.day_count.eq(1).all()and cpdays.sid_count.eq(1).all()
first=pd.read_csv(O.parent/'ALL_FIRST_ENTRIES.csv');first=first[first.first_kind=='add']
missing=[]
for r in first.itertuples():
 key=(r.account,r.signal_day,r.sid);q=pmap.get(key)
 if q is None or not q['industry_active']or not q['pending']:missing.append(key)
assert not missing,missing[:10]
eligible['year']=eligible.day.str[:4].astype(int)
agg=eligible.groupby(['account','year']).agg(candidate_stockdays=('sid','size'),stocks=('sid','nunique'),signal_days=('day','nunique'),cp_ids=('CP1_id','nunique'),PVR_known=('original_PVR','count')).reset_index()
raw.drop(columns=['roles','barriers']).to_parquet(O/'RAW_EMPTY_MOBILE_OPPORTUNITIES.parquet',index=False)
eligible.drop(columns=['roles','barriers']).to_parquet(O/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',index=False)
agg.to_csv(O/'CANDIDATE_ANNUAL_COUNTS.csv',index=False)
summary=dict(status='RECONSTRUCTED_CANDIDATE_DOMAIN_NOT_FUNDED_OR_TRADABLE',seconds=time.monotonic()-start,stats=dict(stats),raw_empty_mobile_no_barrier=len(raw),industry_inactive=int((~raw.industry_active).sum()),missing_original_pending=int((~raw.pending).sum()),legal_candidate_rows=len(eligible),actual_first_mobile_fills=len(first),actual_first_mobile_missing=len(missing),unique_observation_cp_ids_verified=True,source_facts_checks_pass=True,source_opportunities_daily_empty_exact=True,account_runs=0,indicator_runs=0,definition='Original account-specific held=False; fresh CP1 on same close, mobile_Q True, no ACT/pending barriers, actual original mobile intent cap>0; original industry market attempt active. Budget cash/risk/pool ability at next open not required or promised.',limitations=['original account-state conditioned empty domain; reordering could change future held states, not a full policy counterfactual','fixed future1709 and fixed industry members non-PIT','same stock can recur only with a different fresh CP1; not independent trials','unfunded legal intentions included; no next-day OHLC used for candidate membership'])
dump('DOMAIN_AUDIT.json',summary)
dump('DOMAIN_SOURCE_SHA256.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [P/'opportunities.jsonl.gz',P/'daily.jsonl.gz',P/'PVR.json.gz',P/'E31.json.gz',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',Path(__file__)]})
print(json.dumps(summary));print(agg.to_string(index=False))
