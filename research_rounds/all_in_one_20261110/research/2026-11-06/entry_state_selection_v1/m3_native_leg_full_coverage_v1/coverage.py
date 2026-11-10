"""Frozen all-original-AB direction coverage only; no economic replay."""
from pathlib import Path
import json,hashlib,sys,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
C=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code')
sys.path.insert(0,str(C))
from numeric import event_frame_numeric
from data_utils import eligible_prices
S={};t0=time.monotonic();missing_sources=[];regen_errors=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expected=None):
 p=Path(p);h=sha(p);S[str(p)]=h
 if expected:assert h==expected,str(p)
 return p
def unknown_stock(g,reason):
 z=g[['event_id','window','day','sid','name','sector','industry','event_type','I_qualified','PVR_known','I_and_PVR_known','PVR_score','sector_M3_n','sector_N','sector_K']].copy()
 z['source_valid']=False;z['native_prefix_exact']=False;z['leg_direction']=np.nan;z['gate']='UNKNOWN';z['unknown_reason']=reason
 for col in ['source_kind','source_path','segment_id','e0_target','i_target','i_buy','g_grade','event_today','native_close','raw_close']:z[col]=None
 return z
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def scopes(d):
 yield '2022_ALL',d[d.window.eq('2022')]
 yield '2022_Q1',d[d.window.eq('2022')&d.day.le(pd.Timestamp('2022-03-31'))]
 yield '2024_924',d[d.window.eq('2024_924')]
