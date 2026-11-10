"""Read-only fixed 13-case v2 adapter; no PnL columns, orders, or fill calls."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D,ROUND_FLOOR
from collections import Counter
import sys,json,gzip,math,time,hashlib,importlib.util,bisect
import pandas as pd
import numpy as np

T=time.monotonic();O=Path(__file__).resolve().parent;W=O.parent;V=W/'rearm-risk-boundary-design-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def loadmod(name,p):
 sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
fr=json.loads((O/'FREEZE.json').read_text());assert all(sha(p)==h for p,h in fr['sha256'].items());assert not (O/'CASE_RESULTS.csv').exists()
sys.path.insert(0,str(V));from risk_boundary_v2 import RiskBoundary,NegativeReceipt
cases=pd.read_csv(O/'FROZEN_CASES.csv');assert len(cases)==13;ids=set(cases.old)
H=loadmod('v2_behavior_market',R/'s-entry-mechanism-audit-20261029/code/audit.py');_,m,_,_=H.context(ids,False)
arith=loadmod('v2_original_arithmetic',R/'pv-strength-b5-20261025/code/arithmetic.py');snap=H.SNAP;PH=R/'ph1-cross-sector-20261028'
proof=json.loads((PH/'event-validation.json').read_text());rec={x['symbol']:x for x in proof['records'] if x['sector']=='TECH'};assert proof['passed']
AP=W/'act-loss-facts-20261030';EP=W/'down-event-transfer-exposure-20261030';B=R/'pvr-local-finite-capital-20261029/baseline/accounts-v2'
ap=AP/'actual-cycles.csv';hp=AP/'actual-holding-close-paths.csv';bp=B/'I__S0_base.json';dp=B/'daily.jsonl.gz'
actual=pd.read_csv(ap,float_precision='round_trip',usecols=['cycle_id','entry_at','exit_at','exit_request','initial_floor_causal','initial_shares','exit_shares']).set_index('cycle_id')
paths=pd.read_csv(hp,float_precision='round_trip',usecols=['day','shares','cycle_id','old_floor_causal','new_floor_causal','causal_close','ACT_on','I_active']);paths=paths[paths.cycle_id.isin(cases.cycle_id)]
obj=json.loads(bp.read_text());audit=obj['audit_log'];fills=[x['receipt'] for x in audit if x['kind']=='fill'];daily={}
with gzip.open(dp,'rt') as f:
 for line in f:
  x=json.loads(line)
  if x['account']=='I__S0_base':daily[x['at'][:10]]=dict(positions=x['positions'],pending_buys=x['pending_buys'],pending_sells=x['pending_sells'])
calendar=sorted(daily);barid={d:i for i,d in enumerate(calendar)};assert len(calendar)==681
sources=[ap,hp,bp,dp,PH/'event-validation.json',R/'pv-strength-b5-20261025/code/arithmetic.py',R/'pv-strength-b5-20261025/code/evidence.py',R/'pvr-act-comparison-20261027/execution-rules-v2.json',R/'s-entry-mechanism-audit-20261029/code/audit.py',V/'risk_boundary_v2.py',V/'SPECIFICATION.txt',O/'ADAPTER_CONTRACT.txt',Path(__file__)]
identity={str(p):sha(p) for p in sources};facts={};events={};raws={};valid={}
for s in sorted(ids):
 fp=snap/'facts'/f'{s}.parquet';sp=snap/'signals'/f'{s}.parquet';ep=PH/'events/TECH'/f'{s}.parquet'
 for p,h in [(fp,rec[s]['inputs'][str(fp)]),(sp,rec[s]['inputs'][str(sp)]),(ep,rec[s]['output_sha256'])]:assert sha(p)==h;identity[str(p)]=h
 f=pd.read_parquet(fp,columns=['close','raw_close','factor','segment_id','i_floor','e0_target','i_target']);raw=pd.read_parquet(sp,columns=['volume','observed_bar','source_invalid','synthetic_event_bar']);ev=pd.read_parquet(ep,columns=['event','pivot_date','close','segment_id']);assert f.index.equals(ev.index);np.testing.assert_array_equal(f.close,ev.close);np.testing.assert_array_equal(f.segment_id,ev.segment_id)
 facts[s]=f;events[s]=ev;raws[s]=raw;valid[s]={}
 for seg,g in f.groupby('segment_id',sort=False):
  z=g[['close']].join(raw[['volume']]);valid[s][int(seg)]=z[z.gt(0).all(axis=1)&np.isfinite(z).all(axis=1)]
 for ref in [m.bundle.series[s].record['raw'],m.bundle.series[s].record['adjustment']['actions']]:
  p=Path(ref['path']);assert sha(p)==ref['sha256'];identity[str(p)]=sha(p)
save(O/'INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),before_v2_historical_behavior=True,sha256=identity))
sigma_rows=[];event_rows=[];row_rows=[];episodes=[];handoffs=[];results=[];execs=[];company=[];checks=Counter();EPS=64*np.finfo(float).eps
def sigma_at(s,seg,day,eid):
 z=valid[s][seg];past=z[z.index<pd.Timestamp(day)]
 if len(past)<64:return None,'RMS63_warmup_unknown'
 def calc(a):
  q=a[a.index<pd.Timestamp(day)].close.tail(64).to_numpy(float);r=[arith.log_ratio(q[i],q[i-1]) for i in range(1,len(q))];assert len(r)==63;return max(math.sqrt(math.fsum(x*x for x in r)/63),1e-8)
 value=calc(z);prefix=calc(z.loc[:day]);assert value==prefix;assert past.index[-1]<pd.Timestamp(day)
 sigma_rows.append(dict(event_id=eid,symbol=s,confirmation_date=day,sigma=value,return_count=63,first_return_date=str(past.index[-63].date()),last_return_date=str(past.index[-1].date()),confirmation_return_excluded=True,physical_prefix_exact=True));checks['RMS63_prefix_exact']+=1
 return value,'known'
def next_proxy(s,a,day,q):
 tm=H.at(day,dt(15,10));i=bisect.bisect_right(m.sessions['A'],tm);first=m.sessions['A'][i];mature=m.lag('A',datetime.fromisoformat(a.entry_at),m.protocol['sellable_lag_sessions']['A']);detail=[]
 if m.quote(s,tm) is None:return dict(next_market_open=str(first),next_legal_proxy=None,status='quote_unknown',detail=detail)
 for op in m.sessions['A'][i:]:
  if op>datetime.fromisoformat(a.exit_at):break
  w=m.window(s,op,'sell',1);immature=[x for x in audit if x['kind'] in ['split','split_fraction_floor_proxy'] and x.get('sid')==s and a.entry_at<=x.get('at','')<=str(op) and datetime.fromisoformat(x['new_shares_sellable_at'])>op]
  if immature:reason='bonus_share_maturity_unknown_for_full_quantity'
  elif op<mature:reason='initial_T1_unavailable'
  elif w is None:reason='daily_execution_proxy_unknown'
  elif not(w.market_open is True and w.sell_allowed is True):reason='market_or_sell_not_allowed'
  else:
   n=min(w.quantity.sell_floor(q,q),q,w.capacity_shares)//w.quantity.fill_step*w.quantity.fill_step
   if n>0:return dict(next_market_open=str(first),next_legal_proxy=str(op),status='original_offline_window_available_not_filled',quantity_proxy=n,full_quantity_proxy=n==q,detail=detail)
   reason='quantity_or_capacity_unavailable'
  detail.append(dict(at=str(op),reason=reason))
 return dict(next_market_open=str(first),next_legal_proxy=None,status='no_identified_window_in_original_scope',detail=detail)

for case in cases.itertuples(index=False):
 cid=case.cycle_id;s=case.old;a=actual.loc[cid];g=paths[paths.cycle_id.eq(cid)].sort_values('day');f=facts[s];ev=events[s];raw=raws[s];entryday=a.entry_at[:10];assert pd.Timestamp(entryday) in f.index
 source_seg=int(f.loc[pd.Timestamp(entryday),'segment_id']);source=f'{s}|source={source_seg}';unit=f'{snap.name}|{s}|economic_source={source_seg}'
 bu=[x for x in fills if x['security_id']==s and x['side']=='buy' and x['at']==a.entry_at];se=[x for x in fills if x['security_id']==s and x['side']=='sell' and x['at']==a.exit_at];assert len(bu)==len(se)==1 and bu[0]['shares']==int(a.initial_shares) and se[0]['shares']==int(a.exit_shares);checks['actual_buy_sell_identity']+=2
 c=RiskBoundary(cycle_id=cid,symbol=s,source_id=source,unit_id=unit,shares=bu[0]['shares'],e0_floor=float(a.initial_floor_causal));ndates=[];adates=[];rdates=[];hdates=[];unknown_dates=[];added=None;original=None;closed=False;startrow=len(row_rows)
 for x in g.itertuples(index=False):
  day=x.day;d=pd.Timestamp(day);ds=daily[day];q=int(ds['positions'].get(s,0));assert q==int(x.shares) and q>0;checks['actual_daily_shares_exact']+=1
  c.sync_execution(shares=q,buy_pending=s in ds['pending_buys'],exit_order_pending=s in ds['pending_sells']);assert c.e0_floor==float(x.old_floor_causal);checks['floor_state_input_exact']+=1
  native=d in f.index;eknown=d in ev.index;observed=bool(d in raw.index and raw.loc[d,'observed_bar'] and not raw.loc[d,'source_invalid'] and not raw.loc[d,'synthetic_event_bar']);unit_ok=False;rc=factor=canon=None;seg=source_seg;unit_here=unit
  if native:
   rr=f.loc[d];seg=int(rr.segment_id);unit_here=f'{snap.name}|{s}|economic_source={seg}';rc=float(rr.raw_close);factor=float(rr.factor);canon=float(rr.close)
   unit_ok=bool(np.isfinite(rc) and np.isfinite(factor) and rc>0 and factor>0 and math.isclose(rc*factor,canon,rel_tol=EPS,abs_tol=0));assert unit_ok,(cid,day,'economic price identity');checks['raw_factor_canonical_close_exact_precision']+=1
   if observed:assert math.isclose(float(m.raw[s].loc[d,'close']),rc,rel_tol=EPS,abs_tol=0);checks['raw_execution_source_close_exact_precision']+=1
  if not(native and observed):rc=factor=None
  event=int(ev.loc[d,'event']) if eknown else None;receipt=None;sigma=None
  if eknown and event!=0:
   pdte=ev.loc[d,'pivot_date'];assert pd.isna(pdte) or str(pdte)[:10]<=day;checks['native_confirmation_not_backdated']+=1
  if event==-1:
   eid=f'{s}|source={seg}|confirmed={day}|native_event=-1';receipt=NegativeReceipt(eid,s,f'{s}|source={seg}',barid[day]);sigma,sigma_status=sigma_at(s,seg,day,eid);ndates.append(day)
   event_rows.append(dict(cycle_id=cid,event_id=eid,confirmed_date=day,confirmed_bar=barid[day],source_segment=seg,pivot_date=ev.loc[d,'pivot_date'],sigma_status=sigma_status,identity_has_no_future_fields=True))
  before_ep=c.episodes;before_phase=c.phase;original_exit=(day==a.exit_request[:10]) or not bool(x.ACT_on) or not bool(x.I_active)
  nf=float(x.new_floor_causal) if native and pd.notna(x.new_floor_causal) else None
  r=c.on_close(bar=barid[day],raw_close=rc,factor=factor,unit_id=unit_here,negative=receipt,sigma=sigma,updated_floor=nf,floor_known=native and nf is not None,event_feed_known=eknown,original_exit=original_exit)
  r.update(date=day,symbol=s,raw_close=rc,factor=factor,cached_canonical_close=canon,unit_identity_checked=unit_ok,observed_price=observed,native_event=event,event_id=receipt.event_id if receipt else None,original_source_quantity=q);row_rows.append(r)
  if r['current_unknown']:unknown_dates.append(day)
  if c.episodes>before_ep:
   adates.append(day)
   if c.episodes>1:rdates.append(day)
   episodes.append(dict(cycle_id=cid,episode=c.episodes,arm_date=day,event_id=receipt.event_id,P=c.anchor,sigma=c.frozen_sigma,B=c.boundary,original_floor=c.e0_floor,prior_effective_protection=r['protection_before'],new_effective_protection=r['protection_after'],is_rearm=c.episodes>1))
  if before_phase=='PROTECTED' and c.phase=='OBSERVING' and c.last_handoff_bar==barid[day]:hdates.append(day);handoffs.append(dict(cycle_id=cid,date=day,episode=c.episodes,B=c.boundary,original_floor=c.e0_floor))
  if c.exit_locked:
   if c.exit_reason=='risk_boundary':
    added=day;ex=next_proxy(s,a,day,q);execs.append(dict(cycle_id=cid,request=day,**ex));assert c.phase=='EXIT_PENDING' and c.shares>0;checks['new_exit_stops_before_counterfactual_fill']+=1
   else:
    original=day;assert day==a.exit_request[:10],(cid,day,'original exit identity');assert c.phase=='EXIT_PENDING'
    # Only this non-divergent branch may use the original REAL completed sale.
    c.sync_execution(shares=0,buy_pending=False,exit_order_pending=False);assert c.phase=='CLOSED';closed=True;checks['original_only_real_receipt_closure']+=1
   break
 assert c.exit_locked or len(g)==0,(cid,'actual original endpoint missing')
 results.append(dict(cycle_id=cid,symbol=s,name=case.name,role=case.role,entry=a.entry_at,first_known_native_negative=ndates[0] if ndates else None,negative_receipts=len(ndates),protection_episodes=c.episodes,rearm_count=max(0,c.episodes-1),arm_dates=json.dumps(adates),rearm_dates=json.dumps(rdates),handoff_dates=json.dumps(hdates),added_request=added,original_request=a.exit_request,original_exit=a.exit_at,final_phase=c.phase,shares_at_stop=c.shares,holding_responsibility_at_stop=c.shares>0,original_real_receipt_closed=closed,stopped_at_first_added_request=added is not None,unknown_dates=json.dumps(sorted(set(unknown_dates))),unknown_count=len(set(unknown_dates)),unknown_types=json.dumps(sorted(set(c.issues))),rows_processed=len(row_rows)-startrow))
 print(json.dumps(dict(case=cid,episodes=c.episodes,rearm=rdates,added_request=added,phase=c.phase,unknown_rows=len(set(unknown_dates))),ensure_ascii=False),flush=True)

# Existing real actions only; no new cases, money account or assumed v2 fills.
for case in cases.itertuples(index=False):
 s=case.old;res=next(x for x in results if x['cycle_id']==case.cycle_id);end=res['added_request'] or res['original_request'][:10];f=facts[s]
 aa=[a for a in m.actions.get(s,[]) if case.original_entry[:10]<=a['effective_date']<=case.original_exit[:10]]
 if not aa:company.append(dict(cycle_id=case.cycle_id,status='no_action_in_fixed_original_cycle',within_v2_window=False));continue
 for act in aa:
  day=act['effective_date'];prior=f[f.index<pd.Timestamp(day)];after=f[f.index>=pd.Timestamp(day)];in_scope=day<=end
  row=dict(cycle_id=case.cycle_id,date=day,within_v2_window=in_scope,status='unknown',cash_per_old_share=act['cash_per_old_share'],split_ratio=act['split_ratio'],source_id=act['source_id'])
  if len(prior) and len(after):
   pre=prior.iloc[-1];post=after.iloc[0];signal_cash=D(act.get('signal_cash_per_old_share',act['cash_per_old_share']));ratio=D(act.get('signal_split_ratio',act['split_ratio']));rawpre=D(str(pre.raw_close));expected=float(rawpre/((rawpre-signal_cash)/ratio));observed=float(post.factor/pre.factor);match=math.isclose(expected,observed,rel_tol=EPS,abs_tol=0)
   dividend=[x['receivable'] for x in audit if x['kind']=='dividend_accrual' and x['receivable']['security_id']==s and x['receivable']['ex_at'][:10]==day]
   split=[x for x in audit if x['kind'] in ['split','split_fraction_floor_proxy'] and x['sid']==s and x['at'][:10]==day]
   qbefore=daily.get(str(prior.index[-1].date()),{}).get('positions',{}).get(s);qafter=daily.get(str(after.index[0].date()),{}).get('positions',{}).get(s)
   qok=bool(qbefore is not None and qafter is not None and int(D(qbefore)*D(act['split_ratio']))==qafter)
   rights_ok=(D(act['cash_per_old_share'])==0 or len(dividend)==1) and (D(act['split_ratio'])==1 or len(split)==1)
   row.update(pre_date=str(prior.index[-1].date()),post_date=str(after.index[0].date()),expected_factor_ratio=expected,observed_factor_ratio=observed,factor_formula_exact_precision=match,original_shares_before=qbefore,original_shares_after=qafter,original_share_ratio_consistent=qok,rights_record_identity=rights_ok,status='source_price_and_original_ledger_consistent' if match and qok and rights_ok else 'unknown_action_mapping')
  if not in_scope:row['v2_behavior_acceptance']='not_exposed_after_added_intent_only_original_data_check'
  else:row['v2_behavior_acceptance']=row['status']
  company.append(row)

pd.DataFrame(results).to_csv(O/'CASE_RESULTS.csv',index=False);pd.DataFrame(episodes).to_csv(O/'PROTECTION_EPISODES.csv',index=False);pd.DataFrame(handoffs).to_csv(O/'HANDOFFS.csv',index=False);pd.DataFrame(event_rows).to_csv(O/'EVENT_ID_AND_SIGMA_CHECKS.csv',index=False);pd.DataFrame(sigma_rows).to_csv(O/'SIGMA_PREFIX_CHECKS.csv',index=False);pd.DataFrame(company).to_csv(O/'CORPORATE_ACTION_COMPARABILITY.csv',index=False)
save(O/'ROW_AUDIT.json',row_rows);save(O/'EXECUTION_PROXIES.json',execs)
old=pd.read_csv(W/'sell-failure-design-review-20261030/historical-behavior-v1/RESULTS.csv',usecols=['cycle_id','new_trigger','handoff']).set_index('cycle_id');diff=[]
for x in results:
 y=old.loc[x['cycle_id']];prev=None if pd.isna(y.new_trigger) else y.new_trigger;oldhandoff=None if pd.isna(y.handoff) else y.handoff
 reason='same_request_time' if prev==x['added_request'] else 'new_request_after_independent_rearm' if x['rearm_count'] and x['added_request'] else 'new_lifecycle_behavior_requires_row_review'
 diff.append(dict(cycle_id=x['cycle_id'],v1_request=prev,v2_request=x['added_request'],v1_handoff=oldhandoff,v2_handoffs=x['handoff_dates'],v2_rearms=x['rearm_dates'],reason=reason))
pd.DataFrame(diff).to_csv(O/'V1_V2_BEHAVIOR_DIFFERENCE.csv',index=False)
assert all(sha(p)==h for p,h in identity.items());assert all(sha(p)==h for p,h in fr['sha256'].items());assert all(x['protection_after']>=x['protection_before'] for x in row_rows)
summary=dict(passed_adapter_checks=True,cases=13,stocks=12,case_initialization_from_real_buy=True,new_exit_cases=sum(x['added_request'] is not None for x in results),original_receipt_closed_cases=sum(x['original_real_receipt_closed'] for x in results),rearm_cases=sum(x['rearm_count']>0 for x in results),rearm_episodes=sum(x['rearm_count'] for x in results),processed_rows=len(row_rows),unknown_rows=sum(bool(x['current_unknown']) for x in row_rows),cases_with_unknown=sum(x['unknown_count']>0 for x in results),unknown_types=dict(Counter(t for x in row_rows for t in x['current_unknown'])),corporate_action_rows=sum('date' in x for x in company),corporate_action_rows_within_v2_window=sum(x.get('within_v2_window',False) for x in company),checks=dict(checks),no_v1_outcome_reused_as_v2_proof=True,added_requests_never_assumed_filled=True,new_profit_ledgers=0,portfolio_replays=0,core_or_spec_changes=0,input_hashes_unchanged=True,seconds=time.monotonic()-T)
save(O/'VERIFICATION.json',summary);print(json.dumps(summary,ensure_ascii=False))
