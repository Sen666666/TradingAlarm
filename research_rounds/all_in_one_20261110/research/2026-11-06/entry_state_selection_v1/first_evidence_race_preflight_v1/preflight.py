"""Frozen research preflight: no economic replay, no new order or policy return."""
from pathlib import Path
import pandas as pd, numpy as np, json, hashlib, time
O=Path(__file__).resolve().parent; R=O.parent
M=R/'cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
S={};start=time.time()
def src(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();S[str(p)]=h
 if expected is not None:assert h==expected, str(p)
 return p
def clean(x):return None if pd.isna(x) else x
with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
cal=cal[cal<='2026-06-30']; di={d:i for i,d in enumerate(cal)}
sm=json.loads(src(U/'STOCK_MANIFEST.json').read_text());mm={m['symbol']:m for m in sm}
ids=['round_id','window','sid','signal_day','entry_day','entry_status','status']
mother=pd.read_csv(src(M),usecols=ids,parse_dates=['signal_day','entry_day'])
assert len(mother)==4086 and mother.round_id.is_unique
out=[]
for j,(sid,g) in enumerate(mother.groupby('sid',sort=True)):
 m=mm[sid];pe=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'));ps=str(Path(pe).with_name('signal.parquet'))
 f=pd.read_parquet(src(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])).reindex(cal)
 cp=pd.read_parquet(src(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])).reindex(cal)
 ev=pd.read_parquet(src(pe,m['source_sha256'][pe])).reindex(cal)
 b=pd.read_parquet(src(ps,m['source_sha256'][ps])).reindex(cal)
 ik=f.i_target.isin([0,1]).to_numpy()
 lin=b[['source_kind','source_path','segment_id']]
 same=lin.notna().all(axis=1)&lin.shift().notna().all(axis=1)&lin.eq(lin.shift()).all(axis=1)
 same=same.fillna(False).to_numpy()
 rawok=b.observed_bar.eq(True)&b.price_eligible.eq(True)&pd.to_numeric(b.close,errors='coerce').gt(0)&pd.to_numeric(b.raw_close,errors='coerce').gt(0)&pd.to_numeric(f.factor,errors='coerce').gt(0)
 rawok=(rawok&lin.notna().all(axis=1)&f.segment_id.eq(b.segment_id)&ev.segment_id.eq(b.segment_id)).fillna(False).to_numpy()
 iarray=pd.to_numeric(f.i_target,errors='coerce').to_numpy(dtype=float,na_value=np.nan)
 roots=np.full(len(cal),-1,dtype=int);root=-1
 for k in range(len(cal)):
  if not (ik[k] and rawok[k]) or iarray[k]==0:root=-1
  elif k>0 and same[k] and ik[k-1] and rawok[k-1] and iarray[k-1]==0:root=k
  elif not (k>0 and same[k] and ik[k-1] and rawok[k-1] and iarray[k-1]==1):root=-1
  roots[k]=root
 for r in g.itertuples(index=False):
  t=di.get(r.signal_day);entry=di.get(r.entry_day) if pd.notna(r.entry_day) else None
  row=dict(round_id=r.round_id,window=r.window,sid=sid,signal_day=r.signal_day,entry_day=r.entry_day,entry_status=r.entry_status,original_status=r.status,root_known=False,root_day=None,root_before_window=None,race='NO_CONFIRMED_ENTRY',race_day=None,next_common_open_day=None,next_raw_open=None,first_down_day=None,first_cp_day=None,I_off_day=None,cp_preentry_anchor=None,cp_anchor_to_signal_return=None,cp_credit_at_signal=None,cp_credit_at_hit=None,cp_new_frontier_at_hit=None,race_same_day_down_cp=False)
  if t is None:row['race']='UNKNOWN_SIGNAL_DAY';out.append(row);continue
  root=int(roots[t]);row['root_known']=root>=0
  if root>=0:
   row['root_day']=cal[root];lower=pd.Timestamp('2022-01-01' if r.window=='2022' else '2024-09-01');row['root_before_window']=cal[root]<lower
  if entry is None or r.entry_status!='CONDITIONAL_OPEN_PROXY':out.append(row);continue
  assert entry>t
  if root<0:row['race']='UNKNOWN_ROOT';out.append(row);continue
  hit=False;last=entry
  for k in range(entry,len(cal)):
   last=k
   if not(rawok[k] and ik[k] and same[k]):
    if not hit:row.update(race='UNKNOWN_MARKET_PREFIX',race_day=cal[k])
    break
   down=pd.notna(ev.event.iloc[k]) and float(ev.event.iloc[k])==-1
   cpk=pd.notna(cp.receipt.iloc[k]) and bool(cp.receipt.iloc[k])
   if row['first_down_day'] is None and down:row['first_down_day']=cal[k]
   if row['first_cp_day'] is None and cpk:row['first_cp_day']=cal[k]
   if iarray[k]==0:
    row['I_off_day']=cal[k]
    if not hit:row.update(race='ORIGINAL_I_EXIT_FIRST',race_day=cal[k]);hit=True
    break
   if roots[k]!=root:
    if not hit:row.update(race='UNKNOWN_ROOT_CONTINUITY',race_day=cal[k])
    break
   if not hit:
    if pd.isna(ev.event.iloc[k]) or pd.isna(cp.ready.iloc[k]) or not bool(cp.ready.iloc[k]) or pd.isna(cp.receipt.iloc[k]):
     row.update(race='UNKNOWN_EVENT_OR_CP',race_day=cal[k]);break
    if down or cpk:
     row.update(race='DOWN_FIRST' if down else 'CP_FIRST',race_day=cal[k],race_same_day_down_cp=down and cpk)
     if down and k+1<len(cal):
      row['next_common_open_day']=cal[k+1]
      row['next_raw_open']=clean(b.raw_open.iloc[k+1])
     if cpk and not down:
      row['cp_anchor_to_signal_return']=float(np.exp(cp.anchor.iloc[k])/f.close.iloc[t]-1)
      row['cp_preentry_anchor']=float(cp.anchor.iloc[k])<float(np.log(f.close.iloc[t]))-1e-12
      row['cp_credit_at_signal']=clean(cp.credit.iloc[t]);row['cp_credit_at_hit']=clean(cp.credit.iloc[k]);row['cp_new_frontier_at_hit']=clean(cp.delta_frontier.iloc[k])
     hit=True
  if not hit and row['race']=='NO_CONFIRMED_ENTRY':row['race']='RIGHT_CENSORED';row['race_day']=cal[last]
  out.append(row)
 if (j+1)%200==0:print('SIDS',j+1,'seconds',round(time.time()-start,1),flush=True)