def equal(a,b):return ((a==b)|(np.isnan(a)&np.isnan(b))).all(axis=1)
assert (O/'PRE_REVIEW.json').exists(),'Independent pre-review required'
review=json.loads((O/'PRE_REVIEW.json').read_text());assert review['approved_to_compute'] is True
with (O/'RUN_ONCE.lock').open('x') as f:f.write(pd.Timestamp.now(tz='UTC').isoformat())
for f in [O/'PROTOCOL.json',O/'PRE_REVIEW.json',Path(__file__),C/'numeric.py',C/'data_utils.py']:src(f)
allbirth=pd.read_csv(src(R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'],dtype={'window':str})
e=allbirth[allbirth.window.isin(['2022','2024_924'])&allbirth.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy()
assert len(e)==19795 and e.event_id.is_unique and not e.duplicated(['window','day','sid']).any()
excluded=allbirth[allbirth.window.isin(['2022','2024_924'])&~allbirth.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
excluded.groupby(['window','event_type']).size().rename('not_AB_rows').reset_index().to_csv(O/'OUTSIDE_AB_DOMAIN_COUNTS.csv',index=False)
mm={m['symbol']:m for m in json.loads(src(U/'STOCK_MANIFEST.json').read_text())}
old=pd.read_csv(src(R/'m3_native_leg_entry_preflight_v1/SIGNAL_TIME_FEATURES.csv'),parse_dates=['signal_day'])
samples=set((r.sid,r.signal_day) for r in old.itertuples() if ((e.sid.eq(r.sid))&e.day.eq(r.signal_day)).any())
for _,g in e.groupby([e.window,e.day.dt.quarter]):
 r=g.sort_values(['sid','day']).iloc[0];samples.add((r.sid,r.day))
save('PREFIX_SAMPLE_FROZEN.json',[dict(sid=s,day=d) for s,d in sorted(samples)])
cols=['event','leg_direction','target','entered','exited','confirmation','structure_floor_price']
frames=[];prefixrows=[];sourcerows=[]
for num,(sid,g) in enumerate(e.groupby('sid',sort=True),1):
 m=mm[sid];pe=next(q for q in m['source_sha256'] if q.endswith('/events.parquet'));ps=str(Path(pe).with_name('signal.parquet'))
 try:
  b=pd.read_parquet(src(ps,m['source_sha256'][ps])).loc[:g.day.max()]
  ev=pd.read_parquet(src(pe,m['source_sha256'][pe])).reindex(b.index)
  f=pd.read_parquet(src(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])).reindex(b.index)
  validindex=eligible_prices(b).index
 except (FileNotFoundError,ValueError,KeyError) as err:
  missing_sources.append(dict(sid=sid,reason=repr(err),events=len(g)))
  frames.append(unknown_stock(g,'SOURCE_UNAVAILABLE:'+type(err).__name__));continue
 nativeok=pd.Series(False,index=b.index);fulls=[]
 for seg,bseg in b.groupby('segment_id',sort=False):
  try:
   bp=eligible_prices(bseg)
   re=event_frame_numeric(bp.close,bp.volume,joint=True,event_exit=False)
  except (ValueError,KeyError) as err:
   regen_errors.append(dict(sid=sid,segment=seg,reason=repr(err)))
   fulls.append(dict(sid=sid,segment=seg,through=bseg.index[-1],source_rows=len(bseg),native_rows=0,all_prefix_fields_exact=False,mismatch_rows=None,reason=repr(err)));continue
  ce=ev.reindex(re.index)
  good=equal(re[cols].to_numpy(float),ce[cols].to_numpy(float))
  nativeok.loc[re.index]=np.logical_and.accumulate(good)
  fulls.append(dict(sid=sid,segment=seg,through=bseg.index[-1],source_rows=len(bseg),native_rows=len(re),all_prefix_fields_exact=bool(good.all()),mismatch_rows=int((~good).sum())))
 for ss,day in sorted(samples):
  if ss!=sid:continue
  seg=b.at[day,'segment_id'];bp=eligible_prices(b.loc[:day][b.loc[:day].segment_id.eq(seg)])
  try:
   re=event_frame_numeric(bp.close,bp.volume,joint=True,event_exit=False)
   ce=ev.reindex(re.index)
   good=equal(re[cols].to_numpy(float),ce[cols].to_numpy(float))
   prefixrows.append(dict(sid=sid,signal_day=day,physical_prepared_prefix=True,rows=len(re),exact=bool(good.all())))
  except (ValueError,KeyError) as err:
   prefixrows.append(dict(sid=sid,signal_day=day,physical_prepared_prefix=True,rows=0,exact=False,reason=repr(err)))
 z=g[['event_id','window','day','sid','name','sector','industry','event_type','I_qualified','PVR_known','I_and_PVR_known','PVR_score','sector_M3_n','sector_N','sector_K']].copy()
 d=pd.DatetimeIndex(z.day);bb=b.reindex(d);ee=ev.reindex(d);ff=f.reindex(d)
 valid=pd.Series(d.isin(validindex),index=d)&np.isfinite(bb.volume)&bb.volume.gt(0)&ff.segment_id.eq(bb.segment_id)&ee.segment_id.eq(bb.segment_id)&bb.source_kind.notna()&bb.source_path.notna()
 agreement=nativeok.reindex(d).fillna(False)
 leg=ee.leg_direction
 z['source_valid']=valid.to_numpy();z['native_prefix_exact']=agreement.to_numpy();z['leg_direction']=leg.to_numpy()
 z['gate']=np.where(valid.to_numpy()&agreement.to_numpy()&leg.eq(1).to_numpy(),'ALLOW',np.where(valid.to_numpy()&agreement.to_numpy()&leg.eq(-1).to_numpy(),'DENY','UNKNOWN'))
 z['unknown_reason']=np.where(~valid.to_numpy(),'SOURCE_OR_SEGMENT_INVALID',np.where(~agreement.to_numpy(),'NATIVE_PREFIX_MISMATCH',np.where(~leg.isin([-1,1]).to_numpy(),'DIRECTION_UNKNOWN','')))
 for dest,frame,col in [('source_kind',bb,'source_kind'),('source_path',bb,'source_path'),('segment_id',bb,'segment_id'),('e0_target',ff,'e0_target'),('i_target',ff,'i_target'),('i_buy',ff,'i_buy'),('g_grade',ff,'g_grade'),('event_today',ee,'event'),('native_close',bb,'close'),('raw_close',bb,'raw_close')]:z[dest]=frame[col].to_numpy()
 assert np.array_equal(z.i_target.to_numpy(float),g.i_target.to_numpy(float),equal_nan=True)
 frames.append(z);sourcerows.extend(fulls)
 if num%200==0:
  print('STOCKS',num,'/',e.sid.nunique(),'SECONDS',round(time.monotonic()-t0,2),flush=True)
  save('PROGRESS.json',dict(stocks_done=num,stocks_total=e.sid.nunique(),phase='native_signal_coverage',seconds=time.monotonic()-t0))
features=pd.concat(frames,ignore_index=True).sort_values(['window','day','sector','sid'])
assert len(features)==19795 and features.event_id.is_unique
features.to_csv(O/'ALL_AB_SIGNAL_TIME_FEATURES.csv',index=False)
pd.DataFrame(sourcerows).to_csv(O/'NATIVE_FULL_PREFIX_CHECKS.csv',index=False)
pd.DataFrame(prefixrows).to_csv(O/'PHYSICAL_PREFIX_CHECKS.csv',index=False)
# Prior fixed cases are an exact projection where within current domain.
q=old.merge(features,on=['sid'],suffixes=('_old','_new'));q=q[q.signal_day.eq(q.day)]
assert len(q)==24 and q.gate_old.eq(q.gate_new).all()
q[['sid','day','gate_old','gate_new']].to_csv(O/'PRIOR_FIXED_IDENTITY.csv',index=False)
save('FEATURE_SEAL.json',dict(created_utc=pd.Timestamp.now(tz='UTC'),rows=len(features),sha256=sha(O/'ALL_AB_SIGNAL_TIME_FEATURES.csv'),protocol_sha256=sha(O/'PROTOCOL.json'),script_sha256=sha(__file__),no_future_label_or_recovery_fields=True))
coverage=[]
for scope,g in scopes(features):
 for level,sub in [('ALL_AB',g),('ORIGINAL_I_PVR_QUALIFIED',g[g.I_and_PVR_known.eq(True)])]:
  for gate in ['ALLOW','DENY','UNKNOWN']:
   a=sub[sub.gate.eq(gate)]
   coverage.append(dict(scope=scope,level=level,gate=gate,denominator=len(sub),events=len(a),fraction=len(a)/len(sub) if len(sub) else None,stocks=a.sid.nunique(),dates=a.day.nunique(),sector_days=len(a[['day','sector']].drop_duplicates())))
pd.DataFrame(coverage).to_csv(O/'INVITATION_COVERAGE.csv',index=False)
# Only now attach previously known corrected old labels, no new economics.
labs=[]
for path in [R/'m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv',R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv']:
 a=pd.read_csv(src(path),parse_dates=['signal_day','entry_day','exit_day'],dtype={'window':str});labs.append(a[a.arm.eq('A_UNION_B')])
lab=pd.concat(labs,ignore_index=True)
assert len(lab)==4086 and lab.event_id.is_unique and set(lab.event_id)<=set(features.event_id)
a=lab.merge(features[['event_id','day','gate','unknown_reason','source_valid','native_prefix_exact','leg_direction']],on='event_id',validate='one_to_one')
assert a.signal_day.eq(a.day).all()
a.to_csv(O/'OLD_SELECTED_ROUNDS_WITH_DIRECTION.csv',index=False)
leftcols=['event_id','round_id','status','entry_status','financial_coverage_status','evidence_usable_closed','core_net','core_return','net_pnl','net_return_on_buy_cash']
joined=features.merge(lab[leftcols],on='event_id',how='left',validate='one_to_one',indicator=True)
joined['old_selected']=joined['_merge'].eq('both')
assert len(joined)==19795 and joined.old_selected.sum()==4086
joined.drop(columns='_merge').to_csv(O/'ALL_AB_WITH_OLD_SELECTION_STATUS.csv',index=False)
status=[];summ=[]
for scope,g in scopes(a):
 for gate in ['ALLOW','DENY','UNKNOWN']:
  gg=g[g.gate.eq(gate)]
  for key,z in gg.groupby(['status','entry_status','financial_coverage_status','evidence_usable_closed'],dropna=False):
   status.append(dict(scope=scope,gate=gate,status=key[0],entry_status=key[1],financial_coverage_status=key[2],evidence_usable_closed=key[3],count=len(z)))
  known=gg[gg.evidence_usable_closed.eq(True)]
  for layer,col,ret in [('CORE','core_net','core_return'),('FULL','net_pnl','net_return_on_buy_cash')]:
   assert known[col].notna().all() and known[ret].notna().all()
   positive=known[col]>0;negative=known[col]<0;zero=known[col]==0
   summ.append(dict(scope=scope,gate=gate,layer=layer,selected_permits=len(gg),usable_closed=len(known),old_wins=int(positive.sum()),old_losses=int(negative.sum()),old_zero=int(zero.sum()),old_net_sum=float(known[col].sum()),old_gross_profit=float(known.loc[positive,col].sum()),old_gross_loss=float(known.loc[negative,col].sum()),old_winrate=float(positive.mean()) if len(known) else None,old_mean_win=float(known.loc[positive,col].mean()),old_mean_loss=float(known.loc[negative,col].mean()),old_payoff=float(known.loc[positive,col].mean()/-known.loc[negative,col].mean()) if negative.any() and positive.any() else None,old_final_net_ge30=int(known[ret].ge(.3).sum()),old_final_net_ge50=int(known[ret].ge(.5).sum()),other_unusable_selected=len(gg)-len(known)))
pd.DataFrame(status).to_csv(O/'ALL_STATUS_COUNTS.csv',index=False)
pd.DataFrame(summ).to_csv(O/'OLD_LABEL_COVERAGE.csv',index=False)
denied=a[a.gate.eq('DENY')];denied.to_csv(O/'ALL_DENIED_OLD_SELECTED.csv',index=False)
tails=denied[denied.evidence_usable_closed.eq(True)&(denied.core_return.ge(.3)|denied.net_return_on_buy_cash.ge(.3))]
tails.to_csv(O/'DENIED_OLD_FINAL_GE30_TAILS.csv',index=False)
save('MISSING_SOURCES.json',missing_sources);save('REGEN_ERRORS.json',regen_errors)
save('SOURCE_HASHES.json',S);after={p:sha(p) for p in S};save('SOURCE_HASHES_AFTER.json',after);assert S==after
qa=dict(rows=len(features),stocks=features.sid.nunique(),selected=len(a),all_event_keys_unique=True,selected_event_identity_exact=True,fixed_projection_rows=len(q),fixed_projection_exact=True,all_native_fields_exact=all(r['all_prefix_fields_exact'] for r in sourcerows),physical_prefix_checks=len(prefixrows),all_physical_prefix_exact=all(r['exact'] for r in prefixrows),source_hash_count=len(S),all_sources_unchanged=S==after,gates=features.gate.value_counts().to_dict(),no_new_economics=True,seconds=time.monotonic()-t0)
save('QA.json',qa);save('DONE.json',qa);print(json.dumps(qa,indent=2),flush=True)
print(pd.DataFrame(coverage).to_string(index=False),flush=True)
print(pd.DataFrame(summ).to_string(index=False),flush=True)
