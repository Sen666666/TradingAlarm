"""Frozen k10 T-only industry diagnostics. Consume ranks; no ranking/model/account."""
from pathlib import Path
import hashlib,importlib.util,json,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;V6=O.parent;SEL=V6.parent
FEATURE=V6/'features/DAILY_SHRINKAGE_FEATURES.parquet'
LABEL=SEL/'industry_channels_v2/diagnostics/INDUSTRY_PRICE_PATH_LABELS.parquet'
OLDT=SEL/'separated_momentum_v4/ranking/STUDY_STATES_2022_2026.parquet'
HELPER=SEL/'continuous_rank_v3/evaluation/evaluation_core.py'
HELPER_SHA='e353179c2a27ebe5ff289131c58c16daa64f0ce554c7663c941310cab1dbbc01'
SOURCES={};PRIMARY='REL_MFE20_PRIMARY_tail'
METHODS={'T0_ORIGINAL':'T0_selected','T10_KAPPA10':'T10_selected'}
VALUES=[f'{kind}20_{tag}_log'for tag in ['abs','rel']for kind in ['final','mfe','mae']]
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert h==expected,(str(p),'SHA mismatch')
 SOURCES[str(p)]=h;return p
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def save(n,f):f.to_parquet(O/(n+'.parquet'),index=False);f.to_csv(O/(n+'.csv'),index=False)
def strata(f):
 return {'ALL':pd.Series(True,index=f.index),'SPARSE_N_LE10':f.n.le(10),'N1':f.n.eq(1),'N2_TO10':f.n.between(2,10),'DENSE_N_GT10':f.n.gt(10)}
def ratio(a,b):return float(a/b)if b else np.nan
def describe(z,H):
 r={'industry_days':len(z),'unique_days':int(z.date.nunique()),'label20_known':int(z.label_valid20.eq(True).sum())}
 for c in VALUES:
  for stat,value in H.distribution(z.loc[z.label_valid20.eq(True),c]).items():r[c+'_'+stat]=value
 for tag in ['abs','rel']:
  q=z.loc[z.label_valid20.eq(True),f'final20_{tag}_log'].dropna();r[f'final20_{tag}_nonpositive_count']=int(q.le(0).sum());r[f'final20_{tag}_nonpositive_rate']=float(q.le(0).mean())if len(q)else np.nan
 return r
