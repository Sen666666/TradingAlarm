
"""Frozen sequential-certificate versus native CP market-signal comparison.
No portfolio, account replay, random baseline, ranking search, or order execution.
"""
from pathlib import Path
from collections import deque
import json, math, hashlib, time, sys, ast
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

O=Path('/Users/bytedance/Documents/Codex/2026-11-06/cp_sequential_full1709_v1')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
RM=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json')
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
FIRST=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv')
PRIOR=Path('/Users/bytedance/Documents/Codex/2026-11-06/cp_sequential_candidate_audit_v1/FULL_PREFIX_DAILY.parquet')
START=pd.Timestamp('2022-01-04'); END=pd.Timestamp('2026-05-15')
CAL=pd.DatetimeIndex(np.load(HP,allow_pickle=False)['dates']);CAL=CAL[CAL<=END]
sm=json.loads((U/'STOCK_MANIFEST.json').read_text());assert len(sm)==1709
rm={r['series_id']:r for r in json.loads(RM.read_text())['series']}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,pd.Timestamp):return str(x.date())
 return x
def dump(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
def numeric(s):return pd.to_numeric(s,errors='raise').to_numpy(dtype=float,na_value=np.nan)
def calculate(f0):
 ix=CAL[CAL>=f0.index.min()];f=f0.reindex(ix)
 C=numeric(f.close);I=numeric(f.i_target);seg=numeric(f.segment_id)
 good=np.isfinite(C)&(C>0)&np.isfinite(I)&np.isfinite(seg)
 assert np.isin(I[np.isfinite(I)],[0,1]).all()
 same=np.r_[False,good[1:]&good[:-1]&(seg[1:]==seg[:-1])]
 r=np.full(len(f),np.nan)
 # Same arithmetic as the original eight-case implementation.
 for j in np.flatnonzero(same):r[j]=math.log(C[j]/C[j-1])
 z=pd.Series(np.abs(r)).shift(1).rolling(63,min_periods=63).median().to_numpy()*1.4826
 z=np.maximum(z,math.log(1.001));z[~np.isfinite(r)]=np.nan
 u=r/z;delta=.5*u-.125
 S=np.full(len(f),np.nan);before=np.zeros(len(f));after=np.zeros(len(f));fire=np.zeros(len(f),bool)
 age=np.zeros(len(f),np.int32);delayed=np.zeros(len(f),np.int32);opens=np.zeros(len(f),bool)
 prev=0.;origin=-1;above=0
 for j in range(len(f)):
  if not good[j] or (j and good[j-1] and seg[j]!=seg[j-1]):
   prev=0.;origin=-1;above=0
  before[j]=prev
  if np.isfinite(delta[j]):
   S[j]=max(0.,prev+delta[j])
   if prev==0 and S[j]>0:origin=j
   if S[j]==0:origin=-1
  delayed[j]=above;age[j]=j-origin+1 if origin>=0 else 0
  fire[j]=np.isfinite(S[j]) and S[j]>=1 and I[j]==1
  opens[j]=j>0 and same[j] and I[j-1]==0 and I[j]==1
  above=above+1 if np.isfinite(S[j]) and S[j]>=1 and I[j]==0 else 0
  after[j]=0. if fire[j] or not np.isfinite(S[j]) else S[j]
  if fire[j]:origin=-1;above=0
  prev=after[j]
 x=pd.DataFrame(dict(C=C,I=I,segment=seg,good=good,r=r,z=z,u=u,delta=delta,S_before=before,S=S,S_after=after,
  new_receipt_raw=fire,excursion_age=age,prior_closed_above_days=delayed,I_opens=opens),index=ix)
 assert not fire[np.logical_not(np.isfinite(z))].any()
 assert not fire[I!=1].any()
 assert (after[fire]==0).all()
 return f,x
def labels(f,raw,ix):
 C=pd.Series(numeric(f.close),index=ix);factor=pd.Series(numeric(f.factor),index=ix);seg=pd.Series(numeric(f.segment_id),index=ix)
 op=pd.to_numeric(raw.open,errors='raise')*factor
 rv=(np.isfinite(raw.close)&raw.close.gt(0)&np.isfinite(raw.open)&raw.open.gt(0)&np.isfinite(C)&C.gt(0)&np.isfinite(factor)&factor.gt(0))
 for col in ['observed_bar','price_eligible']:
  if col in raw:rv &= raw[col].eq(True)
 entry=op.shift(-1)
 y=pd.DataFrame(index=ix);y['raw_open_next']=raw.open.shift(-1);y['entry_adjusted_open']=entry
 y['next_oneprice']=(raw.high.eq(raw.low)&raw.open.eq(raw.close)).shift(-1,fill_value=False)
 y['next_volume_nonpositive_or_unknown']=(~np.isfinite(raw.volume)|raw.volume.le(0)).shift(-1,fill_value=True)
 for h in [5,20,60]:
  complete=rv.astype(int).rolling(h,min_periods=h).sum().shift(-h).eq(h)&np.isfinite(entry)&entry.gt(0)
  complete &= seg.rolling(h+1,min_periods=h+1).max().shift(-h).eq(seg.rolling(h+1,min_periods=h+1).min().shift(-h))
  ret=C.shift(-h)/entry-1
  mfe=C.rolling(h,min_periods=h).max().shift(-h)/entry-1
  mae=C.rolling(h,min_periods=h).min().shift(-h)/entry-1
  y['complete'+str(h)]=complete
  y['ret'+str(h)]=ret.where(complete)
  y['mfe'+str(h)]=mfe.clip(lower=0).where(complete)
  y['mae'+str(h)]=mae.clip(upper=0).where(complete)
 return y,rv,op
def spells(sid,x,rv,op):
 active=x.I.eq(1)&x.good
 starts=np.flatnonzero(active.to_numpy()&(~active.shift(1,fill_value=False).to_numpy()|x.segment.ne(x.segment.shift()).to_numpy()))
 ends=np.flatnonzero(active.to_numpy()&(~active.shift(-1,fill_value=False).to_numpy()|x.segment.ne(x.segment.shift(-1)).to_numpy()))
 out=[]
 for b,e in zip(starts,ends):
  if x.index[e]<START:continue
  left=not (b>0 and x.good.iloc[b-1] and x.I.iloc[b-1]==0 and x.segment.iloc[b-1]==x.segment.iloc[b])
  right=not (e+1<len(x) and x.good.iloc[e+1] and x.I.iloc[e+1]==0 and x.segment.iloc[e+1]==x.segment.iloc[e])
  q=x.iloc[b:e+1];run_common=bool(q.common.all())
  old=np.flatnonzero(q.old_event.to_numpy());new=np.flatnonzero(q.new_event.to_numpy())
  row=dict(sid=sid,root=sid+'|'+str(x.index[b].date()),birth_day=x.index[b],last_I_day=x.index[e],
   exit_day=x.index[e+1] if e+1<len(x) and not right else None,birth_year=x.index[b].year,duration=e-b+1,
   left_censored=left,right_censored=right,all_active_days_common=run_common,
   strict_complete_spell=not left and not right and run_common and x.index[b]>=START,
   old_n=len(old),new_n=len(new),old_any=bool(len(old)),new_any=bool(len(new)),
   old_first_day=x.index[b+old[0]] if len(old) else None,new_first_day=x.index[b+new[0]] if len(new) else None,
   old_first_delay=int(old[0]) if len(old) else None,new_first_delay=int(new[0]) if len(new) else None,
   old_early6=bool(len(old) and old[0]<=5),new_early6=bool(len(new) and new[0]<=5),
   first_delay_new_minus_old=int(new[0]-old[0]) if len(old) and len(new) else None,
   peak30=False,peak30_end20=False,price_path_complete=False,run_ret=np.nan,run_mfe=np.nan,run_mae=np.nan)
  # Whole original-I spell, including the first close that turns I off. Same anchor for both.
  if not right and b+1<len(x) and rv.iloc[b+1:e+2].all() and x.segment.iloc[b:e+2].nunique()==1 and np.isfinite(op.iloc[b+1]):
   base=float(op.iloc[b+1]);p=x.C.iloc[b+1:e+2];ret=float(p.iloc[-1]/base-1);peak=max(0,float(p.max()/base-1))
   row.update(price_path_complete=True,reference_next_open=base,run_ret=ret,run_mfe=peak,run_mae=min(0,float(p.min()/base-1)),peak30=peak>=.3,peak30_end20=peak>=.3 and ret>=.2)
  for name,ids in [('old',old),('new',new)]:
   row[name+'_price_advance_at_first']=float(x.C.iloc[b+ids[0]]/x.C.iloc[b]-1) if len(ids) else np.nan
  out.append(row)
 return out

def stats(df,group_cols):
 ans=[]
 for keys,g in df.groupby(group_cols,dropna=False):
  if not isinstance(keys,tuple):keys=(keys,)
  base=dict(zip(group_cols,keys));base['signals']=len(g);base['stocks']=g.sid.nunique();base['dates']=g.day.nunique()
  for h in [5,20,60]:
   v=g.loc[g['complete'+str(h)],'ret'+str(h)]
   base.update({f'n{h}':len(v),f'complete_fraction{h}':len(v)/len(g),f'mean{h}':v.mean(),f'median{h}':v.median(),f'p10_{h}':v.quantile(.1),f'p90_{h}':v.quantile(.9),f'price_above_next_open_fraction{h}':v.gt(0).mean() if len(v) else np.nan,f'mfe_mean{h}':g.loc[g['complete'+str(h)],'mfe'+str(h)].mean(),f'mae_mean{h}':g.loc[g['complete'+str(h)],'mae'+str(h)].mean()})
  ans.append(base)
 return pd.DataFrame(ans)

start=time.monotonic()
assert not O.exists(),'Do not rerun or overwrite a prior full run.'
O.mkdir()
freeze=dict(version=1,status='FROZEN_BEFORE_FULL1709_SIGNAL_EVALUATION_NOT_UNSEEN_OOS',
 formula='r=ln(C/Cprev); z=max(1.4826*median(abs(previous63returns)),ln(1.001)); A=max(0,Sprev+0.5*r/z-0.125); new_receipt iff I=1 and A>=1; Safter=0 on receipt else A',
 unchanged_parameters=dict(delta=.5,drift=.125,h=1,scale_observations=63,scale_floor='ln(1.001)'),
 missing_rule='Exactly prior eight-case convention: absent/invalid source price, unknown I or native segment change clears S and return history. No filling or cross-gap return; require63 prior complete returns. I=0 continues accumulation without consuming.',
 consumption='Receipt consumes at signal close regardless of hypothetical position, selection, sector permission or fill. No orders, fill model or new protective price.',
 market_candidate_domain='Fixed1709; valid native and raw price/factor; original e0_ready=1, g_ready=True, I_target=1; original CP ready and new63-return scale ready. No sector gate, H1/PVR rank, cash, position, stop-distance or fill simulation.',
 common_domain_rule='Unknown, warming or source-missing algorithm state is excluded from both sides of comparable outcomes and separately counted. Source warmup is not counted as a quality improvement.',
 comparison_groups=['BOTH','NEW_ONLY','OLD_ONLY'],years='2022,2023,2024,2025 full signal years;2026 partial through2026-05-15; future endpoints censored honestly',
 episode_definition='Original I=1 contiguous known-price spell. A preceding known0 and a following known0 in the same source segment are required for complete spells. Missing/source boundaries censor. Full comparison additionally requires every active day common-ready, and birth on/after2022-01-04.',
 big_definition='For each strictly complete I spell, common price anchor is open on next market day after birth; price path includes that next day through first I-off close. Peak30 means maximum closing advance>=30%; separately peak30_end20 also needs final closing advance>=20%. Posthoc labels never feed decisions.',
 early_capture='First new/old certificate at offsets0..5 from same I-spell birth; also report any eventual certificate and paired first-day delay. Not order or holding capture.',
 price_labels='Next native raw open times native factor;5/20/60 common trading-day endpoints, full valid raw+adjusted-price same-source path required. Close MFE/MAE descriptive; no net profitability claim.',
 actual_account_subset='Only join existing PVR account0-to0 first-entry records on original signal sid/date after all market decisions sealed. Separate CORE and MOBILE; CORE may not require CP. Original PnL is descriptive, not new counterfactual realized PnL.',
 no_account_run=True,no_random_control=True,no_parameter_grid=True,no_strategy_or_source_edits=True,
 fixed_ids=[r['symbol'] for r in sm],start=str(START.date()),end=str(END.date()),
 source_manifest_sha256=sha(U/'STOCK_MANIFEST.json'),raw_manifest_sha256=sha(RM),first_entry_export_sha256=sha(FIRST),
 prior_eight_case_sha256=sha(PRIOR),code_sha256=sha(__file__),calendar_value_sha256=hashlib.sha256(CAL.asi8.tobytes()).hexdigest())
dump('FREEZE.json',freeze)
print('FROZEN',len(sm),'stocks',flush=True)
# Validate the optimized implementation against every stored row of the frozen eight-case implementation.
old=pd.read_parquet(PRIOR);eq=[]
by={r['symbol']:r for r in sm}
for sid,g in old.groupby('sid'):
 f0=pd.read_parquet(by[sid]['refs']['facts']).loc[:END]
 f,x=calculate(f0);g=g.set_index('day')
 for col in ['r','z','S_before','S','S_after']:
  np.testing.assert_allclose(x.loc[g.index,col],g[col],rtol=0,atol=2e-12,equal_nan=True)
 assert np.array_equal(x.loc[g.index,'new_receipt_raw'].to_numpy(),g.signal.to_numpy())
 eq.append(dict(sid=sid,rows=len(g),state_agreement_atol=2e-12,receipt_exact=True))
dump('IMPLEMENTATION_EQUIVALENCE.json',eq)
print('EQUIVALENCE_PASS',sum(r['rows'] for r in eq),'rows',flush=True)
writer=None;events=[];episodes=[];coverage=[];sourcehashes={};checks=[];firstmatch=[]
fa=pd.read_csv(FIRST);fa=fa[(fa.account=='PVR')&fa.signal_day.between(str(START.date()),str(END.date()))].copy()
check_ids={sm[i]['symbol'] for i in np.linspace(0,len(sm)-1,24,dtype=int)}|set(old.sid.unique())
for no,m in enumerate(sm):
 sid=m['symbol'];paths=[Path(m['refs']['facts']),Path(m['refs']['CP1']),Path(rm[sid]['raw']['path'])]
 snapshots=[(p.stat().st_size,p.stat().st_mtime_ns) for p in paths]
 f0=pd.read_parquet(paths[0]).loc[:END];cp0=pd.read_parquet(paths[1]).loc[:END];raw0=pd.read_parquet(paths[2])
 for p,snap in zip(paths,snapshots):
  sourcehashes[str(p)]=sha(p)
  assert (p.stat().st_size,p.stat().st_mtime_ns)==snap,('source changed while reading',p)
 if not len(f0):
  coverage.append(dict(sid=sid,status='EMPTY_NATIVE_PREFIX'));continue
 assert f0.index.is_unique and f0.index.is_monotonic_increasing
 raw0.index=pd.DatetimeIndex(pd.to_datetime(raw0.trade_date)).normalize();assert raw0.index.is_unique
 base=pd.to_numeric(f0.raw_close,errors='raise')
 np.testing.assert_allclose(base,raw0.close.reindex(f0.index),rtol=0,atol=1e-10,equal_nan=True)
 np.testing.assert_allclose(pd.to_numeric(f0.close,errors='raise'),base*pd.to_numeric(f0.factor,errors='raise'),rtol=0,atol=1e-9,equal_nan=True)
 f,x=calculate(f0);ix=x.index;cp=cp0.reindex(ix);raw=raw0.reindex(ix)
 label,rv,op=labels(f,raw,ix)
 cp_known=cp.ready.notna()&cp.receipt.notna()
 cp_ready=cp.ready.eq(True)&cp_known
 new_ready=np.isfinite(x.z)&x.good
 e0=f.e0_ready.eq(1);g=f.g_ready.eq(True)
 price_ok=x.good&rv&np.isfinite(f.factor)&f.factor.gt(0)
 basegate=price_ok&e0&g&x.I.eq(1)
 common=basegate&cp_ready&new_ready
 x['common']=common;x['base_gate']=basegate;x['old_ready']=cp_ready;x['new_ready']=new_ready
 x['old_receipt_raw']=cp.receipt.eq(True);x['old_event']=common&x.old_receipt_raw;x['new_event']=common&x.new_receipt_raw
 x['I_buy']=f.i_buy.eq(True);x['G']=pd.to_numeric(f.g_grade,errors='raise');x['E0']=pd.to_numeric(f.e0_target,errors='raise')
 x['sid']=sid;x['day']=ix;x['year']=ix.year;x['factor']=f.factor;x['raw_close']=f.raw_close
 x['old_cp_candidate']=pd.to_numeric(cp.candidate,errors='raise');x['native_I_floor']=pd.to_numeric(f.i_floor,errors='raise')
 # The original CP protection price is not recycled into new receipts.
 x['original_cp_floor_valid']=(pd.concat([pd.to_numeric(f.i_floor,errors='raise'),pd.to_numeric(cp.candidate,errors='raise')],axis=1).max(axis=1,skipna=False).gt(0)&pd.concat([pd.to_numeric(f.i_floor,errors='raise'),pd.to_numeric(cp.candidate,errors='raise')],axis=1).max(axis=1,skipna=False).lt(x.C))
 x['group']=np.select([x.old_event&x.new_event,x.new_event&~x.old_event,x.old_event&~x.new_event],['BOTH','NEW_ONLY','OLD_ONLY'],default='NONE')
 selected=x.index>=START
 daily=x.loc[selected].copy().reset_index(drop=True)
 # Explicit schemas prevent an all-missing first stock from fixing wrong column types.
 for col in ['day']:daily[col]=pd.to_datetime(daily[col])
 daily['year']=daily.year.astype(np.int16)
 daily['G']=daily.G.astype(float);daily['E0']=daily.E0.astype(float);daily['factor']=pd.to_numeric(daily.factor,errors='raise').astype(float);daily['raw_close']=pd.to_numeric(daily.raw_close,errors='raise').astype(float)
 table=pa.Table.from_pandas(daily,preserve_index=False)
 if writer is None:writer=pq.ParquetWriter(O/'DAILY_MARKET_COMPARE.parquet',table.schema,compression='zstd')
 else:table=table.cast(writer.schema)
 writer.write_table(table)
 ev=x.loc[selected&(x.old_event|x.new_event)].join(label).reset_index(drop=True)
 events.append(ev)
 ep=spells(sid,x,rv,op);episodes.extend(ep)
 for year,q in x.loc[selected].groupby('year'):
  coverage.append(dict(sid=sid,year=int(year),status='OK',calendar_rows=len(q),source_valid=int(q.good.sum()),base_gate=int(q.base_gate.sum()),joint_known=int(q.common.sum()),old_on_base=int((q.base_gate&q.old_receipt_raw).sum()),new_on_base=int((q.base_gate&q.new_receipt_raw).sum()),old_joint=int(q.old_event.sum()),new_joint=int(q.new_event.sum()),both=int((q.old_event&q.new_event).sum()),old_excluded_new_unready=int((q.base_gate&q.old_receipt_raw&~q.new_ready).sum()),new_excluded_old_unready=int((q.base_gate&q.new_receipt_raw&~q.old_ready).sum()),new_consumed_outside_base=int((q.new_receipt_raw&~q.base_gate).sum()),new_delayed_consumption=int((q.new_event&q.prior_closed_above_days.gt(0)).sum()),new_nonpositive_step=int((q.new_event&q.delta.le(0)).sum())))
 if sid in check_ids:
  for cut in [pd.Timestamp('2022-01-04'),pd.Timestamp('2024-09-24'),pd.Timestamp('2026-01-15')]:
   if cut not in f0.index:continue
   _,p=calculate(f0.loc[:cut]);cols=['r','z','S_before','S','S_after','new_receipt_raw']
   pd.testing.assert_frame_equal(p.loc[:cut,cols],x.loc[:cut,cols],check_dtype=False)
   poison=f0.copy();poison.loc[poison.index>cut,'close']*=1.73;poison.loc[poison.index>cut,'i_target']=0
   _,p2=calculate(poison);pd.testing.assert_frame_equal(p2.loc[:cut,cols],x.loc[:cut,cols],check_dtype=False)
   checks.append(dict(sid=sid,cut=cut,prefix_exact=True,future_poison_exact=True))
 for ar in fa[fa.sid.eq(sid)].to_dict('records'):
  dt=pd.Timestamp(ar['signal_day'])
  if dt in x.index:
   z=x.loc[dt]
   ar.update(signal_source_available=bool(z.good),common_market_domain=bool(z.common),native_cp_receipt=bool(z.old_receipt_raw),new_certificate=bool(z.new_receipt_raw),new_certificate_common=bool(z.new_event),new_state=float(z.S),old_ready=bool(z.old_ready),new_ready=bool(z.new_ready))
  else:ar.update(signal_source_available=False,common_market_domain=False,native_cp_receipt=None,new_certificate=None,new_certificate_common=None,new_state=None,old_ready=None,new_ready=None)
  firstmatch.append(ar)
 if (no+1)%100==0:
  dump('PROGRESS.json',dict(done=no+1,total=len(sm),seconds=time.monotonic()-start))
  print('BUILD',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
if writer:writer.close()
event=pd.concat(events,ignore_index=True);episode=pd.DataFrame(episodes);cov=pd.DataFrame(coverage);matched=pd.DataFrame(firstmatch)
event.to_parquet(O/'UNION_SIGNAL_EVENTS_WITH_PRICE_LABELS.parquet',index=False)
episode.to_parquet(O/'ALL_I_SPELLS.parquet',index=False)
cov.to_parquet(O/'SOURCE_COVERAGE.parquet',index=False)
matched.to_parquet(O/'ORIGINAL_ACCOUNT_FIRST_ENTRY_MATCHES.parquet',index=False)
dump('SOURCE_HASHES.json',sourcehashes);dump('PREFIX_CHECKS.json',checks)
dump('DECISION_SEAL.json',dict(event_rows=len(event),I_spell_rows=len(episode),source_files=len(sourcehashes),seconds=time.monotonic()-start,daily_sha256=sha(O/'DAILY_MARKET_COMPARE.parquet'),event_sha256=sha(O/'UNION_SIGNAL_EVENTS_WITH_PRICE_LABELS.parquet'),original_account_only_joined_no_replay=True))
print('DECISIONS_SEALED',len(event),'union events',len(episode),'I spells',flush=True)
# Event summaries: all comparisons share the same known stock-day domain.
groups=stats(event,['year','group'])
oldall=event[event.old_event].copy();oldall['strategy']='OLD_CP'
newall=event[event.new_event].copy();newall['strategy']='NEW_SEQ'
expanded=pd.concat([oldall,newall],ignore_index=True)
overall=stats(expanded,['year','strategy'])
dump('ANNUAL_GROUP_PRICE_DISTRIBUTIONS.json',groups.to_dict('records'))
dump('ANNUAL_STRATEGY_PRICE_DISTRIBUTIONS.json',overall.to_dict('records'))
dump('ANNUAL_DOMAIN_COUNTS.json',cov.select_dtypes(include=[np.number]).groupby('year').sum().reset_index().to_dict('records'))
# Equal-date-weighted outcome summaries on dates where both have at least one complete signal.
paired=[]
for (year,h),_ in [((y,h),None) for y in sorted(expanded.year.unique()) for h in [5,20,60]]:
 q=expanded[(expanded.year==year)&expanded['complete'+str(h)]]
 byday=q.groupby(['day','strategy'])['ret'+str(h)].mean().unstack()
 if not {'OLD_CP','NEW_SEQ'}.issubset(byday):continue
 byday=byday.dropna()
 paired.append(dict(year=int(year),horizon=h,matched_dates=len(byday),old_equal_date_mean=byday.OLD_CP.mean(),new_equal_date_mean=byday.NEW_SEQ.mean(),mean_paired_difference=(byday.NEW_SEQ-byday.OLD_CP).mean(),median_paired_difference=(byday.NEW_SEQ-byday.OLD_CP).median()))
dump('MATCHED_DATES_PRICE_DISTRIBUTIONS.json',paired)
# Full-I-spell de-duplication and retrospective large-move coverage.
strict=episode[episode.strict_complete_spell&episode.price_path_complete].copy()
spellsum=[]
for year,g in strict.groupby('birth_year'):
 for label,mask in [('ALL',pd.Series(True,index=g.index)),('PEAK30',g.peak30),('PEAK30_END20',g.peak30_end20)]:
  v=g[mask];both=v[v.old_any&v.new_any]
  spellsum.append(dict(year=int(year),cohort=label,spells=len(v),old_any=int(v.old_any.sum()),new_any=int(v.new_any.sum()),both_any=int((v.old_any&v.new_any).sum()),lost_any=int((v.old_any&~v.new_any).sum()),gained_any=int((~v.old_any&v.new_any).sum()),neither_any=int((~v.old_any&~v.new_any).sum()),old_early6=int(v.old_early6.sum()),new_early6=int(v.new_early6.sum()),lost_early6=int((v.old_early6&~v.new_early6).sum()),gained_early6=int((~v.old_early6&v.new_early6).sum()),first_new_earlier=int(both.first_delay_new_minus_old.lt(0).sum()),first_same=int(both.first_delay_new_minus_old.eq(0).sum()),first_new_later=int(both.first_delay_new_minus_old.gt(0).sum()),median_first_delay_difference=both.first_delay_new_minus_old.median(),old_first_delay_median=v.loc[v.old_any,'old_first_delay'].median(),new_first_delay_median=v.loc[v.new_any,'new_first_delay'].median(),run_ret_median=v.run_ret.median(),run_duration_median=v.duration.median(),old_signal_total=int(v.old_n.sum()),new_signal_total=int(v.new_n.sum())))
dump('COMPLETE_I_SPELL_COVERAGE.json',spellsum)
dump('I_SPELL_CENSORING.json',episode.groupby('birth_year').agg(total=('sid','size'),left_censored=('left_censored','sum'),right_censored=('right_censored','sum'),all_active_common=('all_active_days_common','sum'),strict_complete=('strict_complete_spell','sum'),price_complete=('price_path_complete','sum')).reset_index().to_dict('records'))
strict[strict.peak30&((strict.old_any!=strict.new_any)|(strict.old_early6!=strict.new_early6))].to_parquet(O/'LARGE_MOVE_COVERAGE_DIFFERENCES.parquet',index=False)
# First certificate per strict complete I-spell, so repeated events do not dominate this view.
firstev=[]
lookup=event.set_index(['sid','day'])
for v in strict.itertuples():
 for strategy,day in [('OLD_CP',v.old_first_day),('NEW_SEQ',v.new_first_day)]:
  if pd.isna(day):continue
  e=lookup.loc[(v.sid,pd.Timestamp(day))].to_dict();e.update(sid=v.sid,day=pd.Timestamp(day),strategy=strategy,root=v.root,birth_year=v.birth_year)
  firstev.append(e)
firstevent=pd.DataFrame(firstev)
if len(firstevent):
 firstevent.to_parquet(O/'FIRST_CERTIFICATE_PER_COMPLETE_I_SPELL.parquet',index=False)
 dump('FIRST_CERTIFICATE_PRICE_DISTRIBUTIONS.json',stats(firstevent,['birth_year','strategy']).to_dict('records'))
# Existing account labels are never called new outcomes or used for generation.
acct=[]
for (year,kind),g in matched.groupby(['year','first_kind']):
 for scope,v in [('ALL_EXISTING',g),('COMMON_MARKET_DOMAIN',g[g.common_market_domain])]:
  for label,w in [('ALL',v),('NEW_CERT_SAME_ORIGINAL_DAY',v[v.new_certificate_common.eq(True)]),('NO_NEW_CERT_SAME_ORIGINAL_DAY',v[v.new_certificate_common.eq(False)])]:
   for closed_scope,z in [('CLOSED_BY_SOURCE_END',w[w.closed.eq(True)]),('CLOSED_IN_ENTRY_YEAR',w[w.closed_in_entry_year.eq(True)])]:
    pnl=pd.to_numeric(z.round_pnl,errors='coerce')
    acct.append(dict(year=int(year),first_kind=kind,scope=scope,certificate_group=label,closed_scope=closed_scope,all_first_entries=len(w),closed_rounds=len(z),original_winners=int(pnl.gt(0).sum()),original_losers=int(pnl.lt(0).sum()),original_zero=int(pnl.eq(0).sum()),original_pnl_sum=pnl.sum(),original_cp_receipt_false=int(z.native_cp_receipt.eq(False).sum())))
dump('EXISTING_ACCOUNT_DESCRIPTIVE_SUBSETS.json',acct)
dump('COMPLETION.json',dict(status='COMPLETE_SIGNAL_ONLY_NO_ACCOUNT',seconds=time.monotonic()-start,stocks=len(sm),union_events=len(event),original_account_firsts=len(matched),I_spells=len(episode),strict_complete_price_spells=len(strict),prefix_checks=len(checks),eight_case_equivalence_rows=sum(r['rows'] for r in eq),endpoint=str(END.date()),limitations=['Fixed retrospective1709 universe, not PIT all-A tradability','All years already known historically, not pristine out-of-sample','2026 partial and forward labels right-censored','Event price outcomes are not0-to0 account win rate','CORE does not necessarily require CP','Hypothetical empty market candidates do not simulate actual holding/cash/sector/ranking/protection/fills','No causal profit claim from matched original rounds']))
dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print('COMPLETE',json.dumps(clean(dict(seconds=time.monotonic()-start,stocks=len(sm),events=len(event),strict_spells=len(strict),prefix_checks=len(checks)))),flush=True)
print(overall[['year','strategy','signals','n5','mean5','median5','price_above_next_open_fraction5','n20','mean20','median20','n60','mean60']].to_string(index=False),flush=True)
