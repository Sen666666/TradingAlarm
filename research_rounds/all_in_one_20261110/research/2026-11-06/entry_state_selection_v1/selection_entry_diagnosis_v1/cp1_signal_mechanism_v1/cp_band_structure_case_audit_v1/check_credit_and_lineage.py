
from pathlib import Path
import pandas as pd,numpy as np,json,math
O=Path(__file__).resolve().parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
manifest={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
summary=pd.read_csv(O/'SIGNAL_SUMMARY.csv');events=pd.read_csv(O/'FULL_PREFIX_STRUCTURAL_EVENTS.csv',parse_dates=['day'])
checks=[];lineage=[]
for sid,g in summary.groupby('sid'):
 f=pd.read_parquet(manifest[sid]['refs']['facts']);cp=pd.read_parquet(manifest[sid]['refs']['CP1'])
 upper=pd.Series(np.nan,index=f.index)
 for _,b in f.groupby('segment_id',sort=False):
  upper.loc[b.index]=(b.close.rolling(21).mean()+2*b.close.rolling(21).std(ddof=0)).shift(1)
 K=Kin=Kout=0.;oldseg=None;maxerr=0.;partmax=0.;n=0;receipts=0
 published=events[events.sid==sid].set_index('day')
 for j,(day,c)in enumerate(cp.iterrows()):
  seg=f.segment_id.iloc[j];reason='' if pd.isna(c.reset_reason)else str(c.reset_reason)
  if seg!=oldseg or reason in ['unprepared','E0_invalid','start','E0_down_reset','lower_anchor','source_reset']:K=Kin=Kout=0.;oldseg=seg
  delta=float(c.delta_frontier)
  if delta>0:
   p=math.log(float(f.close.iloc[j]));a=p-delta;b=math.log(float(upper.iloc[j]));m=float(c.m)
   increment=m*delta
   incin=m*max(0.,min(p,b)-a);incout=m*max(0.,p-max(a,b))
   partmax=max(partmax,abs(increment-incin-incout));assert abs(increment-incin-incout)<1e-12
   K=math.fsum((K,increment));Kin=math.fsum((Kin,incin));Kout=math.fsum((Kout,incout))
  actual=float(c.credit)
  if math.isfinite(actual):
   maxerr=max(maxerr,abs(actual-K),abs(actual-Kin-Kout));assert abs(actual-K)<1e-10 and abs(actual-Kin-Kout)<1e-10
  if bool(c.receipt):
   receipts+=1;pp=published.loc[day];assert abs(Kout-float(pp.outside_credit))<1e-10
   assert abs(Kout/K-float(pp.q))<1e-10
   K=Kin=Kout=0.
  n+=1
 checks.append(dict(sid=sid,source_observations=n,source_receipts=receipts,max_original_credit_reconstruction_error=maxerr,max_increment_partition_error=partmax,receipt_numerator_matches=True))
 ze=events[(events.sid==sid)&events.new_expansion_now.eq(True)&events.day.le('2026-05-15')]
 for q in g.itertuples():
  d=pd.Timestamp(q.signal_day);past=ze[ze.day<=d];future=ze[ze.day>d]
  base=f.index.get_loc(d)
  nextday=future.day.iloc[0]if len(future)else pd.NaT
  prevday=past.day.iloc[-1]if len(past)else pd.NaT
  active_break=pd.Timestamp(q.last_breach_day)if q.state_after_floor_check=='REPAIR'else pd.NaT
  lineage.append(dict(sid=sid,signal_day=q.signal_day,state_before=q.state_before,active_repair_from=str(active_break.date())if pd.notna(active_break)else None,active_repair_observations=(base-f.index.get_loc(active_break))if pd.notna(active_break)else 0,last_expansion_at_or_before_signal=str(prevday.date())if pd.notna(prevday)else None,next_expansion_after_signal=str(nextday.date())if pd.notna(nextday)else None,next_expansion_wait_observations=f.index.get_loc(nextday)-base if pd.notna(nextday)else None,next_expansion_signal_close_vs_case_signal=float(f.at[nextday,'close']/f.at[d,'close']-1)if pd.notna(nextday)else None,next_expansion_is_afterward_description_not_entry_knowledge=True))
pd.DataFrame(checks).to_csv(O/'INDEPENDENT_CREDIT_PARTITION_CHECKS.csv',index=False)
pd.DataFrame(lineage).to_csv(O/'STRUCTURAL_EVENT_LINEAGE.csv',index=False)
print(pd.DataFrame(checks).to_string(index=False));print(pd.DataFrame(lineage).to_string(index=False))
