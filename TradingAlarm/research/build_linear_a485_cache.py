"""Unchanged linear-volume estimator on full histories and prior episode bridge checks."""
import json,hashlib
from pathlib import Path
import pandas as pd
from geometric_strength import geometric_frame,strength_exposure
from ths_volume_units import ths_split_consistent_volume
from a_stock_monthly252 import simulate
OUT=Path('results/broad-shared-linear')
def main():
 OUT.mkdir(exist_ok=True,parents=True);root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());rows=[];hashes={};dates=set();samples=[];prefix=0
 for i,r in enumerate(manifest['records']):
  p=root/f"{r['ths_symbol']}-signal.parquet";q=root/'rights'/f"{r['ths_symbol']}.json"
  for path,key in [(p,'signal_sha256'),(q,'rights_sha256')]:
   h=hashlib.sha256(path.read_bytes()).hexdigest();assert h==r[key];hashes[str(path)]=h
  f=pd.read_parquet(p);v=ths_split_consistent_volume(f.volume,json.loads(q.read_text()));obs=f[f.observed_bar&f.volume.gt(0)];score=geometric_frame(obs.signal_close,obs.close,v.reindex(obs.index),joint=True,degree=1).strength;state=strength_exposure(score)
  for n in [len(score)//2,len(score)-1]:pd.testing.assert_series_equal(strength_exposure(score.iloc[:n]),state.iloc[:n]);prefix+=1
  if i in [0,240,484]:
   n=len(obs)//2;pd.testing.assert_series_equal(geometric_frame(obs.signal_close.iloc[:n],obs.close.iloc[:n],v.reindex(obs.index).iloc[:n],joint=True,degree=1).strength,score.iloc[:n]);samples.append((r['symbol'],f,state))
  dates.update(f.index[f.observed_bar]);out=pd.DataFrame(dict(strength=score,exposure=state));out['symbol']=r['symbol'];out.index.name='date';rows.append(out.loc['2024-01-01':].reset_index())
  if (i+1)%100==0:print('linear histories',i+1,flush=True)
 calendar=pd.DatetimeIndex(sorted(dates));previous=pd.read_parquet('results/strength-pairwise-transfer485/episodes.parquet');checks=[]
 for symbol,f,state in samples:
  scores=state.reindex(f.index,method='ffill').fillna(0).reindex(calendar,method='ffill').fillna(0).to_numpy(bool)
  snapshots=simulate(calendar,f.signal_open.reindex(calendar).to_numpy(),f.signal_close.reindex(calendar).to_numpy(),scores,f.bar_allows_trade.reindex(calendar,fill_value=False).to_numpy(bool),f.high.gt(f.low).reindex(calendar,fill_value=False).to_numpy(bool),[pd.Timestamp('2026-10-16')],symbol,delay=0,cadence='daily',start='2024-01-01')
  expected=previous[previous.symbol.eq(symbol)&previous.strategy.eq('linear_geometry_price_volume_split_units')&previous.delay.eq(0)&previous.cutoff.eq('2026-10-16')].to_dict('records');actual=snapshots['2026-10-16'];assert len(expected)==len(actual)
  for a,b in zip(actual,expected):
   for k,value in a.items():assert value==b[k],(symbol,k,value,b[k])
  checks.append(dict(symbol=symbol,episodes=len(actual)))
 pd.concat(rows,ignore_index=True).to_parquet(OUT/'linear-signals.parquet',index=False)
 (OUT/'signal-validation.json').write_text(json.dumps(dict(input_hashes=hashes,assets=485,state_prefix_checks=prefix,estimator_prefix_checks=3,prior_isolated_episode_bridges=checks,initialization='Full historical estimator and exposure, then same2024 cache start and flat-before-cache convention as shared baseline.'),indent=2));print('Linear signal cache and prior episode bridges validated',flush=True)
if __name__=='__main__':main()
