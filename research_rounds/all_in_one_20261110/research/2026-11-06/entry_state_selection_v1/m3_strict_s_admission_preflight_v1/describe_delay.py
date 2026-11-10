"""Frozen descriptive successor lookup AFTER signal seal; no executable waiting, no PnL."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,pd.Timestamp):return x.date().isoformat()
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,float) and not np.isfinite(x):return None
 return x

def main():
 seal=json.loads((O/'SIGNAL_SEAL.json').read_text())
 for name,h in seal['outputs'].items():assert sha(O/name)==h,(name,'signal seal drift')
 contract=json.loads((O/'DELAY_REPORT_FREEZE.json').read_text());assert sha(Path(__file__))==contract['script_sha256']
 assert not (O/'DELAY_OUTPUT_SEAL.json').exists()
 e=pd.read_parquet(O/'ALL_MARKET_EVENTS.parquet');rows=[]
 fc=json.loads((O/'FEATURES_COMPLETE.json').read_text())
 for sid,g in e[e.B0_feasible&~e.B1_feasible].groupby('sid'):
  p=O/'features'/(sid+'.parquet');assert sha(p)==fc['outputs'][p.name]
  z=pd.read_parquet(p).set_index('day');allg=e[e.sid.eq(sid)].sort_values('day')
  for r in g.itertuples():
   future=z[z.index>r.day];boundary=future[(~future.i_target.eq(True))|future.I_root_serial.ne(r.I_root_serial)]
   stop=boundary.index[0] if len(boundary) else None
   # Missing/unknown I terminates known same-root scope rather than claiming continuity.
   within=future if stop is None else future[future.index<stop]
   s=within[within.S15_strict_state.eq(1)]
   a=dict(event_id=r.event_id,sid=sid,day=r.day,sector=r.sector,event_type=r.event_type,B0_top2=r.B0_top2,B1_gate=r.B1_gate,I_root_serial=r.I_root_serial,same_root_boundary_day=stop,same_root_boundary_state=None if stop is None else str(future.loc[stop,'i_target']),same_root_scope_end='RIGHT_CENSORED_AT_RESEARCH_END' if stop is None else 'I_OFF_CHANGED_OR_UNKNOWN')
   def capture(label,dates):
    d=dates[0] if len(dates) else None;a[label+'_day']=d
    a[label+'_common_delay']=None if d is None else int(z.index.get_loc(d)-z.index.get_loc(r.day))
    a[label+'_close_change']=None if d is None else float(z.loc[d,'close']/z.loc[r.day,'close']-1)
   capture('first_S15_true_same_I',s.index)
   for arm in ['B0','B1']:
    for level in ['feasible','top2']:
     q=allg[(allg.day>r.day)&allg[arm+'_'+level]]
     capture('next_'+arm+'_'+level+'_any_I',pd.DatetimeIndex(q.day))
     q=q[q.I_root_serial.eq(r.I_root_serial)]
     if stop is not None:q=q[q.day<stop]
     capture('next_'+arm+'_'+level+'_same_I',pd.DatetimeIndex(q.day))
   a['S_matures_but_no_same_root_B1_top2']=a['first_S15_true_same_I_day'] is not None and a['next_B1_top2_same_I_day'] is None
   rows.append(a)
 d=pd.DataFrame(rows)
 if d.empty:d=pd.DataFrame(columns=['sector','event_type','B0_top2','first_S15_true_same_I_day','next_B1_feasible_same_I_day','next_B1_top2_same_I_day','S_matures_but_no_same_root_B1_top2','same_root_scope_end','first_S15_true_same_I_common_delay','next_B1_top2_same_I_common_delay'])
 d.to_csv(O/'REJECTED_TICKET_SUCCESSORS.csv',index=False)
 groups=[]
 for keys in [[],['sector'],['event_type']]:
  iterator=[((),d)] if not keys else d.groupby(keys,dropna=False)
  for key,g in iterator:
   key=key if isinstance(key,tuple) else (key,);a=dict(zip(keys,key));a['grouping']='|'.join(keys) or 'ALL'
   a.update(rejected_feasible_tickets=len(g),B0_top2=int(g.B0_top2.sum()),first_S_later_same_I=int(g.first_S15_true_same_I_day.notna().sum()),next_B1_feasible_same_I=int(g.next_B1_feasible_same_I_day.notna().sum()),next_B1_top2_same_I=int(g.next_B1_top2_same_I_day.notna().sum()),S_matures_without_new_top2=int(g.S_matures_but_no_same_root_B1_top2.sum()),right_censored_I=int(g.same_root_scope_end.eq('RIGHT_CENSORED_AT_RESEARCH_END').sum()))
   for col in ['first_S15_true_same_I_common_delay','next_B1_top2_same_I_common_delay']:
    a[col+'_n']=int(g[col].notna().sum());a[col+'_median']=float(g[col].median()) if g[col].notna().any() else None
   groups.append(a)
 pd.DataFrame(groups).to_csv(O/'DELAY_SUMMARY.csv',index=False)
 out=dict(signal_seal_hash=sha(O/'SIGNAL_SEAL.json'),report_freeze_hash=sha(O/'DELAY_REPORT_FREEZE.json'),outputs={n:sha(O/n) for n in ['REJECTED_TICKET_SUCCESSORS.csv','DELAY_SUMMARY.csv']},no_orders=True,no_waiting_permission=True,no_pnl=True,close_ratios_are_descriptive_only=True)
 (O/'DELAY_OUTPUT_SEAL.json').write_text(json.dumps(clean(out),ensure_ascii=False,indent=2)+'\n')
 print(pd.DataFrame(groups).query("grouping=='ALL'").to_string(index=False))
if __name__=='__main__':main()
