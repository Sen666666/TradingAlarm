import json,hashlib
from pathlib import Path
import pandas as pd
from calibrated_order_signal import reset_signal
from strategy_signals import build_signals
from ths_volume_units import ths_split_consistent_volume
OUT=Path('results/strength-calibrated-order-transfer485')
def main():
 p=json.loads((OUT/'protocol.json').read_text())
 for name,h in p['source_sha256'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
 calibration=Path('results/strength-calibrated-order/calibration.json')
 expected=json.loads(Path('results/strength-calibrated-order/calibration-validation.json').read_text())['calibration_sha256'];assert hashlib.sha256(calibration.read_bytes()).hexdigest()==expected
 manifest=json.loads(Path(p['manifest']).read_text());root=Path('data/ths-refresh-20261018')
 for rec in manifest['records'][:3]:
  f=pd.read_parquet(root/f"{rec['ths_symbol']}-signal.parquet");v=ths_split_consistent_volume(f.volume,json.loads((root/'rights'/f"{rec['ths_symbol']}.json").read_text()));raw=f[['open','high','low','close','volume']].copy();raw['volume']=v.where(f.observed_bar,0);sig=f[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_'));obs=f.loc[f.observed_bar&f.volume.gt(0)]
  direct=reset_signal(obs.signal_close,v.reindex(obs.index),'calibrated_pair_order_volume').reindex(sig.index,method='ffill').fillna(0)
  bridge=build_signals({rec['symbol']:{'raw':raw,'signal':sig,'splits':[]}},'calibrated_pair_order_volume')[rec['symbol']]
  pd.testing.assert_series_equal(direct,bridge,check_exact=True)
 new=pd.read_parquet(OUT/'episodes.parquet');old=pd.read_parquet(Path(p['control_reference'])/'episodes.parquet');a=new[new.strategy.eq('pairwise_volume')].reset_index(drop=True);b=old[old.strategy.eq('pairwise_volume')].reset_index(drop=True);pd.testing.assert_frame_equal(a,b,check_exact=True)
 v=json.loads((OUT/'validation.json').read_text());v.update(exact_control_rows=len(a),source_hashes=len(p['source_sha256']),direct_bridge_checks=3,original_calibration_hash_unchanged=True);(OUT/'validation.json').write_text(json.dumps(v,indent=2));print(v)
if __name__=='__main__':main()
