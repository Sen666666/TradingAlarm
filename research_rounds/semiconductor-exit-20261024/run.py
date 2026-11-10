from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
from engine import backtest,SCENARIOS
from model import POLICIES
R=Path(__file__).resolve().parent;O=R/'results/v0';P=R/'../exit-posture-20261024/results/v0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 frozen=json.loads((R/'freeze.json').read_text())
 for path,h in frozen['sha256'].items():assert sha(R/path)==h,path
 O.mkdir(parents=True,exist_ok=False);(O/'accounts').mkdir()
 d=pd.read_parquet(R/'inputs/USHJ512480.parquet').loc['2025-01-02':'2026-06-30'];initial=json.loads((R/'prepared/initial.json').read_text());f=pd.read_parquet(R/'prepared/features.parquet').loc[d.index];states={p:pd.read_parquet(R/'prepared'/f'{p}.parquet') for p in POLICIES};summ=[];pairs=[];identities=[]
 for scenario,sc in SCENARIOS.items():
  bt=None
  for p in POLICIES:
   result=backtest(d,states[p],initial,'USHJ512480',sc);save('P',p,scenario,result,summ,identities)
   if p=='E0':bt=result[2]
  for p in POLICIES[1:]:
   result=backtest(d,states['E0'],initial,'USHJ512480',sc,matched_to=bt,policy=p,features=f);tt=result[2]
   assert tt.entry_date.tolist()==bt.entry_date.tolist();np.testing.assert_allclose(tt.entry_price,bt.entry_price,rtol=0,atol=0);assert (pd.to_datetime(tt.exit_date)<=pd.to_datetime(bt.exit_date)).all()
   for j,(old,new) in enumerate(zip(bt.to_dict('records'),tt.to_dict('records'))):pairs.append(dict(scenario=scenario,policy=p,leg=j,entry_date=old['entry_date'],E0_exit=old['exit_date'],sensitive_exit=new['exit_date'],E0_return=old['net_return'],sensitive_return=new['net_return'],delta=new['net_return']-old['net_return'],E0_terminal=old['terminal'],sensitive_terminal=new['terminal']))
   save('M',p,scenario,result,summ,identities)
  save('H','HOLD',scenario,backtest(d,states['E0'],initial,'USHJ512480',sc,benchmark=True),summ,identities)
 assert len(summ)==24;pd.DataFrame(summ).to_csv(O/'summary.csv',index=False);pd.DataFrame(pairs).to_csv(O/'matched-legs.csv',index=False);pd.DataFrame(identities).to_csv(O/'prior-account-prefix-checks.csv',index=False)
 (O/'run.json').write_text(json.dumps({'accounts':24,'signal_parameter_changes':0,'account_results_after_rule_revisions':0,'prior_account_identity_checks':len(identities),'freeze_sha256':sha(R/'freeze.json')},indent=2));print(pd.DataFrame(summ).to_string(index=False))
def save(mode,policy,scenario,result,summ,identities):
 key=f'{mode}_{policy}_{scenario}';stats,l,t,f,o=result;folder=O/'accounts'/key;folder.mkdir();l.to_parquet(folder/'ledger.parquet');t.to_csv(folder/'trades.csv',index=False);f.to_csv(folder/'fills.csv',index=False);o.to_csv(folder/'orders.csv',index=False)
 old=pd.read_parquet(P/'accounts'/f'USHJ512480__primary__{scenario}__{mode}__{policy}'/'ledger.parquet');pd.testing.assert_frame_equal(l.iloc[:-1],old.loc[l.index[:-1]],check_exact=True)
 identities.append(dict(key=key,through=str(l.index[-2].date()),passed=True))
 summ.append(dict(key=key,mode=mode,policy=policy,scenario=scenario,**stats))
if __name__=='__main__':main()
