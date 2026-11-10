from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,hashlib
import pandas as pd
import numpy as np
A=Path(__file__).resolve().parent;O=A.parent;C=O/'joint51_candidate_v11_suspension_accounting';F=C/'full_20241031_once';B=O/'joint51_candidate_v10_suspension_accounting/full_20241031_once';rd=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();checks=Counter();errors=[]
def ck(k,a,b,ctx=None):
 checks[k]+=1
 if a!=b:errors.append(dict(check=k,actual=str(a),expected=str(b),context=ctx))
pols={p['sid']:p for p in rd(C/'SUSPENSION_POLICY.json')['policies']};orders=rd(F/'ORDERS.json');ledger=rd(F/'DAY_LEDGER.json');holds=rd(F/'HOLDINGS.json');cand=rd(F/'CANDIDATES.json');attempts={x['id']:x for x in rd(F/'ATTEMPTS.json')};pre=rd(F/'PREFLIGHT_CHECKS.json');sus=rd(F/'SUSPENSION_EVENTS.json');cp=rd(F/'CP_EVENTS.json');equity=rd(F/'EQUITY_EVENTS.json');sectors={(r['day'],r['sector51']):r for r in rd(F/'SECTOR_DAILY.json')};families=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END','SUSPENSION_EVENTS','PREFLIGHT_CHECKS']
for n in families:ck('full_run_prior_34_day_11_family_byte_exact',(C/'full_replay_20241028'/(n+'.json')).read_bytes(),(B/(n+'.json')).read_bytes(),n)
ck('complete_37_day_book',len(ledger),37);ck('completed_requested_date',ledger[-1]['day'],'2024-10-31');ck('no_final_blocker',rd(F/'BLOCKERS.json'),[]);ck('no_uncertified_day',rd(F/'UNCERTIFIED_DAY.json'),None)
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024');E=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1');manifest={x['symbol']:x for x in rd(U/'STOCK_MANIFEST.json')};events=rd(E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json')+rd(O/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json')+rd(C/'ADDITIONAL_REVIEWED_EVENTS.json');evmap={(x['sid'],x['ex_date']):x for x in events};cache={}
def source(s):
 if s not in cache:
  p=next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'));ck('actual_target_source_hash',sha(p),manifest[s]['source_sha256'][p],s);cache[s]=(p,pd.read_parquet(p))
 return cache[s][1]
def inventory(dt):
 out={}
 for h in holds:
  if h['day']==dt:out.setdefault(h['sid'],[]).append(h)
 return out
