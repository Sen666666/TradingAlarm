import pandas as pd,numpy as np
from common import *
from engine import backtest

def verify():
 f=read(HERE/'freeze.json')
 for p,h in f['sha256'].items():assert sha(p)==h,p
 return f

def main():
 verify();out=HERE/'results/v0';out.mkdir(parents=True,exist_ok=False);(out/'accounts').mkdir();rows=[];identity=[];cases=read(HERE/'cases.json')
 oldsummary=pd.read_csv(OLD/'results/v0/summary.csv')
 for c in cases:
  d=pd.read_parquet(HERE/'inputs'/(c['symbol']+'.parquet')).loc[c['start']:c['end']];init=read(HERE/'prepared'/c['id']/'initial.json')
  # Technical compatibility replays only, never used to replace old controls.
  oldini=read(OLD/'prepared'/c['id']/'initial.json')
  for p in ['E0','R']:
   s=pd.read_parquet(OLD/'prepared'/c['id']/(p+'.parquet'))
   for sc,cfg in SCENARIOS.items():
    _,l,t,_,_=backtest(d,s,oldini[p],c['symbol'],cfg,policy=p)
    folder=OLD/'results/v0/accounts'/('__'.join([c['id'],p,sc]));pd.testing.assert_frame_equal(l,pd.read_parquet(folder/'ledger.parquet'),check_exact=True,check_freq=False);pd.testing.assert_frame_equal(t,pd.read_csv(folder/'trades.csv'),check_exact=True)
    identity.append(dict(case=c['id'],policy=p,scenario=sc,ledger_rows=len(l),trades=len(t),passed=True))
  for p in NEW_POLICIES:
   s=pd.read_parquet(HERE/'prepared'/c['id']/(p+'.parquet'))
   for sc,cfg in SCENARIOS.items():
    stats,l,t,f,o=backtest(d,s,init[p],c['symbol'],cfg,policy=p,entry_event_column='buy_event' if p in TEMP_POLICIES else None)
    key='__'.join([c['id'],p,sc]);folder=out/'accounts'/key;folder.mkdir();l.to_parquet(folder/'ledger.parquet');t.to_csv(folder/'trades.csv',index=False);f.to_csv(folder/'fills.csv',index=False);o.to_csv(folder/'orders.csv',index=False)
    rows.append(dict(key=key,case=c['id'],symbol=c['symbol'],name=c['name'],type=c['type'],role=c['role'],start=c['start'],end=c['end'],first=str(d.index[0].date()),last=str(d.index[-1].date()),policy=p,policy_name=name(p),scenario=sc,origin='new',carry_in=bool(init[p]['active']),**stats))
  print({'completed_case':c['id']},flush=True)
 new=pd.DataFrame(rows);assert len(new)==756;new.to_csv(out/'new-summary.csv',index=False)
 reused=oldsummary.loc[oldsummary.policy.isin(OLD_POLICIES)].copy();assert len(reused)==216;reused['origin']='old_readonly';reused['policy_name']=reused.policy.map(name);reused['carry_in']=False
 for i,row in reused.iterrows():
  ini=read(OLD/'prepared'/row['case']/'initial.json');reused.at[i,'carry_in']=bool(ini['E0' if row['policy']=='HOLD' else row['policy']]['active'] or row['policy']=='HOLD')
 pd.concat([new,reused],ignore_index=True).to_csv(out/'summary.csv',index=False);pd.DataFrame(identity).to_csv(HERE/'audit/control-identity.csv',index=False)
 write(out/'run.json',dict(recorded_at=now(),new_economic_accounts=756,reused_old_accounts=216,displayed_accounts=972,technical_control_replays=108,formula_changes_after_results=0,freeze=ref(HERE/'freeze.json')))
 print({'done':True,'new':756,'old_reused':216,'technical':108},flush=True)
if __name__=='__main__':main()
