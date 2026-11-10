from pathlib import Path
import pandas as pd,numpy as np,json,math,hashlib,sys,time
O=Path(__file__).resolve().parent;R=O.parent;U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
C=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code')
sys.path.insert(0,str(C));from numeric import log_ratio;from data_utils import eligible_prices,boolean_column
S={};t0=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p):p=Path(p);S[str(p)]=sha(p);return p
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
with (O/'RUN_ONCE.lock').open('x') as h:h.write(pd.Timestamp.now(tz='UTC').isoformat())
for p in [O/'PROTOCOL.json',Path(__file__),C/'numeric.py',C/'data_utils.py']:src(p)
def lag(r,b):
 r=np.asarray(r,float);b=np.asarray(b,float);assert len(r)==len(b)==21
 x=r-math.fsum(r)/21;y=b-math.fsum(b)/21
 if np.ptp(r)==0:x=np.zeros(21)
 if np.ptp(b)==0:y=np.zeros(21)
 F=math.fsum(y[:-1]*x[1:]);G=math.fsum(x[:-1]*y[1:]);D=math.fsum(np.abs(y[:-1]*x[1:])+np.abs(x[:-1]*y[1:]))
 den=math.fsum(x*x);ar=math.fsum(x[:-1]*x[1:])/den if den>0 else 0.
 return dict(Z=(F-G)/D if D>0 else 0.,F=F,R=G,D=D,var_r=math.fsum(x*x)/21,var_log_amount=math.fsum(y*y)/21,AR1=ar)
r=np.zeros(21);b=np.zeros(21);b[8]=1;r[9]=.01
base=lag(r,b);tests=[]
def check(name,actual,expected):tests.append(dict(name=name,actual=float(actual),expected=float(expected),pass_check=bool(np.isclose(actual,expected,rtol=1e-10,atol=1e-12))))
check('constant_amount',lag(r,np.ones(21))['Z'],0)
check('constant_returns',lag(np.ones(21)*.01,b)['Z'],0)
check('log_amount_unit_translation',lag(r,b+math.log(10000))['Z'],base['Z'])
check('return_positive_scale',lag(r*17,b)['Z'],base['Z'])
check('paired_observation_reversal',lag(r[::-1],b[::-1])['Z'],-base['Z'])
check('physical_price_path_reversal',lag(-r[::-1],b[::-1])['Z'],base['Z'])
check('exchange_amount_and_return_pulse',lag(b*.01,r*100)['Z'],-base['Z'])
assert base['Z']>0 and all(q['pass_check'] for q in tests)
save('SYNTHETIC_CONTROLS.json',dict(checks=tests,lead_pulse=base,pure_price_driven_volume_example=lag(np.cos(np.arange(21)*.3)*.01,np.cos((np.arange(21)-1)*.3)),note='Nonzero pure lagged-price response is a semantic counterexample, not evidence of informed volume.'))
a=pd.read_csv(src(R/'m3_native_leg_entry_preflight_v1/SIGNAL_TIME_FEATURES.csv'),parse_dates=['signal_day'])
b=pd.read_csv(src(R/'m3_q1_entry_path_strata_v1/ALL_Q1_TAIL_SAME_DAY_SECTOR_CONTEXT.csv'),parse_dates=['signal_day'])
cases=pd.concat([a[['sid','signal_day','scope']],b[['sid','signal_day']].assign(scope='prior_all_Q1_tail_and_same_day_peers')],ignore_index=True).drop_duplicates(['sid','signal_day'])
cases.to_csv(O/'FIXED_CASE_IDENTITIES.csv',index=False);assert len(cases)==40
manifest={m['symbol']:m for m in json.loads(src(U/'STOCK_MANIFEST.json').read_text())}
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
with np.load(src(H),allow_pickle=False) as hh:cal=pd.DatetimeIndex(hh['dates'])
cache={};out=[];prefix=[];daily=[]
for sid,g in cases.groupby('sid'):
 m=manifest[sid];pp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 frame=pd.read_parquet(src(pp));assert sha(pp)==m['source_sha256'][pp]
 f=pd.read_parquet(src(m['refs']['facts']));inp=pd.read_parquet(src(m['refs']['CP1_input']))
 cp=pd.read_parquet(src(m['refs']['CP1']))
 def point(d,bb,ff,ii):
  k=cal.get_loc(d);days=cal[k-21:k+1];result=dict(known=False,reason=None)
  if len(days)!=22:return dict(known=False,reason='SHORT_CALENDAR')
  z=bb.reindex(days);facts=ff.reindex(days);i=ii.reindex(days)
  valid=days.isin(eligible_prices(bb).index)&np.isfinite(z.close)&z.close.gt(0)&boolean_column(z,'price_eligible',False)
  good=bool(valid.all()) and z[['source_kind','source_path','segment_id']].notna().all().all() and z[['source_kind','source_path','segment_id']].nunique(dropna=False).eq(1).all() and facts.segment_id.eq(z.segment_id).all() and i.segment_id.eq(z.segment_id).all()
  good=good and bool(np.isfinite(i.amount.iloc[1:]).all() and i.amount.iloc[1:].gt(0).all())
  good=good and bool(i.close.eq(z.close).all() and facts.close.eq(z.close).all())
  if not good:return dict(known=False,reason='SOURCE_PRICE_AMOUNT_OR_SEGMENT_UNKNOWN')
  prices=z.close.to_numpy(float);amount=i.amount.iloc[1:].to_numpy(float)
  rr=np.array([log_ratio(prices[j],prices[j-1]) for j in range(1,22)])
  bb=np.array([log_ratio(v,amount[0]) for v in amount])
  res=dict(known=True,reason='KNOWN',**lag(rr,bb),ret21=math.fsum(rr),amount_ratio_end_start=amount[-1]/amount[0],e0_target=ff.at[d,'e0_target'],i_target=ff.at[d,'i_target'],i_buy=ff.at[d,'i_buy'],g_grade=ff.at[d,'g_grade'],close=ff.at[d,'close'],source_kind=z.source_kind.iloc[-1],source_path=z.source_path.iloc[-1],segment_id=z.segment_id.iloc[-1])
  return res
 for q in g.itertuples():
  d=q.signal_day;v=point(d,frame,f,inp);w=point(d,frame.loc[:d],f.loc[:d],inp.loc[:d])
  exact=all((pd.isna(vv) and pd.isna(w[k])) or vv==w[k] for k,vv in v.items());assert exact
  prefix.append(dict(sid=sid,signal_day=d,physical_in_memory_input_truncated=True,exact=exact))
  row=dict(sid=sid,signal_day=d,scope=q.scope,**v)
  row['sign']='UNKNOWN' if not v['known'] else 'POSITIVE' if v['Z']>0 else 'NEGATIVE' if v['Z']<0 else 'ZERO'
  row['earliest_next_common_open']=cal[cal.get_loc(d)+1] if cal.get_loc(d)+1<len(cal) else pd.NaT
  row['CP']=cp.at[d,'receipt'] if d in cp.index else None
  out.append(row)
  for day in cal[cal.get_loc(d)-21:cal.get_loc(d)+1]:
   daily.append(dict(sid=sid,signal_day=d,day=day,close=frame.close.get(day),amount=inp.amount.get(day),segment=frame.segment_id.get(day)))
