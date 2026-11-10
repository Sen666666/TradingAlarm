"""Saved replay/ranking/diagnostics audit. No original full E0/G1/I or account calls."""
from pathlib import Path
import json,hashlib,math,statistics,ast
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];E=R.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
D=['2022-01-24','2024-09-24','2026-01-15'];KEY=['day','sid'];P={'BREAKOUT':0,'START':1,'RETRACED':2}
prior={d:E/'full_local_signal_two_dates_v1'/d/'FROZEN_IBUY_PRIOR_RANKS.parquet'for d in D};prior[D[1]]=E/'pvr_924_discrimination_v1/FROZEN2313_PRIOR_RANKS.parquet'
raw={d:E/'full_local_signal_two_dates_v1'/d/'signals/ALL_SIGNALS.parquet'for d in D};raw[D[1]]=E/'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet'
paths={d:(E/'pvr_924_discrimination_v1'if d==D[1]else E/'full_local_signal_two_dates_v1'/d)/'paths/HORIZON_PATHS.parquet'for d in D}
def null(x):return x is None or x is pd.NA or x is pd.NaT or(isinstance(x,(float,np.floating))and math.isnan(x))
def eq(a,b):
 if null(a)or null(b):return null(a)and null(b)
 if isinstance(a,(float,np.floating))and isinstance(b,(float,np.floating)):return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)
 return a==b
def close(a,b):
 if null(a)or null(b):assert null(a)and null(b),(a,b)
 else:assert math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-12),(a,b)
receipt=read(R/'RANK_FREEZE_RECEIPT.json');binding=read(R/'SOURCE_BINDING.json');freeze=read(R/'FREEZE.json')
for p,h in binding['files'].items():assert sha(p)==h,('source changed',p)
assert sha(R/'STAGED_PRIOR_RANKS.parquet')==receipt['stage_rank_sha256'] and sha(R/'research.py')==receipt['code_sha256'] and sha(R/'FREEZE.json')==receipt['freeze_sha256']
q=pd.read_parquet(R/'STAGED_PRIOR_RANKS.parquet');snap=pd.read_parquet(R/'ALL_REQUEST_STAGE_SNAPSHOTS.parquet');assert q[KEY].duplicated().sum()==snap[KEY].duplicated().sum()==0
j=[];parts=sorted((R/'parts').glob('*.jsonl'))
for p in parts:
 b=p.read_bytes();assert not b or b.endswith(b'\n')
 j.extend(json.loads(line,parse_constant=lambda z:(_ for _ in ()).throw(ValueError(z)))for line in b.splitlines())
assert len(j)==len({(r['day'],r['sid'])for r in j})==len(snap)==3287
indexed=snap.set_index(KEY).sort_index();pairfields=[('research_e0_ready','e0_ready'),('research_e0_target','e0_target'),('research_e0_floor','e0_floor'),('research_e0_entered','e0_entered'),('research_e0_exited','e0_exited'),('numeric_event','numeric_event'),('numeric_leg_direction','numeric_leg_direction'),('close','close')]
rawframes={d:pd.read_parquet(raw[d]).set_index('sid')for d in D};exact=missing=0
for r in j:
 z=indexed.loc[(r['day'],r['sid'])]
 for c in z.index:assert eq(z[c],r.get(c)),(r['day'],r['sid'],c,'journal')
 old=rawframes[r['day']].loc[r['sid']]
 if r['status']=='COMPLETE':
  exact+=1;assert old.signal_status=='EXACT_TARGET_STOCK_SIGNAL'
  for new,oldc in pairfields:assert eq(z[new],old[oldc]),(r['day'],r['sid'],oldc)
  assert r['source_prefix_last']==r['day'] and r['source_prefix_first']<=r['day']
  for event in r['last_six_confirmed_events']:
   assert event['occurred']<event['confirmed']<=r['day'] and event['kind']in ['PEAK','TROUGH']
  for row in r['case_event_trail']:
   assert row['day']<=r['day']
   if row['reference_peak_confirmed'] is not None:assert row['reference_peak_occurred']<row['reference_peak_confirmed']<=row['start_date']<=row['day']
 else:missing+=1;assert old.signal_status!='EXACT_TARGET_STOCK_SIGNAL'