def main():
 begun=time.monotonic();bind(__file__);bind(V6/'FROZEN_CONTRACT.txt');bind(O/'EXECUTION_CONTRACT.txt')
 spec=importlib.util.spec_from_file_location('v6_frozen_v3_helpers',bind(HELPER,HELPER_SHA));H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
 d=pd.read_parquet(bind(FEATURE));assert len(d)==97650 and not d.duplicated(['date','sector_id_static']).any()
 assert d.groupby('date').size().eq(90).all()and d.n.gt(0).all()
 for c in METHODS.values():d[c]=d[c].astype('boolean');assert d[c].notna().all()and d.groupby('date')[c].sum().eq(3).all()
 old=pd.read_parquet(bind(OLDT),columns=['date','sector_id_static','T_selected']).rename(columns={'T_selected':'original_cached_T_selected'})
 d=d.merge(old,on=['date','sector_id_static'],validate='one_to_one');assert d.T0_selected.equals(d.original_cached_T_selected.astype('boolean'))
 d=d.merge(pd.read_parquet(bind(LABEL)),on=['date','sector_id_static'],validate='one_to_one').sort_values(['date','sector_id_static']).reset_index(drop=True)
 assert len(d)==97650;d['study_window']=d.date.map(H.study_window);d['year']=d.date.str[:4];d['month']=d.date.str[:7]
 d['all90_reference']=True;tail=H.future_tail_columns(d,reference_column='all90_reference');assert tail[['date','sector_id_static']].equals(d[['date','sector_id_static']])
 d=pd.concat([d,tail.drop(columns=['date','sector_id_static'])],axis=1)
 d.to_parquet(O/'ALL90_EVALUATION_PANEL.parquet',index=False)
 alltail_byday=d.groupby('date')[PRIMARY].sum()
 selected=[];daily=[];summaries=[]
 for method,col in METHODS.items():
  z=d.loc[d[col].eq(True)].copy();z['method']=method;selected.append(z)
  for stratum,mask in strata(d).items():
   sub=d.loc[mask];sel=sub.loc[sub[col].eq(True)]
   # If a sparse stratum is absent on a known comparison day, it still has
   # zero selected/hits against that day's all90 future-tail denominator.
   byday={day:g for day,g in sub.groupby('date',sort=True)};empty=sub.iloc[:0]
   for day in sorted(d.date.unique()):
    g=byday.get(day,empty)
    sg=g.loc[g[col].eq(True)];hit=int(sg[PRIMARY].sum());tailN=int(g[PRIMARY].sum());known=int((sg.label_valid20.eq(True)&np.isfinite(sg.mfe20_rel_log)).sum())
    alltail=int(alltail_byday.loc[day])
    daily.append(dict(date=day,study_window=H.study_window(day),year=day[:4],month=day[:7],method=method,stratum=stratum,selected=len(sg),selected_label_known=known,hits=hit,tailN_in_stratum=tailN,tailN_all90=alltail,coverage_within_stratum=ratio(hit,tailN),coverage_of_all90_tail=ratio(hit,alltail),precision=ratio(hit,known),tail_empty_in_stratum=tailN==0))
   for grouping in ['study_window']:
    for period,g in sub.groupby(grouping):
     zz=g.loc[g[col].eq(True)];rr=dict(grouping=grouping,period=period,method=method,stratum=stratum,**describe(zz,H));hit=int(zz[PRIMARY].sum());den=int(g[PRIMARY].sum());known=int((zz.label_valid20.eq(True)&np.isfinite(zz.mfe20_rel_log)).sum())
     alltail=int(d.loc[d[grouping].eq(period),PRIMARY].sum());rr.update(tail_hits=hit,tailN_in_stratum=den,tailN_all90=alltail,coverage_within_stratum=ratio(hit,den),coverage_of_all90_tail=ratio(hit,alltail),precision=ratio(hit,known))
     summaries.append(rr)
 save('SELECTED_EXISTING_LABELS',pd.concat(selected,ignore_index=True));dt=pd.DataFrame(daily);save('DAILY_TAIL_EXPOSURE_COUNTS',dt);su=pd.DataFrame(summaries)
 for i,r in su.iterrows():
  q=dt.loc[dt[r.grouping].eq(r.period)&dt.method.eq(r.method)&dt.stratum.eq(r.stratum)]
  su.loc[i,'mean_daily_coverage_of_all90_tail']=q.coverage_of_all90_tail.mean();su.loc[i,'mean_daily_coverage_within_stratum']=q.coverage_within_stratum.mean();su.loc[i,'mean_daily_precision']=q.precision.mean()
 save('PATH_TAIL_EXPOSURE_BY_PERIOD_AND_N',su)
 # Selection changes are frozen flags, never selected by future outcomes.
 d['change_group']=np.select([(d.T10_selected.eq(True)&~d.T0_selected.eq(True)).to_numpy(dtype=bool),(d.T0_selected.eq(True)&~d.T10_selected.eq(True)).to_numpy(dtype=bool),(d.T0_selected.eq(True)&d.T10_selected.eq(True)).to_numpy(dtype=bool)],['ADDED_T10','REMOVED_T0','RETAINED_BOTH'],default='NEITHER')
 changed=d.loc[d.change_group.ne('NEITHER')].copy();save('ORIGINAL_ADDED_REMOVED_RETAINED_SIGNALS',changed)
 changes=[];net=[]
 for grouping in ['study_window']:
  for period,gg in d.groupby(grouping):
   for stratum,mask in strata(gg).items():
    z=gg.loc[mask];counts={}
    for group in ['ADDED_T10','REMOVED_T0','RETAINED_BOTH']:
     q=z.loc[z.change_group.eq(group)];rr=dict(grouping=grouping,period=period,stratum=stratum,change_group=group,**describe(q,H));rr['tail_hits']=int(q[PRIMARY].sum());changes.append(rr);counts[group]=(len(q),int(q[PRIMARY].sum()))
    net.append(dict(grouping=grouping,period=period,stratum=stratum,added=counts['ADDED_T10'][0],removed=counts['REMOVED_T0'][0],added_tail_hits=counts['ADDED_T10'][1],removed_tail_hits=counts['REMOVED_T0'][1],net_tail_hits=counts['ADDED_T10'][1]-counts['REMOVED_T0'][1]))
 save('CHANGED_SIGNAL_PATHS_BY_PERIOD_AND_N',pd.DataFrame(changes));save('ADDED_MINUS_REMOVED_TAIL_HITS',pd.DataFrame(net))
 # A zero net number of above-MA stocks does not prove no stock crossed.
 assert np.allclose(d.D_shrunk,d.Self+d.Market,rtol=0,atol=1e-14)
 d['du_zero_drift']=np.select([d.du.eq(0)&d.D_shrunk.gt(0),d.du.eq(0)&d.D_shrunk.lt(0),d.du.eq(0)&d.D_shrunk.eq(0)],['NET_COUNT_UNCHANGED_POSITIVE_MARKET_DRIFT','NET_COUNT_UNCHANGED_NEGATIVE_MARKET_DRIFT','NET_COUNT_UNCHANGED_ZERO'],default='NET_COUNT_CHANGED')
 for c in ['a5_D_shrunk','a5_Self','a5_Market']:
  assert d.groupby('sector_id_static')[c].apply(lambda q:q.iloc[:5].isna().all()).all(),c
 known=d[['a5_D_shrunk','a5_Self','a5_Market']].notna().all(axis=1);assert np.allclose(d.loc[known,'a5_D_shrunk'],d.loc[known,'a5_Self']+d.loc[known,'a5_Market'],rtol=0,atol=1e-14)
 drift=[]
 for win,g in d.groupby('study_window'):
  for stratum,mask in strata(g).items():
   for driftclass,q in g.loc[mask].groupby('du_zero_drift'):
    rr=dict(study_window=win,stratum=stratum,drift_class=driftclass,industry_days=len(q),T0_selected=int(q.T0_selected.sum()),T10_selected=int(q.T10_selected.sum()))
    for c in ['Self','Market','D_original','D_shrunk','a5_D_original','a5_D_shrunk','a5_Self','a5_Market']:
     for stat,value in H.distribution(q[c]).items():rr[c+'_'+stat]=value
    drift.append(rr)
 save('NET_COUNT_UNCHANGED_MARKET_DRIFT_AND_ACCELERATION',pd.DataFrame(drift))
 cc=pd.read_csv(bind(O/'FROZEN_V5_CASE_MAPPING_168.csv'));case=cc.merge(d,on=['date','sector_id_static'],how='left',validate='many_to_one',suffixes=('','_daily'));assert len(case)==168 and case.n.notna().all();save('FIXED_V5_CASES_ALL_RANKS_AND_LABELS',case)
 # Root explicitly predeclared the original 924 cutoff as the small-N example.
 focal=d.loc[d.date.eq('2024-09-24')&d.industry_static.isin(['厨卫电器','软件开发','半导体','通信设备'])].copy();assert len(focal)==4;save('PREDECLARED_924_CUTOFF_AND_FOCAL',focal)
 dump('SOURCE_SHA256.json',SOURCES);dump('RUN_STATUS.json',dict(status='COMPLETE',rows=len(d),days=int(d.date.nunique()),all90_known=True,each_method_N=3,kappa=10,labels_reused=True,new_ranks_in_evaluator=0,new_labels=0,new_accounts=0,first5_acceleration_unknown=True,seconds=time.monotonic()-begun))
 print(su.loc[su.grouping.eq('study_window')&su.stratum.eq('ALL'),['period','method','industry_days','final20_rel_log_mean','final20_abs_nonpositive_rate','tail_hits','tailN_all90','coverage_of_all90_tail','precision']].to_string(index=False),flush=True)
 print(pd.DataFrame(net).loc[lambda q:q.grouping.eq('study_window')].to_string(index=False),flush=True)
if __name__=='__main__':main()
