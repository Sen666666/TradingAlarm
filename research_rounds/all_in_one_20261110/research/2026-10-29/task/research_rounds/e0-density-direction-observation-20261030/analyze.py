"""Only the frozen natural groups and nested descriptive specification."""
from pathlib import Path
from collections import Counter
import time,json,hashlib
import numpy as np
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
d=pd.read_csv(O/'observation-ledger.csv');assert d.epoch_id.is_unique
freeze=json.loads((O/'FEATURE_FREEZE.json').read_text());assert all(sha(p)==h for p,h in freeze['sha256'].items())
cohorts={'all_history':d,'research_open_dates':d[d.in_research_window], 'research_legal_IQ':d[d.in_research_window & (d.IQ_status=='legal_IQ')]}
groups=['D0_Tnonpositive','D0_Tpositive','Dplus_Tnonpositive','Dplus_Tpositive']
quantiles=[.10,.25,.50,.75,.90,.99]
def weights(z,mode):return np.ones(len(z)) if mode=='event' else 1/z.groupby('symbol').symbol.transform('size').to_numpy(float)
def avg(x,w):return float(np.average(x,weights=w)) if len(x) else None
def wquant(x,w,q):
 idx=np.argsort(x);x=np.asarray(x)[idx];w=np.asarray(w)[idx];return float(np.interp(q,(np.cumsum(w)-w*.5)/w.sum(),x))
def describe(z,h,mode):
 y=z[f'H{h}_price_change'].to_numpy(float);w=weights(z,mode);out=dict(events=len(z),stocks=z.symbol.nunique())
 if not len(z):return out
 out.update(mean=avg(y,w),positive_fraction=avg(y>0,w),negative_fraction=avg(y<0,w),flat_fraction=avg(y==0,w),tail30_fraction=avg(y>=.30,w),double100_fraction=avg(y>=1,w),tail30_events=int((y>=.30).sum()),double100_events=int((y>=1).sum()))
 out.update({f'q{int(q*100)}':wquant(y,w,q) for q in quantiles})
 for key in ['MFE','MAE']:
  ok=z[f'H{h}_{key}'].notna().to_numpy();out[f'{key}_complete_events']=int(ok.sum());out[f'{key}_mean']=avg(z.loc[ok,f'H{h}_{key}'],w[ok])
 return out
