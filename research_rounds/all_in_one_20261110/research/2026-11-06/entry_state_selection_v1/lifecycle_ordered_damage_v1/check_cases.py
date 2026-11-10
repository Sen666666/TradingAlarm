"""Frozen ordered path-state audit. No trading/account imports or native signal rerun."""
from pathlib import Path
import json, math, hashlib
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent
R=O.parent
B=R/'selection_entry_diagnosis_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
END='2026-05-15';rho=20/21;floor=math.log1p(.001)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
manifest={r['symbol']:r for r in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(HP,allow_pickle=False)['dates']);ci={d:i for i,d in enumerate(cal)}
first=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');first=first[first.account.eq('PVR')].copy()
cs=[]
for y,g in first[first.closed].groupby('year'):
 for kind,r in [('annual_worst',g.sort_values('round_pnl').iloc[0]),('annual_best',g.sort_values('round_pnl').iloc[-1])]:
  cs.append(dict(sid=r.sid,day=r.signal_day,selection=kind,entry_year=int(y),original_round_pnl=float(r.round_pnl),original_role=r.first_kind,entry_day=r.entry_day))
for sid,day in [('600056.SH','2022-03-30'),('002317.SZ','2022-10-14'),('300182.SZ','2022-01-04'),('002385.SZ','2022-03-04'),('600606.SH','2022-03-22'),('688582.SH','2024-07-29'),('300085.SZ','2024-09-19'),('300085.SZ','2024-10-09'),('002583.SZ','2024-09-19')]:
 r=first[first.sid.eq(sid)&first.signal_day.eq(day)]
 cs.append(dict(sid=sid,day=day,selection='fixed_prior_counterexample' if len(r) else 'fixed_signal_path_not_original_fill',entry_year=int(day[:4]),original_round_pnl=float(r.iloc[0].round_pnl)if len(r)and r.iloc[0].closed else None,original_role=r.iloc[0].first_kind if len(r)else None,entry_day=r.iloc[0].entry_day if len(r)else None))
dump('FIXED_CASES_BEFORE_COMPUTE.json',cs)
sources={str(p):sha(p) for p in [M,HP,B/'ALL_FIRST_ENTRIES.csv',O/'PROTOCOL.json',Path(__file__)]}
def calculate(f,cp):
 rows=[];U=0.;H=0.;hist=[];seg=None;prevday=None;prevp=None;nknown=0
 for day,row in f.iterrows():
  p=math.log(float(row.close));gap=(prevday is not None and (day not in ci or prevday not in ci or ci[day]!=ci[prevday]+1))
  reset=seg is None or row.segment_id!=seg or gap
  if reset:U=0.;H=0.;hist=[];prevp=None;nknown=0
  s=math.sqrt(float(np.mean(np.square(hist[-63:]))))if len(hist)>=63 else math.nan
  if math.isfinite(s):s=max(s,floor)
  r=p-prevp if prevp is not None else math.nan;oldU=U;oldH=H
  a=oldU/(oldU+math.sqrt(21)*s)if math.isfinite(s) else math.nan
  shock=a*(max(-r,0.)/s)**2 if math.isfinite(s)and math.isfinite(r)else math.nan
  if math.isfinite(r):
   U=max(0.,rho*U+r);hist.append(r)
   if math.isfinite(shock):H=rho*H+(1-rho)*shock;nknown+=1
  health=1/(1+H)if math.isfinite(shock)else math.nan
  cr=cp.loc[day]
  out=dict(day=day,raw_close=float(row.raw_close),close=float(row.close),r=r,sigma=s,advance_before=oldU,advance_after=U,advance_fraction=a,damage_before=oldH,downshock=shock,damage=H if math.isfinite(shock)else math.nan,health=health,fresh_weight=health*(1-a),established_weight=health*a,damaged_weight=1-health,observations_scale_known=nknown,fully_warmed=nknown>=63,source_reset=reset,common_gap_reset=gap,native_i=bool(row.i_target),native_i_buy=bool(row.i_buy),native_e0=bool(row.e0_target),native_ready=bool(row.e0_ready and row.g_ready),cp_receipt=bool(cr.receipt),cp_phase=str(cr.phase),cp_reset=str(cr.reset_reason),cp_candidate=float(cr.candidate),i_floor=float(row.i_floor),factor=float(row.factor))
  rows.append(out);seg=row.segment_id;prevday=day;prevp=p
 return pd.DataFrame(rows).set_index('day')