features=pd.DataFrame(out)
features.to_csv(O/'FEATURES_PRELABEL.csv',index=False);pd.DataFrame(daily).to_csv(O/'FIXED_INPUT_PATHS.csv',index=False);pd.DataFrame(prefix).to_csv(O/'PREFIX_CHECKS.csv',index=False)
save('FEATURE_SEAL.json',dict(rows=len(features),feature_hash=sha(O/'FEATURES_PRELABEL.csv'),created_utc=pd.Timestamp.now(tz='UTC'),all_cases_fixed_before_features=True))
labs=pd.read_csv(src(R/'m3_q1_entry_path_strata_v1/ENTRY_FEATURES_WITH_OLD_LABELS.csv'),parse_dates=['signal_day'])
cols=['sid','signal_day','round_id','event_id','window','name','entry_type','status','entry_status','evidence_usable_closed','core_net','core_return','net_pnl','net_return_on_buy_cash']
ans=features.merge(labs[cols],on=['sid','signal_day'],how='left',validate='one_to_one')
ans['old_actual_round_in_mother']=ans.round_id.notna()
ans.to_csv(O/'CASES_WITH_OLD_LABELS.csv',index=False)
pairs=[]
keys=a[a.scope.eq('prior_fixed_16_AB_pair')][['sid','signal_day']]
pp=ans.merge(keys,on=['sid','signal_day'],validate='one_to_one')
for d,g in pp.groupby('signal_day'):
 assert len(g)==2
 x,y=list(g.itertuples());both=x.old_actual_round_in_mother and y.old_actual_round_in_mother and x.evidence_usable_closed==True and y.evidence_usable_closed==True
 pairs.append(dict(signal_day=d,sid1=x.sid,sid2=y.sid,Z1=x.Z if x.known else None,Z2=y.Z if y.known else None,old_net1=x.core_net,old_net2=y.core_net,both_actual_financial_known=both,opposite_old_signs=bool(both and (x.core_net>0)!=(y.core_net>0)),higher_Z_is_old_winner=bool((x.Z>y.Z)==(x.core_net>0)) if both and x.known and y.known and (x.core_net>0)!=(y.core_net>0) and x.Z!=y.Z else None))
pd.DataFrame(pairs).to_csv(O/'ORIGINAL_8_PAIR_DIAGNOSTIC.csv',index=False)
save('SOURCE_HASHES.json',S);assert S=={p:sha(p) for p in S}
save('QA.json',dict(rows=len(ans),known=int(ans.known.sum()),stocks=ans.sid.nunique(),prefix_exact=True,sources_unchanged=True,no_new_economics=True,seconds=time.monotonic()-t0))
print(ans[['sid','signal_day','scope','sign','Z','old_actual_round_in_mother','core_return','net_return_on_buy_cash']].to_string(index=False),flush=True)
print(pd.DataFrame(pairs).to_string(index=False),flush=True)
