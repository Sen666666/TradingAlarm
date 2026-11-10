import warnings; warnings.filterwarnings('ignore', category=FutureWarning)
import pandas as pd,numpy as np,json,sys,hashlib,time
from pathlib import Path
R=Path('.'); M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
F=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design')
sys.path.insert(0,str(F));from features import original_pvr,original_observation_clock
spec={'candidate':'OBV21 signed raw-share pressure, one unoptimized research hypothesis, not standard OBV trading rule','q':'sum(sign(log(Cj/Cprev))*raw_volume_j over21)/sum(raw_volume_j over21)','fusion':'E*=E-max(E,0)*max(0,-q); score*=50+50*tanh(2E*)','scope':'Original legal empty MOBILE only, preserve negative E, direct launch, E0/I/CP/exits; no hard q gate; no account or param search','unknown':'all22 price/quantity-valid observations, same original block, stable nonmissing source_kind and source_path, stable positive volume_factor; adjusted return sign; raw shares; zero volume/amount invalid; no imputation','stage':'Compute original actual 0-to-0 first entries and pre-existing fixed cases only. Proceed to frozen all-opportunity same-day/sector/K only if useful mechanism separation and nontrivial coverage. No formula changes after this print.'}
print('FROZEN_SPEC',json.dumps(spec,ensure_ascii=False),flush=True)
mp={x['symbol']:x for x in json.loads(M.read_text())};end='2026-05-15'
f=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv');f=f[f.account.eq('PVR')].copy()
cases=json.loads((R/'lifecycle_ordered_damage_v1/FIXED_CASES_BEFORE_COMPUTE.json').read_text())
extra=[('300085.SZ','2024-09-24'),('002583.SZ','2024-09-24'),('300666.SZ','2026-01-15'),('301611.SZ','2026-01-15'),('603061.SH','2026-01-15'),('600839.SH','2024-10-18'),('002131.SZ','2024-10-24'),('001896.SZ','2026-02-25'),('002716.SZ','2026-01-15'),('600396.SH','2026-03-16')]
cases+= [dict(sid=s,day=d,selection='preexisting_prior_report_case') for s,d in extra]
want={}
for x in cases:want.setdefault(x['sid'],set()).add(x['day'])
def calc(p):
 v,b=original_observation_clock(p); cols=['raw_open','raw_high','raw_low','raw_close']
 good=v & np.isfinite(p[cols]).all(axis=1)&p[cols].gt(0).all(axis=1)&p.raw_high.ge(p[cols].max(axis=1))&p.raw_low.le(p[cols].min(axis=1))
 for col in ['observed_bar','is_observed_bar','price_eligible','volume_eligible']:good &= p[col].notna()&p[col].eq(True)
 for col in ['source_invalid','synthetic_event_bar']:good &= p[col].notna()&p[col].eq(False)
 good &= p.volume_unit.eq('shares')&p.amount_unit.eq('CNY')&np.isfinite(p.raw_volume)&p.raw_volume.gt(0)&np.isfinite(p.volume_factor)&p.volume_factor.gt(0)&np.isfinite(p.adjustment_factor)&p.adjustment_factor.gt(0)
 unitp=p.amount/p.raw_volume;tol=.5/p.raw_volume+1e-8
 good &= np.isfinite(unitp)&unitp.ge(p.raw_low-tol)&unitp.le(p.raw_high+tol)&(p.raw_close*p.adjustment_factor-p.close).abs().le(1e-10)
 z=original_pvr(p);z['q']=np.nan
 for _,g in p[v].groupby(b[v],sort=False):
  ix=g.index;ok=good.loc[ix].rolling(22,min_periods=22).sum().eq(22)
  for col in ['source_kind','source_path']:
   codes=pd.Series(pd.factorize(g[col])[0],index=ix)
   ok &= codes.rolling(22).min().eq(codes.rolling(22).max())&g[col].notna().rolling(22).sum().eq(22)
  fac=g.volume_factor;ok &= fac.rolling(22).min().eq(fac.rolling(22).max())
  signed=np.sign(np.log(g.close).diff())*g.raw_volume
  den=g.raw_volume.rolling(21,min_periods=21).sum()
  q=(signed.rolling(21,min_periods=21).sum()/den).where(ok&den.gt(0))
  z.loc[ix,'q']=q
 z['fused']=50+50*np.tanh(2*(z.E-z.E.clip(lower=0)*(-z.q).clip(lower=0)))
 return z