summaries=[];suspended_daily=[]
for dt,prev in [('2024-10-29','2024-10-28'),('2024-10-30','2024-10-29'),('2024-10-31','2024-10-30')]:
 old=inventory(prev);current=inventory(dt);pending={x['sid']:x for x in cand if x['day']==prev and x['phase']=='CLOSE' and x['event'] in ['A','B'] and x['decision']=='PASS'};targets=sorted(set(old)|set(pending));logs=[r for r in pre if r['day']==dt];logmap={x['sid']:x for x in logs};ck('all_actual_targets_logged_once',(set(logmap),len(logs)),(set(targets),len(targets)),dt)
 for s in targets:
  z=source(s);t=pd.Timestamp(dt);actions=[x for x in rd(AS/'inputs-v1/actions'/(s+'.json'))['events'] if x['effective_date']==dt];ev=evmap.get((s,dt));q=sum(h['qty'] for h in old.get(s,[]));row=logmap[s];pol=pols.get(s);covered=bool(pol and dt in pol['covered_dates'])
  if s in old:origin=tuple(attempts[old[s][0]['round_id']]['origin']);factor=D(old[s][0]['factor'])
  else:
   zz=z.loc[pd.Timestamp(prev)];origin=tuple(str(zz[k]) for k in ['source_kind','source_path','segment_id']);factor=D(str(zz.adjustment_factor))
  if covered:
   anchor=z.loc[pd.Timestamp(pol['mark_source_day'])];ck('suspended_missing_raw_remains_missing',t in z.index,False,[dt,s]);ck('suspended_current_action_requires_bridge',(actions,ev),([],None),[dt,s]);ck('suspended_prior_origin_matches_anchor',origin,tuple(str(anchor[k]) for k in ['source_kind','source_path','segment_id']),[dt,s]);ck('suspended_prior_factor_matches_anchor',factor,D(pol['factor']),[dt,s]);expected=dict(status='OFFICIAL_SUSPENSION_ANCHOR_ONLY',held_qty=q,pending_count=int(s in pending),effective_actions=0,observed_source=False,observed_factor=False,tradable=False)
  else:
   valid=t in z.index and np.isfinite(z.loc[t].raw_open) and z.loc[t].raw_open>0;ck('all_other_targets_observed_OPEN_required',valid,True,[dt,s])
   if not valid:continue
   zz=z.loc[t];f1=D(str(zz.adjustment_factor));ck('all_other_targets_same_source',tuple(str(zz[k]) for k in ['source_kind','source_path','segment_id']),origin,[dt,s]);ck('all_other_targets_valid_factor',f1.is_finite() and f1>0,True,[dt,s]);ck('all_other_actions_admitted',not actions or ev is not None,True,[dt,s]);ck('all_other_factor_changes_admitted',abs(f1/factor-1)<=D('1e-11') or ev is not None,True,[dt,s])
   if ev:
    zz0=z[z.index<t].iloc[-1];f0=D(str(zz0.adjustment_factor));pc=D(str(zz0.raw_close));ds=D(ev['d_source']);ck('actual_factor_bridge_old',factor,f0,[dt,s]);ck('actual_factor_bridge',abs(f0*pc/(pc-ds)/f1-1)<D('1e-11'),True,[dt,s]);ck('local_action_single',len(actions),1,[dt,s])
   expected=dict(status='ORIGINAL_OBSERVED_SOURCE_CHECKS_PASS',held_qty=q,pending_count=int(s in pending),effective_actions=len(actions),admitted_event=ev is not None,observed_source=True,observed_factor=True,tradable=True)
  for k,v in expected.items():ck('actual_preflight_'+k,row[k],v,[dt,s])
 for s,pol in pols.items():
  hs=current[s];before=old[s];ck('suspended_same_lots_quantities',[(x['lot_id'],x['qty'],x['bought']) for x in hs],[(x['lot_id'],x['qty'],x['bought']) for x in before],[dt,s]);ck('suspended_100_shares',sum(h['qty'] for h in hs),100,[dt,s]);ck('suspended_floor_preserved',[x['protection_signal'] for x in hs],[x['protection_signal'] for x in before],[dt,s]);ck('suspended_factor_preserved',[x['factor'] for x in hs],[x['factor'] for x in before],[dt,s])
  for h in hs:
   for k,v in dict(raw_mark=pol['raw_mark'],market_value=str(D(100)*D(pol['raw_mark'])),stale=True,tradable=False,observed_bar=False,mark_source_day=pol['mark_source_day'],valuation_only=True).items():ck('suspended_mark_disclosure_'+k,h[k],v,[dt,s])
  for label,rows in [('order',orders),('CP',cp),('equity_cash',equity)]:ck('no_suspended_'+label,[x for x in rows if x['sid']==s and x['day']==dt],[],[dt,s])
  rows=[x for x in cand if x['sid']==s and x['day']==dt and x['phase']=='CLOSE'];g=[x for x in rows if x['event']=='ADD_GATE'];ck('no_suspended_price_signal',len(g)==1 and g[0]['decision']=='SUSPENDED_NO_PRICE_SIGNAL' and g[0]['close_net'] is None,True,[dt,s]);ck('original_stock_unknown_ticket',any(x['event']=='NO_NEW_TICKET' and x['decision']=='STOCK_UNKNOWN' for x in rows),True,[dt,s])
  opening=next(x for x in sus if x['sid']==s and x['day']==dt and x['phase']=='OPEN');closing=next(x for x in sus if x['sid']==s and x['day']==dt and x['phase']=='CLOSE');ck('suspension_daily_two_logs',sum(x['sid']==s and x['day']==dt for x in sus),2,[dt,s]);had_lock=any(x['locked_exit'] for x in before);ck('locked_exit_preserved_at_open',opening['event'],'EXIT_DEFERRED_NONTRADABLE' if had_lock else 'NO_TRADE_SUSPENSION',[dt,s]);ck('close_mark_event',closing['event'],'STALE_MARK_ONLY_NO_PRICE_SIGNAL',[dt,s])
  oldlocks=[x['locked_exit'] for x in before];newlocks=[x['locked_exit'] for x in hs]
  if oldlocks!=newlocks:
   sector=sectors[(dt,hs[0]['sector51'])];ck('only_sector_FALSE_can_create_suspended_lock',sector['state']==0 and attempts[hs[0]['round_id']]['add_count']==0 and all(x=='TRIAL_SECTOR_FALSE' for x in newlocks),True,[dt,s])
  else:ck('old_suspended_exit_lock_never_cleared',all(not a or b==a for a,b in zip(oldlocks,newlocks)),True,[dt,s])
  suspended_daily.append(dict(day=dt,sid=s,qty=100,stale_market_value=hs[0]['market_value'],locked_exit=hs[0]['locked_exit'],opening_event=opening['event'],sector_state=sectors[(dt,hs[0]['sector51'])]['state']))
 row=next(x for x in ledger if x['day']==dt);ck('two_stock_stale_total',row['stale_market_value'],'2013.00',dt);ck('two_nontradable_stocks',row['nontradable_stocks'],2,dt);ck('whole_liquidation_undefined',row['net_liquidation_NAV'],None,dt);ck('whole_liquidation_unavailable',row['whole_account_liquidation_available'],False,dt)
 summaries.append(dict(day=dt,held_symbols=len(old),pending_seed_count=len(pending),actual_target_count=len(targets),new_orders=sum(x['day']==dt for x in orders),NAV=row['NAV'],stale_market_value=row['stale_market_value']))
