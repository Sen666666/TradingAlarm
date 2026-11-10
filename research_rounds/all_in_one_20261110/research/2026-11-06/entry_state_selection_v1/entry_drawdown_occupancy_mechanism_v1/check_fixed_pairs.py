from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;P=R/'entry_positive_never_profit_attribution_v1';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
paths=[O/'PROTOCOL.json',Path(__file__),P/'PAIRED_FEATURES.csv',P/'FIXED_CASE_PAIRS.csv',R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/MU5.parquet',U/'STOCK_MANIFEST.json']
hashes={str(p):sha(p) for p in paths};pairs=pd.read_csv(paths[2],dtype={'window':str});pairs=pairs[pairs.scope.eq('SAME_EVENT_AND_STATE')].copy();mu=pd.read_parquet(paths[4]);cal=mu.index;sm={x['symbol']:x for x in json.load(open(paths[5]))}
def feature(x):
 dr=np.diff(x);v=abs(dr).sum();dd=np.maximum.accumulate(x)-x;a=dd[1:].mean()
 return dict(V=v,A=a,Q=1-a/v if v>0 else np.nan,ER=(x[-1]-x[0])/v if v>0 else np.nan,net21=x[-1]-x[0],max_DD=max(dd),current_DD=dd[-1],underwater_days=int((dd[1:]>0).sum()),peak_day_offset=int(np.argmax(x)),up_sum=np.maximum(dr,0).sum(),down_sum=np.maximum(-dr,0).sum())
keys=set((r.event_id,r.day,r.loss_sid) for r in pairs.itertuples())|set((r.event_id,r.day,r.win_sid) for r in pairs.itertuples());rows=[];daily=[];prefix=[]
for eid,day,sid in sorted(keys):
 m=sm[sid];sp=Path(next(z for z in m['source_sha256'] if z.endswith('/signal.parquet')));fp=Path(m['refs']['facts']);cp=Path(m['refs']['CP1']);raw=pd.read_parquet(sp);facts=pd.read_parquet(fp);cr=pd.read_parquet(cp);hashes[str(sp)]=sha(sp);hashes[str(fp)]=sha(fp);hashes[str(cp)]=sha(cp)
 t=pd.Timestamp(day);k=cal.get_loc(t);ds=cal[max(0,k-21):k+1];w=raw.reindex(ds);ff=facts.reindex(ds)
 valid=w.observed_bar.eq(True)&w.price_eligible.eq(True)&~w.source_invalid.eq(True)&~w.synthetic_event_bar.eq(True)&w.raw_close.gt(0)
 same=w[['source_kind','source_path','segment_id','adjustment_factor']].notna().all().all() and w[['source_kind','source_path','segment_id','adjustment_factor']].nunique().eq(1).all()
 coordinate=np.allclose(w.raw_close*w.adjustment_factor,ff.close,rtol=1e-12,atol=1e-10,equal_nan=False)
 known=len(w)==22 and valid.all() and same and coordinate
 row=dict(event_id=eid,day=day,sid=sid,known=bool(known),known_reason='KNOWN' if known else ('SHORT_WINDOW' if len(w)!=22 else 'SOURCE_FACTOR_OR_VALIDITY_UNKNOWN'),mu5=float(mu.at[t,sid]),CP_receipt=cr.at[t,'receipt'],CP_credit=cr.at[t,'credit'],CP_displacement=cr.at[t,'displacement'],CP_scale=cr.at[t,'scale'])
 if known:
  x=np.log(ff.close.to_numpy());v=feature(x);row.update(v)
  # Fresh physical prefix load then reindex; no rows after t can influence the function.
  zz=np.log(facts.loc[:t].reindex(ds).close.to_numpy());vv=feature(zz)
  assert all((np.isnan(a) and np.isnan(vv[c])) or a==vv[c] for c,a in v.items());prefix.append(dict(event_id=eid,sid=sid,day=day,exact=True))
  assert 0<=v['Q']<=1 and -1<=v['ER']<=1
  dd=np.maximum.accumulate(x)-x
  for j,d in enumerate(ds):daily.append(dict(event_id=eid,sid=sid,day=d,log_close=x[j],raw_close=w.raw_close.iloc[j],frontier_log=np.maximum.accumulate(x)[j],drawdown_log=dd[j],signal_day=day))
 rows.append(row)
f=pd.DataFrame(rows);f.to_csv(O/'FIXED_PAIR_FEATURES.csv',index=False);pd.DataFrame(daily).to_csv(O/'FIXED_PAIR_DAILY.csv',index=False);pd.DataFrame(prefix).to_csv(O/'PREFIX_QA.csv',index=False)
for side in ['loss','win']:
 z=f.rename(columns={'sid':side+'_sid',**{c:side+'_'+c for c in f.columns if c not in ['event_id','day','sid']}})
 pairs=pairs.merge(z,on=['event_id','day',side+'_sid'],validate='many_to_one')
pairs['both_known']=pairs.loss_known&pairs.win_known
for c in ['Q','ER','V','A','net21','max_DD','current_DD','underwater_days','mu5']:pairs['difference_'+c]=pairs['win_'+c]-pairs['loss_'+c]
pairs.to_csv(O/'FIXED_PAIRS_WITH_FEATURES.csv',index=False)
s=[]
for w,g in pairs.groupby('window'):
 z=g[g.both_known];pos=z[z.loss_net21.gt(0)&z.win_net21.gt(0)]
 for scope,v in [('ALL_KNOWN',z),('BOTH_NET21_POSITIVE_CONTROL',pos)]:
  for c in ['Q','ER','V','A','net21','max_DD','current_DD','underwater_days','mu5']:
   s.append(dict(window=w,scope=scope,metric=c,total_pairs=len(g),known_pairs=len(v),dates=v.day.nunique(),win_larger=int(v['difference_'+c].gt(0).sum()),loss_median=v['loss_'+c].median(),win_median=v['win_'+c].median(),median_difference=v['difference_'+c].median(),date_equal_difference=v.groupby('day')['difference_'+c].mean().mean()))
ss=pd.DataFrame(s);ss.to_csv(O/'PAIR_DESCRIPTION.csv',index=False)
fixed=pd.read_csv(paths[3],dtype={'window':str});fixed=pairs.merge(fixed[['event_id','loss_sid','win_sid']],on=['event_id','loss_sid','win_sid'],validate='one_to_one');fixed.to_csv(O/'NAMED_CASE_PAIRS.csv',index=False)
synthetic=[]
for name,x in [('SLOW_REPAIR',[0,.02,.01,.01,.02,.03]),('QUICK_REPAIR',[0,.02,.02,.02,.01,.03]),('MONOTONE_UP',[0,.01,.02,.03,.04,.05]),('MONOTONE_DOWN',[0,-.01,-.02,-.03,-.04,-.05]),('FLAT',[0,0,0,0,0,0])]:
 synthetic.append(dict(name=name,log_path=x,**feature(np.array(x))))
a,b=synthetic[:2];assert abs(a['V']-b['V'])<1e-12 and abs(a['ER']-b['ER'])<1e-12 and a['max_DD']==b['max_DD'] and a['current_DD']==b['current_DD'];assert a['Q']<b['Q']
# Exact transform overlap at an ending maximum: frontier advancement / positive variation is 2ER/(1+ER).
for s0 in synthetic:
 if s0['net21']>0 and s0['current_DD']==0:assert abs(s0['net21']/s0['up_sum']-2*s0['ER']/(1+s0['ER']))<1e-12
x=np.array([0,.02,.01,.01,.02,.03]);q=feature(x)['Q'];assert abs(feature(x*1e-12)['Q']-q)<1e-12
save('SYNTHETIC_CHECKS.json',synthetic)
assert all(sha(p)==h for p,h in hashes.items());save('SOURCE_HASHES.json',hashes)
save('QA.json',dict(frozen_pairs=len(pairs),unique_event_stock_features=len(f),known=int(f.known.sum()),known_pairs=int(pairs.both_known.sum()),prefix_checks=len(prefix),bounded_Q=True,no_epsilon_division=True,scale_invariance=True,no_parameter_scan=True,no_new_ranking=True,no_new_economic_simulation=True,source_hashes_unchanged=True,outcome_conditioned_pairs_not_incremental_predictive_test=True))
print('SUMMARY\n',ss.to_string(index=False))
show=['window','day','loss_name','win_name','both_known','loss_PVR_score','win_PVR_score','loss_Q','win_Q','loss_ER','win_ER','loss_A','win_A','loss_net21','win_net21','loss_underwater_days','win_underwater_days','loss_mu5','win_mu5']
print('NAMED\n',fixed[show].to_string(index=False));print('SYNTHETIC',synthetic)