parts=[];fixed=[];pre=[];hs=[];t=time.monotonic()
for no,sid in enumerate(sorted(set(f.sid)|set(want))):
 m=mp[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 h=hashlib.sha256(Path(p).read_bytes()).hexdigest();assert h==m['source_sha256'][p]
 raw=pd.read_parquet(p).loc[:end];z=calc(raw)
 g=f[f.sid.eq(sid)];zz=z.reindex(pd.DatetimeIndex(g.signal_day)).reset_index(drop=True);zz['sid']=sid;zz['signal_day']=g.signal_day.to_numpy()
 parts.append(zz)
 if sid in want:
  c=z.reindex(pd.DatetimeIndex(sorted(want[sid]))).copy();c['sid']=sid;c['day']=c.index.strftime('%Y-%m-%d');fixed.append(c)
  for cut in sorted(want[sid]):
   pd.testing.assert_frame_equal(calc(raw.loc[:cut]),z.loc[:cut],check_exact=True);pre.append((sid,cut))
 hs.append((p,h))
 if (no+1)%300==0:print('PROGRESS',no+1,round(time.monotonic()-t,1),flush=True)
a=f.merge(pd.concat(parts,ignore_index=True),on=['sid','signal_day'],validate='one_to_one')
er=(a.PVR_decision-a.score).abs();assert er.max()<1e-10
print('BASELINE',len(a),'closed',int(a.closed.sum()),'win',int((a.closed&a.round_pnl.gt(0)).sum()),'pvr_max_err',er.max(),'q_known',int(a.q.notna().sum()),'fused_known',int(a.fused.notna().sum()),'prefix',len(pre))
def auc(z,col):
 z=z[[col,'round_pnl']].dropna();w=z.round_pnl.gt(0);n=int(w.sum());l=int((~w).sum())
 return (z[col].rank()[w].sum()-n*(n+1)/2)/(n*l) if n*l else None
rows=[]
for kind in ['add','core']:
 for y,g in a[a.first_kind.eq(kind)].groupby('year'):
  cl=g[g.closed];k=cl[cl.q.notna()&cl.score.notna()];neg=k[k.q.lt(0)&k.E.gt(0)]
  rows.append(dict(kind=kind,year=int(y),n=len(g),closed=len(cl),known_closed=len(k),win=int(k.round_pnl.gt(0).sum()),q_negative=int(k.q.lt(0).sum()),penalized=len(neg),penalized_win=int(neg.round_pnl.gt(0).sum()),pvr_auc=auc(k,'score'),q_auc=auc(k,'q'),fused_auc=auc(k,'fused'),q_win=float(k[k.round_pnl.gt(0)].q.mean()),q_loss=float(k[k.round_pnl.le(0)].q.mean())))
print('MECHANISM',json.dumps(rows),flush=True)
c=pd.concat(fixed,ignore_index=True).merge(pd.DataFrame(cases),on=['sid','day'],how='left',validate='one_to_one')
print('FIXED',c[['sid','day','selection','original_round_pnl','score','q','fused']].to_json(orient='records'),flush=True)
# Exact same day/sector pairs among actual MOBILE, original score gap <= 2 points, descriptive not ranking candidate.
mobile=a[a.first_kind.eq('add')&a.closed&a.q.notna()&a.score.notna()]
pair=[]
for (day,sec),g in mobile.groupby(['signal_day','sector']):
 for i in range(len(g)):
  for j in range(i):
   x,y=g.iloc[i],g.iloc[j]
   if abs(x.score-y.score)<=2 and x.q!=y.q:
    hi,lo=(x,y) if x.q>y.q else (y,x)
    pair.append(dict(day=day,hiwin=hi.round_pnl>0,lowin=lo.round_pnl>0,hineg=hi.q<0,loneg=lo.q<0))
print('PAIR_DIAGNOSTIC_ONLY',len(pair),pd.DataFrame(pair).sum(numeric_only=True).to_dict() if pair else {})
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hs)
print('END',time.monotonic()-t,'source_unchanged',True,flush=True)
