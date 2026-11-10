from pathlib import Path
import sys,json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];BASE=ROOT/'research_rounds/tech-finite-compound-20261026';ORIG=BASE/'prepared-v2'
sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'))
from data_utils import eligible_prices
from model import run
SYMS=['688498.SH','300308.SZ','300502.SZ','688256.SH','001309.SZ','688195.SH','603256.SH','603061.SH','603115.SH','688048.SH','688432.SH','300475.SZ']
if __name__=='__main__':
 name=sys.argv[1];rev=int(name[-1]);price=name.startswith('P');out=O/name;out.mkdir(exist_ok=False);(out/'traces').mkdir();audit=[]
 for policy in ['H','C']:
  p=out/policy/'prepared';(p/'facts').mkdir(parents=True);(p/'h1.npz').symlink_to(ORIG/'h1.npz')
 for path in sorted((ORIG/'facts').glob('*.parquet')):
  f=pd.read_parquet(path);sid=path.stem
  if sid.startswith('URFI'):
   for pol in ['H','C']:f.to_parquet(out/pol/'prepared/facts'/path.name)
   continue
  raw=eligible_prices(pd.read_parquet(ORIG/'signals'/path.name));assert raw.index.equals(f.index);assert set(raw.amount_unit.dropna())=={'CNY'}
  z=run(raw,rev,price);z.to_parquet(out/'traces'/path.name)
  for pol in ['H','C']:
   new=f.copy();new['e0_ready']=z.ready;new['e0_target']=z.h_target;new['e0_floor']=z.h_floor;new['i_target']=z[pol.lower()+'_target'];new['i_floor']=z[pol.lower()+'_floor'];new['i_buy']=z[pol.lower()+'_buy'];new.to_parquet(out/pol/'prepared/facts'/path.name)
  audit.append(dict(symbol=sid,rows=len(raw),last=str(raw.index[-1].date()),missing_amount=int((~np.isfinite(raw.amount)|raw.amount.le(0)).sum()),events=int(z.loc['2024':].event.ne(0).sum()),shocks=int(z.loc['2024':].shock.sum()),up=int(z.loc['2024':].event.eq(1).sum()),source_sha=hashlib.sha256((ORIG/'signals'/path.name).read_bytes()).hexdigest()))
 pd.DataFrame(audit).to_csv(out/'input-audit.csv',index=False);print(name,len(audit),'missingamount',sum(x['missing_amount'] for x in audit),'last',sorted(set(x['last'] for x in audit)),flush=True)