features=pd.DataFrame(out).sort_values(['window','sid','signal_day','round_id'])
features['campaign_key']=np.where(features.root_known,features.window+'|'+features.sid+'|'+features.root_day.astype(str),features.round_id+'|UNKNOWN')
features['first_observed_baseline_entry_in_root']=~features.campaign_key.duplicated()
features.to_csv(O/'ALL_PERMIT_RACE_FEATURES_PRELABEL.csv',index=False)
seal=dict(time_utc=pd.Timestamp.now(tz='UTC').isoformat(),feature_sha256=hashlib.sha256((O/'ALL_PERMIT_RACE_FEATURES_PRELABEL.csv').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),protocol_sha256=hashlib.sha256((O/'PROTOCOL.json').read_bytes()).hexdigest(),rows=len(features),source_count=len(S))
(O/'FEATURE_SEAL.json').write_text(json.dumps(seal,indent=2))
(O/'SOURCE_HASHES.json').write_text(json.dumps(S,indent=2))
labels=pd.read_csv(M,usecols=['round_id','name','industry','sector','evidence_usable_closed','core_net','core_return','net_pnl','exit_day','exit_price'])
x=features.merge(labels,on='round_id',validate='one_to_one')
x.to_csv(O/'RACE_WITH_OLD_LABELS.csv',index=False)
stats=[]
for scope,df in [('ALL_PERMITS',x),('FIRST_BASELINE_ENTRY_PER_ROOT',x[x.first_observed_baseline_entry_in_root])]:
 for (win,race),v in df.groupby(['window','race']):
  c=v[v.evidence_usable_closed.eq(True)]
  stats.append(dict(scope=scope,window=win,race=race,permits=len(v),known_roots=int(v.root_known.sum()),old_usable=len(c),old_wins=int(c.core_net.gt(0).sum()),old_losses=int(c.core_net.lt(0).sum()),old_mean_net=c.core_net.mean(),old_tail30=int(c.core_return.ge(.3).sum()),old_tail50=int(c.core_return.ge(.5).sum()),preentry_anchor=int(v.cp_preentry_anchor.eq(True).sum()),root_before_window=int(v.root_before_window.eq(True).sum())))
summary=pd.DataFrame(stats);summary.to_csv(O/'SUMMARY_OLD_LABEL_ASSOCIATION.csv',index=False)
tails=x[x.evidence_usable_closed.eq(True)&x.core_return.ge(.5)]
tails.to_csv(O/'ALL_108_OLD_TAILS.csv',index=False)
assert len(tails)==108
counts=dict(permits=len(x),root_known=int(x.root_known.sum()),unique_known_campaigns=x[x.root_known].campaign_key.nunique(),first_rows=int(x.first_observed_baseline_entry_in_root.sum()),same_day_down_cp=int(x.race_same_day_down_cp.sum()),seconds=time.time()-start,new_economic_runs=0,source_hashes_passed=True,prelabel_seal=True)
(O/'QA.json').write_text(json.dumps(counts,indent=2))
print(summary.to_string(index=False));print(json.dumps(counts,indent=2));print('TAIL_DOWN_FIRST');print(tails[tails.race.eq('DOWN_FIRST')][['window','sid','name','signal_day','race_day','next_common_open_day','next_raw_open','core_return']].to_string(index=False))
