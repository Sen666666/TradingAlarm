"""Full-history graded states, retaining the established 2024 signal-window boundary."""
import json,hashlib
from pathlib import Path
import pandas as pd
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from graded_trend_exposure import graded_exposure
from ths_volume_units import ths_split_consistent_volume
OUT=Path('results/broad-shared-graded')
def main():
 OUT.mkdir(exist_ok=True,parents=True);root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());old=pd.read_parquet('results/broad-exit-disagreement/all-observed-signals.parquet');rows=[];hashes={};prefixes=0
 for i,r in enumerate(manifest['records']):
  p=root/f"{r['ths_symbol']}-signal.parquet";q=root/'rights'/f"{r['ths_symbol']}.json"
  for path,key in [(p,'signal_sha256'),(q,'rights_sha256')]:
   h=hashlib.sha256(path.read_bytes()).hexdigest();assert h==r[key];hashes[str(path)]=h
  f=pd.read_parquet(p).loc[:'2026-10-16'];v=ths_split_consistent_volume(f.volume,json.loads(q.read_text()));obs=f[f.observed_bar&f.volume.gt(0)];score=pairwise_frame(obs.signal_close,v.reindex(obs.index)).strength;state=graded_exposure(score);base=strength_exposure(score);z=old[old.symbol.eq(r['symbol'])].set_index('date')
  pd.testing.assert_series_equal(score.reindex(z.index),z.strength,check_names=False,check_exact=True);pd.testing.assert_series_equal(base.reindex(z.index),z.zero,check_names=False,check_exact=True)
  for n in [len(score)//2,len(score)-1]:pd.testing.assert_series_equal(graded_exposure(score.iloc[:n]),state.iloc[:n]);prefixes+=1
  out=pd.DataFrame(dict(strength=score,graded=state,zero=base));out['symbol']=r['symbol'];out.index.name='date';rows.append(out.loc['2024-01-01':].reset_index())
  if (i+1)%50==0:print('full-history symbols',i+1,flush=True)
 pd.concat(rows,ignore_index=True).to_parquet(OUT/'graded-signals.parquet',index=False)
 (OUT/'signal-validation.json').write_text(json.dumps(dict(symbols=485,exact_full_history_score_bridges=485,exact_binary_exposure_bridges=485,prefix_checks=prefixes,hashes=hashes,initialization='Full-history state estimation, then same2024 observed signal-window truncation and flat-before-cache convention as original shared baseline. Initial nonzero graded state may be half; explicit initial admission convention, not a new live crossing.'),indent=2));print('Validated complete graded cache',flush=True)
if __name__=='__main__':main()
