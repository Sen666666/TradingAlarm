from pathlib import Path
import json,gzip
import pandas as pd,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];BASE=ROOT/'research_rounds/tech-finite-compound-20261026';NR=ROOT/'research_rounds/e0-reclaim-accounts-20261026/prepared'
def gate(nav,off,on):
 state=True;peak=1e6;rows=[]
 for n in nav:
  peak=max(peak,n);d=1-n/peak
  if d>=off:state=False
  elif d<=on:state=True
  rows.append(state)
 return pd.Series(rows,index=nav.index)
if __name__=='__main__':
 with gzip.open(O/'CONTROL/accounts-v2/daily.jsonl.gz','rt') as f:rs=[r for r in map(json.loads,f) if r['account']=='I__S0_base']
 n=pd.Series([float(r['nav']) for r in rs],index=pd.to_datetime([r['at'][:10] for r in rs]));states=pd.DataFrame({v:gate(n,t,t/2) for v,t in [('SHADOW10',.1),('SHADOW20',.2)]});out=O/'shadow-signals';out.mkdir(exist_ok=False);states.to_csv(out/'gates.csv');pd.DataFrame({'nav':n,'drawdown':1-n/np.maximum(n.cummax(),1e6)}).to_csv(out/'reference.csv')
 for cutoff in ['2024-12-31','2025-12-31','2026-06-30']:
  for v,t in [('SHADOW10',.1),('SHADOW20',.2)]:pd.testing.assert_series_equal(gate(n.loc[:cutoff],t,t/2),states[v].loc[:cutoff],check_names=False)
 for v in states:
  root=O/v/'prepared';(root/'facts').mkdir(parents=True,exist_ok=False);(root/'h1.npz').symlink_to(BASE/'prepared-v2/h1.npz')
  for path in sorted((NR/'facts').glob('*.parquet')):
   f=pd.read_parquet(path)
   if not path.stem.startswith('URFI'):
    # reference unavailable before account start: original states retained for warmup;
    # from first decision onward every observed date is evaluated with latest known reference.
    mask=states[v].reindex(f.index,method='ffill').fillna(True);f['i_target']=f.i_target&mask;f['i_buy']=f.i_buy&mask
   f.to_parquet(root/'facts'/path.name)
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False;fig,ax=plt.subplots(2,1,figsize=(14,7),sharex=True);ax[0].plot(n.index,n/1e6);ax[0].set_title('固定原I影子净值与风险开关：不等于目标账户收益');states.astype(int).plot(ax=ax[1]);fig.tight_layout();fig.savefig(out/'reference.png',dpi=110)
 (out/'validation.json').write_text(json.dumps({'passed':True,'gate_prefixes':6,'source_account_prefix':'../account-validation.json 2025末原I真实执行前缀','reference':'CONTROL base only; never actual target account'},indent=2));print('shadow prepared')
