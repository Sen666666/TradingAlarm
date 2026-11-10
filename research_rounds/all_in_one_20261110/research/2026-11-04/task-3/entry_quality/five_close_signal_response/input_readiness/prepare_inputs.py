"""Inventory original all-market Q logs and attach original I-root lineage only.

No first-root selection until parent protocol confirmation; no future prices,
fixed-age labels, account construction or original-model recalculation.
"""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
import json,gzip,hashlib
import pandas as pd

O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str,allow_nan=False)
def jsline(z):return json.dumps(z,ensure_ascii=False,separators=(',',':'))+'\n'
def main():
 O.mkdir(parents=True,exist_ok=True)
 save('SCOPE.json',dict(created=datetime.now().astimezone().isoformat(),status='input preparation only; no first signal selection before parent protocol',qualification='core_Q is True OR (mobile_Q is True AND current original CP1_id nonempty)',root_proposed='sid+original source_segment+I_target false-to-true real start; E0 root retained separately but never mixed',excluded_inputs=['actual intents','roles','held','barriers','funded flags','account ACT on','return labels','future close'],left_censor='real I start before first continuous opportunity-log day is inherited and first-ever qualified event unknown; do not promote first seen to first ever',new_accounts=0,new_models=0,new_five_close_results=0))
 smp=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';sm={x['symbol']:x for x in read(smp)};roster=set(sm);assert len(roster)==1709
 roots={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/opportunities.jsonl.gz','strong':B/'pvr_pool_feasibility/runs/2025_26/pair/opportunities.jsonl.gz'}
 qualified={};summary={};dailyall={}
 for ref,p in roots.items():
  SRC[str(p)]=sha(p);daily={};signals=[];accounts=Counter();n=0
  with gzip.open(p,'rt') as f:
   for line in f:
    z=json.loads(line);n+=1;day=z['day'];sid=z['sid'];accounts[z['account']]+=1
    d=daily.setdefault(day,dict(sids=set(),core=Counter(),mobile=Counter(),fresh_CP1=0,union_signals=0,signal_types=Counter(),duplicates=[]))
    if sid in d['sids']:d['duplicates'].append(sid)
    d['sids'].add(sid);d['core'][str(z['core_Q'])]+=1;d['mobile'][str(z['mobile_Q'])]+=1;d['fresh_CP1']+=bool(z['CP1_id'])
    core=z['core_Q'] is True;mobile=z['mobile_Q'] is True and bool(z['CP1_id'])
    if core or mobile:
     kind='core_and_fresh_mobile' if core and mobile else 'core_only' if core else 'fresh_mobile_only';d['signal_types'][kind]+=1;d['union_signals']+=1
     signals.append(dict(window=ref,day=day,sid=sid,sector=z['sector'],core_Q=z['core_Q'],mobile_Q=z['mobile_Q'],CP1_id=z['CP1_id'],union_signal_kind=kind,original_log_source=str(p),account_fields_not_used=True))
  assert len(accounts)==1 and not any(d['duplicates'] for d in daily.values())
  boundary=min(daily);assert set().union(*(d['sids'] for d in daily.values()))<=roster
  coverage=[dict(day=day,observed_stock_rows=len(d['sids']),fixed_roster=1709,missing_roster_ids=sorted(roster-d['sids']),core_Q_counts=dict(d['core']),mobile_Q_counts=dict(d['mobile']),fresh_CP1_count=d['fresh_CP1'],union_signal_count=d['union_signals'],union_signal_type_counts=dict(d['signal_types'])) for day,d in sorted(daily.items())]
  qualified[ref]=signals;dailyall[ref]=coverage
  summary[ref]=dict(source=str(p),rows=n,accounts=dict(accounts),continuous_log_start=boundary,last_day=max(daily),sessions=len(daily),min_stock_rows_per_day=min(len(d['sids']) for d in daily.values()),max_stock_rows_per_day=max(len(d['sids']) for d in daily.values()),union_signals=len(signals),stocks_with_union_signals=len({z['sid'] for z in signals}),core_Q_unknown_stock_days=sum(d['core']['None'] for d in daily.values()),mobile_Q_unknown_stock_days=sum(d['mobile']['None'] for d in daily.values()),signal_type_counts=dict(Counter(z['union_signal_kind'] for z in signals)),stock_missing_any_day_ids=sorted(set().union(*(roster-d['sids'] for d in daily.values()))),stock_absent_entire_log_ids=sorted(roster-set().union(*(d['sids'] for d in daily.values()))))
  print('LOG',ref,n,'sessions',len(daily),'signal events',len(signals),flush=True)
 # Only existing cached factual I/E0 state is read; no model call or new indicator.
 requests=defaultdict(list)
 for ref,zs in qualified.items():
  for z in zs:requests[z['sid']].append(z)
 source_checks={};unresolved=[]
 for ix,(sid,zs) in enumerate(sorted(requests.items())):
  rec=sm[sid]
  if rec['status']!='complete':
   for z in zs:z.update(lineage_status='manifest_not_complete',original_I_root=None);unresolved.append(z)
   continue
  p=Path(rec['refs']['facts']);assert sha(p)==rec['output_sha256'][str(p)];SRC[str(p)]=sha(p);f=pd.read_parquet(p,columns=['i_target','e0_target','segment_id']);assert f.index.is_unique and f.index.is_monotonic_increasing
  # Match original target false->true/source transition semantics; I and E0 distinct.
  for target,label in [('i_target','I'),('e0_target','E0')]:
   on=f[target].eq(1);opening=on&~on.groupby(f.segment_id).shift(fill_value=False)
   start=pd.Series(pd.NaT,index=f.index,dtype='datetime64[ns]');start.loc[opening]=f.index[opening];f[label+'_root_start']=start.groupby(f.segment_id,sort=False).ffill().where(on)
  for z in zs:
   d=pd.Timestamp(z['day'])
   if d not in f.index:
    z.update(lineage_status='no_exact_signal_day_in_original_facts',original_I_root=None);unresolved.append(z);continue
   r=f.loc[d];start=r.I_root_start;estart=r.E0_root_start
   if not bool(r.i_target) or pd.isna(start):
    z.update(lineage_status='qualified_signal_but_I_not_true_or_start_unknown',original_I_root=None,original_I_target=bool(r.i_target));unresolved.append(z);continue
   isday=str(start.date());esday=None if pd.isna(estart) else str(estart.date());segment=int(r.segment_id);boundary=summary[z['window']]['continuous_log_start']
   z.update(lineage_status='exact_cached_I_root',source_segment=segment,original_I_target=True,original_I_root_start=isday,original_I_root=f'{sid}|{segment}|I|{isday}',
    original_E0_root_start=esday,original_E0_root=None if esday is None else f'{sid}|{segment}|E0|{esday}',original_facts_source=str(p),original_facts_source_sha256=SRC[str(p)],
    first_continuous_opportunity_day=boundary,left_censored_root=isday<boundary,
    left_censor_meaning='I root predates source log; first-ever Q event unknown' if isday<boundary else 'source log covers original I root from its start',
    source_max_used_for_lineage=z['day'])
  source_checks[sid]=dict(facts_rows=len(f),first_cached_day=str(f.index.min().date()),last_cached_day=str(f.index.max().date()),qualified_events_attached=len(zs),source_sha256=SRC[str(p)])
  if (ix+1)%400==0:print('LINEAGE',ix+1,flush=True)
 for ref,zs in qualified.items():
  summary[ref]['qualified_I_lineage_unknown']=sum(z['lineage_status']!='exact_cached_I_root' for z in zs)
  summary[ref]['qualified_I_target_false']=sum(z.get('original_I_target') is False for z in zs)
  summary[ref]['left_censored_signal_events']=sum(z.get('left_censored_root',False) for z in zs)
  summary[ref]['root_start_covered_signal_events']=sum(z.get('left_censored_root') is False for z in zs)
  with gzip.open(O/(ref+'_UNION_SOURCE_EVENTS_NO_FIRST_SELECTION.jsonl.gz'),'wt') as f:
   for z in zs:f.write(jsline(z))
  save(ref+'_DAILY_INPUT_COVERAGE.json',dailyall[ref])
 save('SOURCE_COVERAGE.json',summary);save('LINEAGE_INPUT_CHECKS.json',dict(stocks_read=len(source_checks),stock_facts=source_checks,unresolved=unresolved,first_root_selection_done=False,new_5close_labels=0,root_dedup_outcome_comparisons=0))
 save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=sha(__file__),manifest_status_counts=dict(Counter(x['status'] for x in sm.values())),new_models=0,new_accounts=0,new_future_price_reads=0))
 print('COMPLETE',flush=True)
if __name__=='__main__':main()
