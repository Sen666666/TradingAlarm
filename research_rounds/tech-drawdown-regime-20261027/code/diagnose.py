from pathlib import Path
import sys,json,gzip,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];BASE=ROOT/'research_rounds/tech-finite-compound-20261026';NR=ROOT/'research_rounds/e0-reclaim-accounts-20261026/prepared';sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'))
from data_utils import eligible_prices

def make(cutoff=None):
 roster=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv');print(roster.columns.tolist(),flush=True)
 traces={};audit=[]
 for sid in roster.symbol:
  raw=eligible_prices(pd.read_parquet(BASE/'prepared-v2/signals'/f'{sid}.parquet'));f=pd.read_parquet(NR/'facts'/f'{sid}.parquet')
  if cutoff:raw=raw.loc[:cutoff];f=f.loc[:cutoff]
  parts=[]
  for seg,g in raw.groupby('segment_id',sort=False):
   r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();m=(r*np.minimum(1,np.sqrt(q))).ewm(span=21,adjust=False).mean();ready=np.arange(len(g))>=64
   z=pd.DataFrame({'r':r,'q':q,'m':m,'price_m':r.ewm(span=21,adjust=False).mean(),'ready':ready,'close':g.close,'amount':g.amount},index=g.index);parts.append(z)
  z=pd.concat(parts).sort_index();z['e0']=f.e0_target;z['warm']=f.g_grade.ge(2);z['cold']=f.g_grade.lt(2);z['floor_distance']=1-f.e0_floor/f.close;traces[sid]=z
 return roster,traces
if __name__=='__main__':
 out=O/'diagnostic-v1';out.mkdir(exist_ok=False);(out/'traces').mkdir();roster,traces=make();sectorcol=next(c for c in ['sector_id','industry_id','sector'] if c in roster.columns);sectors={}
 dates=sorted(set().union(*(set(z.index) for z in traces.values())));dates=pd.DatetimeIndex(dates)
 for sec,rs in roster.groupby(sectorcol):
  masks={k:pd.DataFrame({sid:traces[sid][k].where(traces[sid].ready) for sid in rs.symbol}).reindex(dates) for k in ['m','price_m','e0','warm','r']}
  secdf=pd.DataFrame(index=dates)
  for k,df in masks.items():secdf[k]=df.gt(0).sum(axis=1)/df.notna().sum(axis=1) if k!='r' else df.mean(axis=1)
  secdf['n']=masks['m'].notna().sum(axis=1);sectors[sec]=secdf
  secdf.to_csv(out/f'sector-{sec}.csv')
 agg=pd.DataFrame({k:pd.concat({s:z[k] for s,z in sectors.items()},axis=1).mean(axis=1) for k in ['m','price_m','e0','warm','r']});agg['equal_sector_price']=(1+np.expm1(agg.r.fillna(0))).cumprod();agg.to_csv(out/'breadth.csv')
 for sid,z in traces.items():z.to_parquet(out/'traces'/f'{sid}.parquet')
 ds=[]
 with gzip.open(BASE/'accounts-v2/daily.jsonl.gz','rt') as f:
  for line in f:
   d=json.loads(line)
   if d['account']!='I__S0_base':continue
   at=pd.Timestamp(d['at'][:10]);N=float(d['nav']);inv=float(d['inventory']);held=list(d['positions']);weights=[];cold=0;dist=0
   for sid in held:
    z=traces[sid].loc[:at]
    if z.empty:continue
    r=z.iloc[-1];raw=pd.read_parquet(NR/'facts'/f'{sid}.parquet').loc[:at].iloc[-1];w=float(d['positions'][sid])*raw.raw_close/N;cold+=w*float(r.cold);dist+=w*float(r.floor_distance)
   ds.append(dict(date=at,nav=N,exposure=inv/N,cold_exposure=cold,weighted_floor_distance=dist/(inv/N) if inv else 0,holdings=len(held),pending_sells=len(d['pending_sells'])))
 account=pd.DataFrame(ds).set_index('date');account.to_csv(out/'account.csv');plt.rcParams['font.sans-serif']=['Arial Unicode MS','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
 for label,start in [('full','2024'),('2026','2026')]:
  a=account.loc[start:];b=agg.loc[start:];fig,ax=plt.subplots(4,1,figsize=(15,12),sharex=True)
  ax[0].plot(a.index,a.nav/1e6,label='原I净值 / 初始100万元');ax[0].plot(b.index,b.equal_sector_price/b.equal_sector_price.iloc[0],label='等行业价格描述指数（非账户）',alpha=.6);ax[0].legend();ax[0].set_title('科技组合：净值、仓位与当时可见的量价广度')
  ax[1].plot(a.index,a.exposure,label='总仓位');ax[1].plot(a.index,a.cold_exposure,label='已低于暖的持仓市值/NAV');ax[1].legend()
  for k,lab in [('m','金额方向为正比例（行业等权）'),('e0','E0仍上行比例'),('warm','G1暖热比例')]:ax[2].plot(b.index,b[k],label=lab)
  ax[2].axhline(.5,color='grey',ls='--');ax[2].legend();ax[3].plot(a.index,a.weighted_floor_distance,label='持仓市值加权支持距离');ax[3].legend()
  for x in ax:x.grid(alpha=.2);x.axvspan(pd.Timestamp('2026-07-01'),pd.Timestamp('2026-10-26'),alpha=.06,color='red')
  fig.tight_layout();fig.savefig(out/f'account-{label}.png',dpi=130);plt.close(fig)
 joined=account.join(agg,rsuffix='_breadth');joined.loc['2024':].resample('ME').last().to_csv(out/'monthly.csv');print(joined.loc['2026':].resample('ME').last().to_string(),flush=True)
