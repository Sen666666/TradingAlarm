"""Bridge agreement plus exact preexisting adaptive episode control."""
import json,hashlib
from pathlib import Path
import pandas as pd
from strategy_signals import build_signals
from pairwise_trend_strength import pairwise_frame
from geometric_strength import geometric_frame,strength_exposure
from ths_volume_units import ths_split_consistent_volume
OUT=Path('results/strength-pairwise-transfer485')
def main():
 protocol=json.loads((OUT/'protocol.json').read_text())
 for p,h in protocol['source_sha256'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
 manifest=json.loads(Path(protocol['manifest']).read_text());root=Path('data/ths-refresh-20261018');count=0
 for r in manifest['records'][:3]:
  f=pd.read_parquet(root/f"{r['ths_symbol']}-signal.parquet");v=ths_split_consistent_volume(f.volume,json.loads((root/'rights'/f"{r['ths_symbol']}.json").read_text()));raw=f[['open','high','low','close','volume']].copy();raw['volume']=v.where(f.observed_bar,0);sig=f[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_'));obs=f.loc[f.observed_bar&f.volume.gt(0)]
  for name in ['pairwise_price','pairwise_volume','linear_geometry_price_volume_split_units']:
   if name.startswith('pairwise'):score=pairwise_frame(obs.signal_close,v.reindex(obs.index),joint=name.endswith('_volume')).strength
   else:score=geometric_frame(obs.signal_close,obs.close,v.reindex(obs.index),joint=True,degree=1).strength
   direct=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0);bridged=build_signals({r['symbol']:{'raw':raw,'signal':sig,'splits':[]}},name)[r['symbol']];pd.testing.assert_series_equal(direct,bridged,check_exact=True);count+=1
 new=pd.read_parquet(OUT/'episodes.parquet');old=pd.read_parquet(Path(protocol['control_reference'])/'episodes.parquet');name='adaptive_geometry_price_volume_split_units';a=new.loc[new.strategy.eq(name)].reset_index(drop=True);b=old.loc[old.strategy.eq(name)].reset_index(drop=True);pd.testing.assert_frame_equal(a,b,check_exact=True)
 p=OUT/'validation.json';v=json.loads(p.read_text());v.update(source_hashes_verified=len(protocol['source_sha256']),direct_bridge_checks=count,exact_control_episode_rows=len(a),unit_tests=2);p.write_text(json.dumps(v,indent=2));print(v)
if __name__=='__main__':main()
