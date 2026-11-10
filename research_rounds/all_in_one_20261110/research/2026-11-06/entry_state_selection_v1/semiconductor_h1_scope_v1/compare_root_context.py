"""Describe pre-outcome first-CP context only. No fitting, thresholds or strategy."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;M=Path('/Users/bytedance/Documents/ChatGPT/money');P=Path(json.load(open(M/'TradingAlarm/runtime/market/current.json'))['path']);W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
rr=pd.read_csv(O/'ALL_ROOTS_EXPLAINED.csv');d=pd.read_parquet(O/'ENRICHED_DAILY.parquet');d=d.set_index(['sid','day']);srec=next(x for x in json.load(open(W/'INDUSTRY_MANIFEST.json')) if x['series']=='URFI881121');sec=pd.read_parquet(srec['refs']['state']);sec=sec.set_index(pd.DatetimeIndex(sec.day));sec['past20_return']=sec.close/sec.close.shift(20)-1;sec['prior_close_stage']=sec.stage.shift();sec['prior_close_E0']=sec.E0_valid.shift();sec['prior_close_return20']=sec.past20_return.shift();cal=sec.index;stocks={};rows=[]
for r in rr[rr.cohort.isin(['born_Q1','born_Q2'])&rr.old_first.notna()].to_dict('records'):
 sid=r['sid'];day=r['old_first'];dt=pd.Timestamp(day);start=pd.Timestamp(r['I_root']);n=cal.get_loc(dt);anchor=cal[n-20] if n>=20 else None;sr=sec.loc[dt]
 if sid not in stocks:stocks[sid]=pd.read_parquet(P/'signals'/(sid+'.parquet')).loc[:'2026-06-30']
 pr=stocks[sid];row=d.loc[(sid,day)];ret20=float(pr.loc[dt,'close']/pr.loc[anchor,'close']-1) if anchor in pr.index else np.nan;sectorret=float(sr.past20_return);secroot=float(sr.close/sec.loc[start,'close']-1);rootmove=r['old_move_already']
 rows.append(dict(sid=sid,name=r['name'],I_root=r['I_root'],cohort=r['cohort'],first_CP=day,CP_calendar_quarter=str(dt.to_period('Q')),PVR_score=row.PVR_score,CP_lag_observations=r['old_lag'],stock_gain_since_I_root=rootmove,sector_gain_since_stock_I_root=secroot,relative_gain_since_I_root=(1+rootmove)/(1+secroot)-1,sector_E0_at_CP_close=sr.E0_valid,sector_stage_at_CP_close=int(sr.stage),sector_authorization_at_CP_close=sr.authorization_usable,sector_stage_prior_close=int(sr.prior_close_stage),sector_E0_prior_close=bool(sr.prior_close_E0),past20_anchor=str(anchor.date()) if anchor is not None else None,stock_past20_return=ret20,sector_past20_return=sectorret,relative_past20_return=(1+ret20)/(1+sectorret)-1,sector_past20_return_prior_close=sr.prior_close_return20,complete_forward_common20=bool(r.get('old_common20')==True),forward_common20_return=r.get('old_common20_return')))
f=pd.DataFrame(rows);f.to_csv(O/'FIRST_CP_PRE_OUTCOME_CONTEXT.csv',index=False)
metrics=['PVR_score','CP_lag_observations','stock_gain_since_I_root','sector_gain_since_stock_I_root','relative_gain_since_I_root','stock_past20_return','sector_past20_return','relative_past20_return','sector_past20_return_prior_close']
def dist(x):
 x=x.dropna();return dict(n=len(x),p25=float(x.quantile(.25)),median=float(x.median()),p75=float(x.quantile(.75)))
result=[]
for domain in ['all_first_CP','complete_forward_common20']:
 a=f if domain=='all_first_CP' else f[f.complete_forward_common20]
 for cohort,g in a.groupby('cohort'):
  result.append(dict(domain=domain,cohort=cohort,roots=len(g),stocks=g.sid.nunique(),CP_calendar_quarters=g.CP_calendar_quarter.value_counts().to_dict(),sector_stage_at_close=g.sector_stage_at_CP_close.value_counts().sort_index().to_dict(),sector_stage_prior_close=g.sector_stage_prior_close.value_counts().sort_index().to_dict(),sector_E0_true_at_close=int(g.sector_E0_at_CP_close.sum()),sector_authorized_at_close=int(g.sector_authorization_at_CP_close.sum()),distribution={m:dist(g[m]) for m in metrics}))
summary={'clock':'All values known by first stock CP date close, before future path. Explicit prior-close industry stages/returns also included. Stage at CLOSE must not be described as known before OPEN. Stock/sector past20 uses exact common-calendar anchor, missing anchor UNKNOWN. Relative return=(stock gross return)/(sector gross return)-1. Original I roots selected independently of future price; complete20 subset is descriptive maturity/coverage control, not eligibility.', 'not_strategy':'No thresholds, fitting, winner selection, financial simulation or causal claim about quarterly effects. Same-stock roots and forward windows overlap.', 'results':result}
(O/'FIRST_CP_CONTEXT_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False));print(json.dumps(summary,ensure_ascii=False,indent=2))
