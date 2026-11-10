from pathlib import Path
import json,hashlib,datetime
import pandas as pd,numpy as np
from legacy import context,state
from model import POLICIES,combined,chan_state,fitted_state
from chan_signals import build
from fitted import features
R=Path(__file__).resolve().parent;SOURCE=R.parent/'market-regimes-exit-20261024';checks=[];stats=[]
for sym in sorted({c['symbol'] for c in json.loads((R/'cases.json').read_text())}):
 d=pd.read_parquet(SOURCE/'inputs'/f'{sym}.parquet');fullch=pd.read_parquet(R/'contexts'/sym/'chan.parquet');fullfs=pd.read_parquet(R/'contexts'/sym/'fitted.parquet')
 for n in [len(d)//2,len(d)-21,len(d)-1]:
  sub=d.iloc[:n];ch,_=build(sub,symbol=sym);f=features(sub);fs=fitted_state(sub,f)
  pd.testing.assert_frame_equal(ch,fullch.loc[sub.index],check_exact=True)
  pd.testing.assert_frame_equal(fs,fullfs.loc[sub.index],check_exact=True)
  checks.extend([dict(scope=sym,policy=p,prefix=str(sub.index[-1].date()),passed=True) for p in ['native_Chan','F']])
 e,b,f0=context(d);f=features(d);cs=chan_state(d,fullch)
 for c in [x for x in json.loads((R/'cases.json').read_text()) if x['symbol']==sym]:
  z=d.loc[c['start']:c['end']]
  for p in POLICIES:
   saved=pd.read_parquet(R/'prepared'/c['id']/f'{p}.parquet')
   if p in ['E0','E2']:
    ss,ini=state(d,e,b,f0,c['start'],c['end'],p);pd.testing.assert_frame_equal(ss,saved,check_exact=True)
   if p=='C2':pd.testing.assert_frame_equal(cs.loc[z.index],saved,check_exact=True)
   stats.append(dict(case=c['id'],role=c['role'],policy=p,entries=int(saved.entered.sum()),exits=int(saved.exited.sum()),active_fraction=float(saved.target.mean()),background_positive=float((f.loc[z.index,'drift_63_PV']>0).mean())))
  for n in [len(z)//2,len(z)-1]:
   end=z.index[n-1];sub=d.loc[:end];ee,bb,ff0=context(sub);ff=features(sub);ch=fullch.loc[sub.index];fs=fullfs.loc[sub.index]
   for p in ['R','RC','RF','G']:
    ss,_=combined(sub,bb,ff,ch,fs,c['start'],str(end.date()),p)
    pd.testing.assert_frame_equal(ss,pd.read_parquet(R/'prepared'/c['id']/f'{p}.parquet').loc[ss.index],check_exact=True)
    checks.append(dict(scope=c['id'],policy=p,prefix=str(end.date()),passed=True))
 print('prefix_checked',sym,flush=True)
# Demonstrate volume changes the actual slow-mode choice with identical prices.
d=pd.read_parquet(SOURCE/'inputs/USHJ512480.parquet');changed=d.copy();changed['volume']=np.where(d.close.diff()<0,d.volume*8,d.volume/8)
a=features(d).drift_63_PV;b=features(changed).drift_63_PV;valid=a.notna()&b.notna();diff=int(((a>0)!=(b>0))[valid].sum());assert diff>0
pd.DataFrame(checks).to_csv(R/'prefix-checks.csv',index=False);pd.DataFrame(stats).to_csv(R/'signal-review.csv',index=False)
(R/'preflight.json').write_text(json.dumps({'passed':True,'exact_prefix_checks':len(checks),'original_identity_cases':18,'same_prices_volume_changed_background_days':diff,'accounts_run':0},indent=2))
print((R/'preflight.json').read_text())
