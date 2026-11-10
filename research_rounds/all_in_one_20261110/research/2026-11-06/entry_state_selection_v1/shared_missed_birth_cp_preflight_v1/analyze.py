"""Frozen fixed-window missed birth / fresh CP signal preflight. No account engine, fills or outcome labels."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import ast,json,hashlib,sys,math,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
END=pd.Timestamp('2024-10-16');START=pd.Timestamp('2024-09-24');S={};qa=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,h=None):
 p=Path(p);S[str(p)]=sha(p)
 if h:assert S[str(p)]==h,(p,'SOURCE_DRIFT')
 return p
def read(p):return json.loads(source(p).read_text())
def save(n,x):
 p=O/n
 if p.exists():
  assert json.loads(p.read_text())==json.loads(json.dumps(x,default=str));return
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
for p,h in read(O/'FREEZE.json')['hashes'].items():assert sha(p)==h
seed=read(O/'FIXED_SEEDS.json');sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};im={x['series']:x for x in read(U/'INDUSTRY_MANIFEST.json')}
ids=sorted({x['sid'] for x in seed})
pp=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
panel=pd.read_parquet(source(pp/'COMMON_K_COMPARISON.parquet'));cal=pd.DatetimeIndex(sorted(panel.day.unique()));days=cal[(cal>=START)&(cal<=END)]
sec=panel.set_index(['sector','day']).M3_candidate
K=pd.read_parquet(source(pp/'KNOWN3.parquet'),columns=ids).reindex(days)
RIGHT=pd.read_parquet(source(pp/'RIGHT3.parquet'),columns=ids).reindex(days)
pvr=pd.read_parquet(source(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'),filters=[('sid','in',ids),('day','>=',START),('day','<=',END)]).set_index(['sid','day'])
canonical=pd.read_parquet(source(R/'fast_entry_equity_2022_v1/CANONICAL_CP_2022_2026.parquet'),filters=[('sid','in',ids),('day','>=',START),('day','<=',END)])
assert not canonical.duplicated(['sid','day']).any() and not canonical.cp_id.duplicated().any()
canon=canonical.set_index(['sid','day'])
dec=[x for x in read(B/'DECISIONS.json') if x['day'][:10]<=str(END.date())]
ab={(x['sid'],pd.Timestamp(x['day'])):x for x in dec}
acts=[x for x in read(B/'ACTIONS.json') if x['day'][:10]<=str(END.date())]
audit=[x for x in read(B/'AUDIT.json') if x['day'][:10]<=str(END.date())]
snap={pd.Timestamp(x['day']):x for x in audit if x['type']=='CLOSE_SNAPSHOT'}
save('AUDIT_TYPES.json',dict(Counter(x['type'] for x in audit)))
sys.path[:0]=[str(M/'pv-strength-b5-20261025/code'),str(M/'b5-g1-20261025/code'),str(M/'pv-participation-response-20261020/code'),str(M/'rs-h1-execution-20261025/code')]
from policy import e0_policy
from policies_g1 import project
from data_utils import eligible_prices
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
for p in [M/'pv-strength-b5-20261025/code/policy.py',M/'b5-g1-20261025/code/policies_g1.py',M/'pv-participation-response-20261020/code/data_utils.py',M/'rs-h1-execution-20261025/code/market_rules.py',M/'rs-h1-execution-20261025/code/sector_account.py']:source(p)
old=source(R/'shared_probe_order_credit_identity_v1/analyze.py').read_text()
nd=next(n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name=='native')
exec(compile(ast.Module(body=[nd],type_ignores=[]),'ORIGINAL_NATIVE_I_DEFINITION_ONLY','exec'),globals())
oldp=source(R/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py')
wanted={'finite','true','false','lineage','flags','fee','getmeta','size','DayFrame'}
nodes=[n for n in ast.parse(oldp.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in wanted]
assert {n.name for n in nodes}==wanted
env=dict(Path=Path,D=D,np=np,pd=pd,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,version_on=version_on,market_identity_on=market_identity_on,
rules=read(M/'rs-h1-execution-20261025/inputs-v2/market-rules.json'),proxies=read(M/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json')['approved_proxy_ids'],meta={},SLIP=D('.0005'))
exec(compile(ast.Module(body=nodes,type_ignores=[]),'ORIGINAL_SIZE_FLAGS_ONLY','exec'),env)
def closecheck(sid,t,raw,floor,cap):
 ss=snap.get(t,{})
 if not ss.get('certified') or 'Nd' not in ss:return dict(close_check='SHARED_NAV_UNCERTIFIED')
 z=raw.loc[t].to_dict()
 if not env['flags'](z) or not env['finite'](z.get('raw_close')) or z['raw_close']<=0 or not env['finite'](z.get('adjustment_factor')) or z['adjustment_factor']<=0:return dict(close_check='INVALID_CLOSE_UNKNOWN')
 fl=D(str(floor))/D(str(z['adjustment_factor']));op=D(str(z['raw_close']));nd=D(str(ss['Nd']))
 if not np.isfinite(cap):return dict(close_check='PRIOR_VOLUME_UNKNOWN_AT_CLOSE')
 if op<=fl:return dict(close_check='CLOSE_AT_OR_BELOW_PROTECTION')
 try:
  q,bf,risk,_,_=env['size'](sid,t,op*D('1.0005'),fl,nd*D('.02'),nd*D('.0025'),int(cap))
  return dict(close_check='PASS' if q>0 else 'MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE',close_q=q,close_fee=float(bf),close_plan_risk=float(risk),close_floor_raw=float(fl),prior20_capacity=int(cap),close_NAV=str(nd))
 except (RuleUnavailable,KeyError,ValueError) as e:return dict(close_check='DATED_RULE_UNKNOWN_AT_CLOSE',reason=str(e))
def seriesknown(frame):
 return frame.observed_bar.eq(True)&frame.price_eligible.eq(True)&frame.volume_eligible.eq(True)&frame.source_invalid.eq(False)&frame.synthetic_event_bar.eq(False)&np.isfinite(frame.close)&frame.close.gt(0)&np.isfinite(frame.adjustment_factor)&frame.adjustment_factor.gt(0)
industry={}
for s in sorted({x['sector'] for x in seed}):
 m=im[s];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));industry[s]=pd.read_parquet(source(p,m['source_sha256'][p])).reindex(days)
daily=[];tickets=[];receipts=[];allrows=0
for num,z in enumerate(sorted(seed,key=lambda x:(x['day'],x['sid']))):
 sid=z['sid'];sector=z['sector'];m=sm[sid];sd=pd.Timestamp(z['day']);reject=pd.Timestamp(z['rejected_day'])
 paths={k:next(p for p in m['source_sha256'] if p.endswith('/'+k+'.parquet')) for k in ['signal','events','states']};xp=next(p for p in m['source_sha256'] if '/ix-a-share-entry-' in p)
 raw=pd.read_parquet(source(paths['signal'],m['source_sha256'][paths['signal']])).loc[:END]
 ev=pd.read_parquet(source(paths['events'],m['source_sha256'][paths['events']])).loc[:END]
 st=pd.read_parquet(source(paths['states'],m['source_sha256'][paths['states']])).loc[:END]
 xx=pd.read_parquet(source(xp,m['source_sha256'][xp])).loc[:END]
 f=pd.read_parquet(source(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])).loc[:END]
 cp=pd.read_parquet(source(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])).loc[:END]
 n,_=native(raw,ev,st,xx)
 for a,c in [('target','i_target'),('floor','i_floor'),('buy_event','i_buy')]:np.testing.assert_allclose(n[a].to_numpy(float),f[c].to_numpy(float),rtol=0,atol=0,equal_nan=True)
 allrows+=len(n)
 root=pd.Series(pd.NaT,index=n.index,dtype='datetime64[ns]');rr=pd.NaT
 for t,v in n.iterrows():
  if v.entered==1:rr=t
  if v.target!=1:rr=pd.NaT
  root.at[t]=rr
 birthroot=root.at[sd];assert pd.notna(birthroot)
 ds=days[days>=sd];p=raw.reindex(ds);ff=f.reindex(ds);nn=n.reindex(ds);rt=root.reindex(ds);cc=cp.reindex(ds);ip=industry[sector].reindex(ds)
 identity=p[['source_kind','source_path','segment_id']].astype('string')
 sourceok=seriesknown(p)&identity.notna().all(axis=1)&identity.eq(identity.loc[sd]).all(axis=1)
 ii=ip[['source_kind','source_path','segment_id']].astype('string')
 sourceok&=seriesknown(ip)&ii.notna().all(axis=1)&ii.eq(ii.loc[sd]).all(axis=1)
 factorok=np.isclose(p.adjustment_factor,p.at[sd,'adjustment_factor'],rtol=1e-11,atol=0)
 sourceok&=factorok
 contsource=sourceok.astype(bool).cummin()
 iq=ff.e0_ready.eq(1)&ff.g_ready.eq(True)&ff.i_target.eq(1)&np.isfinite(ff.i_floor)&ff.i_floor.gt(0)
 ik=ff.e0_ready.isin([0,1])&ff.g_ready.isin([False,True,0,1])&ff.i_target.isin([0,1])&(~ff.i_target.eq(1)|(np.isfinite(ff.i_floor)&ff.i_floor.gt(0)))
 sameI=rt.eq(birthroot)&nn.target.eq(1);continuousI=sameI.astype(bool).cummin()
 ss=sec.loc[sector].reindex(ds);sk=ss.isin([0,1]);mk=K[sid].reindex(ds).eq(True);mr=RIGHT[sid].reindex(ds).eq(True)
 both=ss.eq(1)&mk&mr;persist=both.astype(bool).cummin()
 no_unknown=(ik&sk&mk&contsource).astype(bool).cummin()
 pv=pvr.loc[sid].reindex(ds);pk=pv.state.ge(0)&pv.valid_observation.eq(True)&np.isfinite(pv.score)
 vol=raw.raw_volume[raw.raw_volume.gt(0)];capacity=(vol.rolling(20,min_periods=20).mean()*.01).reindex(raw.index).ffill()
 chk=closecheck(sid,sd,raw,ff.at[sd,'i_floor'],capacity.at[sd]);orig=ab[(sid,sd)]
 assert chk['close_check']==orig['close_check']=='PASS'
 for k in ['close_q','close_fee','close_plan_risk','close_floor_raw','prior20_capacity']:assert np.isclose(chk[k],orig[k],rtol=1e-12,atol=1e-8),(sid,k,chk[k],orig[k])
 stockacts=[a for a in acts if a['sid']==sid]
 buy_days=[pd.Timestamp(a['day']) for a in stockacts if a['side']=='buy_core']
 later_ab=[t for (s,t) in ab if s==sid and t>sd]
 future_cp=[];candidate_cp=[];strict_cp=[];signal_cp=[]
 for t in ds:
  if t<reject:continue
  a_today=ab.get((sid,t));ab_since=any(sd<dt<=t for dt in later_ab)
  pos=0
  for a in stockacts:
   if pd.Timestamp(a['day'])>t:continue
   pos+=int(a['q'])*(1 if a['side'].startswith('buy') else -1)
  assert pos>=0
  alreadyfill=any(sd<dt<=t for dt in buy_days)
  flat=pos==0
  # Unknown initial state is checked against original decision states below.
  c=canon.loc[(sid,t)] if (sid,t) in canon.index else None
  fresh=bool(cc.at[t,'receipt']) if pd.notna(cc.at[t,'receipt']) else False
  assert fresh==(c is not None),(sid,t,'canonical native receipt mismatch')
  cpknown=bool(c is not None and c.cp_trace_known==True and (pd.isna(c.trace_unknown) or str(c.trace_unknown)==''))
  if c is not None:
   assert np.isclose(c.cp_candidate,cc.at[t,'candidate'],rtol=0,atol=1e-10)
   assert pd.Timestamp(c.formation_end_inclusive)==t
   assert str(c.source_segment)==str(int(p.at[t,'segment_id']))
   assert json.loads(c.new_advance_price_event_ids) and c.confirmation_observation_id in json.loads(c.new_advance_price_event_ids)
   assert cc.at[t,'delta_frontier']>0
  marker=bool(continuousI.at[t] and contsource.at[t] and no_unknown.at[t] and not alreadyfill)
  signal=bool(t>sd and marker and flat and ss.at[t]==1 and iq.at[t] and pk.at[t] and cpknown and a_today is None)
  row={k:z[k] for k in ['event_id','round_id','sid','name','sector','event_type','probe_primary']}
  row.update(seed_signal_day=sd,rejected_open_day=reject,day=t,next_common_open=cal[cal.get_loc(t)+1],original_I_entered=birthroot,current_original_I_entered=rt.at[t],
   same_original_I=bool(sameI.at[t]),same_I_continuously=bool(continuousI.at[t]),source_known_continuously=bool(contsource.at[t]),qualification_known_continuously=bool(no_unknown.at[t]),
   sector_M3=ss.at[t],stock_M3_known=bool(mk.at[t]),stock_M3=bool(mr.at[t]),sector_stock_M3_continuous=bool(persist.at[t]),
   I_qualified=bool(iq.at[t]),i_buy=ff.at[t,'i_buy'],PVR_known=bool(pk.at[t]),PVR_score=pv.at[t,'score'],new_AB_since_seed=ab_since,AB_today=a_today['event_type'] if a_today else None,
   original_current_qty=pos,original_FLAT=flat,actual_fill_since_seed=alreadyfill,marker_active=marker,cp_fresh=fresh,cp_trace_known=cpknown,cp_id=c.cp_id if c is not None else None,
   signal_permission=signal,strict_persistent_permission=bool(signal and persist.at[t] and not ab_since),
   close_adjusted=p.at[t,'close'],raw_close=p.at[t,'raw_close'],I_floor=ff.at[t,'i_floor'],close_vs_seed=p.at[t,'close']/p.at[sd,'close']-1,
   seed_cp_receipt=bool(cp.at[sd,'receipt']),cp_formation_start=c.formation_start_exclusive if c is not None else None,
   cp_formation_crosses_seed=bool(c is not None and pd.Timestamp(c.formation_start_exclusive)<sd),cp_new_displacement=cc.at[t,'displacement'] if fresh else None,
   cp_frontier_delta=cc.at[t,'delta_frontier'] if fresh else None,cp_scale=cc.at[t,'scale'] if fresh else None,cp_candidate=cc.at[t,'candidate'] if fresh else None)
  row['strict_persistent_valid_no_AB']=bool(marker and flat and persist.at[t] and not ab_since)
  if fresh:
   future_cp.append(t)
   row.update(closecheck(sid,t,raw,ff.at[t,'i_floor'],capacity.get(t,np.nan)) if iq.at[t] else dict(close_check='I_INELIGIBLE'))
   row['close_feasible_permission']=bool(signal and row['close_check']=='PASS')
   row['strict_close_feasible_permission']=bool(row['strict_persistent_permission'] and row['close_check']=='PASS')
   row.update({k:c[k] for k in ['decision_evidence_key','original_E0_episode_id','anchor_observation_id','confirmation_observation_id','previous_market_receipt_id','evidence_signature','new_advance_price_event_ids']})
   receipts.append(row.copy())
   if signal:signal_cp.append(t)
   if row['close_feasible_permission']:candidate_cp.append(t)
   if row['strict_close_feasible_permission']:strict_cp.append(t)
  daily.append(row)
 tickets.append(dict(z,original_I_entered=birthroot,native_rows=len(n),later_CP_count=len(future_cp),first_later_CP=min(future_cp) if future_cp else None,
  signal_permission_count=len(signal_cp),close_feasible_CP_count=len(candidate_cp),first_close_feasible_CP=min(candidate_cp) if candidate_cp else None,
  strict_persistent_CP_count=len(strict_cp),first_strict_persistent_CP=min(strict_cp) if strict_cp else None,
  first_new_AB=min(later_ab) if later_ab else None,actual_first_buy_after_seed=min([dt for dt in buy_days if dt>sd],default=None),
  any_strict_persistent_valid_no_AB=any(x['strict_persistent_valid_no_AB'] for x in daily if x['sid']==sid),
  window_end_same_I=bool(sameI.iloc[-1]),window_end_continuous_M3=bool(persist.iloc[-1]),factor_changed_since_seed=not bool(np.all(factorok))))
 qa.append(dict(sid=sid,root=str(birthroot),native_full_prefix_rows=len(n),native_floor_target_buy_exact=True,original_seed_close_exact=True,source_window_known=bool(contsource.iloc[-1])))
 if (num+1)%25==0:print('PREFLIGHT',num+1,len(seed),flush=True)
daily=pd.DataFrame(daily);receipts=pd.DataFrame(receipts);tickets=pd.DataFrame(tickets)
daily.to_csv(O/'FIXED_DAILY_FEATURES.csv',index=False);receipts.to_csv(O/'NEW_CP_RECEIPTS.csv',index=False);tickets.to_csv(O/'TICKET_COVERAGE.csv',index=False)
receipts[receipts.close_feasible_permission].to_csv(O/'NEW_SIGNAL_PERMISSIONS.csv',index=False)
summary=dict(tickets=len(seed),stocks=len(ids),primary_probe_tickets=sum(x['probe_primary'] for x in seed),native_verified_rows=allrows,daily_rows=len(daily),post_rejection_CP=len(receipts),stocks_with_post_rejection_CP=receipts.sid.nunique(),
 tickets_with_persistent_valid_no_AB=int(tickets.any_strict_persistent_valid_no_AB.sum()),end_same_I=int(tickets.window_end_same_I.sum()),end_continuous_M3=int(tickets.window_end_continuous_M3.sum()),factor_changed=int(tickets.factor_changed_since_seed.sum()),
 signal_permissions=int(receipts.signal_permission.sum()),signal_permission_stocks=receipts.loc[receipts.signal_permission,'sid'].nunique(),
 close_feasible_permissions=int(receipts.close_feasible_permission.sum()),close_feasible_stocks=receipts.loc[receipts.close_feasible_permission,'sid'].nunique(),
 strict_permissions=int(receipts.strict_persistent_permission.sum()),strict_close_feasible=int(receipts.strict_close_feasible_permission.sum()),strict_close_feasible_stocks=receipts.loc[receipts.strict_close_feasible_permission,'sid'].nunique(),
 original_seed_channels=dict(Counter(x['event_type'] for x in seed)),future_receipt_source='Existing canonical original CP cache, exact native numeric CP receipt matching; true original I entries regenerated',
 source_count=len(S),no_account=True,no_outcomes=True)
save('SUMMARY.json',summary);save('SOURCE_QA.json',qa)
assert all(sha(p)==h for p,h in S.items())
save('SOURCE_SHA256.json',S)
print(json.dumps(summary,ensure_ascii=False,indent=2))
print(receipts.loc[receipts.close_feasible_permission].groupby('day').agg(permissions=('sid','size'),strict=('strict_close_feasible_permission','sum')).to_string())