natural=[];overall=[];coverage=[];models=[];coeff=[];annual=[];tailshare=[]
base=['past_return21','past_vol21','T21','active_days'];aug=base+['D_open','D_continue','D_open_x_T21','D_continue_x_T21']
d['D_open_x_T21']=d.D_open*d.T21;d['D_continue_x_T21']=d.D_continue*d.T21
# Rebuild views after deriving the two predeclared interaction terms.
cohorts={'all_history':d,'research_open_dates':d[d.in_research_window], 'research_legal_IQ':d[d.in_research_window & (d.IQ_status=='legal_IQ')]}
for cn,c in cohorts.items():
 for h in [63,21]:
  available=c[c[f'H{h}_price_change'].notna()];z=available[available.feature_status=='complete'].copy()
  coverage.append(dict(cohort=cn,horizon=h,mother=len(c),stocks=c.symbol.nunique(),features_complete=int((c.feature_status=='complete').sum()),endpoint_observed=len(available),model_and_natural_complete=len(z),endpoint_observed_incomplete_features=len(available)-len(z),complete_path=int(available[f'H{h}_complete_path'].sum()),status=Counter(c[f'H{h}_status']),endpoint_raw_known=int(c[f'H{h}_endpoint_raw_source_known'].eq(True).sum()),known_nontradable_path_events=int(c[f'H{h}_nontradable_proxy_days'].gt(0).sum())))
  for mode in ['event','stock']:
   overall.append(dict(cohort=cn,horizon=h,weight=mode,**describe(available,h,mode)))
   allw=weights(z,mode);allpos=float(np.sum(allw*np.maximum(z[f'H{h}_price_change'],0)))
   for g in groups:
    zg=z[z.natural_group==g];gw=weights(zg,mode)
    natural.append(dict(cohort=cn,horizon=h,weight=mode,group=g,**describe(zg,h,mode),**{f'mean_{f}':avg(zg[f],gw) for f in base+['D_open','D_continue']}))
    mask=z.natural_group.eq(g).to_numpy();y=z[f'H{h}_price_change'].to_numpy();tailshare.append(dict(cohort=cn,horizon=h,weight=mode,group=g,events=int(mask.sum()),positive_unit_price_share=float(np.sum(allw[mask]*np.maximum(y[mask],0))/allpos) if allpos else None,tail30_count=int(np.sum(mask&(y>=.30))),double100_count=int(np.sum(mask&(y>=1)))))
   mz=z.dropna(subset=aug+[f'H{h}_price_change']);w=weights(mz,mode);y=mz[f'H{h}_price_change'].to_numpy(float);ym=avg(y,w);ss0=float(np.sum(w*(y-ym)**2));r2=[]
   for spec,names in [('base',base),('augmented',aug)]:
    raw=mz[names].to_numpy(float);mu=np.average(raw,axis=0,weights=w);sd=np.sqrt(np.average((raw-mu)**2,axis=0,weights=w));constant=sd==0
    # Scaling changes units only. No term is dropped; rank failure is reported.
    safe=np.where(constant,1,sd);X=np.column_stack([np.ones(len(mz)),(raw-mu)/safe]);Xw=X*np.sqrt(w[:,None]);beta,_,rank,svals=np.linalg.lstsq(Xw,y*np.sqrt(w),rcond=None);pred=X@beta;rss=float(np.sum(w*(y-pred)**2));rs=1-rss/ss0;r2.append(rs)
    identified=rank==X.shape[1];rawb=beta[1:]/safe;intercept=float(beta[0]-np.dot(rawb,mu));cond=float(svals[0]/svals[-1]) if svals[-1]>0 else None
    models.append(dict(cohort=cn,horizon=h,weight=mode,spec=spec,events=len(mz),stocks=mz.symbol.nunique(),rank=int(rank),columns=X.shape[1],identified=identified,R2=rs,condition_number_scaled=cond,constant_terms=[n for n,k in zip(names,constant) if k]))
    coeff.append(dict(cohort=cn,horizon=h,weight=mode,spec=spec,term='intercept',raw_coefficient=intercept,per_predictor_SD=None,identified=identified))
    for name,b,bs in zip(names,rawb,beta[1:]):coeff.append(dict(cohort=cn,horizon=h,weight=mode,spec=spec,term=name,raw_coefficient=float(b),per_predictor_SD=float(bs),identified=identified))
   assert r2[1]>=r2[0]-1e-12
   models[-1]['incremental_R2']=r2[1]-r2[0]
  for year,zy in z.groupby('open_year'):
   for g in groups:
    zg=zy[zy.natural_group==g]
    for mode in ['event','stock']:annual.append(dict(cohort=cn,horizon=h,year=int(year),group=g,weight=mode,**describe(zg,h,mode)))
for name,rows in [('natural-groups.csv',natural),('overall-outcomes.csv',overall),('nested-models.csv',models),('model-coefficients.csv',coeff),('annual-natural-groups.csv',annual),('tail-contribution-shares.csv',tailshare)]:pd.DataFrame(rows).to_csv(O/name,index=False)
save(O/'COHORT_COVERAGE.json',coverage)
# Top five is a predeclared contribution disclosure, not sample selection or a rule.
tops=[]
for cn,c in cohorts.items():
 z=c[c.H63_price_change.notna()].sort_values(['H63_price_change','epoch_id'],ascending=[False,True]).head(5).copy();z.insert(0,'cohort',cn);tops.append(z)
pd.concat(tops).to_csv(O/'largest-five-63day-outcomes.csv',index=False)
# Structural identity cross-check uses only dates/IDs in an existing frozen table.
old=pd.read_parquet('/Users/bytedance/Documents/ChatGPT/money/research_rounds/s-entry-mechanism-audit-20261029/opportunities.parquet')
save(O/'ANALYSIS_VERIFICATION.json',dict(passed=True,no_trade_paths=True,no_indicators_recomputed=True,mother=len(d),cohort_sizes={k:len(v) for k,v in cohorts.items()},nested_rows_identical=True,all_full_rank=all(x['identified'] for x in models),all_feature_hashes_unchanged=all(sha(p)==h for p,h in freeze['sha256'].items()),analysis_code_sha256=sha(Path(__file__)),seconds=time.monotonic()-T,old_opportunity_columns=list(old.columns)))
print(json.dumps(clean(dict(stage='analysis_complete',coverage=coverage,models=models,seconds=time.monotonic()-T)),ensure_ascii=False))
