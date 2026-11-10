from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,hashlib
import pandas as pd
import numpy as np
A=Path(__file__).resolve().parent;O=A.parent;C=O/'joint51_candidate_v10_suspension_accounting';F=C/'full_20241031_once';B=O/'joint51_candidate_v9_facts/full_20241031_once';rd=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();checks=Counter();errors=[]
def ck(k,x,y,ctx=None):
 checks[k]+=1
 if x!=y:errors.append(dict(check=k,actual=str(x),expected=str(y),context=ctx))
pol=rd(C/'SUSPENSION_POLICY.json');orders=rd(F/'ORDERS.json');ledger=rd(F/'DAY_LEDGER.json');holds=rd(F/'HOLDINGS.json');candidates=rd(F/'CANDIDATES.json');attempts={x['id']:x for x in rd(F/'ATTEMPTS.json')};pre=rd(F/'PREFLIGHT_CHECKS.json');sus=rd(F/'SUSPENSION_EVENTS.json');cp=rd(F/'CP_EVENTS.json');equity=rd(F/'EQUITY_EVENTS.json');families=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END']
for n in families:ck('full_run_old_prefix_byte_exact',(C/'full_replay_20241025'/(n+'.json')).read_bytes(),(B/(n+'.json')).read_bytes(),n)
for n in families+['SUSPENSION_EVENTS','PREFLIGHT_CHECKS']:
 for row in rd(F/(n+'.json')):
  if 'day' in row:ck('no_10_29_uncertified_rows',row['day']<'2024-10-29',True,n)
# Build all exposed targets from actual previous close inventory and A/B-approved tickets.
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024');E=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1');manifest={x['symbol']:x for x in rd(U/'STOCK_MANIFEST.json')};events=rd(E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json')+rd(O/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json')+rd(C/'ADDITIONAL_REVIEWED_EVENTS.json');evmap={(x['sid'],x['ex_date']):x for x in events};cache={}
def source(s):
 if s not in cache:
  p=next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'));ck('actual_target_frozen_source_hash',sha(p),manifest[s]['source_sha256'][p],s);cache[s]=(p,pd.read_parquet(p))
 return cache[s]
def targets_from(previous):
 hs={}
 for h in holds:
  if h['day']==previous:hs.setdefault(h['sid'],[]).append(h)
 ps={x['sid']:x for x in candidates if x['day']==previous and x['phase']=='CLOSE' and x['event'] in ['A','B'] and x['decision']=='PASS'}
 return hs,ps
summaries=[];blocked_details=[]
for dt,previous in [('2024-10-28','2024-10-25'),('2024-10-29','2024-10-28')]:
 hs,ps=targets_from(previous);targets=sorted(set(hs)|set(ps));rows={r['sid']:r for r in pre if r['day']==dt};issues=[]
 if dt=='2024-10-28':ck('every_actual_target_preflight_logged_once',set(rows),set(targets),dt);ck('no_duplicate_preflight_rows',len(rows),sum(r['day']==dt for r in pre),dt)
 else:ck('blocked_day_preflight_logs_rolled_back',rows,{})
 for s in targets:
  p,z=source(s);now=pd.Timestamp(dt);act=[x for x in rd(AS/'inputs-v1/actions'/(s+'.json'))['events'] if x['effective_date']==dt];ev=evmap.get((s,dt));held_qty=sum(h['qty'] for h in hs.get(s,[]));problem=[]
  if s in hs:origin=tuple(attempts[hs[s][0]['round_id']]['origin']);factor=D(hs[s][0]['factor'])
  else:
   prior=z.loc[pd.Timestamp(previous)];origin=tuple(str(prior[k]) for k in ['source_kind','source_path','segment_id']);factor=D(str(prior.adjustment_factor))
  covered=s==pol['sid'] and dt in pol['covered_dates']
  if covered:
   anchor=z.loc[pd.Timestamp(pol['mark_source_day'])];checkorigin=tuple(str(anchor[k]) for k in ['source_kind','source_path','segment_id']);ck('suspension_only_missing_source',now in z.index,False,dt);ck('suspension_anchor_origin',origin,checkorigin,dt);ck('suspension_anchor_factor',factor,D(pol['factor']),dt);ck('suspension_no_action_or_ex_event',(act,ev),([],None),dt)
   if dt=='2024-10-28':
    row=rows[s]
    for k,v in dict(status='OFFICIAL_SUSPENSION_ANCHOR_ONLY',held_qty=held_qty,pending_count=int(s in ps),effective_actions=0,observed_source=False,observed_factor=False,tradable=False).items():ck('suspension_preflight_disclosure_'+k,row[k],v,dt)
  elif now not in z.index or not np.isfinite(z.loc[now].raw_open) or z.loc[now].raw_open<=0:problem.append('OPEN_MISSING')
  else:
   zz=z.loc[now];lin=tuple(str(zz[k]) for k in ['source_kind','source_path','segment_id']);f1=D(str(zz.adjustment_factor))
   if lin!=origin:problem.append('SOURCE_CHANGE')
   if not f1.is_finite() or f1<=0:problem.append('FACTOR_INVALID')
   else:
    if act and ev is None:problem.append('UNADMITTED_EQUITY_EVENT')
    if abs(f1/factor-1)>D('1e-11') and ev is None:problem.append('UNADMITTED_FACTOR_CHANGE')
    if ev:
     prior=z[z.index<now].iloc[-1];ds=D(ev['d_source']);pclose=D(str(prior.raw_close));f0=D(str(prior.adjustment_factor));ck('observed_event_bridge_matches_prior_factor',factor,f0,[dt,s]);ck('observed_event_factor_bridge',abs(f0*pclose/(pclose-ds)/f1-1)<D('1e-11'),True,[dt,s]);ck('observed_event_local_term_count',len(act),1,[dt,s])
   if dt=='2024-10-28':
    for k,v in dict(status='ORIGINAL_OBSERVED_SOURCE_CHECKS_PASS',held_qty=held_qty,pending_count=int(s in ps),effective_actions=len(act),admitted_event=ev is not None,observed_source=True,observed_factor=True,tradable=True).items():ck('normal_preflight_'+k,rows[s][k],v,[dt,s])
  if problem:
   nextrows=z.index[z.index>now];detail=dict(day=dt,sid=s,held_qty=held_qty,pending_seed=s in ps,primary_issues=problem,source_path=p,source_sha256=sha(p),last_prior_source_row=str(z.index[z.index<now][-1].date()),next_source_row=str(nextrows[0].date()) if len(nextrows) else None,remaining_requested_missing=[dd for dd in ['2024-10-29','2024-10-30','2024-10-31'] if pd.Timestamp(dd) not in z.index]);issues.append(detail)
 summaries.append(dict(day=dt,held_symbols=len(hs),pending_seed_count=len(ps),actual_target_count=len(targets),primary_issues=issues))
 if dt=='2024-10-28':ck('new_certified_day_all_targets_valid',issues,[])
 else:blocked_details=issues;ck('new_blocker_is_other_missing_held',[(x['sid'],x['held_qty'],x['primary_issues']) for x in issues],[('002064.SZ',100,['OPEN_MISSING'])])
