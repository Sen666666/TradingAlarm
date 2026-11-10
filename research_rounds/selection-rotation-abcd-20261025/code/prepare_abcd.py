from common_abcd import *
from board_abcd import build
import pandas as pd
def main():
 out=HERE/'prepared';out.mkdir(exist_ok=False);z=dict(np.load(OLD/'h1/matrix.npz'));meta=read(OLD/'inputs-v2/metadata.json');b=build(z,meta);np.savez_compressed(out/'dual-board.npz',**b)
 stocks=[str(s) for s in z['symbols'] if not str(s).startswith('URFI')];sectors=[str(s) for s in z['symbols'] if str(s).startswith('URFI')];assert len(stocks)==1709 and len(sectors)==90
 buy={};targets={}
 for sid in stocks:
  f=pd.read_parquet(SRC/'signals'/f'{sid}.parquet',columns=['IX','ix_target']);buy[sid]=f.index[f.IX.astype(bool)].strftime('%Y-%m-%d').tolist()
 write(out/'buy-events.json',buy)
 # Explicit unchanged source identities, not new input downloads.
 paths=[OLD/'h1/matrix.npz',OLD/'inputs-v2/metadata.json',OLD/'inputs-v2/input-manifest.json',OLD/'prepared-v2/manifest.json',OLD/'inputs-v2/market-rules.json',OLD/'inputs-v2/economic-protocol.json',SRC/'complete.json']
 write(out/'manifest.json',dict(recorded_at=now(),stocks=1709,sectors=90,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},outputs={str(p.relative_to(ROOT)):sha(p) for p in [out/'dual-board.npz',out/'buy-events.json']},downloads=0))
 print(dict(prepared=True,stocks=1709,sectors=90),flush=True)
if __name__=='__main__':main()
