from pathlib import Path
import pandas as pd,numpy as np,json,gzip,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];R=O.parents[1];A=R/'research_rounds/staged-risk-20261027';F=R/'research_rounds/e0-reclaim-accounts-20261026/prepared/facts';P=R/'research_rounds/tech-finite-compound-20261026/prepared-v2/signals'
with gzip.open(A/'CONTROL/accounts-v2/decisions.jsonl.gz','rt') as f:decisions=[x for x in map(json.loads,f) if x['account']=='I__S0_base']
calendar=pd.DatetimeIndex([pd.Timestamp(x['at'][:10]) for x in decisions]);by_sid={}
for r in decisions:
 for sid in r['eligible']:by_sid.setdefault(sid,set()).add(pd.Timestamp(r['at'][:10]))
roster=pd.read_csv(R/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol');prices={};facts={}
for sid in roster.index:
 f=pd.read_parquet(P/f'{sid}.parquet');prices[sid]=f[f.price_eligible & f.is_observed_bar & ~f.synthetic_event_bar][['close','segment_id']];facts[sid]=pd.read_parquet(F/f'{sid}.parquet')[['i_target']]
def run(end):
 cal=calendar[calendar<=pd.Timestamp(end)];records=[];pending=[]
 for sid in roster.index:
  p=prices[sid].loc[:end];f=facts[sid].loc[:end];allowed={d for d in by_sid.get(sid,set()) if d<=pd.Timestamp(end)};busy_until=None
  for d in sorted(allowed):
   if busy_until is not None and d<=busy_until:continue
   k=p.index.searchsorted(d,side='right')-1
   if k<0 or p.index[k]!=d:continue
   j=k+5
   if j>=len(p):pending.append(dict(symbol=sid,signal=str(d.date())));break
   busy_until=p.index[j];chunk=p.iloc[k:j+1]
   if chunk.segment_id.nunique()!=1:continue
   t=f.reindex(chunk.index[1:]).i_target
   if t.isna().any():continue
   records.append(dict(symbol=sid,industry=roster.loc[sid,'industry'],signal=d,published=p.index[j],structure_fail=bool(t.eq(0).any()),price_fail=bool(p.close.iloc[j]<p.close.iloc[k]),price_return=float(p.close.iloc[j]/p.close.iloc[k]-1)))
 events=pd.DataFrame(records);daily=[]
 for i,d in enumerate(cal):
  lo=cal[max(0,i-20)];z=events[(events.published>=lo)&(events.published<=d)] if len(events) else pd.DataFrame();sectors=[];n=0
  if len(z):
   for industry,q in z.groupby('industry'):
    per=q.groupby('symbol')[['structure_fail','price_fail']].mean()
    if len(per)<5:continue
    sectors.append(per.mean());n+=len(per)
  daily.append(dict(date=d,valid_sectors=len(sectors),stocks=n,completed_observations=len(z),structure_failure=pd.DataFrame(sectors).structure_fail.mean() if len(sectors)>=8 else np.nan,price_failure=pd.DataFrame(sectors).price_fail.mean() if len(sectors)>=8 else np.nan))
 return events,pd.DataFrame(daily).set_index('date'),pending
if __name__=='__main__':
 out=O/'results';out.mkdir(exist_ok=False);ev,b,pending=run('2026-10-26');ev.to_csv(out/'observations.csv',index=False);b.to_csv(out/'breadth.csv');(out/'pending.json').write_text(json.dumps(pending,indent=2));receipts=[]
 for end in ['2024-12-31','2025-12-31','2026-06-30','2026-08-31']:
  e,z,_=run(end);pd.testing.assert_frame_equal(b.loc[:end],z);pd.testing.assert_frame_equal(ev[ev.published<=pd.Timestamp(end)].reset_index(drop=True),e.reset_index(drop=True));receipts.append(end)
 assert (ev.published>ev.signal).all();assert ev.groupby('symbol').apply(lambda z:z.sort_values('signal').signal.iloc[1:].reset_index(drop=True).gt(z.sort_values('signal').published.iloc[:-1].reset_index(drop=True)).all(),include_groups=False).all()
 old=pd.read_csv(R/'research_rounds/tech-drawdown-regime-20261027/signals-v1/breadth.csv',index_col=0,parse_dates=True);b['old_positive_amount_breadth']=old.m21;b.to_csv(out/'comparison.csv')
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 c=pd.read_csv(A/'results/curves.csv',parse_dates=['date']);c=c[(c.scenario=='base') & c.version.isin(['CONTROL','STEP'])]
 for label,start,end in [('full','2024-01-01','2026-10-26'),('july','2026-05-01','2026-08-31')]:
  fig,ax=plt.subplots(3,1,figsize=(14,10),sharex=True)
  for name,g in c.groupby('version'):
   g=g.set_index('date').loc[start:end];ax[0].plot(g.index,g.nav/1e6,label=name)
  b.loc[start:end,['structure_failure','price_failure','old_positive_amount_breadth']].plot(ax=ax[1]);b.loc[start:end,['valid_sectors']].plot(ax=ax[2]);ax[0].set_title('原I与分级策略净值；新趋势失败广度（仅当时成熟观察）');ax[0].legend();ax[1].set_ylim(0,1);ax[2].set_ylim(0,12)
  for x in ax:x.grid(alpha=.2)
  fig.tight_layout();fig.savefig(out/f'{label}.png',dpi=120);plt.close(fig)
 b.loc['2026-06-22':'2026-07-20'].to_csv(out/'july-table.csv');b.groupby(b.index.year).agg({'structure_failure':['mean','count'],'price_failure':['mean','count'],'valid_sectors':'mean'}).to_csv(out/'annual-description.csv')
 (O/'verification.json').write_text(json.dumps({'passed':True,'prefixes':receipts,'observations':len(ev),'pending':len(pending),'daily_rows':len(b),'economic_accounts':0},indent=2));print(b.loc['2026-06-29':'2026-07-17'].to_string())