# No new liquidity, price signals, CP receipts, fees or quantities from suspended holding.
sid=pol['sid'];oldhs=[h for h in holds if h['day']=='2024-10-25' and h['sid']==sid];newhs=[h for h in holds if h['day']=='2024-10-28' and h['sid']==sid];ck('suspended_lot_count',len(newhs),len(oldhs));ck('suspended_lot_identity_and_inventory',[(h['lot_id'],h['qty'],h['bought']) for h in newhs],[(h['lot_id'],h['qty'],h['bought']) for h in oldhs]);ck('suspended_protection_unchanged',[h['protection_signal'] for h in newhs],[h['protection_signal'] for h in oldhs]);ck('suspended_factor_not_inferred',[h['factor'] for h in newhs],[h['factor'] for h in oldhs]);ck('no_suspension_orders',[x for x in orders if x['sid']==sid and x['day']>='2024-10-28'],[]);ck('no_suspension_CP_actions',[x for x in cp if x['sid']==sid and x['day']>='2024-10-28'],[]);ck('no_suspension_equity_cash',[x for x in equity if x['sid']==sid and x['day']>='2024-10-28'],[])
for h in newhs:
 for k,v in dict(raw_mark='12.02',market_value='1202.00',stale=True,tradable=False,observed_bar=False,mark_source_day='2024-10-25',valuation_only=True).items():ck('suspended_lot_mark_'+k,h[k],v)
oldas={x['id']:x for x in rd(B/'ATTEMPTS.json')};rid=oldhs[0]['round_id']
for k in ['cashflow','fees','dividend','factor','ifloor','add_count']:ck('suspended_attempt_frozen_'+k,attempts[rid][k],oldas[rid][k])
ck('exact_suspension_log_phases',[(x['day'],x['phase'],x['event'],x['qty']) for x in sus],[('2024-10-28','OPEN','NO_TRADE_SUSPENSION',100),('2024-10-28','CLOSE','STALE_MARK_ONLY_NO_PRICE_SIGNAL',100)])
block=rd(F/'UNCERTIFIED_DAY.json');ck('stop_day','2024-10-29',block['day']);ck('no_partial_orders',block['partial_orders'],[]);ck('only_one_new_certified_day',[x['day'] for x in ledger if x['day']>'2024-10-25'],['2024-10-28'])
for p,h in rd(C/'FREEZE.json')['hashes'].items():ck('frozen_input_hash_unchanged',sha(p),h,p)
for p,h in rd(F/'OUTPUT_HASHES.json').items():ck('final_output_hash',sha(F/p),h,p)
report=dict(status='PASS_ONE_DAY_EXTENSION_ONLY' if not errors else 'FAIL',check_count=sum(checks.values()),checks=dict(checks),errors=errors,certified_through=ledger[-1]['day'],completed_planned_horizon=False,actual_new_certified_days=['2024-10-28'],actual_preflight_summaries=summaries,blocker=block,last=ledger[-1],reviewed_engine_sha256=sha(C/'engine.py'),scope='Independent output and all-exposed-source audit. 300277 carries 1202 only as stale valuation; no suspended trade or manufactured bar. Other missing source still causes whole-day stop; no assertion of suspension is made about 002064 from missing rows alone.')
p=A/'EXTENSION_AND_NEW_STOP.json';assert not p.exists();p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
