"""Predefined descriptive groups/correlations and one stock-balanced R+depth WLS."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,time,hashlib,os
import numpy as np,pandas as pd
T=time.monotonic();O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
for p,h in read(O/'FEATURE_FREEZE.json')['sha256'].items():assert sha(p)==h,p
f=pd.read_csv(O/'observation-ledger.csv',dtype=str).fillna('');assert len(f)==12972 and f.epoch_id.is_unique
for k in ['R','depth','wait_valid_price_observations','up_log_amplitude_x','post_end_price_change','post_MFE','post_MAE','post_observations']:f[k]=pd.to_numeric(f[k],errors='coerce')
f['has_T1']=f.T1.ne('');f['ended']=f.end_kind.eq('E0_off');ended=f[f.ended&f.has_T1&f.post_end_price_change.notna()].copy();censored=f[~f.ended&f.has_T1].copy();assert len(ended)==8715 and (ended.post_observations>0).all()
def weights(g):return 1/g.groupby('symbol').symbol.transform('size').to_numpy(float)
def corr(x,y,w):
 x=np.asarray(x,float);y=np.asarray(y,float);w=np.asarray(w,float);w=w/w.sum();dx=x-np.sum(w*x);dy=y-np.sum(w*y);den=np.sqrt(np.sum(w*dx*dx)*np.sum(w*dy*dy));return float(np.sum(w*dx*dy)/den) if den else None
def describe(g):
 cols=['R','depth','wait_valid_price_observations','post_end_price_change','post_MFE','post_MAE','post_observations'];means=g.groupby('symbol')[cols].mean()
 return dict(events=len(g),stocks=int(g.symbol.nunique()),event_mean={c:float(g[c].mean()) if g[c].notna().any() else None for c in cols},event_median={c:float(g[c].median()) if g[c].notna().any() else None for c in cols},stock_equal_mean={c:float(means[c].mean()) if means[c].notna().any() else None for c in cols},event_positive_end_fraction=float((g.post_end_price_change>0).mean()) if len(g) else None,stock_equal_positive_end_fraction=float(g.assign(pos=(g.post_end_price_change>0).astype(float)).groupby('symbol').pos.mean().mean()) if len(g) else None)
coverage={}
for tag,g in [('all_T0',f),('ended_E0',f[f.ended]),('right_censored',f[~f.ended])]:coverage[tag]=dict(T0=len(g),stocks=int(g.symbol.nunique()),observed_T1=int(g.has_T1.sum()),observed_T1_event_fraction=float(g.has_T1.mean()),observed_T1_stock_equal_fraction=float(g.groupby('symbol').has_T1.mean().mean()),no_T1=int((~g.has_T1).sum()))
groups={}
for status,g0 in [('ended_E0',ended),('right_censored',censored)]:
 for group,g in g0.groupby('natural_group',sort=True):groups[status+'|'+group]=describe(g)
relations={}
for tag,w in [('event_equal',np.ones(len(ended))),('stock_equal',weights(ended))]:relations[tag]={name:corr(ended[a],ended[b],w) for name,a,b in [('R_depth','R','depth'),('R_post_end_change','R','post_end_price_change'),('depth_post_end_change','depth','post_end_price_change')]}
# Exactly one controlled specification. Center/scale is algebraically equivalent to raw R+depth.
Xraw=ended[['R','depth']].to_numpy(float);y=ended.post_end_price_change.to_numpy(float);w=weights(ended);w=w/w.sum();mx=np.sum(w[:,None]*Xraw,axis=0);sd=np.sqrt(np.sum(w[:,None]*(Xraw-mx)**2,axis=0));assert (sd>0).all();X=np.column_stack([np.ones(len(ended)),(Xraw-mx)/sd]);sw=np.sqrt(w);b,_,rank,_=np.linalg.lstsq(X*sw[:,None],y*sw,rcond=None)
if rank<3:reg=dict(status='unidentified_rank_deficient',rank=int(rank),specification='post_end_price_change ~ 1 + R + depth, stock-balanced WLS')
else:
 beta=b[1:]/sd;intercept=b[0]-np.sum(beta*mx);pred=X@b;SSE=np.sum(w*(y-pred)**2);SST=np.sum(w*(y-np.sum(w*y))**2);reg=dict(status='descriptive_fit_only',specification='post_end_price_change ~ 1 + R + depth, stock-balanced WLS',events=len(ended),stocks=int(ended.symbol.nunique()),intercept=float(intercept),beta_R=float(beta[0]),beta_depth=float(beta[1]),standardized_predictor_beta_R=float(b[1]),standardized_predictor_beta_depth=float(b[2]),weighted_R2=float(1-SSE/SST),rank=int(rank),standardized_design_condition=float(np.linalg.cond(X*sw[:,None])),p_values='not_computed_events_not_independent',limitations='Linear depth adjustment only; sigma/activity missing; variable E0 stopping endpoint and duration remain confounded.')
pos=ended.assign(positive=ended.post_end_price_change.clip(lower=0),negative=(-ended.post_end_price_change).clip(lower=0));by=pos.groupby('symbol')[['positive','negative']].sum();stockmeans=ended.groupby('symbol').post_end_price_change.mean();smpos=stockmeans.clip(lower=0);smneg=(-stockmeans).clip(lower=0)
def tops(series):
 total=float(series.sum());return dict(total=total,top3=[dict(symbol=s,value=float(v)) for s,v in series.sort_values(ascending=False).head(3).items()],top3_fraction=float(series.nlargest(3).sum()/total) if total else None)
concentration=dict(equal_unit_end_changes_not_money=dict(positive=tops(by.positive),negative=tops(by.negative)),stock_mean_changes_not_money=dict(positive=tops(smpos),negative=tops(smneg)))
low=pos[pos.R<1];kept=pos[pos.R>=1];positive_total=float(pos.positive.sum());fields=['epoch_id','symbol','name','start','T0','T1','H','L','C','R','depth','observed_end','post_end_price_change','post_MFE','post_MAE','post_observations']
def examples(g):return json.loads(g[fields].to_json(orient='records',force_ascii=False))
tails=dict(R_below_1=dict(events=len(low),positive_end_events=int((low.post_end_price_change>0).sum()),positive_unit_change_sum=float(low.positive.sum()),negative_unit_change_sum=float(low.negative.sum()),fraction_all_positive_unit_changes=float(low.positive.sum()/positive_total)),R_at_or_above_1=dict(events=len(kept),positive_end_events=int((kept.post_end_price_change>0).sum()),positive_unit_change_sum=float(kept.positive.sum()),negative_unit_change_sum=float(kept.negative.sum()),fraction_all_positive_unit_changes=float(kept.positive.sum()/positive_total)),largest_post_changes_all=examples(ended.nlargest(5,'post_end_price_change')),largest_post_changes_R_below_1=examples(low.nlargest(5,'post_end_price_change')))
quality=dict(R_min=float(ended.R.min()),R_median=float(ended.R.median()),R_max=float(ended.R.max()),depth_min=float(ended.depth.min()),depth_max=float(ended.depth.max()),R_max_case=examples(ended.nlargest(1,'R'))[0],future_labels_start_strictly_after_T1=True,right_censored_not_in_main_association=True,sigma_activity_numeric_lower_bound_unverified_due_cache_gap=True)
res=dict(coverage=coverage,natural_groups=groups,main_closed_T1=describe(ended),right_censored_T1=describe(censored),continuous_relations=relations,single_control=reg,concentration=concentration,R_below_1_tail_retention=tails,quality=quality)
save('RESULTS.json',res)
# Only a display of all points: no range selection, clipping, fitting or threshold search.
try:
 os.environ['MPLCONFIGDIR']=str(O/'mpl-cache')
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,ax=plt.subplots(1,2,figsize=(10,3.7));ax[0].scatter(ended.R,ended.depth,s=3,alpha=.20,rasterized=True);ax[0].set(xscale='log',xlabel='R (log display axis; raw values retained)',ylabel='Depth: 1 - L/H',title='Repair size and preceding depth')
 ax[1].scatter(ended.R,ended.post_end_price_change,s=3,alpha=.20,rasterized=True);ax[1].set(xscale='log',xlabel='R (log display axis)',ylabel='Post-T1 end close / C_T1 - 1',title='Closed E0 periods; price observations')
 fig.tight_layout();fig.savefig(O/'continuous-scatter.png',dpi=160);plt.close(fig)
except ImportError as e:save('PLOT_UNAVAILABLE.json',dict(reason=str(e)))
for p,h in read(O/'FEATURE_FREEZE.json')['sha256'].items():assert sha(p)==h,p
save('ANALYSIS_VERIFICATION.json',dict(passed=True,closed_T1=len(ended),censored_T1=len(censored),only_one_control_model=True,groups_fixed_C_vs_H=True,no_feature_or_threshold_selection=True,no_event_independence_claim=True,trade_paths=0,seconds=time.monotonic()-T));print(json.dumps(dict(coverage=coverage,natural_groups=groups,continuous_relations=relations,single_control=reg,R_below_1= tails['R_below_1'],R_above_1=tails['R_at_or_above_1'],top_post= tails['largest_post_changes_all'],concentration=concentration,quality=quality,seconds=time.monotonic()-T),ensure_ascii=False),flush=True)