assert (exact,missing)==(3283,4)
counts={};swaps=[];old_priors={}
for d in D:
 old=pd.read_parquet(prior[d]).set_index('sid').sort_index();g=q[q.day.eq(d)].set_index('sid').sort_index();old_priors[d]=old
 assert g.index.equals(old.index)
 for c in old.columns:pd.testing.assert_series_equal(g[c],old[c],check_names=False,check_dtype=False,check_exact=True)
 expected_request=set(old.index)|set(freeze['cases']);actual_request=set(snap[snap.day.eq(d)].sid);assert expected_request==actual_request
 g_snap=indexed.loc[d].loc[g.index]
 for c in g_snap.columns:
  if c not in old.columns:pd.testing.assert_series_equal(g[c],g_snap[c],check_names=False,check_dtype=False)
 assert g.phase.isin(P).all() and g.phase_priority.eq(g.phase.map(P)).all()
 known=g.score.notna();assert g.loc[~known,['rank_STAGE_PVR','rank_WITHIN_PHASE']].isna().all().all()
 ordered=g[known].reset_index().sort_values(['phase_priority','score','sid'],ascending=[True,False,True]);assert ordered.rank_STAGE_PVR.tolist()==list(range(1,len(ordered)+1))
 for phase,t in g[known].groupby('phase'):
  t=t.reset_index().sort_values(['score','sid'],ascending=[False,True]);assert t.rank_WITHIN_PHASE.tolist()==list(range(1,len(t)+1))
 assert g.research_e0_target.eq(1).all() and g.research_e0_ready.eq(1).all()
 ref=g.reference_peak.notna();assert g.loc[ref,'reference_peak_confirmed'].le(g.loc[ref,'start_date']).all() and g.loc[ref,'start_date'].le(d).all()
 assert g.no_confirmed_peak_reference.eq(g.phase.eq('START')&g.reference_peak.isna()).all()
 assert g.loc[g.phase.eq('BREAKOUT'),'breakout_date'].notna().all()
 phases=g.phase.value_counts().to_dict();counts[d]={'N':len(g),'known_PVR':int(known.sum()),'unknown_PVR':int((~known).sum()),'phases':phases}
 assert receipt['by_date'][d]=={'N':len(g),'known_PVR':int(known.sum()),'phases':phases}
 for k in [20,100]:
  a=set(g[g.rank_ALL_LOCAL_I_BUY.le(k)].index);b=set(g[g.rank_STAGE_PVR.le(k)].index)
  assert len(a)==len(b)==min(k,int(known.sum()))
  swaps.append({'day':d,'topK':k,'original_N':len(a),'stage_N':len(b),'kept':len(a&b),'added':len(b-a),'dropped':len(a-b),'new_phase_counts':g.loc[list(b),'phase'].value_counts().to_dict()})
assert [counts[d]['N']for d in D]==[177,2313,779] and [counts[d]['unknown_PVR']for d in D]==[2,0,0]
# Validate saved labels are joined exactly, then recompute the small diagnostic tables.
x=pd.read_parquet(R/'STAGE_RANKS_WITH_EXISTING_PRICE_LABELS.parquet');assert x[KEY].duplicated().sum()==0
xi=x.set_index(KEY).sort_index();qi=q.set_index(KEY).sort_index();assert xi.index.equals(qi.index)
for c in q.columns:
 if c not in KEY:pd.testing.assert_series_equal(xi[c],qi[c],check_names=False,check_exact=True)