for s,pol in pols.items():
 hs=[h for h in holds if h['sid']==s and h['day']==pol['mark_source_day']];rid=hs[0]['round_id'];anchor_orders=[x for x in orders if x['round_id']==rid and x['day']<=pol['mark_source_day']];ck('suspended_attempt_cashflow_no_change',D(attempts[rid]['cashflow']),sum((D(x['cash_delta']) for x in anchor_orders),D(0)),s);ck('suspended_attempt_fees_no_change',D(attempts[rid]['fees']),sum((D(x['fee']) for x in anchor_orders),D(0)),s)
for path,h in rd(C/'FREEZE.json')['hashes'].items():ck('frozen_input_hash',sha(path),h,path)
for n,h in rd(F/'OUTPUT_HASHES.json').items():ck('final_output_hash',sha(F/n),h,n)
report=dict(status='PASS_THROUGH_20241031_WITH_STALE_NONTRADABLE_ASSETS' if not errors else 'FAIL',check_count=sum(checks.values()),checks=dict(checks),errors=errors,certified_days=len(ledger),certified_through=ledger[-1]['day'],completed_accounting_horizon=True,whole_account_liquidation_certified=False,actual_preflight_summaries=summaries,suspended_daily=suspended_daily,last=ledger[-1],scope='Independent three-day extension audit. Full account book can be valued to 10/31 only under explicit two-stock stale/nontradable accounting. No actual suspended executions or price signals, no future resumption information or new general missing-data exception.')
p=A/'FINAL_EXTENSION_BOUNDARY.json';assert not p.exists();p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['checks','suspended_daily']},ensure_ascii=False,indent=2))
