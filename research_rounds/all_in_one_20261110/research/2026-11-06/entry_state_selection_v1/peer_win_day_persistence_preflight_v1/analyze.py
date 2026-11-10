
from pathlib import Path
import pandas as pd,numpy as np,json
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
E=R/'m3_stock_birth_during_sector_v1'
paths=[E/'relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv',E/'cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv']
z=pd.concat([pd.read_csv(p,low_memory=False) for p in paths],ignore_index=True)
z=z[z.arm.eq('A_UNION_B')].copy()
z['usable']=z.evidence_usable_closed.eq(True)
pairs=[]
for (y,d,s),g in z.groupby(['window','signal_day','sector']):
 if len(g)==2 and g.usable.all() and g.core_net.gt(0).sum()==1:
  w=g[g.core_net.gt(0)].iloc[0]; l=g[g.core_net.le(0)].iloc[0]
  pairs.append(dict(year=y,day=d,sector=s,industry=w.industry,winner=w.sid,loser=l.sid,winname=w['name'],lossname=l['name'],wret=w.core_return,lret=l.core_return,wpvr=w.PVR_score,lpvr=l.PVR_score))
p=pd.DataFrame(pairs)
print('BASELINE',z.groupby('window').agg(rows=('sid','size'),usable=('usable','sum')).to_string())
print('PAIRS',p.groupby('year').agg(pairs=('day','size'),days=('day','nunique'),sectors=('sector','nunique')).to_string())


U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sm={r['symbol']:r for r in json.load(open(U/'STOCK_MANIFEST.json'))}
im={r['series']:r for r in json.load(open(U/'INDUSTRY_MANIFEST.json'))}
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
with np.load(H,allow_pickle=False) as hz: cal=pd.DatetimeIndex(hz['dates'])
cal=cal[cal<=pd.Timestamp('2026-06-30')]
ix={x:i for i,x in enumerate(cal)}
cache={}
def src(key,ind=False):
 if key not in cache:
  m=(im if ind else sm)[key];f=next(f for f in m['source_sha256'] if f.endswith('/signal.parquet'))
  q=pd.read_parquet(f).reindex(cal)
  cache[key]=q
 return cache[key]
def valid(q):
 if len(q)!=22:return False
 for c in ['close','raw_close','adjustment_factor']:
  if not np.isfinite(q[c]).all() or not q[c].gt(0).all(): return False
 for c in ['observed_bar','price_eligible','volume_eligible']:
  if not q[c].eq(True).all():return False
 for c in ['source_invalid','synthetic_event_bar']:
  if not q[c].eq(False).all():return False
 if any(q[c].isna().any() or q[c].nunique()!=1 for c in ['source_kind','source_path','segment_id']): return False
 return np.allclose(q.raw_close*q.adjustment_factor,q.close,rtol=1e-9,atol=1e-9)
def feat(sid,sec,day,cut=False):
 k=ix[pd.Timestamp(day)];a=src(sid);b=src(sec,True)
 if cut:a=a.loc[:day];b=b.loc[:day]
 a=a.iloc[k-22:k];b=b.iloc[k-22:k]
 if not (valid(a) and valid(b)):return (np.nan,np.nan)
 ri=np.diff(np.log(a.close.to_numpy()));rs=np.diff(np.log(b.close.to_numpy()));x=ri-rs
 return (float(((x>0)+.5*(x==0)).mean()),float(ri.sum()))
prefix=0
for j,r in p.iterrows():
 w=feat(r.winner,r.sector,r.day);l=feat(r.loser,r.sector,r.day)
 p.loc[j,['wd','wr21','ld','lr21']]=[*w,*l]
 if j<12:
  assert np.allclose(w,feat(r.winner,r.sector,r.day,True),equal_nan=True);assert np.allclose(l,feat(r.loser,r.sector,r.day,True),equal_nan=True);prefix+=2
print('PREFIX',prefix)
for y,g in p.groupby('year'):
 g=g[g.wd.notna()&g.ld.notna()]
 print('YEAR',y,'KNOWN',len(g))
 for name,a,b in [('D','wd','ld'),('PVR','wpvr','lpvr'),('R21','wr21','lr21')]:
  d=g[a]-g[b];dg=pd.DataFrame({'day':g.day,'diff':d}).groupby('day')['diff'].mean()
  loo=[dg.drop(i).mean() for i in dg.index]
  print(name,json.dumps(dict(win=int((d>0).sum()),loss=int((d<0).sum()),ties=int((d==0).sum()),pairmean=float(d.mean()),datemean=float(dg.mean()),datespositive=int((dg>0).sum()),datesnegative=int((dg<0).sum()),loo_min=float(min(loo)),loo_max=float(max(loo)))))
 d=g.wd-g.ld;pdiff=g.wpvr-g.lpvr;rd=g.wr21-g.lr21
 print('REVERSE_VS_PVR',int((d*pdiff<0).sum()),'benefit',int(((d>0)&(pdiff<0)).sum()),'harm',int(((d<0)&(pdiff>0)).sum()))
 print('REVERSE_VS_R21',int((d*rd<0).sum()),'benefit',int(((d>0)&(rd<0)).sum()),'harm',int(((d<0)&(rd>0)).sum()))
 g=g.assign(d=d,pdiff=pdiff)