for d in D:
 hh=pd.read_parquet(paths[d]).set_index('sid').sort_index();g=xi.loc[d].sort_index();assert g.index.equals(hh.index)
 for c in hh.columns:
  if c.startswith(('h5_','h20_')):pd.testing.assert_series_equal(g[c],hh[c],check_names=False,check_exact=True)
 assert g[['h5_complete','h20_complete']].notna().all().all() and g.h5_complete.all() and g.h20_complete.all()
stat=pd.read_csv(R/'GROUP_COMPARISONS.csv',float_precision='round_trip');comp=pd.read_csv(R/'PHASE_COMPOSITION.csv');chg=pd.read_csv(R/'TOPK_MEMBERSHIP_CHANGES.csv',float_precision='round_trip');tails=pd.read_csv(R/'EXPOST_TAIL_LABELS_ONLY.csv');cases=pd.read_csv(R/'PREDECLARED_CASE_STAGE_AND_RANK.csv',float_precision='round_trip')
expected_stat={};expected_comp=[];expected_chg=set();expected_tails=set();stat_cells=0
for d,g in x.groupby('day'):
 n=len(g)
 for phase,f in g.groupby('phase'):
  expected_comp.append({'day':d,'phase':phase,'N':len(f),'known_PVR':int(f.score.notna().sum()),'original_top20':int(f.rank_ALL_LOCAL_I_BUY.le(20).sum()),'new_top20':int(f.rank_STAGE_PVR.le(20).sum()),'original_top100':int(f.rank_ALL_LOCAL_I_BUY.le(100).sum()),'new_top100':int(f.rank_STAGE_PVR.le(100).sum()),'no_reference':int(f.no_confirmed_peak_reference.sum())})
 for horizon in [5,20]:
  tailsets={p:set(g.sort_values([f'h{horizon}_return','sid'],ascending=[False,True]).head(math.ceil(n*p/100)).sid)for p in [1,5]}
  for p,ids in tailsets.items():expected_tails|={(d,horizon,p,sid)for sid in ids}
  for scheme,col in [('ORIGINAL_PVR','rank_ALL_LOCAL_I_BUY'),('STAGE_PVR','rank_STAGE_PVR')]:
   groups={'ALL':g,'RANKABLE':g[g[col].notna()],**{'PHASE_'+p:f for p,f in g.groupby('phase')}}
   for k in [20,100]:groups['TOP'+str(k)]=g[g[col].le(k)];groups['REST'+str(k)]=g[g[col].gt(k)]
   for band,f in groups.items():
    vals=f[f'h{horizon}_return'].tolist();key=(d,horizon,scheme,band)
    expected_stat[key]={'N':len(f),'terminal_mean':statistics.fmean(vals)if vals else np.nan,'terminal_median':statistics.median(vals)if vals else np.nan,'positive_fraction':sum(v>0 for v in vals)/len(vals)if vals else np.nan,'MFE_mean':statistics.fmean(f[f'h{horizon}_max_up'])if vals else np.nan,'MAE_mean':statistics.fmean(f[f'h{horizon}_max_adverse'])if vals else np.nan,'top1pct_hit':len(set(f.sid)&tailsets[1]),'top1pct_denominator':len(tailsets[1]),'top5pct_hit':len(set(f.sid)&tailsets[5]),'top5pct_denominator':len(tailsets[5])}
 for k in [20,100]:
  a=set(g.loc[g.rank_ALL_LOCAL_I_BUY.le(k),'sid']);b=set(g.loc[g.rank_STAGE_PVR.le(k),'sid'])
  for kind,ids in [('DROPPED',a-b),('ADDED',b-a),('KEPT',a&b)]:expected_chg|={(d,k,kind,sid)for sid in ids}
assert len(stat)==len(expected_stat)==108
for row in stat.to_dict('records'):
 key=tuple(row[k]for k in ['day','h','scheme','band']);v=expected_stat.pop(key)
 for k,b in v.items():close(row[k],b);stat_cells+=1
