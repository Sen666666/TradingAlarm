from pathlib import Path
import json,importlib.util,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('frozen',O/'experiment.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
c=pd.read_parquet(O/'PREDICTIONS.parquet');sel=pd.read_parquet(O/'SEALED_PICKS.parquet')
s=sel.merge(c,left_on='row',right_index=True,validate='many_to_one',suffixes=('_pick',''))
periods=[('ALL',c.index[c.year.ge(2023)])]+[(str(y),c.index[c.year.eq(y)])for y in [2022,2023,2024,2025,2026]]+[('2024_924',c.index[c.day.between('2024-09-24','2024-10-31')]),('2026Q1',c.index[c.day.between('2026-01-01','2026-03-31')])]
rows=[]
for period,ids in periods:
 a=s[s.row.isin(ids)]
 for H in [5,20,60]:
  ok=a.groupby('day')['complete'+str(H)].all();g=a[a.day.isin(ok[ok].index)]
  counts=g.groupby(['day','method']).size().unstack('method')
  assert counts.apply(lambda r:r.nunique(),axis=1).eq(1).all()
  for method,q in g.groupby('method'):
   met=M.evaluation_metrics(q,H);met['ES10_quantile_inclusion40bp']=met.pop('ES10')
   gross=q['ret'+str(H)].to_numpy(float)
   for cost,tag in [(0.,'gross'),(.004,'40bp'),(.01,'100bp')]:
    vv=np.sort(gross-cost);mass=.1*len(vv);k=int(np.floor(mass));rem=mass-k
    tail=(vv[:k].sum()+(rem*vv[k]if rem>0 and k<len(vv)else 0))/mass
    met['ES10_exact_'+tag]=float(-tail);met['positive_'+tag]=float((vv>0).mean())
   rows.append(dict(period=period,H=H,method=method,common_all_methods=True,**met))
pd.DataFrame(rows).to_csv(O/'COMMON_COMPLETE_DATE_METRICS.csv',index=False)
cov=pd.read_csv(O/'ROOT_COVERAGE.csv')
ambig=set(c.loc[c.epoch.eq('None'),'birth_key'])
vc=cov[~cov.key.isin(ambig)]
rootrows=[]
methods=['PVR','MIX_EV_ES','PC','DIRECT_MEAN','HISTORY_MEAN']
for period,mask in [('ALL',vc.year.ge(2023))]+[(str(y),vc.year.eq(y))for y in [2022,2023,2024,2025,2026]]+[('2024_924',vc.birth.between('2024-09-24','2024-10-31')),('2026Q1',vc.birth.between('2026-01-01','2026-03-31'))]:
 b=vc[mask&vc.big60]
 for m in methods:rootrows.append(dict(period=period,method=m,big_roots=len(b),base_captured=int(b.PVR.sum()),captured=int(b[m].sum()),lost=int((b.PVR&~b[m]).sum()),added=int((~b.PVR&b[m]).sum())))
pd.DataFrame(rootrows).to_csv(O/'ROOT_VALID_EPOCH_SENSITIVITY.csv',index=False)
f=pd.read_csv(O/'ORIGINAL_ACTUAL_ASSOCIATION.csv');f['signal_year']=f.signal_day.str[:4];rr=[]
for yr,g in f.groupby('signal_year'):
 for method in methods[1:]:
  q=g[g.closed&g[method].notna()]
  rr.append(dict(signal_year=yr,method=method,n=len(q),unclosed=int((~g.closed&g[method].notna()).sum()),source_winrate=float(q.round_pnl.gt(0).mean()),auc=M.auc(q.round_pnl.gt(0),q[method])if len(q)else None))
pd.DataFrame(rr).to_csv(O/'ACTUAL_ASSOCIATION_SIGNAL_YEAR.csv',index=False)
cal=[]
for yr,g in c[c.pC.notna()].groupby('year'):
 groups=[]
 for _,q in g[g.label20_known].groupby(['day','sector']):
  aa=M.auc(q.state.eq('C'),q.PC)
  if np.isfinite(aa):groups.append(aa)
 h=g[g.label60_known]
 cal.append(dict(year=int(yr),mature60=len(h),actual_meanY=float(h.Y.mean()),predicted_meanY=float(h.mix_mu.mean()),within_group_C_auc=float(np.mean(groups)),eligible_groups=len(groups)))
pd.DataFrame(cal).to_csv(O/'CONDITIONAL_CALIBRATION.csv',index=False)
# Compare v1/v2 only on the same dates complete across BOTH versions and ALL methods.
old=O.parent/'conditional_distribution_v1';a=pd.read_parquet(old/'PREDICTIONS.parquet');p=pd.read_parquet(old/'SEALED_PICKS.parquet')
p=p.merge(a,left_on='row',right_index=True,validate='many_to_one',suffixes=('_pick',''))
both=pd.concat([p.assign(version='v1'),s.assign(version='v2')],ignore_index=True)
vr=[]
for period,ids in periods:
 g=both[both.row.isin(ids)]
 for H in [5,20,60]:
  ok=g.groupby('day')['complete'+str(H)].all();g=g[g.day.isin(ok[ok].index)]
  dm=g.groupby(['day','version','method'])['ret'+str(H)].mean().unstack(['version','method'])
  for method in methods:
   if len(dm):
    d=dm[('v2',method)]-dm[('v1',method)]
    vr.append(dict(period=period,H=H,method=method,**M.paired_ci(d,c.groupby('day').t.first())))
pd.DataFrame(vr).to_csv(O/'V1_V2_COMMON_DATE_COMPARISON.csv',index=False)
oldhash=json.loads((O/'V1_PRESERVED_HASHES.json').read_text())
assert all(hashlib.sha256((old/n).read_bytes()).hexdigest()==h for n,h in oldhash.items())
qa=dict(only_descriptive_supplements=True,new_fits=0,v1_preserved=True,unknown_epoch_rows=int(c.epoch.eq('None').sum()),unknown_epoch_roots=len(ambig),all_common_daily_K_identical=True,common_complete_60_all=[r for r in rows if r['period']=='ALL'and r['H']==60],zero_scale_prediction_unknown=int(c.loc[c.scale_floor_unknown,'MIX_EV_ES'].isna().sum()))
(O/'SUPPLEMENT_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
print(json.dumps(qa,ensure_ascii=False),flush=True)
