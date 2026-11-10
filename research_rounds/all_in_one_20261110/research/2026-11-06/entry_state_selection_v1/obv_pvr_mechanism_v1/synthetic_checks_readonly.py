import warnings;warnings.filterwarnings('ignore',category=FutureWarning)
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

# Boundary checks on the same frozen function, no alternative formula.
def frame(close,vol=None):
 n=len(close);v=np.ones(n)*100 if vol is None else np.array(vol,dtype=float);c=np.array(close,dtype=float);idx=pd.date_range('2020-01-01',periods=n)
 d=pd.DataFrame(index=idx)
 for k in ['open','high','low','close','raw_open','raw_high','raw_low','raw_close']:d[k]=c
 for k in ['observed_bar','is_observed_bar','price_eligible','volume_eligible']:d[k]=True
 for k in ['source_invalid','synthetic_event_bar']:d[k]=False
 d['segment_id']=0;d['source_kind']='synthetic_test_only';d['source_path']='synthetic_test_only';d['volume_unit']='shares';d['amount_unit']='CNY';d['raw_volume']=v;d['amount']=v*c;d['volume_factor']=1.;d['adjustment_factor']=1.
 return d
n=120;p=frame(100*np.exp(.001*np.arange(n)));z=calc(p);ans={}
ans['all_up_q_one']=bool(np.isclose(z.q.iloc[-1],1))
ans['all_down_q_minus_one']=bool(np.isclose(calc(frame(100*np.exp(-.001*np.arange(n)))).q.iloc[-1],-1))
ans['constant_close_q_zero']=bool(np.isclose(calc(frame(np.ones(n)*100)).q.iloc[-1],0))
p2=p.copy();p2.raw_volume*=1000;p2.amount*=1000;ans['constant_share_unit_scaling_q_invariant']=bool(np.allclose(calc(p2).q,z.q,equal_nan=True))
tiny=calc(frame(100*np.exp(np.log1p(.0001)*np.arange(n))));large=calc(frame(100*np.exp(np.log1p(.1)*np.arange(n))));ans['0.01pct_vs_10pct_up_same_q_full_volume']=bool(np.isclose(tiny.q.iloc[-1],large.q.iloc[-1]))
for col,val in [('amount',0),('raw_volume',0),('source_kind','OTHER'),('source_path','OTHER'),('volume_factor',2.)]:
 bad=p.copy();bad.iloc[-1,bad.columns.get_loc(col)]=val
 ans['last_'+col+'_invalid_or_changed_unknown']=bool(pd.isna(calc(bad).q.iloc[-1]))
neg=calc(frame(100*np.exp(-.001*np.arange(n))));ans['negative_E_preserved']=bool(np.allclose(neg.loc[neg.E.le(0),'fused'],neg.loc[neg.E.le(0),'score'],equal_nan=True))
assert all(ans.values()),ans
print('SYNTHETIC_QA',json.dumps(ans),flush=True)