assert not expected_stat
pd.testing.assert_frame_equal(comp.sort_values(['day','phase']).reset_index(drop=True),pd.DataFrame(expected_comp).sort_values(['day','phase']).reset_index(drop=True))
assert set(chg[['day','comparison_topK','change','sid']].itertuples(index=False,name=None))==expected_chg and len(chg)==len(expected_chg)
assert set(tails[['day','h','tail_percent','sid']].itertuples(index=False,name=None))==expected_tails and len(tails)==len(expected_tails)
assert len(cases)==33 and set(cases.sid)==set(freeze['cases'])
for z in cases.itertuples(index=False):
 key=(z.day,z.sid);assert z.original_i_buy_member==(key in qi.index)
 for c in ['e0_ready','g_ready','i_target','i_buy','signal_status']:assert eq(getattr(z,c),rawframes[z.day].loc[z.sid,c])
 for c in ['rank_ALL_LOCAL_I_BUY','rank_STAGE_PVR','rank_WITHIN_PHASE']:
  assert eq(getattr(z,c),qi.loc[key,c]if key in qi.index else np.nan)
files=[R/'FREEZE.json',R/'SOURCE_BINDING.json',R/'research.py',R/'diagnose.py',R/'PILOT_RECEIPT.json',R/'GENERATION_RECEIPT.json',R/'RANK_FREEZE_RECEIPT.json',R/'DIAGNOSTIC_RECEIPT.json',R/'STAGED_PRIOR_RANKS.parquet',R/'ALL_REQUEST_STAGE_SNAPSHOTS.parquet',R/'STAGE_RANKS_WITH_EXISTING_PRICE_LABELS.parquet',R/'GROUP_COMPARISONS.csv',R/'PHASE_COMPOSITION.csv',R/'TOPK_MEMBERSHIP_CHANGES.csv',R/'PREDECLARED_CASE_STAGE_AND_RANK.csv',R/'EXPOST_TAIL_LABELS_ONLY.csv',Path(__file__)]+list(prior.values())+list(paths.values())+list(raw.values())+parts
out={'status':'PASS_BOUNDED_IMPLEMENTATION_SAVED_STAGES_RANKINGS_AND_EXISTING_LABEL_DIAGNOSTICS','remaining_blocks':[],'request_rows':3287,'exact_raw8_comparisons':3283,'missing_target_rows':4,'cohort_rows':len(q),'dates':counts,'topK_swaps':swaps,'all_diagnostic_rows':len(stat),'diagnostic_cells_checked':stat_cells,'tail_label_memberships':len(tails),'case_rows':len(cases),'source_code_observations':['Replay checks every eligible close before event and new ratchet; ready carries leg observation; not numeric.active.','Only -event records peak; +event freezes previously confirmed peak, no future peak/backfill. BREAKOUT latched until down/floor failure.','Stage generation and rank use no outcome file; diagnostic invocation first validates prior saved rank SHA.','Unknown PVR remains unranked; all177/2313/779 source prior fields and members unchanged.','Corrected diagnose case membership uses real cohort key set, not rank nonnull or a hard-coded exception.'],'limits':['Saved original8 state fields compare at requested dates, not an independent full E0/G1/I replay.','Four-stock numeric-only physical-prefix audit is separately pending and is not claimed here.','No new prices/labels or returns recomputed; existing previously reviewed paths are joined by exact sid/date.','Lexicographic phase priority is a finite-slot hard preference and may exclude START from topK.','No account/order/position/cash/fees/PIT/legal/executable/causal-alpha validation.'],'source_sha256':{str(p.resolve()):sha(p)for p in files},'new_full_signal_models':0,'new_accounts':0,'numeric_calls_in_this_script':0}
p=O/'OUTPUT_AUDIT.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':out['status'],'sha256':sha(p),'dates':counts,'topK_swaps':swaps,'diagnostic_rows':len(stat)},ensure_ascii=False))