O=R/'peer_win_day_persistence_preflight_v1'
p.to_csv(O/'PAIRED_FEATURES.csv',index=False)
stats=[]
for y,g in p.groupby('year'):
 g=g[g.wd.notna()&g.ld.notna()]
 for name,a,b in [('D','wd','ld'),('PVR','wpvr','lpvr'),('R21','wr21','lr21')]:
  d=g[a]-g[b];dg=pd.DataFrame({'day':g.day,'diff':d}).groupby('day')['diff'].mean();loo=[dg.drop(i).mean() for i in dg.index]
  stats.append(dict(window=str(y),metric=name,pairs=len(g),wins_higher=int((d>0).sum()),losses_higher=int((d<0).sum()),ties=int((d==0).sum()),pair_mean=float(d.mean()),date_mean=float(dg.mean()),dates_positive=int((dg>0).sum()),dates_negative=int((dg<0).sum()),loo_min=float(min(loo)),loo_max=float(max(loo))))
pd.DataFrame(stats).to_csv(O/'PAIR_SUMMARY.csv',index=False)
ds=pd.concat([pd.read_csv(E/'relative_priority_equity_run_2022_v1/dynamic/DECISIONS.csv',low_memory=False),pd.read_csv(E/'cash_equity_baseline_2024_v1/economic/DECISIONS.csv',low_memory=False)],ignore_index=True)
ds=ds[ds.arm.eq('A_UNION_B')&ds.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])].copy()
targets=[('2022-05-06','002050.SZ'),('2022-05-12','300260.SZ'),('2024-09-05','002625.SZ'),('2024-09-26','688568.SH')]
prefix=[]
queueframes=[]
for day,sid in targets:
 t=ds[(ds.day==day)&(ds.sid==sid)]
 if len(t)!=1:print('TARGET_MISSING',day,sid,len(t));continue
 sec=t.iloc[0].sector
 g=ds[(ds.day==day)&(ds.sector==sec)].sort_values(['PVR_score','sid'],ascending=[False,True]).copy()
 g['oldrank']=np.arange(1,len(g)+1)
 for i,r in g.iterrows():g.loc[i,'D']=feat(r.sid,r.sector,r.day)[0]
 # Unknown positions stay unchanged; stable tiebreak PVR then sid.
 known=g[g.D.notna()].sort_values(['D','PVR_score','sid'],ascending=[False,False,True])
 g['newrank']=g.oldrank
 for pos,idx in zip(g[g.D.notna()].oldrank,known.index):g.loc[idx,'newrank']=pos
 g['sameK_in']=g.newrank<=g.selected.eq(True).sum()
 ret=z[z.signal_day.eq(day)&z.sector.eq(sec)][['sid','core_return','usable']]
 g=g.merge(ret,on='sid',how='left',validate='one_to_one')
 g['case_day']=day;g['target_sid']=sid;queueframes.append(g)
 print('QUEUE',day,sid,'K',int(g.selected.eq(True).sum()),g[['sid','name','PVR_score','D','oldrank','newrank','selected','sameK_in','core_return','usable']].to_json(orient='records',force_ascii=False))
 for s in g.sid:
  a=feat(s,sec,day);b=feat(s,sec,day,True)
  assert np.allclose(a,b,equal_nan=True)
  # Independent direct daily ratio form against sector, not difference of logs.
  k=ix[pd.Timestamp(day)];aa=src(s).iloc[k-22:k];bb=src(sec,True).iloc[k-22:k]
  if valid(aa) and valid(bb):
   u=aa.close.to_numpy()[1:]/aa.close.to_numpy()[:-1];v=bb.close.to_numpy()[1:]/bb.close.to_numpy()[:-1]
   direct=float(((u>v)+.5*(u==v)).mean());assert direct==a[0],(s,day,direct,a)
  prefix.append((day,s))
print('PREFIX_FIXED',len(prefix),prefix)

pd.concat(queueframes,ignore_index=True).to_csv(O/'FOUR_FIXED_QUEUES.csv',index=False)
import hashlib
source_hashes={}
for path in paths+[U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',H,E/'relative_priority_equity_run_2022_v1/dynamic/DECISIONS.csv',E/'cash_equity_baseline_2024_v1/economic/DECISIONS.csv']:
 source_hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
for key in cache:
 m=(im if key in im else sm)[key];f=next(f for f in m['source_sha256'] if f.endswith('/signal.parquet'))
 digest=hashlib.sha256(Path(f).read_bytes()).hexdigest()
 assert digest==m['source_sha256'][f],f
 source_hashes[f]=digest
(O/'SOURCE_HASHES.json').write_text(json.dumps(source_hashes,ensure_ascii=False,indent=2)+'\n')
(O/'QA.json').write_text(json.dumps(dict(pair_rows=len(p),features_known=int((p.wd.notna()&p.ld.notna()).sum()),fixed_queue_prefix_checks=len(prefix),initial_pair_prefix_checks=24,unique_fixed_cases=4,source_hashes_verified=len(source_hashes),new_economic_runs=0,formula_searches=0,original_files_changed=0,history_seen=True,not_oos=True,computation='Initial exploratory read-only command completed first; artifacts reproduce that fixed formula, not a retrospective preregistration.'),ensure_ascii=False,indent=2)+'\n')
