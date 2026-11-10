"""Invalidate a future first-Q anchor before paired outcomes; reuse all scores."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,collections,shutil,ast,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
archive=O/'feature-asof-errata-v1';archive.mkdir(exist_ok=False)
names=['PAIR_ID_FREEZE.json','COVERAGE_PRE_OUTCOMES.json','MOBILE_CHAIN_CENSUS.json','CAPITAL_CHAIN_READINESS.json','READINESS.json']
for win in ['2022','2025_26']:
 names += [f'{win}/FEATURES.parquet',f'{win}/PAIRS_PRE_OUTCOMES.parquet',f'{win}/UNMATCHED_STATUS.parquet',f'{win}/PAIRED_CAPITAL_CONTEXT_PRE_OUTCOMES.json']
for name in names:
 p=archive/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(O/name,p)
# The original executed preparation source is already byte-preserved by the prior filter errata.
oldsource=O/'capital-time-filter-errata-v1/prepare_only.py';shutil.copy2(oldsource,archive/'prepare_only.executed-v1.py')
contract=json.loads((O/'CONTRACT_FREEZE.json').read_text());assert sha(O/'CONTRACT.txt')==contract['contract_sha256']
source=O/'original_match_function.py';env=dict(pd=pd,collections=collections,digest=lambda x:hashlib.sha256(x.encode()).hexdigest());exec(compile(source.read_text(),str(source),'exec'),env);match=env['match']
oldcoverage=json.loads((O/'COVERAGE_PRE_OUTCOMES.json').read_text());output={};pairids={};corrections={};regress=[]
for win in ['2022','2025_26']:
 f=pd.read_parquet(O/win/'FEATURES.parquet');bad=f.anchor.notna()&pd.to_datetime(f.anchor).gt(f.date)
 wrong=f.loc[bad,['symbol','date','i_start','anchor','age','known_id']].to_dict('records');corrections[win]=wrong
 for i in f.index[bad]:
  rr=list(f.at[i,'unknown_reasons']);rr.append('no_original_core_Q_anchor_yet');f.at[i,'unknown_reasons']=np.array(sorted(set(rr)),dtype=object)
  f.at[i,'anchor']=None;f.at[i,'age']=np.nan;f.at[i,'runup']=np.nan;f.at[i,'feature_ready']=False
  old=f.at[i,'known_id'];a=next(x['anchor'] for x in wrong if x['known_id']==old);f.at[i,'known_id']=old.replace('|anchor='+a+'|','|anchor=None|')
 assert not (f.anchor.notna()&pd.to_datetime(f.anchor).gt(f.date)).any();assert not f.age.lt(0).any()
 assert not f.date.lt(pd.to_datetime(f.i_start)).any()
 f.to_parquet(O/win/'FEATURES.parquet',index=False);p,status=match(f);neutral=f.copy();neutral['pvr']=0.;pn,_=match(neutral);assert list(p.pair_id)==list(pn.pair_id)
 cuts=['2022-06-30','2022-09-30'] if win=='2022' else ['2025-12-31','2026-03-31'];pref=[]
 for cut in cuts:
  pp,_=match(f[f.date<=pd.Timestamp(cut)]);assert list(pp.pair_id)==list(p.loc[p.date<=cut,'pair_id']);pref.append(dict(cut=cut,pairs=len(pp)))
 p.to_parquet(O/win/'PAIRS_PRE_OUTCOMES.parquet',index=False);status.to_parquet(O/win/'UNMATCHED_STATUS.parquet',index=False)
 rs=f.to_dict('records');matched=set(status.loc[status.reason=='matched_today','known_id'])
 def desc(rows):
  out={}
  for key in ['h1','age','runup','scale','pvr']:
   a=[float(r[key]) for r in rows if r[key] is not None and np.isfinite(r[key])];out[key]=dict(known=len(a),unknown=len(rows)-len(a),min=min(a) if a else None,median=float(np.median(a)) if a else None,max=max(a) if a else None)
  return out
 output[win]=dict(mother_events=len(f),ready_events=int(f.feature_ready.sum()),feature_unknown_counts=dict(collections.Counter(x for r in rs for x in r['unknown_reasons'])),pairs=len(p),pair_dates=p.date.nunique(),pair_stocks=len(set(p.h1_symbol)|set(p.other_symbol)),pair_industries=p.sector.nunique(),kinds=dict(collections.Counter(p.pair_kind)),status=dict(collections.Counter(status.reason)),matched_distributions=desc([r for r in rs if r['known_id'] in matched]),unmatched_distributions=desc([r for r in rs if r['known_id'] not in matched]),prefix_checks=pref,PVR_neutral_pair_IDs_exact=True)
 pairids[win]=list(p.pair_id);regress.append(dict(window=win,removed_future_anchor_count=int(bad.sum()),no_future_anchor=True,no_negative_age=True,I_start_not_future=True,new_pair_label_joins=0,old_pair_ids_unchanged=list(p.pair_id)==list(pd.read_parquet(archive/win/'PAIRS_PRE_OUTCOMES.parquet').pair_id)))
 # Cache/score identity: never touch original PVR output parts.
cache=json.loads((O/'CACHE_MANIFEST.json').read_text());assert all(sha(O/'pvr-cache'/f"{r['symbol']}.parquet")==r['output_sha256'] for r in cache['entries'])
save('COVERAGE_PRE_OUTCOMES.json',output);save('PAIR_ID_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),contract_sha256=sha(O/'CONTRACT.txt'),pair_ids=pairids,before_any_new_pair_label_join=True,feature_outcome_columns=[],new_account_paths=0,asof_fix='onlyinvalidate futureQanchors; source scores unchanged'))
save('ASOF_FEATURE_CORRECTION.json',dict(corrections=corrections,regressions=regress,all1659_score_files_byte_identical=True,matching_rules_unchanged=True,contract_unchanged=True,paired_label_outcomes_never_joined=True,original_bad_outputs_preserved=str(archive),updated_prepare_source_sha256=sha(O/'prepare_only.py')))
print(json.dumps({w:{k:v for k,v in r.items() if k not in ['matched_distributions','unmatched_distributions']} for w,r in output.items()},ensure_ascii=False));print('ASOF_FIX',regress)
