"""Independent existing-table audit, no author analysis imports or accounts."""
from pathlib import Path
from decimal import Decimal
import hashlib,json,signal,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;R=P/'analysis/results_v2';KEY=['window','day','sid']
CONT=['sign_persistence21_w09','logreturn_std20','close_gap_prior_high20','close_location_in_day_range','return5','return20','positive_effective_observations21_w09','sector_return20','sector_sign_persistence21_w09','relative_return20']
PERIODS=[('FULL_2022_2024','2022_2024','2022-01-01','2024-12-31'),('Y2022','2022_2024','2022-01-01','2022-12-31'),('Y2023','2022_2024','2023-01-01','2023-12-31'),('Y2024','2022_2024','2024-01-01','2024-12-31'),('FROM_924','2022_2024','2024-09-24','2024-12-31'),('AFTER_OCT8','2022_2024','2024-10-09','2024-12-31'),('STRONG','strong','2025-07-01','2026-06-30'),('Y2025_H2','strong','2025-07-01','2025-12-31'),('Y2026_H1','strong','2026-01-01','2026-06-30')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def close(a,b):assert np.allclose(np.asarray(a,dtype=float),np.asarray(b,dtype=float),equal_nan=True,rtol=1e-11,atol=1e-12)
def eq(a,b):assert np.array_equal(np.asarray(a),np.asarray(b))
def masks(x):
 yield 'stock_day',np.ones(len(x),bool)
 for role in ['CORE','mobile']:
  m=x.roles.map(lambda a:role.lower()in a)&x[role+'_event_firstseen_in_PRIMARY'].eq(True);yield role+'_source_event_firstseen',m
def main():
 started=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Independent table audit60s')));signal.setitimer(signal.ITIMER_REAL,60)
 source={};validation=load(R/'VALIDATION.json');assert validation['status']=='COMPLETE_FROZEN_DESCRIPTIVE_INFORMATION_ANALYSIS'
 for p,h in load(R/'SOURCE_SHA256.json').items():assert sha(p)==h;source[p]=h
 def read(n):p=R/n;source[str(p)]=sha(p);return pd.read_parquet(p)
 X=read('PRIMARY_FEATURE_GROUPS_PRE_LABEL.parquet');L=read('LABELS.parquet');A=read('ALL3436_ORIGINAL_ECONOMIC_ASSOCIATIONS.parquet');F=read('FIXED_ORIGINAL83_94_IDENTITIES.parquet')
 assert len(X)==133713 and len(L)==133723 and len(A)==3436 and len(F)==177
 assert not X.duplicated(KEY).any() and not L.duplicated(KEY).any() and not A.duplicated(['window','key']).any()
 mf=load(P/'export/FEATURE_MANIFEST_PRE_LABEL.json');Q=pd.read_parquet(P/'export/reference_quotes.parquet');B=pd.read_parquet(P/'export/features.parquet',columns=KEY+['source_segment','stock_source_row_present'])
 labelchecks=[]
 for w,cal in mf['calendars'].items():
  q=Q.loc[Q.window.eq(w)];f=B.loc[B.window.eq(w)];l=L.loc[L.window.eq(w)];n=len(cal);symbols=q.sid.drop_duplicates();shape=(len(symbols),n)
  eq(q[KEY].to_numpy(),f[KEY].to_numpy());eq(q.day.to_numpy().reshape(shape),np.tile(cal,(len(symbols),1)))
  si=pd.Index(symbols).get_indexer(l.sid);ti=pd.Index(cal).get_indexer(l.day);assert (si>=0).all() and (ti>=0).all()
  raw=lambda a:np.asarray(a).reshape(shape)
  C=raw(q.close.to_numpy(float));Op=raw(q.open.to_numpy(float));present=raw(f.stock_source_row_present);obs=raw(q.observed);valid=raw(q.valid);block=raw(q.block.to_numpy(float,na_value=np.nan));seg=raw(f.source_segment.to_numpy(float));good=present&obs&valid&np.isfinite(C)&(C>0)
  same=lambda d:(np.isfinite(block[si,ti])&np.isfinite(block[si,d])&(block[si,ti]==block[si,d])&np.isfinite(seg[si,ti])&np.isfinite(seg[si,d])&(seg[si,ti]==seg[si,d]))
  nxt=np.minimum(ti+1,n-1);openok=(ti+1<n)&good[si,ti]&good[si,nxt]&np.isfinite(Op[si,nxt])&(Op[si,nxt]>0)&same(nxt)
  gap=np.full(len(l),np.nan);gap[openok]=Op[si[openok],nxt[openok]]/C[si[openok],ti[openok]]-1;close(l.next_OPEN_gap,gap)
  for h in [5,20,60]:
   tag='h'+str(h)+'_';end=np.minimum(ti+h,n-1);mature=ti+h<n;endpoint=mature&good[si,ti]&good[si,end]&same(end);known=endpoint&openok
   eq(l[tag+'mature'],mature);eq(l[tag+'status'].eq('KNOWN'),known)
   ro=np.full(len(l),np.nan);rc=ro.copy();ro[known]=C[si[known],end[known]]/Op[si[known],nxt[known]]-1;rc[endpoint]=C[si[endpoint],end[endpoint]]/C[si[endpoint],ti[endpoint]]-1
   close(l[tag+'next_OPEN_return'],ro);close(l[tag+'decision_CLOSE_return'],rc);close(1+rc[known],(1+gap[known])*(1+ro[known]))
   def future_any(a):
    cs=np.pad(np.cumsum(a,axis=1,dtype=np.int32),((0,0),(1,0)));return cs[si,end+1]-cs[si,ti+1]>0
   for name,a in [('any_future_missing',~present),('any_future_nonobserved',present&~obs),('any_future_joint_invalid',present&~valid)]:
    value=l[tag+name];eq(value.isna(),~mature);eq(value.loc[mature].to_numpy(bool),future_any(a)[mature])
   if h==60:
    complete=known&~future_any(~good);eq(l.h60_entire_future_path_valid,complete)
    # Native fixed market offsets t+1..t+60, excluding signal CLOSE.
    v=np.lib.stride_tricks.sliding_window_view(C,60,axis=1);j=np.minimum(ti+1,n-60);hi=v.max(axis=-1)[si,j];lo=v.min(axis=-1)[si,j]
    peak=np.full(len(l),np.nan);low=peak.copy();peak[complete]=hi[complete]/Op[si[complete],nxt[complete]]-1;low[complete]=lo[complete]/Op[si[complete],nxt[complete]]-1
    close(l.h60_max_CLOSE_from_next_OPEN,peak);close(l.h60_min_CLOSE_from_next_OPEN,low);eq(l.h60_future_tail_ge30.isna(),~complete);eq(l.loc[complete,'h60_future_tail_ge30'].to_numpy(bool),peak[complete]>=.3)
   labelchecks.append(dict(window=w,horizon=h,keys=len(l),mature=int(mature.sum()),known=int(known.sum()),close_known=int(endpoint.sum())))
 # Independently reconstruct every daily pre-label quantile from all PRIMARY.
 for name,col,k,labels in [('original_PVR','PVR_quartile',4,['Q1','Q2','Q3','Q4'])]+[(f,'G__'+f,3,['LOW','MID','HIGH'])for f in CONT]:
  value=X[name].where(X.original_PVR_ready if name=='original_PVR'else X[name+'_status'].eq('KNOWN'));r=value.groupby([X.window,X.day]).rank(method='average',pct=True);expected=pd.Series('UNKNOWN',index=X.index);good=r.notna();expected.loc[good]=np.asarray(labels)[np.ceil(r[good]*k).clip(1,k).astype(int)-1];eq(X[col],expected)
 # Full original-money identities; no labels determine inclusion.
 original=P.parent/'structural_failure_v1/state_semantics';moneychecks={}
 for w in ['2022_2024','strong']:
  state=load(original/(w+'_ROWS.json'));a=A.loc[A.window.eq(w)].set_index('layer');assert len(state)==len(a)
  for r in state:
   z=a.loc[r['layer']];assert z.sid==r['sid'] and z.day==r['decision_at'][:10] and Decimal(z.net_source)==Decimal(r['net']) and Decimal(z.cost_source)==Decimal(r['cost'])
  moneychecks[w]=dict(layers=len(a),net=str(sum((Decimal(z)for z in a.net_source),Decimal(0))),own_tail=int(a.own_terminal_tail_ge30.sum()),fixed_current=int(a.fixed_current_tail.sum()))
 eq(A.is_postOct8_303,A.window.eq('2022_2024')&A.opened.str[:10].ge('2024-10-09'));assert A.is_postOct8_303.sum()==303
 assert F.groupby('window').size().to_dict()=={'2022_2024':83,'strong':94} and F.groupby('window').current_No60_exact_key.sum().to_dict()=={'2022_2024':45,'strong':67}
 assert len(A.loc[A.is_postOct8_303])==303 and len(A.loc[A.window.eq('strong')&A.own_terminal_tail_ge30])==123
 # Recalculate ALL4860 period summaries from the actual saved daily pairs.
 D=read('DAILY_PAIRED_CONTRASTS.parquet');S=read('DAY_EQUAL_PAIRED_SUMMARY.parquet');assert len(D)==364713 and len(S)==4860
 sk=['view','axis','horizon','PVR_quartile'];frames=[]
 for period,w,start,end in PERIODS:
  d=D.loc[D.window.eq(w)&D.day.between(start,end)];g=d.groupby(sk,sort=False,dropna=False)
  out=g.agg(stockday_quartile_cells=('day','size'),source_pair_days=('source_pair_available','sum'),label_pair_days=('label_pair_available','sum'))
  for old,new in [('delta_return_median','mean_day_equal_median_return_difference'),('delta_return_mean','mean_day_equal_mean_return_difference'),('delta_win_fraction','mean_day_equal_win_fraction_difference'),('delta_E_mean','mean_day_equal_E_difference'),('delta_PVR_mean','mean_day_equal_PVR_difference')]:out[new]=g[old].mean()
  out=out.reset_index();out['period']=period;out['window']=w;out['pair_day_coverage']=out.label_pair_days/out.source_pair_days.replace(0,np.nan);frames.append(out)
 expected=pd.concat(frames,ignore_index=True).set_index(sk+['period','window']).sort_index();actual=S.set_index(sk+['period','window']).sort_index();eq(expected.index.to_numpy(),actual.index.to_numpy())
 for col in expected:close(expected[col],actual[col])
 # Daily raw-value audit is deliberately sampled, balanced across windows/roles/axes/horizons.
 XL=X.merge(L,on=KEY,validate='one_to_one');sampledates={'2022_2024':['2022-01-21','2022-12-01','2023-07-20','2024-10-09','2024-10-21','2024-12-20'],'strong':['2025-07-14','2025-12-01','2026-04-22','2026-06-29']};dailychecked=0
 for view,mask in masks(XL):
  for w,days in sampledates.items():
   d=XL.loc[mask&XL.window.eq(w)&XL.day.isin(days)];rows=D.loc[D.view.eq(view)&D.window.eq(w)&D.day.isin(days)]
   for (axis,h),r in rows.groupby(['axis','horizon'],sort=False):
    col='G__'+axis;high=r.high_group.iloc[0];low=r.low_group.iloc[0];ret='h'+str(h)+'_next_OPEN_return'
    for _,z in r.iterrows():
     s=d.loc[d.day.eq(z.day)&d.PVR_quartile.eq(z.PVR_quartile)];aa=s.loc[s[col].eq(high)];bb=s.loc[s[col].eq(low)];na=aa[ret].notna();nb=bb[ret].notna()
     close([z.high_mother,z.low_mother],[len(aa)or np.nan,len(bb)or np.nan]);close([z.high_label_count,z.low_label_count],[int(na.sum())if len(aa)else np.nan,int(nb.sum())if len(bb)else np.nan])
     paired=na.any()and nb.any();assert bool(z.label_pair_available)==paired and bool(z.source_pair_available)==(len(aa)>0 and len(bb)>0)
     expected=[aa[ret].median()-bb[ret].median(),aa[ret].mean()-bb[ret].mean(),(aa.loc[na,ret]>0).mean()-(bb.loc[nb,ret]>0).mean(),aa.loc[na,'E'].mean()-bb.loc[nb,'E'].mean(),aa.loc[na,'original_PVR'].mean()-bb.loc[nb,'original_PVR'].mean()]if paired else[np.nan]*5
     close(z[['delta_return_median','delta_return_mean','delta_win_fraction','delta_E_mean','delta_PVR_mean']],expected);dailychecked+=1
 # Every economic grouped row must sum its unchanged original layers, including censored60.
 EG=read('ORIGINAL_ECONOMIC_GROUP_SUMMARIES.parquet');scopes={'ALL3436':np.ones(len(A),bool),'POST_OCT8_303':A.is_postOct8_303,'POST_OCT8_SHORT_LE5_POSTERIOR':A.is_postOct8_303&A.posterior_short_hold_le5,'STRONG_ORDINARY_SHORT_LE5_POSTERIOR':A.window.eq('strong')&A.posterior_short_hold_le5&~A.own_terminal_tail_ge30,'OWN_TERMINAL_TAIL_GE30':A.own_terminal_tail_ge30,'FIXED_CURRENT45_67':A.fixed_current_tail}
 for _,r in EG.iterrows():
  col=r.dimension if r.dimension in ['role','actual_action','signal_year','industry_stage','actual_exit_reasons']else 'G__'+r.dimension;mask=scopes[r.scope]&A.window.eq(r.window)&(A[col].isna()if pd.isna(r['group'])else A[col].eq(r['group']))
  if pd.notna(r.PVR_quartile):mask &= A.PVR_quartile.eq(r.PVR_quartile)
  a=A.loc[mask];assert len(a)==r.layers;close([a.cost.sum(),a.net.sum(),a.positive_contribution.sum(),a.negative_contribution.sum(),a.tail_contribution.sum()],[r.cost,r.original_net,r.positive_contribution,r.negative_contribution,r.own_tail_contribution])
  assert a.own_terminal_tail_ge30.sum()==r.own_tail_count and a.h60_mature.sum()==r.h60_mature and a.h60_entire_future_path_valid.sum()==r.h60_full_future_path
 for p in [Path(__file__),R/'VALIDATION.json',R/'SOURCE_SHA256.json',P/'export/FEATURE_MANIFEST_PRE_LABEL.json',O/'COMPLETED_EXPORT_AND_ANALYSIS_GATE_AUDIT.json']:source[str(p)]=sha(p)
 post=A.loc[A.is_postOct8_303];strongtail=A.loc[A.window.eq('strong')&A.own_terminal_tail_ge30]
 z=dict(status='PASS_INFORMATION_LABELS_GROUPS_ECONOMICS_WITH_SAMPLING_LIMITS',label_endpoint_scope=labelchecks,all_h60_path_extrema=True,all_PRIMARY_prelabel_quantiles=133713,original_economics=moneychecks,original3436_identities_checked=True,fixed83_94_retained=True,current45_67_retained=True,post303_retained=True,all_day_equal_summary_rows=len(S),sampled_raw_daily_pair_rows=dailychecked,sampled_raw_pair_dates=sampledates,economic_group_rows_checked=len(EG),
  overlap_facts=dict(post303_positive_persistence=int(post.sign_persistence21_w09.gt(0).sum()),post303_breakout=int(post.breakout_prior_high20.fillna(False).sum()),strong123_positive_persistence=int(strongtail.sign_persistence21_w09.gt(0).sum()),strong123_breakout=int(strongtail.breakout_prior_high20.fillna(False).sum())),
  limits=['Full label endpoints/nextOPEN/maturity/5-20-60 returns/gaps and max/min60 checked on all133723 saved keys against original stored quote grid; original signal-source certification reuses prior export gate.','All primary continuous quantiles and all4860 day-equal summaries checked; raw daily-pair medians/means checked only on ten listed dates across both windows, all available views/axes/horizons/quartiles.','POOLED_GROUP_SUMMARIES numerical value cells are not independently recalculated in this receipt; no claim of all20322 pooled-statistics audit.','These are dependent descriptive labels and original-lifecycle money associations. No execution feasibility or new-account return is estimated; source snapshot and unknown/missing/censor limits remain.'],technical_note='First own economic-group join selected raw feature name rather than G__feature for continuous axes; corrected own join mapping, without modifying any producer data or outputs.',source_sha256=source,elapsed_seconds=time.monotonic()-started,new_financial_paths=0,new_feature_exports=0,new_label_exports=0,remaining_blocks=[])
 (O/'INFORMATION_RESULTS_V2_AUDIT.json').write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n');signal.setitimer(signal.ITIMER_REAL,0);print(z['status'],round(z['elapsed_seconds'],2),dailychecked,sha(O/'INFORMATION_RESULTS_V2_AUDIT.json'))
if __name__=='__main__':main()
