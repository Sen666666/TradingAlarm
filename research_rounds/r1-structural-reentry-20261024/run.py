from pathlib import Path
import json,hashlib,datetime
import pandas as pd,numpy as np
from engine import backtest,SCENARIOS
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';S=R.parent/'market-regimes-exit-20261024/inputs';O=R/'results/v0';CONTROLS=['E0','R','E2','HOLD']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 fr=json.loads((R/'freeze.json').read_text())
 for name,h in fr['sha256'].items():assert sha(R/name)==h,name
 return fr

def main():
 verify();O.mkdir(parents=True,exist_ok=False);(O/'accounts').mkdir();(O/'cash-reference').mkdir();summary=[];comparison=[];cashrows=[]
 old=pd.read_csv(P/'results/v0/summary.csv')
 for c in json.loads((R/'cases.json').read_text()):
  d=pd.read_parquet(S/f'{c["symbol"]}.parquet').loc[c['start']:c['end']];state=pd.read_parquet(R/'prepared'/c['id']/'R1.parquet');ini=json.loads((R/'prepared'/c['id']/'initial.json').read_text());meta={k:c[k] for k in ['symbol','name','type','role','start','end']};meta.update(case=c['id'],first=str(d.index[0].date()),last=str(d.index[-1].date()))
  for scenario,sc in SCENARIOS.items():
   stats,l,t,f,o=backtest(d,state,ini,c['symbol'],sc);key=f"{c['id']}__R1__{scenario}";folder=O/'accounts'/key;folder.mkdir();l.to_parquet(folder/'ledger.parquet');t.to_csv(folder/'trades.csv',index=False);f.to_csv(folder/'fills.csv',index=False);o.to_csv(folder/'orders.csv',index=False)
   row=dict(key=key,**meta,policy='R1',scenario=scenario,**stats,mean_capital_exposure=float((l.quantity*l.close/l.nav).mean()),reused_control=False);summary.append(row);comparison.append(row)
   e0=None
   for p in CONTROLS:
    src=old[(old.case==c['id'])&(old.policy==p)&(old.scenario==scenario)].iloc[0].to_dict();ll=pd.read_parquet(P/'results/v0/accounts'/src['key']/'ledger.parquet');src['mean_capital_exposure']=float((ll.quantity*ll.close/ll.nav).mean());src['reused_control']=True;comparison.append(src)
    if p=='E0':e0=ll;control=src
   nav=.5*e0.nav+.5;cash=pd.DataFrame({'nav':nav,'cash':.5*e0.cash+.5,'quantity':.5*e0.quantity,'close':e0.close});cash['drawdown']=cash.nav/np.maximum.accumulate(np.r_[1.,cash.nav.to_numpy()])[1:]-1;cash.to_parquet(O/'cash-reference'/f"{c['id']}__{scenario}.parquet")
   ref=dict(key=f"{c['id']}__HALF_E0__{scenario}",**meta,policy='HALF_E0',scenario=scenario,net_return=float(nav.iloc[-1]-1),max_drawdown=float(-cash.drawdown.min()),mean_capital_exposure=float((cash.quantity*cash.close/cash.nav).mean()),fees=.5*control['fees'],slippage=.5*control['slippage'],tail_pnl=.5*control['tail_pnl'],ordinary_pnl=.5*control['ordinary_pnl'],reused_control=False,reference_only=True);cashrows.append(ref)
  print('completed',c['id'],flush=True)
 assert len(summary)==54 and len(comparison)==270 and len(cashrows)==54
 pd.DataFrame(summary).to_csv(O/'R1-summary.csv',index=False);pd.DataFrame(comparison).to_csv(O/'comparison.csv',index=False);pd.DataFrame(cashrows).to_csv(O/'cash-reference.csv',index=False)
 (O/'run.json').write_text(json.dumps({'new_R1_engine_accounts':54,'reused_control_accounts':216,'reference_paths':54,'policy_changes_after_freeze':0,'freeze_sha256':sha(R/'freeze.json'),'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2));print('DONE new54 / reused216 / reference54',flush=True)
if __name__=='__main__':main()
