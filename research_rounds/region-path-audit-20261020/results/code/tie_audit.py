import sys,json,hashlib
from pathlib import Path
import pandas as pd,numpy as np
b=Path(__file__).resolve().parents[1];o=b/'results';pr=json.loads((o/'tie-protocol.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(Path(__file__))==pr['code_sha256']
s=Path(pr['source']);sys.path.insert(0,str(s/'code'));from trend_price_region import quantiles
rows=[]
for p in sorted(s.glob('*-signals.csv')):
 assert sha(p)==pr['inputs'][str(p)]
 f=pd.read_csv(p,index_col='date',parse_dates=True);f=f.loc[f.close.gt(0)&f.volume.gt(0)&np.isfinite(f.close)&np.isfinite(f.volume)];y=np.log(f.close/f.close.iloc[0]).to_numpy();w=np.sqrt(f.volume/f.volume.iloc[0]).to_numpy();delta=np.full(len(f),np.nan)
 for i in range(20,len(f)):
  z=y[i-20:i+1];v=w[i-20:i+1];delta[i]=np.max(np.abs(quantiles(z,v)-quantiles(z[::-1],v[::-1])))
 affected=delta>1e-12;any_evidence=affected.copy();any_evidence[21:] |= affected[:-21]
 rows.append(dict(symbol=p.name.removesuffix('-signals.csv'),blocks=len(f)-20,affected_blocks=int(affected.sum()),max_log_quantile_change=float(np.nanmax(delta)),entry_n=int(f.entered.sum()),affected_entries=int((any_evidence&f.entered.eq(1).to_numpy()).sum()),exit_n=int(f.exited.sum()),affected_exits=int((any_evidence&f.exited.eq(1).to_numpy()).sum())))
pd.DataFrame(rows).to_csv(o/'tie-sensitivity.csv',index=False);print(pd.DataFrame(rows).to_string(index=False))
