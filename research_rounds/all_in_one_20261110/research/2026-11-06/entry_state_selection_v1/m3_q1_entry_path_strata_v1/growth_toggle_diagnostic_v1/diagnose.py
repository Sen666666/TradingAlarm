from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';t0=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
with (O/'RUN_ONCE.lock').open('x') as h:h.write(pd.Timestamp.now(tz='UTC').isoformat())
paths=[Path(__file__),O/'PROTOCOL.json',D/'COMMON_K_COMPARISON.parquet',D/'RIGHT3.parquet',D/'KNOWN3.parquet',D/'WARM_PREFIX_M_R.parquet',D/'WARM_PREFIX_M_K.parquet',R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv',O.parent/'ENTRY_FEATURES_PRELABEL.csv',O.parent/'ENTRY_FEATURES_WITH_OLD_LABELS.csv']
S={str(p):sha(p) for p in paths}
p=pd.read_parquet(paths[2]).sort_values(['sector','day'])
# L is only the original lower breadth level, with fixed-N UNKNOWN bounds.
def trace(g):
 g=g.copy().sort_values('day')
 n=g.M3_n;mx=n+g.U
 lo=(n>=3)&(3*n>=g.N);hi=(mx>=3)&(3*mx>=g.N)
 g['L']=np.where(lo,1,np.where(~hi,0,-1));g['prevL']=g.L.shift()
 g['prevS']=g.M3_candidate.shift()
 g['A']=g.M3_candidate.eq(1)&g.prevS.eq(0)
 seq=-1;start=None;seen=False;origin=None;rows=[]
 for r in g.itertuples():
  if r.L==1:
   if r.prevL!=1:
    seq+=1;start=r.day;seen=False
    origin='KNOWN_FALSE' if r.prevL==0 else 'UNKNOWN_OR_LEFT'
   prior=seen
   if r.A:seen=True
   rows.append((seq,start,origin,prior))
  else:rows.append((-1,pd.NaT,'NOT_TRUE',False))
 g[['L_span_id','L_span_start','L_span_origin','prior_sector_A_in_L_span']]=pd.DataFrame(rows,index=g.index)
 return g
p=pd.concat([trace(g) for _,g in p.groupby('sector')],ignore_index=True)
assert p.loc[p.A,'L'].eq(1).all()
p['A_trigger_class']=np.select([~p.A,p.prevL.eq(0),p.prevL.eq(1)],['NOT_A','LEVEL_REACQUIRED','LEVEL_STAYED_TRUE'],'PRIOR_LEVEL_UNKNOWN')
p.to_csv(O/'SECTOR_DAILY_PRELABEL.csv',index=False)
ev=pd.read_csv(paths[7],parse_dates=['day'],dtype={'window':str})
ev=ev[ev.window.isin(['2022','2024_924'])&ev.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy()
ee=ev.merge(p[['day','sector','L_span_id','L_span_start','L_span_origin','A_trigger_class','prior_sector_A_in_L_span']],on=['day','sector'],how='left',validate='many_to_one')
assert ee.L_span_id.notna().all()
feat=pd.read_csv(paths[8],parse_dates=['signal_day','root_day'],dtype={'window':str})
rr=pd.concat([pd.read_parquet(paths[5]),pd.read_parquet(paths[3])]).sort_index()
kk=pd.concat([pd.read_parquet(paths[6]),pd.read_parquet(paths[4])]).sort_index()
M=rr.astype(int).where(kk,-1)
groups={(w,s,sec):g.sort_values('day') for (w,s,sec),g in ee[ee.event_type.eq('A_SECTOR_BIRTH')&ee.I_and_PVR_known.eq(True)].groupby(['window','sid','sector'])}
rows=[]
for r in feat.itertuples():
 cur=ee[ee.event_id.eq(r.event_id)].iloc[0]
 out=dict(event_id=r.event_id,round_id=r.round_id,window=r.window,sid=r.sid,name=r.name,sector=r.sector,industry=r.industry,signal_day=r.signal_day,entry_type=r.entry_type,root_day=r.root_day,L_span_id=cur.L_span_id,L_span_start=cur.L_span_start,L_span_origin=cur.L_span_origin,A_trigger_class=cur.A_trigger_class,prior_sector_A_in_L_span=cur.prior_sector_A_in_L_span,prior_qualified_A_day=pd.NaT,prior_qualified_A_id=None,continuous_stock_M3=None,same_known_I_root=None,diagnostic='KEEP_B')
 if r.entry_type=='A':
  g=groups.get((r.window,r.sid,r.sector),pd.DataFrame())
  prev=g[(g.day<r.signal_day)&g.L_span_id.eq(cur.L_span_id)] if len(g) else g
  if len(prev):
   old=prev.iloc[-1];out.update(prior_qualified_A_day=old.day,prior_qualified_A_id=old.event_id)
   m=M.loc[old.day:r.signal_day,r.sid]
   cm=True if m.eq(1).all() else False if m.eq(0).any() else None
   ir=bool(r.root_day<=old.day) if r.root_independently_verified else None
   out.update(continuous_stock_M3=cm,same_known_I_root=ir)
   out['diagnostic']='STALE_REPEAT_CANDIDATE' if cm is True and ir is True else 'UNKNOWN_REARM' if (cm is None or ir is None) and cm is not False and ir is not False else 'KEEP_NEW_STOCK_OR_I_EVIDENCE'
  else:
   start=pd.Timestamp(cur.L_span_start)
   window_start=pd.Timestamp('2022-01-04' if r.window=='2022' else '2024-09-01')
   complete=cur.L_span_origin=='KNOWN_FALSE' and start>=window_start
   out['diagnostic']='KEEP_FIRST_QUALIFIED_A_IN_KNOWN_SPAN' if complete else 'UNKNOWN_PRIOR_HISTORY'
 rows.append(out)
x=pd.DataFrame(rows);assert len(x)==4086 and x.event_id.is_unique
x.to_csv(O/'SELECTED_PRELABEL_CLASSIFICATION.csv',index=False)
save('FEATURE_SEAL.json',dict(created_utc=pd.Timestamp.now(tz='UTC'),rows=len(x),sources=S,output=sha(O/'SELECTED_PRELABEL_CLASSIFICATION.csv'),classification_frozen_before_label_join=True,old_history_already_seen=True))
lab=pd.read_csv(paths[9],dtype={'window':str})
z=x.merge(lab[['event_id','entry_status','status','evidence_usable_closed','core_net','core_return','net_pnl','net_return_on_buy_cash']],on='event_id',validate='one_to_one')
z.to_csv(O/'SELECTED_WITH_OLD_LABELS.csv',index=False)
def periods(z):
 yield '2022_ALL',z[z.window.eq('2022')]
 yield '2022_Q1',z[z.window.eq('2022')&z.signal_day.dt.quarter.eq(1)]
 yield '2022_REST',z[z.window.eq('2022')&z.signal_day.dt.quarter.gt(1)]
 for q in [2,3,4]:yield '2022_Q'+str(q),z[z.window.eq('2022')&z.signal_day.dt.quarter.eq(q)]
 yield '2024_924',z[z.window.eq('2024_924')]
def stats(p,axis,v,g,layer):
 a=g[g.evidence_usable_closed.eq(True)];c,ret=('core_net','core_return') if layer=='CORE' else ('net_pnl','net_return_on_buy_cash')
 pos=a[c]>0;neg=a[c]<0
 return dict(period=p,axis=axis,value=v,layer=layer,permits=len(g),usable_closed=len(a),wins=int(pos.sum()),losses=int(neg.sum()),winrate=float(pos.mean()) if len(a) else None,mean_net=float(a[c].mean()),net=float(a[c].sum()),mean_win=float(a.loc[pos,c].mean()),mean_loss=float(a.loc[neg,c].mean()),payoff=float(a.loc[pos,c].mean()/-a.loc[neg,c].mean()) if pos.any() and neg.any() else None,tail30=int(a[ret].ge(.3).sum()),tail50=int(a[ret].ge(.5).sum()),financial_unknown=int((g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&~g.evidence_usable_closed).sum()),execution_unknown=int(g.status.str.contains('UNKNOWN',na=False).sum()),nofill=int(g.status.str.contains('NOFILL',na=False).sum()),censored=int(g.status.str.contains('CENSORED',na=False).sum()))
cats={'A_trigger_class':['NOT_A','LEVEL_REACQUIRED','LEVEL_STAYED_TRUE','PRIOR_LEVEL_UNKNOWN'],'diagnostic':['KEEP_B','KEEP_NEW_STOCK_OR_I_EVIDENCE','KEEP_FIRST_QUALIFIED_A_IN_KNOWN_SPAN','UNKNOWN_PRIOR_HISTORY','UNKNOWN_REARM','STALE_REPEAT_CANDIDATE']}
out=[]
for period,g in periods(z):
 for axis,vals in cats.items():
  for val in vals:
   for layer in ['CORE','FULL']:out.append(stats(period,axis,val,g[g[axis].eq(val)],layer))
pd.DataFrame(out).to_csv(O/'ALL_FROZEN_STRATA.csv',index=False)
# Prefix sample chosen on labels-free calendar: first A per original window and quarter, plus first observed stale repeat.
checks=[]
samples=[]
for _,g in x[x.entry_type.eq('A')].groupby([x.window,x.signal_day.dt.quarter]):
 samples.append(g.sort_values(['signal_day','sid']).iloc[0])
for _,g in x[x.diagnostic.eq('STALE_REPEAT_CANDIDATE')].groupby('window'):samples.append(g.sort_values(['signal_day','sid']).iloc[0])
for r in samples:
 full=p[p.sector.eq(r.sector)&p.day.le(r.signal_day)]
 again=trace(full).iloc[-1];old=full.iloc[-1]
 cols=['L','L_span_id','L_span_start','L_span_origin','prior_sector_A_in_L_span']
 checks.append(dict(event_id=r.event_id,all_exact=all(again[c]==old[c] for c in cols),rows=len(full)))
pd.DataFrame(checks).to_csv(O/'PHYSICAL_PREFIX_CHECKS.csv',index=False)
assert all(q['all_exact'] for q in checks)
# Existing all-Q1-tail/same-day counterpart identities only, not newly chosen favorable examples.
oldcase=pd.read_csv(O.parent/'ALL_Q1_TAIL_SAME_DAY_SECTOR_CONTEXT.csv',usecols=['event_id'])
z[z.event_id.isin(oldcase.event_id)].to_csv(O/'EXISTING_FIXED_Q1_CASES.csv',index=False)
z[z.diagnostic.eq('STALE_REPEAT_CANDIDATE')].to_csv(O/'ALL_STALE_REPEAT_CASES.csv',index=False)
after={p:sha(p) for p in S};assert after==S
save('QA.json',dict(rows=len(x),all_old_labels_unchanged=True,no_new_economics=True,sources_unchanged=True,prefix_checks=len(checks),seconds=time.monotonic()-t0))
save('SOURCE_HASHES_AFTER.json',after)
print(pd.DataFrame(out).query("axis=='diagnostic' and value=='STALE_REPEAT_CANDIDATE'").to_string(index=False),flush=True)
print('QA',json.dumps(dict(rows=len(x),seconds=time.monotonic()-t0)),flush=True)
