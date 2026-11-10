
from pathlib import Path
import json
import numpy as np,pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sm={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
raw={x['series_id']:x['raw']['path']for x in json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json').read_text())['series']}
a=pd.read_parquet(O/'EMPTY_MOBILE_SIGNAL_GATE.parquet');start=a[~a.source_i_buy].copy()
h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
dates=pd.DatetimeIndex(h['dates']);dates=dates[(dates>='2022-01-01')&(dates<='2026-05-15')];calendar={d:i for i,d in enumerate(dates)}
legal=set(zip(a.account,a.sid,a.day));rows=[]
def ds(x):return str(x.date())
for gi,(sid,g) in enumerate(start.groupby('sid')):
 f=pd.read_parquet(sm[sid]['refs']['facts']);cp=pd.read_parquet(sm[sid]['refs']['CP1']).reindex(f.index)
 b=pd.read_parquet(raw[sid]);b.index=pd.to_datetime(b.trade_date)
 close=f.close.to_numpy(float);valid=f.i_target.eq(True).to_numpy();seg=f.segment_id.to_numpy();ib=f.i_buy.eq(True).to_numpy();rec=cp.receipt.fillna(False).to_numpy(bool);cand=cp.candidate.to_numpy(float)
 ix=f.index;end=int(ix.searchsorted(dates[-1],side='right'))
 def nxt_open(d):
  if d not in calendar or calendar[d]+1>=len(dates):return (None,np.nan,np.nan)
  nd=dates[calendar[d]+1]
  if nd not in b.index or nd not in f.index:return(ds(nd),np.nan,np.nan)
  return ds(nd),float(b.at[nd,'open'])*float(f.at[nd,'factor']),float(b.at[nd,'open'])
 for q in g.itertuples():
  t=int(ix.get_loc(pd.Timestamp(q.day)));R=close[t];L=cand[t];k=0
  z=dict(account=q.account,sid=sid,year=q.year,signal_day=q.day,original_next_day=q.entry_day,original_open_native=q.entry_adjusted_open,initial_CP1_id=q.CP1_id)
  first_new=False;first_struct=False;first_legal=False;first_and=False;termination='right_censored';terminal_day=ds(ix[end-1])
  for j in range(t+1,end):
   d=ix[j];day=ds(d)
   if seg[j]!=seg[t] or not valid[j] or close[j]<=L:
    termination='segment_change'if seg[j]!=seg[t]else('I_invalid'if not valid[j]else'baseline_floor_broken');terminal_day=day;break
   k=k+1 if close[j]>R else 0
   if not rec[j]:continue
   present=(q.account,sid,day)in legal
   nd,no,nr=nxt_open(d);delta=no/q.entry_adjusted_open-1 if np.isfinite(no)else np.nan
   base=dict(day=day,wait_observations=j-t,wait_common=calendar.get(d,np.nan)-calendar[pd.Timestamp(q.day)],k=k,i_buy=bool(ib[j]),legal=bool(present),next_day=nd,next_open_native=no,next_raw_open=nr,price_change_from_original_open=delta)
   if not first_new:
    z.update({'second_'+v:x for v,x in base.items()});first_new=True
   if k>=2 and not first_struct:
    z.update({'strict_structure_'+v:x for v,x in base.items()});first_struct=True
   if k>=2 and present and not first_legal:
    z.update({'strict_legal_'+v:x for v,x in base.items()});first_legal=True
   if ib[j]and present and not first_and:
    z.update({'AND_legal_'+v:x for v,x in base.items()});first_and=True
   # Current new certificate always updates evidence baseline; no expired order retained.
   R=close[j];L=cand[j];k=0
   if first_legal and first_and:
    termination='both_reachable';terminal_day=day;break
  z.update(termination=termination,terminal_day=terminal_day);rows.append(z)
 if gi%200==0:print('sid groups',gi,'rows',len(rows),flush=True)
r=pd.DataFrame(rows);r.to_csv(O/'STRICT_REACHABILITY_ALL_FALSE_CANDIDATES.csv',index=False)
stats=[]
for(a0,y),g in r.groupby(['account','year']):
 ok=g.strict_legal_day.notna();false=g.strict_legal_i_buy.eq(False)&ok
 stats.append(dict(account=a0,year=y,original_false_candidates=len(g),second_exists=int(g.second_day.notna().sum()),second_i_buy_still_false=int((g.second_i_buy.eq(False)&g.second_day.notna()).sum()),second_k_ge2=int(g.second_k.ge(2).sum()),strict_structure_exists=int(g.strict_structure_day.notna().sum()),strict_legal_reached=int(ok.sum()),strict_legal_still_false=int(false.sum()),strict_legal_already_true=int((ok&g.strict_legal_i_buy.eq(True)).sum()),strict_legal_false_unique_events=len(g.loc[false,['sid','strict_legal_day']].drop_duplicates()),strict_legal_median_wait=float(g.loc[ok,'strict_legal_wait_observations'].median()),strict_legal_median_price_cost=float(g.loc[ok,'strict_legal_price_change_from_original_open'].median()),AND_legal_reached=int(g.AND_legal_day.notna().sum()),never_second_before_invalidation=int((g.second_day.isna()&g.termination.ne('right_censored')).sum()),right_censored=int(g.termination.eq('right_censored').sum())))
pd.DataFrame(stats).to_csv(O/'STRICT_REACHABILITY_BY_YEAR.csv',index=False)
actual=pd.read_csv(O/'ACTUAL_FIRST_MOBILE_GATE_ATTRIBUTION.csv');actual=actual[(actual.account=='PVR')&~actual.accepted]
actual=actual.merge(r,on=['account','sid','signal_day','year'],how='left',validate='1:1');actual.to_csv(O/'STRICT_REACHABILITY_ACTUAL_FALSE_FIRST.csv',index=False)
z=actual.copy();print('PVR ALL CANDIDATES');print(pd.DataFrame(stats).query("account=='PVR'").to_string(index=False))
print('ACTUAL:');print(z.groupby('year').agg(n=('sid','size'),second=('second_day','count'),strict_legal=('strict_legal_day','count'),strict_legal_still_false=('strict_legal_i_buy',lambda x:x.eq(False).sum()),median_delay=('strict_legal_wait_observations','median'),median_price_cost=('strict_legal_price_change_from_original_open','median')).to_string())
