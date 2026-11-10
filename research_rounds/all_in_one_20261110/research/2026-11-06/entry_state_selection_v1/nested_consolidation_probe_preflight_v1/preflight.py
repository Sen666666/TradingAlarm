from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def cleanval(v):return None if pd.isna(v) else v
assert not (O/'RUN_ONCE.json').exists()
cases=json.load(open(R/'frontier_volume_bound_preflight_v1/FIXED_CASES.json'))
cases += [dict(sid=s,day=d,role=role) for s,d,role in [('002385.SZ','2022-03-04','原PVR亏例大北农'),('300182.SZ','2022-01-04','原PVR亏例捷成股份'),('601607.SH','2022-03-24','原PVR亏例上海医药'),('600606.SH','2022-03-22','原PVR盈利绿地控股'),('688582.SH','2024-07-29','原PVR盈利芯动联科'),('002317.SZ','2022-10-14','原PVR盈利众生药业')]]
dump('FIXED_CASES.json',cases)
protocol=dict(name='nested_consolidation_probe_preflight_v1',scope='25 fixed previously seen cases and each case prior20 through next5 common sessions; no economic run, ranking or optimized thresholds.',formula='At close t, old block[t-20,t-11], recent block[t-10,t-1]. U0=maxH old,L0=minL old,U1=maxH recent,L1=minL recent,V0=median amount old,V1=median amount recent. Nested=(U1<=U0 and L1>=L0 and U1-L1<U0-L0). Dry=(V1<V0). Local break=(C_t>U1). Candidate=nested and dry and localbreak. Incremental early=(candidate and C_t<=max(U0,U1)). Exact10/10 splits inherited20day reference; zero/natural order boundaries, no tuned cutoffs.',purpose='New local consolidation breakout event below the older20day high can invite an independent small probe, not PVR/DMI/Qrange score modification and not an added gate to original births. Current first probe routes remain unchanged. Not a certified VCP or supply-exhaustion measure.',consumer_draft='Unimplemented market contract only: original AB/PRICE priority and existing births preserved. A new candidate may create a local root with old known local floorL1 and a next-common-open-only receipt if no existing position/parent/unsettled obligations. One small target under unchanged original budget/risk. Root only fails at close<=oldS, no same-day re-open; no permanent blacklist, no fixed cooldown, fresh later preparation may reenter. Existing root/parent prevents duplicated probes; new frontier receipts follow original target/ACK responsibility. Profit-before-add unchanged; no added confirmation waiting gate. Exact union/collision/financial consumer requires a separately frozen implementation, not simulated here.',postbreak='Only report observed subsequent close relative to fixed candidateU1 and localL1, next day onwards. Not used to certify birth or select fixed cases; no new retest score/gate. Current cumulative amount never called inventory or net flow.',known='21 consecutive common sessions; price positive and valid, raw/native coherent; no source_kind/path/segment change, factor constant; prior20 amount positive and volume eligible; no dropna clock. Unknown separate.',duplicate='PriorJ:two realized legs plus volatility/amount ratio. PriorZ:fixedI-root first retest unit amount. PriorA:age weighted historical bar relative current price. LER:shortrest then yesterdayHigh insideE0. This tests two completed nested10bar price boxes and prebreak amount contraction, withoutE0 requirement; not first use of consolidation or volume contraction.',limits='Known outcomes of fixed cases already seen; nonPIT/static pool; day-level fills/ACK unknown; no strategy win rate, filtering PnL, threshold sweep or full account.',clock='Candidate requires tclose, earliest next-commonOPEN. No future prices used in calculation.')
dump('PROTOCOL.json',protocol);dump('RUN_ONCE.json',dict(started_utc=str(pd.Timestamp.now(tz='UTC')),protocol_sha=sha(O/'PROTOCOL.json'),cases_sha=sha(O/'FIXED_CASES.json')))
manifest={x['symbol']:x for x in json.load(open(M))}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);sources={};hashes={str(M):sha(M),str(H):sha(H)}
for sid in sorted({x['sid'] for x in cases}):
 m=manifest[sid];p=Path(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet')));assert sha(p)==m['source_sha256'][str(p)];hashes[str(p)]=sha(p);sources[sid]=pd.read_parquet(p)
def feature(raw,day):
 pos=cal.get_indexer([day])[0];out=dict(day=str(day.date()),status='UNKNOWN',reason=None)
 if pos<20:return out|dict(reason='SHORT_COMMON_HISTORY')
 x=raw.reindex(cal[pos-20:pos+1]);prices=['open','high','low','close','raw_open','raw_high','raw_low','raw_close','adjustment_factor']
 if x[prices].isna().any().any() or not x[prices].gt(0).all().all():return out|dict(reason='MISSING_OR_INVALID_PRICE')
 for c in ['observed_bar','is_observed_bar','price_eligible']:
  if not x[c].eq(True).all():return out|dict(reason='PRICE_INELIGIBLE')
 for c in ['source_invalid','synthetic_event_bar']:
  if not x[c].eq(False).all():return out|dict(reason='SYNTHETIC_OR_INVALID')
 for c in ['source_kind','source_path','segment_id']:
  if x[c].isna().any() or x[c].nunique()!=1:return out|dict(reason='SOURCE_CHANGE')
 if not np.isclose(x.adjustment_factor,x.adjustment_factor.iloc[-1],rtol=1e-12,atol=1e-12).all():return out|dict(reason='FACTOR_CHANGE')
 for c in ['open','high','low','close']:
  if not np.allclose(x[c],x['raw_'+c]*x.adjustment_factor,rtol=1e-12,atol=1e-8):return out|dict(reason='COORDINATE_MISMATCH')
 if not (x.high.ge(x[['open','close']].max(axis=1))&x.low.le(x[['open','close']].min(axis=1))&x.high.ge(x.low)).all():return out|dict(reason='INVALID_OHLC')
 a=x.iloc[:10];b=x.iloc[10:20];r=x.iloc[-1]
 if not (x.iloc[:20].amount.gt(0)&np.isfinite(x.iloc[:20].amount)&x.iloc[:20].volume_eligible.eq(True)).all():return out|dict(reason='AMOUNT_UNKNOWN')
 U0=float(a.high.max());L0=float(a.low.min());U1=float(b.high.max());L1=float(b.low.min());V0=float(a.amount.median());V1=float(b.amount.median());C=float(r.close);factor=float(r.adjustment_factor)
 nested=U1<=U0 and L1>=L0 and U1-L1<U0-L0;dry=V1<V0;local=C>U1;candidate=bool(nested and dry and local)
 return out|dict(status='KNOWN',reason=None,U0=U0/factor,L0=L0/factor,U1=U1/factor,L1=L1/factor,C=C/factor,range_ratio=(U1-L1)/(U0-L0) if U0>L0 else None,amount_ratio=V1/V0,upper_nested=bool(U1<=U0),lower_nested=bool(L1>=L0),nested=bool(nested),dry=bool(dry),local_break=bool(local),candidate=candidate,incremental_early=bool(candidate and C<=max(U0,U1)),raw_floor_distance=1-L1/C,old20_break=bool(C>max(U0,U1)),pre_recent_return=float(b.close.iloc[-1]/b.close.iloc[0]-1),pre_old_return=float(a.close.iloc[-1]/a.close.iloc[0]-1),V0=V0,V1=V1,factor=factor)
targets=[];daily=[];prefix=[]
for i,case in enumerate(cases):
 sid=case['sid'];day=pd.Timestamp(case['day']);pos=cal.get_indexer([day])[0];raw=sources[sid];r=feature(raw,day);targets.append(dict(case_id=i)|case|r)
 for d in cal[max(0,pos-20):min(len(cal),pos+6)]:
  z=feature(raw,d);daily.append(dict(case_id=i,sid=sid,target_day=case['day'],role=case['role'],relative_session=int(cal.get_loc(d)-pos),**z))
 for d in cal[max(20,pos-1):pos+1]:
  a=feature(raw,d);b=feature(raw.loc[:d],d);assert a==b
  future=raw.copy();future.loc[future.index>d,['open','high','low','close','amount']]=1e15
  assert feature(future,d)==a
  prefix.append(dict(case_id=i,sid=sid,day=str(d.date()),physical_prefix_equal=True,future_perturbation_equal=True))
t=pd.DataFrame(targets);d=pd.DataFrame(daily);t.to_csv(O/'FIXED_TARGET_FEATURES.csv',index=False);d.to_csv(O/'CASE_DAILY_FEATURES.csv',index=False)
events=d[d.candidate.eq(True)].copy();events.to_csv(O/'ALL_FIXED_WINDOW_CANDIDATE_FACTS.csv',index=False)
# Keep each setup's future observations as dated diagnostics only; no outcome labels are loaded.
post=[]
for e in events.itertuples():
 raw=sources[e.sid];p=cal.get_loc(pd.Timestamp(e.day))
 for ahead in range(1,6):
  if p+ahead>=len(cal):continue
  day=cal[p+ahead]
  if day not in raw.index:post.append(dict(case_id=e.case_id,sid=e.sid,event_day=e.day,known_at=str(day.date()),ahead=ahead,status='MISSING'));continue
  r=raw.loc[day];valid=pd.notna(r.raw_close) and bool(r.observed_bar) and float(r.adjustment_factor)==float(e.factor)
  post.append(dict(case_id=e.case_id,sid=e.sid,event_day=e.day,known_at=str(day.date()),ahead=ahead,status='DIAGNOSTIC_ONLY' if valid else 'UNKNOWN',raw_C=float(r.raw_close) if valid else None,above_frozen_U1=bool(r.raw_close>e.U1) if valid else None,above_local_floor=bool(r.raw_close>e.L1) if valid else None))
pd.DataFrame(post).to_csv(O/'POST_EVENT_DATED_OBSERVATIONS.csv',index=False)
pd.DataFrame(prefix).to_csv(O/'PREFIX_QA.csv',index=False);dump('FEATURE_SEAL.json',dict(time=str(pd.Timestamp.now(tz='UTC')),source_hashes=hashes,features_hash=sha(O/'FIXED_TARGET_FEATURES.csv'),no_future_labels_for_features=True))
assert all(sha(p)==h for p,h in hashes.items())
dump('QA.json',dict(cases=len(t),stocks=t.sid.nunique(),daily_rows=len(d),target_known=int(t.status.eq('KNOWN').sum()),target_unknown=int(t.status.eq('UNKNOWN').sum()),target_candidates=int(t.candidate.eq(True).sum()),target_incremental=int(t.incremental_early.eq(True).sum()),past_candidate_rows=int((events.relative_session<=0).sum()),all_candidate_rows=len(events),unique_candidate_stockdays=len(events.drop_duplicates(['sid','day'])),prefix_checks=len(prefix),source_hashes_unchanged=True,account_runs=0,ranking_runs=0,parameter_sweeps=0,economic_labels_loaded=0))
print(t[['sid','day','role','status','range_ratio','amount_ratio','nested','dry','local_break','candidate','incremental_early']].to_string(index=False))
print('PAST LOCAL BREAKOUTS\n',events[events.relative_session<=0][['sid','day','target_day','role','relative_session','U0','U1','L1','C','amount_ratio','incremental_early']].to_string(index=False))
print('QA',json.load(open(O/'QA.json')))
