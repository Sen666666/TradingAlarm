from pathlib import Path
import hashlib,json,datetime
import pandas as pd
from engine import backtest,SCENARIOS
from model import POLICIES
R=Path(__file__).resolve().parent;O=R/'results/v0';SOURCE=R.parent/'market-regimes-exit-20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 fr=json.loads((R/'freeze.json').read_text())
 for name,h in fr['sha256'].items():assert sha(R/name)==h,name
 return fr

def main():
 verify();O.mkdir(parents=True,exist_ok=False);(O/'accounts').mkdir();summ=[]
 for c in json.loads((R/'cases.json').read_text()):
  d=pd.read_parquet(SOURCE/'inputs'/f'{c["symbol"]}.parquet').loc[c['start']:c['end']];sd=R/'prepared'/c['id'];initial=json.loads((sd/'initial.json').read_text())
  for p in POLICIES+['HOLD']:
   s=pd.read_parquet(sd/f'{p if p!="HOLD" else "E0"}.parquet');ini=initial[p if p!='HOLD' else 'E0']
   for scenario,sc in SCENARIOS.items():
    stats,l,t,f,o=backtest(d,s,ini,c['symbol'],sc,benchmark=p=='HOLD')
    key='__'.join([c['id'],p,scenario]);folder=O/'accounts'/key;folder.mkdir()
    l.to_parquet(folder/'ledger.parquet');t.to_csv(folder/'trades.csv',index=False);f.to_csv(folder/'fills.csv',index=False);o.to_csv(folder/'orders.csv',index=False)
    summ.append(dict(key=key,case=c['id'],symbol=c['symbol'],name=c['name'],type=c['type'],role=c['role'],start=c['start'],end=c['end'],first=str(d.index[0].date()),last=str(d.index[-1].date()),policy=p,scenario=scenario,**stats))
  print('completed',c['id'],flush=True)
 assert len(summ)==486;pd.DataFrame(summ).to_csv(O/'summary.csv',index=False)
 (O/'run.json').write_text(json.dumps({'accounts':486,'policy_parameter_changes_after_freeze':0,'freeze_sha256':sha(R/'freeze.json'),'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2));print('DONE 486',flush=True)
if __name__=='__main__':main()
