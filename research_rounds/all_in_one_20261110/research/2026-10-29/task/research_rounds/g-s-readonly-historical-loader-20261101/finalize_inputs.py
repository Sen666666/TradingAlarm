"""Add original legacy-sector H1 attribution (not an admission gate)."""
from loader import *
import argparse

def finalize(root):
 root=Path(root);f=read(root/'FREEZE.json');assert not (root/'FINALIZED.json').exists()
 sources=read(root/'SOURCE_BINDINGS.json');p=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
 assert sha(p)==sources[str(p)]
 h=np.load(p,allow_pickle=False);dates=pd.DatetimeIndex(h['dates']);scores=h['score'];cols={str(s):n for n,s in enumerate(h['symbols'])}
 for k in ('2022','2025_26'):
  path=root/k/'MANIFEST.json';m=read(path);hp=root/k/'h1.parquet';z=pd.read_parquet(hp)
  rows=[dict(sid=s,day=d,score=float(scores[dates.get_indexer([pd.Timestamp(d)])[0],cols[s]])) for d in [m['warm_through']]+m['days'] for s in m['sectors']]
  z=pd.concat([z,pd.DataFrame(rows)],ignore_index=True);assert not z.duplicated(['sid','day']).any();z.to_parquet(hp,index=False)
  m['files']['h1']['sha256']=sha(hp);write(path,m)
  f['summary'][k]['manifest_sha256']=sha(path)
 write(root/'BASE_EXPORT_FREEZE.json',read(root/'FREEZE.json'));write(root/'FREEZE.json',f)
 write(root/'FINALIZED.json',dict(legacy_sector_H1_attribution_added=90,source_h1_sha256=sha(p),no_new_signal_or_account=True))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();finalize(a.root)
