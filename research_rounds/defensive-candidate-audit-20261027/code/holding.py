from pathlib import Path
import pandas as pd,numpy as np,json
O=Path(__file__).resolve().parents[1];R=O.parents[1];P=R/'research_rounds/tech-finite-compound-20261026/prepared-v2/signals';F=R/'research_rounds/e0-reclaim-accounts-20261026/prepared/facts'
x=pd.read_csv(O/'results/candidate-observations.csv');x=x[x.first_in_phase].copy();out=O/'holding';out.mkdir(exist_ok=False);rr=[]
for sid,z in x.groupby('symbol'):
 f=pd.read_parquet(P/f'{sid}.parquet');f=f[f.price_eligible & f.is_observed_bar & ~f.synthetic_event_bar];facts=pd.read_parquet(F/f'{sid}.parquet').reindex(f.index)
 for row in z.to_dict('records'):
  day=pd.Timestamp(row['date']);i=f.index.searchsorted(day,side='right');k=i-1;row['status']='incomplete';row['holding_return']=np.nan
  if k<0 or i>=len(f):rr.append(row);continue
  floor=facts.i_floor.iloc[k]
  if not np.isfinite(floor) or f.open.iloc[i]<=floor:row['status']='entry_protection_reject';rr.append(row);continue
  bad=np.flatnonzero(~facts.i_target.iloc[i:].fillna(False).astype(bool).to_numpy());j=i+bad[0]+1 if len(bad) else len(f)
  end=min(j,len(f)-1)
  if f.segment_id.iloc[k:end+1].nunique()!=1:row['status']='segment_gap';rr.append(row);continue
  row['entry_date']=str(f.index[i].date());row['exit_or_mark_date']=str(f.index[end].date());row['status']='closed' if j<len(f) else 'open'
  row['holding_return']=float((f.open.iloc[j] if j<len(f) else f.close.iloc[-1])/f.open.iloc[i]-1);rr.append(row)
y=pd.DataFrame(rr);y.to_csv(out/'paths.csv',index=False);summ=[]
for (aid,phase,period),g in y.groupby(['account','phase','period']):
 c=g[g.status=='closed'].holding_return;o=g[g.status=='open'].holding_return
 summ.append(dict(account=aid,phase=phase,period=period,candidates=len(g),closed=len(c),open=len(o),entry_reject=int(g.status.eq('entry_protection_reject').sum()),mean_closed=c.mean(),median_closed=c.median(),positive_closed=c.gt(0).mean(),tail_count=int(c.ge(.3).sum()),tail_return_sum=c[c.ge(.3)].sum(),ordinary_return_sum=c[c.lt(.3)].sum(),all_negative_sum=-c[c.lt(0)].sum(),open_mean=o.mean()))
s=pd.DataFrame(summ);s.to_csv(out/'summary.csv',index=False);print(s[(s.account=='I__S0_base')&(s.phase=='defensive')].to_string(index=False));(O/'holding-receipt.json').write_text(json.dumps({'rows':len(y),'economic_accounts':0,'missing_kept':True,'overlap_possible':True},indent=2))
