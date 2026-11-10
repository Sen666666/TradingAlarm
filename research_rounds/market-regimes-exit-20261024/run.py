from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd
from engine import backtest,SCENARIOS
from model import POLICIES
R=Path(__file__).resolve().parent;O=R/'results/v0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 fr=json.loads((R/'freeze.json').read_text())
 for path,h in fr['sha256'].items():assert sha(R/path)==h,path
 O.mkdir(parents=True,exist_ok=False);(O/'accounts').mkdir();cases=json.loads((R/'cases.json').read_text());summ=[];pairs=[]
 for c in cases:
  d=pd.read_parquet(R/'inputs'/f'{c["symbol"]}.parquet').loc[c['start']:c['end']];sd=R/'prepared'/c['id'];states={p:pd.read_parquet(sd/f'{p}.parquet') for p in POLICIES};ini=json.loads((sd/'initial.json').read_text());f=pd.read_parquet(sd/'features.parquet')
  for scenario,sc in SCENARIOS.items():
   bt=None
   for p in POLICIES:
    result=backtest(d,states[p],ini,c['symbol'],sc);save(c,'P',p,scenario,result,summ)
    if p=='E0':bt=result[2]
   for p in POLICIES[1:]:
    result=backtest(d,states['E0'],ini,c['symbol'],sc,matched_to=bt,policy=p,features=f);t=result[2]
    assert t.entry_date.tolist()==bt.entry_date.tolist();np.testing.assert_allclose(t.entry_price,bt.entry_price,rtol=0,atol=0);assert (pd.to_datetime(t.exit_date)<=pd.to_datetime(bt.exit_date)).all()
    for j,(x,y) in enumerate(zip(bt.to_dict('records'),t.to_dict('records'))):pairs.append(dict(case=c['id'],scenario=scenario,policy=p,leg=j,entry_date=x['entry_date'],base_exit=x['exit_date'],sensitive_exit=y['exit_date'],base_return=x['net_return'],sensitive_return=y['net_return'],delta=y['net_return']-x['net_return'],base_terminal=x['terminal'],sensitive_terminal=y['terminal']))
    save(c,'M',p,scenario,result,summ)
   save(c,'H','HOLD',scenario,backtest(d,states['E0'],ini,c['symbol'],sc,benchmark=True),summ)
  print('completed',c['id'],flush=True)
 assert len(summ)==240;pd.DataFrame(summ).to_csv(O/'summary.csv',index=False);pd.DataFrame(pairs).to_csv(O/'matched-legs.csv',index=False);(O/'run.json').write_text(json.dumps({'accounts':240,'policy_parameter_changes':0,'freeze_sha256':sha(R/'freeze.json')},indent=2));print('DONE240',flush=True)
def save(c,mode,p,scenario,result,summ):
 key='__'.join([c['id'],mode,p,scenario]);stats,l,t,f,o=result;folder=O/'accounts'/key;folder.mkdir();l.to_parquet(folder/'ledger.parquet');t.to_csv(folder/'trades.csv',index=False);f.to_csv(folder/'fills.csv',index=False);o.to_csv(folder/'orders.csv',index=False);summ.append(dict(key=key,case=c['id'],symbol=c['symbol'],name=c['name'],type=c['type'],start=c['start'],end=c['end'],mode=mode,policy=p,scenario=scenario,**stats))
if __name__=='__main__':main()
