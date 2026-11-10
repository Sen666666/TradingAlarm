"""One frozen native E0-leg preflight. No new economic ledger or parameter search."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,sys,time
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
CODE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code')
sys.path.insert(0,str(CODE))
from numeric import event_frame_numeric
from data_utils import eligible_prices
S={};t0=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expected=None):
 p=Path(p);h=sha(p);S[str(p)]=h
 if expected:assert h==expected,str(p)
 return p
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def v(x):return None if pd.isna(x) else x
with (O/'RUN_ONCE.lock').open('x') as z:z.write(pd.Timestamp.now(tz='UTC').isoformat())
p=json.loads(src(O/'PROTOCOL.json').read_text())
for x in [Path(__file__),CODE/'numeric.py',CODE/'data_utils.py']:src(x)
sm={m['symbol']:m for m in json.loads(src(U/'STOCK_MANIFEST.json').read_text())}
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
cal=cal[cal<='2026-06-30']
birth=pd.read_csv(src(R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'])
D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
M=pd.read_parquet(src(D/'RIGHT3.parquet'));K=pd.read_parquet(src(D/'KNOWN3.parquet'))
rows=[];paths=[];checks=[];future=[]
for c in p['cases']:
 sid=c['sid'];d=pd.Timestamp(c['signal_day']);m=sm[sid]
 pe=next(q for q in m['source_sha256'] if q.endswith('/events.parquet'));ps=str(Path(pe).with_name('signal.parquet'))
 b=pd.read_parquet(src(ps,m['source_sha256'][ps]))
 e=pd.read_parquet(src(pe,m['source_sha256'][pe]))
 f=pd.read_parquet(src(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]))
 cp=pd.read_parquet(src(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']]))
 inp=pd.read_parquet(src(m['refs']['CP1_input'],m['output_sha256'][m['refs']['CP1_input']]))
 assert d in b.index and d in f.index and d in e.index
 prefix=b.loc[:d].copy();sg=b.at[d,'segment_id'];prefix=prefix[prefix.segment_id.eq(sg)]
 pp=eligible_prices(prefix);re=event_frame_numeric(pp.close,pp.volume,joint=True,event_exit=False)
 cached=e.reindex(re.index)
 equal={x:bool(np.allclose(re[x],cached[x],rtol=0,atol=0,equal_nan=True)) for x in ['event','leg_direction','target','entered','exited','confirmation','structure_floor_price']}
 end_exact=all(equal.values())
 checks.append(dict(sid=sid,signal_day=d,physical_prepared_source_cutoff=d,prefix_rows=len(prefix),regenerated_rows=len(re),**equal))
 valid=d in pp.index and np.isfinite(b.at[d,'volume']) and b.at[d,'volume']>0 and f.at[d,'segment_id']==sg and e.at[d,'segment_id']==sg and pd.notna(b.at[d,'source_kind']) and pd.notna(b.at[d,'source_path'])
 leg=v(e.at[d,'leg_direction']);gate='ALLOW' if valid and end_exact and leg==1 else 'DENY' if valid and end_exact and leg==-1 else 'UNKNOWN'
 ep=e.loc[:d];ep=ep[ep.segment_id.eq(sg)];evt=ep[ep.event.isin([-1,1])]
 last=evt.iloc[-1] if len(evt) else None;lastd=evt.index[-1] if len(evt) else None
 br=birth[birth.sid.eq(sid)&birth.day.eq(d)]
 ab=br[br.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
 row=dict(**c,gate=gate,source_valid=valid,full_prefix_native_exact=end_exact,leg_direction=leg,event_today=v(e.at[d,'event']),
 last_direction_event_day=lastd,last_direction_event=v(last.event) if last is not None else None,
 last_confirmed_pivot_day=v(last.confirmed_pivot_date) if last is not None else None,
 e0_target=v(f.at[d,'e0_target']),i_target=v(f.at[d,'i_target']),i_buy=v(f.at[d,'i_buy']),g_grade=v(f.at[d,'g_grade']),
 close=v(f.at[d,'close']),raw_close=v(f.at[d,'raw_close']),i_floor=v(f.at[d,'i_floor']),
 stock_M3_known=bool(K.at[d,sid]),stock_M3=bool(M.at[d,sid]) if K.at[d,sid] else None,
 CP=v(cp.at[d,'receipt']),CP_credit=v(cp.at[d,'next_credit']),CP_phase=v(cp.at[d,'next_phase']),
 amount=v(inp.at[d,'amount']),volume=v(b.at[d,'volume']),original_AB_events=len(ab),
 original_event_type='|'.join(br.event_type),original_I_PVR_qualified=bool(ab.I_and_PVR_known.any()),
 native_facts_close_difference=float(f.at[d,'close']-b.at[d,'close']),
 source_kind=b.at[d,'source_kind'],source_path=b.at[d,'source_path'],segment_id=sg,
 earliest_next_common_open=cal[cal.get_loc(d)+1] if d in cal and cal.get_loc(d)+1<len(cal) else None)
 if len(ab):
  assert len(ab)==1
  row.update(event_id=ab.iloc[0].event_id,PVR_score=ab.iloc[0].PVR_score,sector=ab.iloc[0].sector,industry=ab.iloc[0].industry,
   sector_M3_n=ab.iloc[0].sector_M3_n,sector_K=ab.iloc[0].sector_K,sector_N=ab.iloc[0].sector_N)
 else:row['event_id']=None
 rows.append(row)
 # Future below is for causal-path explanation only; never feeds gate.
 ix=cal.get_loc(d);ds=cal[max(0,ix-21):min(len(cal),ix+11)]
 for td in ds:
  q=dict(sid=sid,signal_day=d,day=td,relative_day=cal.get_loc(td)-ix,is_future_for_gate=td>d)
  for dest,frame,field in [('raw_close',f,'raw_close'),('close',f,'close'),('i_target',f,'i_target'),('i_floor',f,'i_floor'),('i_buy',f,'i_buy'),('g_grade',f,'g_grade'),('e0_target',f,'e0_target'),('leg_direction',e,'leg_direction'),('event',e,'event'),('confirmation',e,'confirmation'),('CP',cp,'receipt'),('CP_credit',cp,'next_credit'),('CP_displacement',cp,'displacement'),('amount',inp,'amount'),('raw_open',b,'raw_open')]:
   q[dest]=v(frame.at[td,field]) if td in frame.index else None
  q['stock_M3']=bool(M.at[td,sid]) if td in M.index and K.at[td,sid] else None
  paths.append(q)
 if gate=='DENY':
  rr=birth[birth.sid.eq(sid)&birth.day.gt(d)&birth.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].sort_values('day')
  nextup=e[(e.index>d)&e.event.eq(1)&e.segment_id.eq(sg)]
  row['next_native_UP_day']=nextup.index[0] if len(nextup) else None
  for z in rr.itertuples():
   if len(future)>500:break
   if (pd.Timestamp(z.day)-d).days>180:break
   future.append(dict(original_signal_day=d,sid=sid,next_signal_day=z.day,event_type=z.event_type,I_PVR_qualified=z.I_and_PVR_known,leg_direction=v(e.at[z.day,'leg_direction']) if z.day in e.index else None,I_target=z.i_target,PVR_score=z.PVR_score))
features=pd.DataFrame(rows)
features.to_csv(O/'FEATURES_PRELABEL.csv',index=False)
pd.DataFrame(checks).to_csv(O/'NATIVE_PREFIX_CHECKS.csv',index=False)
pd.DataFrame(paths).to_csv(O/'DAILY_PATHS.csv',index=False)
pd.DataFrame(future).to_csv(O/'DENIED_NEXT_ORIGINAL_INVITATIONS.csv',index=False)
save('FEATURE_SEAL.json',dict(created_utc=pd.Timestamp.now(tz='UTC'),feature_sha256=sha(O/'FEATURES_PRELABEL.csv'),protocol_sha256=sha(O/'PROTOCOL.json'),code_sha256=sha(__file__),no_new_economics=True))
# Corrected old labels only after features sealed.
labs=[]
for q in [R/'m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv',R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv']:
 ll=pd.read_csv(src(q),parse_dates=['signal_day','entry_day','exit_day']);labs.append(ll[ll.arm.eq('A_UNION_B')])
ll=pd.concat(labs,ignore_index=True)
assert not ll.duplicated(['sid','signal_day']).any()
features['signal_day']=pd.to_datetime(features.signal_day)
cols=['sid','signal_day','round_id','name','entry_day','entry_open','entry_q','entry_fee','exit_day','exit_reason','core_net','core_return','net_pnl','net_return_on_buy_cash','evidence_usable_closed','financial_coverage_status']
joined=features.merge(ll[cols],on=['sid','signal_day'],how='left',validate='one_to_one')
joined.to_csv(O/'FIXED_CASES_WITH_OLD_LABELS.csv',index=False)
lab=joined[joined.evidence_usable_closed.eq(True)].copy();lab['old_core_win']=lab.core_net>0;lab['old_core_ge30']=lab.core_return>=.3;lab['old_full_ge30']=lab.net_return_on_buy_cash>=.3
summary=lab.groupby(['gate']).agg(cases=('sid','size'),old_core_wins=('old_core_win','sum'),old_core_net=('core_net','sum'),old_full_net=('net_pnl','sum'),old_core_ge30=('old_core_ge30','sum'),old_full_ge30=('old_full_ge30','sum')).reset_index()
summary.to_csv(O/'DESCRIPTIVE_OLD_LABEL_SUMMARY.csv',index=False)
save('SOURCE_HASHES.json',S);after={q:sha(q) for q in S};save('SOURCE_HASHES_AFTER.json',after);assert S==after
qa=dict(cases=len(features),stocks=features.sid.nunique(),gates=features.gate.value_counts().to_dict(),original_AB_events=int(features.original_AB_events.sum()),corrected_old_label_rows=len(lab),prefix_checks=len(checks),all_original_native_prefix_fields_exact=all(x['full_prefix_native_exact'] for x in rows),native_facts_close_max_abs=float(features.native_facts_close_difference.abs().max()),source_count=len(S),sources_unchanged=S==after,seconds=time.monotonic()-t0,no_new_economics=True,all_future_rows_only_descriptive=True)
save('QA.json',qa);save('DONE.json',qa)
print(joined[['sid','signal_day','name','gate','leg_direction','last_direction_event_day','original_AB_events','core_net','core_return']].to_string(index=False),flush=True)
print(json.dumps(qa,ensure_ascii=False,indent=2),flush=True)
print(summary.to_string(index=False),flush=True)
