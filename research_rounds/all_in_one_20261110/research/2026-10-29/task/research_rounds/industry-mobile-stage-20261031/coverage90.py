"""All90 unchanged market-state coverage; no account or stock CP1 generation."""
from pathlib import Path
import sys,time,json,importlib.util,collections,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent/'coverage90';O.mkdir(exist_ok=True);W=O.parent.parent
s=importlib.util.spec_from_file_location('coverage90_frozen_stage',O.parent/'stage.py');S=importlib.util.module_from_spec(s);sys.modules[s.name]=S;s.loader.exec_module(S);T=S.T
BEGIN='2025-07-01';END='2026-06-30';T.BEGIN='1900-01-01';T.END=END
def save(n,x):
 x=T.norm(x);(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 if isinstance(x,list) and x:pd.DataFrame(x).to_csv(O/(n+'.csv'),index=False)
def read(p):return json.loads(Path(p).read_text())
records={r['series_id']:r for r in read(T.OLD/'manifest.json')['series']};ids=sorted(r for r in records if r.startswith('URFI'));assert len(ids)==90
matrix=pd.read_parquet(W/'market-mainline-measurement-20261031/FEATURE_MATRIX_90.parquet');days=sorted(matrix.day.unique());calendar=pd.DatetimeIndex(days);assert len(days)==242
def one(sid,pilot=False):
 start=time.monotonic();f,ev,ep,ref=T.source_frame(sid,records);loaded=time.monotonic();z=T.M.calculate(f);calculated=time.monotonic();rr,_,_=T.trace(sid,f,z,ev,ep);ids_by={r['confirmed_day']:r['receipt_id'] for r in rr};rows=S.run(sid,f,z,ids_by);traced=time.monotonic();checks={}
 if pilot:
  cut='2025-12-31';short=f.loc[:cut];zs=T.M.calculate(short);pd.testing.assert_frame_equal(z.loc[:cut],zs,check_exact=True,check_freq=False);sr,_,_=T.trace(sid,short,zs,ev.loc[:cut],ep.loc[:cut]);past=S.run(sid,short,zs,{r['confirmed_day']:r['receipt_id'] for r in sr});assert past==[r for r in rows if r['day']<=cut];checks['physical_signal_and_state_prefix']=True
 old=O.parent/(sid+'_STATE.json')
 if old.exists():assert read(old)==[r for r in rows if r['day']<='2026-03-31'];checks['previous_five_full_state_prefix']=True
 audit=[dict(series=sid,**r) for r in rows if BEGIN<=r['day']<=END];pd.DataFrame(audit).to_parquet(O/(sid+'.parquet'),index=False)
 info=dict(series=sid,full_warm_start=str(f.index.min().date()),full_observations=len(f),audit_observations=len(audit),price_missing_dates=[d for d in days if d not in {r['day'] for r in audit}],source_load_seconds=loaded-start,CP1_seconds=calculated-loaded,trace_and_stage_seconds=traced-calculated,seconds=time.monotonic()-start,checks=checks)
 save(sid+'_CHECK',info);print('INDUSTRY',sid,round(info['seconds'],3),flush=True);return info
def stats(values):
 a=np.array(values,dtype=float)
 return dict(n=len(a),min=float(a.min()),p25=float(np.quantile(a,.25)),median=float(np.median(a)),p75=float(np.quantile(a,.75)),p90=float(np.quantile(a,.9)),max=float(a.max()),mean=float(a.mean())) if len(a) else dict(n=0)
def aggregate(infos):
 rows=pd.concat([pd.read_parquet(O/(sid+'.parquet')) for sid in ids],ignore_index=True);rows['quarter']=pd.PeriodIndex(pd.to_datetime(rows.day),freq='Q').astype(str);assert not rows.duplicated(['series','day']).any();daily=[]
 for day,g in rows.groupby('day'):
  known=g.action.ne('unknown');counts=g.loc[known,'stage_name'].value_counts();e0=g.E0_valid;h=matrix[matrix.day==day].set_index('sector').H1_original
  daily.append(dict(day=day,quarter=str(pd.Period(day,freq='Q')),expected_industries=90,observed_industries=len(g),missing_price_industries=90-len(g),unknown_state_industries=int((~known).sum()),observation=int(counts.get('observe',0)),probe=int(counts.get('probe',0)),confirmed=int(counts.get('confirmed',0)),expanded=int(counts.get('expanded',0)),confirmed_or_expanded=int(g.loc[known,'stage'].ge(2).sum()),E0_active=int(e0.eq(True).sum()),H1_unknown=int(h.isna().sum()),E0_and_H1_known=int(sum(bool(r.E0_valid) and pd.notna(h.get(r.series,np.nan)) for _,r in g.iterrows())),new_attempts=int(g.action.eq('probe').sum()),mobile_resets=int(g.reason.eq('mobile_line').sum()),E0_attempt_ends=int((g.reason.eq('E0_invalid')&g.attempt_before.notna()).sum()),full_Q='not reconstructed; E0/H1 layer only'))
 save('DAILY_COUNTS',daily);daily=pd.DataFrame(daily);quarters=[]
 for q,g in daily.groupby('quarter'):
  quarters.append(dict(quarter=q,days=len(g),zero_confirmed_only_days=int(g.confirmed.eq(0).sum()),zero_confirmed_or_expanded_days=int(g.confirmed_or_expanded.eq(0).sum()),zero_expanded_days=int(g.expanded.eq(0).sum()),missing_price_sector_days=int(g.missing_price_industries.sum()),unknown_state_sector_days=int(g.unknown_state_industries.sum()),new_attempts=int(g.new_attempts.sum()),mobile_resets=int(g.mobile_resets.sum()),counts={k:stats(g[k]) for k in ['observation','probe','confirmed','expanded','confirmed_or_expanded','E0_active']}))
 save('QUARTER_COUNTS',quarters)
 attempts=[]
 for (sid,aid),g in rows[rows.attempt_id.notna()].groupby(['series','attempt_id']):
  g=g.sort_values('day');end=rows[(rows.series==sid)&(rows.attempt_before==aid)&rows.action.eq('end_attempt')];opened=g[g.action.eq('probe')];attempts.append(dict(series=sid,attempt_id=aid,observed_start=g.day.iloc[0],observed_last_active=g.day.iloc[-1],opened_in_evaluation=not opened.empty,left_truncated=opened.empty,right_censored=end.empty,exit_day=None if end.empty else end.day.iloc[0],exit_reason=None if end.empty else end.reason.iloc[0],active_observations_in_evaluation=len(g),max_stage=int(g.stage.max()),stage_observations=g.stage_name.value_counts().to_dict()))
 save('ATTEMPT_DURATIONS',attempts);completed=[a['active_observations_in_evaluation'] for a in attempts if not a['left_truncated'] and not a['right_censored']];save('ATTEMPT_SUMMARY',dict(attempts_intersecting_window=len(attempts),opened_in_window=sum(a['opened_in_evaluation'] for a in attempts),carried_in=sum(a['left_truncated'] for a in attempts),right_censored=sum(a['right_censored'] for a in attempts),completed_fully_observed=stats(completed),all_attempt_observed_durations_truncated=stats([a['active_observations_in_evaluation'] for a in attempts]),per_quarter_new_attempts={q:int(g.new_attempts.sum()) for q,g in daily.groupby('quarter')},not_independent_market_samples=True))
 blocks=read(W/'behavior-contract-20261031/ALL_NONOVERLAP21_MARKET_BLOCKS.json');weak=read(W/'behavior-contract-20261031/CANDIDATES_PENDING_REVIEW.json');weak_ids={r['review_id'] for r in weak if r['review_id'].startswith('ALL90|')};out=[]
 for b in blocks:
  d=daily[(daily.day>=b['start'])&(daily.day<=b['end'])];out.append(dict(**b,previously_selected_weak_candidate=b['review_id'] in weak_ids,observed_days=len(d),confirmed_or_expanded=stats(d.confirmed_or_expanded),expanded=stats(d.expanded),probe=stats(d.probe),zero_confirmed_or_expanded_days=int(d.confirmed_or_expanded.eq(0).sum()),zero_expanded_days=int(d.expanded.eq(0).sum()),note='original price-defined blocks, no relabeling from state; not certified no-mainline'))
 save('FIXED_PRICE_BLOCKS',out)
 cpcover=read(W/'cp1-evidence-trace-20261031/CASE_STOCK_CP1_COVERAGE.json');stocks=[r['sid'] for r in cpcover];receipts=[read(W/'native-I-cache-interface-20261031/receipts'/f'{sid}.json') for sid in stocks]
 required={sid:[T.OLD/records[sid]['files'][k]['path'] for k in ['signal','events','states']]+[T.RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet'] for sid in stocks}
 missing=[dict(sid=sid,path=str(p)) for sid,paths in required.items() for p in paths if not p.exists()];first=read(O/(ids[0]+'_CHECK.json'));total_rows=sum(r.get('warm_rows',0) for r in receipts);derive=sum(r['seconds'] for r in receipts);cpestimate=total_rows*first['CP1_seconds']/first['full_observations'];save('STOCK79_PREFLIGHT',dict(stocks=79,existing_complete_original_CP1=0,all_cached_input_paths_present=not missing,missing=missing,source_fields='full warm i_target/i_floor from original cache.py:derive; same-source close/amount/segment and native event=-1; no G1/raw indicator recompute; CP1 needs pre-window anchor/frontier/frozen scale/credit state',existing_derivation_receipt_total_seconds=derive,estimated_CP1_seconds_from_industry_pilot=cpestimate,estimated_sequential_total_seconds_with_25pct_margin=1.25*(derive+cpestimate),estimate_is_not_run=True,full_warm_observation_upper_bound=total_rows,first_observation_after_evaluation=[dict(sid=r['sid'],warm_from=r['warm_from']) for r in receipts if r.get('warm_from','')>END],no_cached_observation_before_prior_cut=[r['sid'] for r in receipts if r['status']=='no_observation_before_cut'],no_stocks_recalculated=True,no1709_expansion=True))
 save('SUMMARY',dict(quarter=quarters,zero_confirmed_or_expanded_all_days=int(daily.confirmed_or_expanded.eq(0).sum()),zero_expanded_all_days=int(daily.expanded.eq(0).sum()),calendar_days=len(daily),expected_sector_days=len(daily)*90,observed_sector_days=len(rows),missing_sector_days=len(daily)*90-len(rows),unknown_state_rows=int(rows.action.eq('unknown').sum()),separate_full_Q_unknown=True))
def main():
 mode=sys.argv[1];start=time.monotonic()
 if mode=='pilot':
  save('FREEZE',dict(before_run=True,industries=ids,window=[BEGIN,END],unchanged_stage_sha256=T.sha(O.parent/'stage.py'),source_matrix_sha256=T.sha(W/'market-mainline-measurement-20261031/FEATURE_MATRIX_90.parquet'),script_sha256=T.sha(Path(__file__)),account_paths=0));r=one(ids[0],True);estimate=90*(r['source_load_seconds']+r['CP1_seconds']+r['trace_and_stage_seconds'])*1.15+8;save('PILOT',dict(info=r,estimated_total_seconds=estimate,allowed=estimate<=120,seconds=time.monotonic()-start));print('ESTIMATE',estimate,flush=True)
 elif mode=='aggregate':
  infos=[read(O/(sid+'_CHECK.json')) for sid in ids];aggregate(infos);save('COMPLETION',dict(completed=True,industries=90,pilot_reused=True,all_history_seconds=sum(x['seconds'] for x in infos),aggregation_seconds=time.monotonic()-start,new_economic_paths=0,aggregation_resume_without_market_recalculation=True));print('AGGREGATE_DONE',round(time.monotonic()-start,3),flush=True)
 elif mode=='full':
  gate=read(O/'PILOT.json');assert gate['allowed'];infos=[gate['info']]
  for sid in ids[1:]:
   if time.monotonic()-start>112:save('PARTIAL',dict(completed=len(infos),seconds=time.monotonic()-start));raise TimeoutError('120s bounded audit; outputs retained')
   infos.append(one(sid))
  aggregate(infos);save('COMPLETION',dict(completed=True,industries=90,pilot_reused=True,seconds=time.monotonic()-start,total_compute_including_pilot=time.monotonic()-start+gate['seconds'],new_economic_paths=0));print('ALL90_DONE',round(time.monotonic()-start,3),flush=True)
if __name__=='__main__':main()
