from pathlib import Path
import json,gzip,hashlib
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];R=O.parents[1];S=R/'research_rounds/staged-risk-20261027';P=R/'research_rounds/tech-finite-compound-20261026/prepared-v2/signals'
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
if __name__=='__main__':
 out=O/'results';out.mkdir(exist_ok=False)
 raw={r['at']:r['eligible'] for r in rows(S/'CONTROL/accounts-v2/decisions.jsonl.gz') if r['account']=='I__S0_base'}
 days={(r['account'],r['at']):r for r in rows(S/'STEP/accounts-v2/daily.jsonl.gz')}
 roster=pd.read_csv(R/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol');prices={};records=[]
 for aid in ['I__S0_base','I__S0_cost2','I__S0_delay1']:
  a=json.loads((S/'STEP/accounts-v2'/f'{aid}.json').read_text());rr=[r for r in a['audit_log'] if r['kind']=='risk_checkpoint'];last=None;phase_id=0;seen=set()
  for r in rr:
   phase=r['phase'];at=r['at'];day=pd.Timestamp(at[:10]);d=days[aid,at]
   if phase!=last:phase_id+=1;seen=set();last=phase
   for sid in raw[at]:
    if sid in d['positions']:continue
    if sid not in prices:
     f=pd.read_parquet(P/f'{sid}.parquet');prices[sid]=f[f.price_eligible & f.is_observed_bar & ~f.synthetic_event_bar].copy()
    f=prices[sid];i=f.index.searchsorted(day,side='right');prev=i-1
    row=dict(account=aid,date=str(day.date()),phase=phase,phase_id=phase_id,symbol=sid,name=roster.loc[sid,'name'],first_in_phase=sid not in seen)
    seen.add(sid)
    for n in [5,21,63]:
     j=i+n-1;valid=prev>=0 and j<len(f) and f.segment_id.iloc[prev:j+1].nunique()==1
     row[f'r{n}']=float(f.close.iloc[j]/f.open.iloc[i]-1) if valid else np.nan
    records.append(row)
 x=pd.DataFrame(records);x['period']=np.where(x.date>='2026-07-01','2026H2',np.where(x.date>='2026-01-01','2026H1',x.date.str[:4]));x.to_csv(out/'candidate-observations.csv',index=False)
 summary=[]
 for sample,z in [('stock_days',x),('first_per_phase',x[x.first_in_phase])]:
  for (aid,phase,period),g in z.groupby(['account','phase','period']):
   for n in [5,21,63]:
    v=g[f'r{n}'].dropna();summary.append(dict(sample=sample,account=aid,phase=phase,period=period,horizon=n,candidates=len(g),complete=len(v),mean=v.mean(),median=v.median(),positive=v.gt(0).mean(),big_up=v.ge(.3).mean(),large_loss=v.le(-.1).mean()))
 q=pd.DataFrame(summary);q.to_csv(out/'summary.csv',index=False)
 # Sanity: no held positions counted, repeated first marker unique per phase.
 assert not x[x.first_in_phase].duplicated(['account','phase_id','symbol']).any()
 assert all(sid not in days[aid,pd.Timestamp(date).strftime('%Y-%m-%d')+' 15:10:00+08:00']['positions'] for aid,date,sid in x[['account','date','symbol']].itertuples(index=False,name=None))
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 z=q[(q.account=='I__S0_base')&(q['sample']=='first_per_phase')&(q.horizon==21)];fig,ax=plt.subplots(2,1,figsize=(12,8));z.pivot(index='period',columns='phase',values='median').plot.bar(ax=ax[0]);z.pivot(index='period',columns='phase',values='positive').plot.bar(ax=ax[1]);ax[0].set_title('未持有原I候选：每阶段每股首次，后21观察价格中位收益');ax[1].set_title('后21观察价格上涨比例（非交易收益，未计费用）');fig.tight_layout();fig.savefig(out/'candidate-diagnostic.png',dpi=130)
 (O/'verification.json').write_text(json.dumps({'passed':True,'rows':len(x),'first_rows':int(x.first_in_phase.sum()),'economic_accounts':0,'held_exclusion':True,'first_unique':True},indent=2));print(z.to_string(index=False))