allstates=[];windows=[];summ=[];checks=[];data={}
for sid in sorted({r['sid'] for r in cs}):
 refs=manifest[sid]['refs'];f=pd.read_parquet(refs['facts']).loc[:END];cp=pd.read_parquet(refs['CP1']).loc[f.index]
 p=[p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet')][0]
 prices=pd.read_parquet(p).reindex(f.index)
 assert np.max(np.abs(prices.close-f.close))<1e-7
 for path in [refs['facts'],refs['CP1'],p]:sources[path]=sha(path)
 z=calculate(f,cp);z['sid']=sid;allstates.append(z.reset_index());data[sid]=(f,cp,z,prices)
 for ca in [r for r in cs if r['sid']==sid]:
  t=pd.Timestamp(ca['day']);ix=z.index.get_loc(t);out=ca|z.loc[t].to_dict();out['b_per_1200000_before_debt']=1200*out['health'];out['next_common_day']=str(cal[ci[t]+1].date())
  nd=cal[ci[t]+1];full=prices.reindex(cal)
  out['next_open']=float(full.loc[nd,'open']);out['next_open_raw']=out['next_open']/float(f.reindex(cal).loc[nd,'factor']);out['next_gap']=out['next_open']/float(f.loc[t,'close'])-1
  for h in [5,20,60]:
   endpos=ci[t]+h;days=cal[ci[t]+1:endpos+1];q=full.reindex(days);ok=len(q)==h and np.isfinite(q.close).all() and np.isfinite(out['next_open']) and out['next_open']>0 and endpos<len(cal) and str(days[-1].date())<=END
   out['ret'+str(h)]=float(q.close.iloc[-1]/out['next_open']-1)if ok else None
   out['mfe'+str(h)]=float(max(0,q.close.max()/out['next_open']-1))if ok else None
   out['mae'+str(h)]=float(min(0,q.close.min()/out['next_open']-1))if ok else None
  summ.append(out)
  lo=max(0,ix-20);hi=min(len(z),ix+11);w=z.iloc[lo:hi].copy();w['case_signal']=ca['day'];w['relative_observation']=np.arange(lo,hi)-ix;windows.append(w.reset_index())
  for cutoff in [ix,ix+1]:
   part=calculate(f.iloc[:cutoff],cp.iloc[:cutoff]);pd.testing.assert_frame_equal(part,z.iloc[:cutoff].drop(columns='sid'),check_exact=True);checks.append(dict(sid=sid,case_day=ca['day'],prefix_length=cutoff,pass_prefix=True))
# Closed-round label only for observed original selection. No simulation or score cutoff.
pd.DataFrame(summ).to_csv(O/'CASE_SUMMARY.csv',index=False)
pd.concat(windows,ignore_index=True).to_csv(O/'CASE_DAILY_PATHS.csv',index=False)
pd.concat(allstates,ignore_index=True).to_csv(O/'FULL_PREFIX_STATES.csv',index=False)
pd.DataFrame(checks).to_csv(O/'PREFIX_CHECKS.csv',index=False)
for p,h in sources.items():assert sha(p)==h
allz=pd.concat(allstates,ignore_index=True);k=allz.health.notna();err=float((allz.loc[k,['fresh_weight','established_weight','damaged_weight']].sum(axis=1)-1).abs().max());assert err<1e-12
assert allz.loc[k,'health'].between(0,1).all()
dump('SOURCE_HASHES.json',sources)
dump('CHECKS.json',dict(cases=len(cs),stocks=len(data),rows=len(allz),prefix_checks=len(checks),prefix_all_pass=True,max_weight_sum_error=err,sources_unchanged=True,accounts_run=0,native_models_rerun=0,parameter_searches=0,case_outcomes_preknown=True,fully_warmed_cases=sum(bool(r['fully_warmed'])for r in summ)))
print(pd.DataFrame(summ)[['sid','day','selection','original_round_pnl','health','advance_fraction','damage','b_per_1200000_before_debt','native_i_buy','cp_receipt','ret20','mfe20']].round(6).to_string(index=False))
print('CHECKS',json.loads((O/'CHECKS.json').read_text()))
