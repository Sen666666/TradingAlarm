"""Full frozen calendar RS-H1 cache; no account imports or new quotes."""
from pathlib import Path
import json,hashlib,datetime
import numpy as np,pandas as pd
from rs_h1_model import raw_momentum,MIN_REFERENCE
HERE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 out=HERE/'h1';out.mkdir(exist_ok=False)
 pm={x['series_id']:x for x in read(HERE/'prepared-v2/manifest.json')['series']}
 records={x['series_id']:x for x in read(HERE/'inputs-v2/input-manifest.json')['series']}
 stock=sorted(x['security_id'] for x in read(HERE/'inputs-v2/selection.json')['lines'] if (x.get('company_cap_cny') or 0)>1e10)
 sector=sorted(k for k,x in records.items() if x['kind']=='sector_index')
 historical_dates=set()
 for sid in sector:
  f=pd.read_parquet(HERE/'prepared-v2'/pm[sid]['files']['signal']['path'],columns=['observed_bar'])
  historical_dates.update(f.index[(f.index<'2015-01-01')&f.observed_bar.astype(bool)])
 rules=read(HERE/'inputs-v2/market-rules.json')
 days=[pd.Timestamp(x).tz_localize(None).normalize() for x in rules['calendars']['A'] if x[:10]<='2026-10-22']
 calendar=pd.DatetimeIndex(sorted(historical_dates|set(days)))
 assert len(stock)==1709 and len(sector)==90
 symbols=stock+sector;n=len(symbols);shape=(len(calendar),n)
 arr={k:np.full(shape,np.nan) for k in ['close','segment']};counts=np.zeros(shape,dtype=np.int32);origins=np.zeros(n,dtype=np.int32);sources=[]
 for j,sid in enumerate(symbols):
  x=pm[sid];assert x['blocked_reason'] is None
  ref=x['files']['signal'];p=HERE/'prepared-v2'/ref['path'];assert sha(p)==ref['sha256'];sources.append(dict(symbol=sid,path=str(p.resolve()),sha256=ref['sha256']))
  f=pd.read_parquet(p,columns=['open','high','low','close','observed_bar','synthetic_event_bar','source_invalid','raw_volume','segment_id'])
  o=f[['open','high','low','close']]
  valid=(np.isfinite(o).all(axis=1)&o.gt(0).all(axis=1)&f.high.ge(f.low)&f.high.ge(f[['open','close']].max(axis=1))&f.low.le(f[['open','close']].min(axis=1))&f.observed_bar.astype(bool)&~f.synthetic_event_bar.astype(bool)&~f.source_invalid.astype(bool)&f.raw_volume.gt(0)&np.isfinite(f.raw_volume))
  real=f.loc[valid];a=real.reindex(calendar);arr['close'][:,j]=a.close;arr['segment'][:,j]=a.segment_id
  c=pd.Series(np.arange(1,len(real)+1),index=real.index);counts[:,j]=c.reindex(c.index.union(calendar)).sort_index().ffill().reindex(calendar).fillna(0).astype(int)
  origins[j]=calendar.searchsorted(real.index[0])
  if j%400==0:print({'loaded':j},flush=True)
 score=np.full(shape,np.nan);horizons=np.minimum(np.maximum(np.arange(len(calendar))[:,None]-origins,0),252).astype(np.int16);raw=np.full(shape,np.nan);nref=np.zeros(shape,dtype=np.int16)
 for t in range(len(calendar)):
  if calendar[t]<pd.Timestamp('2015-01-01'):continue
  for left,right in [(0,len(stock)),(len(stock),n)]:
   age=horizons[t,left:right];ready=np.isfinite(arr['close'][t,left:right])&(counts[t,left:right]>=6)&(age>=5)
   for h in np.unique(age[ready]):
    values=raw_momentum(arr['close'][:,left:right],arr['segment'][:,left:right],counts[:,left:right],t,int(h));ref=np.sort(values[np.isfinite(values)])
    target=np.flatnonzero((age==h)&ready);j=target+left;raw[t,j]=values[target];nref[t,j]=len(ref)
    if len(ref)>=MIN_REFERENCE:
     v=values[target];pct=100*(np.searchsorted(ref,v,'left')+.5*(np.searchsorted(ref,v,'right')-np.searchsorted(ref,v,'left')))/len(ref)
     score[t,j]=np.where(np.isfinite(v),pct,np.nan)
  if t%500==0:print({'scored_date':str(calendar[t].date())},flush=True)
 np.savez_compressed(out/'matrix.npz',dates=calendar.values,symbols=np.array(symbols),score=score,close=arr['close'],segment=arr['segment'],obs_count=counts,h=horizons,raw=raw,nref=nref)
 write(out/'manifest.json',dict(source_signal_files=sources,prepared_sha256=sha(HERE/'prepared-v2/manifest.json'),rules_sha256=sha(HERE/'inputs-v2/market-rules.json'),matrix_sha256=sha(out/'matrix.npz'),calendar_start=str(calendar[0].date()),calendar_end=str(calendar[-1].date()),warmup_calendar='observed industry source date union pre2015; frozen A market calendar after',stocks=len(stock),industries=len(sector),code_sha256=sha(__file__),formula_sha256=sha(HERE/'code/rs_h1_model.py')))
 print({'done':True,'shape':shape,'calendar_start':str(calendar[0])},flush=True)
if __name__=='__main__':main()
