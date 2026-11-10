"""Additional independent checks for the fixed GH-PVR consumer; no alternative models."""
from pathlib import Path
import importlib.util,sys,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ghdiag',O/'diagnose.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
ix=pd.bdate_range('2020-01-02',periods=450);checks=[]
def sample(c):
 return pd.DataFrame(dict(close=c,amount=1e8,segment_id=0),index=ix)
for name,c in [('flat',np.full(450,100.)),('rising',100*np.exp(np.arange(450)*.002)),('falling',100*np.exp(-np.arange(450)*.002))]:
 p=sample(c);z=d.calc(p,ix);known=z.PVR_fused.notna();assert known.any()
 if name in ['flat','rising','falling']:np.testing.assert_allclose(z.loc[known,'score'],z.loc[known,'PVR_fused'],rtol=0,atol=1e-12)
 p2=p.copy();p2['close']*=7.3;z2=d.calc(p2,ix);np.testing.assert_allclose(z.q,z2.q,rtol=0,atol=1e-12,equal_nan=True)
 np.testing.assert_allclose(z.PVR_fused,z2.PVR_fused,rtol=0,atol=1e-10,equal_nan=True)
 checks.append(dict(name=name,known=int(known.sum()),score_equal=True,scale_invariant=True))
p=sample(np.full(450,100.));p.iloc[10,p.columns.get_loc('close')]=200.;z=d.calc(p,ix);qq=z.q.dropna();assert qq.min()==.5 and qq.max()==1
changes=qq.diff();roll=changes[changes.gt(0)].index[0];assert p.close.at[roll]==p.close.shift().at[roll]
checks.append(dict(name='old_peak_rolloff',day=str(roll.date()),Q_lift=float(changes.at[roll]),price_unchanged=True))
p=sample(np.full(450,100.));p.iloc[280,p.columns.get_loc('close')]=np.nan;z=d.calc(p,ix);assert z.q.iloc[280:].isna().all();checks.append(dict(name='missing_price_stays_unknown',passed=True))
p=sample(np.full(450,100.));p.iloc[280:,p.columns.get_loc('segment_id')]=1;z=d.calc(p,ix);assert z.q.iloc[280:].isna().all();checks.append(dict(name='source_change_stays_unknown',passed=True))
f=pd.read_csv(O/'FIXED_CASES.csv');m={r['symbol']:r for r in json.load(open(d.MP))};count=0
for row in f.itertuples():
 if not np.isfinite(row.q):continue
 pp=next(p for p in m[row.sid]['source_sha256']if p.endswith('/signal.parquet'));p=pd.read_parquet(pp);dt=pd.Timestamp(row.day);start=dt-pd.DateOffset(months=12);win=p.loc[(p.index>start)&(p.index<=dt),'close'];q=float(p.at[dt,'close']/win.max())
 assert abs(q-row.q)<1e-12;count+=1
out=dict(synthetic_checks=checks,independent_fixed_Q_checks=count,formula='unchanged',no_account=True)
(O/'SUPPLEMENT_AUDIT.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
