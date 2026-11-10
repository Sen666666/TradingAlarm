from pathlib import Path
import json
import pandas as pd,numpy as np
from model import r1_state
from legacy import context,compare
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';S=R.parent/'market-regimes-exit-20261024/inputs'
def synthetic():
 idx=pd.bdate_range('2024-01-01',periods=10);d=pd.DataFrame({'close':[100,105,101,103,104,106,100,105,100,108]},index=idx);base=pd.DataFrame({'target':[1]*8+[0,1],'entered':[0]*9+[1],'floor':[90]*5+[92,92,93,np.nan,89]},index=idx);f=pd.DataFrame({'atr':.01},index=idx)
 e=pd.DataFrame({'event':0,'confirmed_pivot_date':'','confirmed_pivot_price':np.nan,'confirmation':np.nan},index=idx)
 for i,j,px in [(2,1,90),(3,1,90),(4,3,90),(5,3,92),(7,4,93),(9,8,89)]:e.loc[idx[i],['event','confirmed_pivot_date','confirmed_pivot_price','confirmation']]=[1,str(idx[j].date()),px,1.1]
 s,_=r1_state(d,e,base,f,str(idx[1].date()),str(idx[-1].date()))
 assert s.loc[idx[2],'exited']==1 and s.loc[idx[2],'entered']==0
 assert s.loc[idx[3],'recovery_rejection']=='trough_not_after_exit_signal'
 assert s.loc[idx[4],'recovery_rejection']=='trough_not_higher_than_exit_support'
 assert s.loc[idx[5],'entry_kind']=='higher_trough_reentry' and s.loc[idx[5],'floor']==92
 assert s.loc[idx[6],'exited']==1 and s.loc[idx[6],'recovery_anchor_floor']==92
 assert s.loc[idx[7],'recovery_rejection']=='trough_not_after_exit_signal'
 assert s.loc[idx[8],'recovery_armed']==0
 assert s.loc[idx[9],'entry_kind']=='E0_new_cycle' and s.loc[idx[9],'floor']==89
 return ['same_day_exit_priority','stale_trough_rejected','equal_support_rejected','fresh_higher_trough_accepted','repeated_exit_new_anchor','consumed_pivot_not_reused','E0_invalid_clears_memory','new_E0_cycle_unblocked']
def main():
 small=synthetic();checks=[];recoveries=0;cases=json.loads((R/'cases.json').read_text())
 for sym in sorted({c['symbol'] for c in cases}):
  d=pd.read_parquet(S/f'{sym}.parquet');e,b,f=context(d)
  for c in [x for x in cases if x['symbol']==sym]:
   full=pd.read_parquet(R/'prepared'/c['id']/'R1.parquet');z=d.loc[c['start']:c['end']]
   for n in [len(z)//3,2*len(z)//3,len(z)-1]:
    sub=d.loc[:z.index[n-1]];ee,bb,ff=context(sub);s,_=r1_state(sub,ee,bb,ff,c['start'],str(z.index[n-1].date()));pd.testing.assert_frame_equal(s,full.loc[s.index],check_exact=True);checks.append(dict(case=c['id'],prefix=str(z.index[n-1].date()),passed=True))
   for dt,x in full.loc[full.recovery_entry.astype(bool)].iterrows():
    assert b.loc[dt,'target']==1 and b.loc[dt,'entered']==0 and e.loc[dt,'event']==1
    assert pd.Timestamp(x.confirmed_pivot_date)>pd.Timestamp(x.recovery_exit_signal) and pd.Timestamp(x.confirmed_pivot_date)<dt
    assert compare(x.confirmed_pivot_price,x.recovery_anchor_floor)>0 and compare(max(x.confirmation,0),1)>=0
    assert x.entered==1 and not x.exited;recoveries+=1
  print('prefix_checked',sym,flush=True)
 pd.DataFrame(checks).to_csv(R/'prefix-checks.csv',index=False);ab=pd.read_csv(R/'mechanism/volume-confirmation-ablation.csv')
 report=dict(passed=True,exact_prefix_checks=len(checks),old_R_daily_identity_cases=18,synthetic_economic_checks=small,all_recovery_conditions_checked=recoveries,volume_ablation_changed_recovery_days=int(ab.changed_recovery_days.sum()),volume_ablation_changed_state_days=int(ab.changed_state_days.sum()),new_signal_accounts_run=0)
 (R/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
