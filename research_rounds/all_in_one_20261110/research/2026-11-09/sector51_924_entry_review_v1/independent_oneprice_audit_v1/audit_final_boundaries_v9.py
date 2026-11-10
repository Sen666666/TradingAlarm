"""Independent final stress-prefix chain, exposed-source preflight and seed expiry checks."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,hashlib,ast
import pandas as pd
import numpy as np
A=Path(__file__).resolve().parent;O=A.parent;R=O/'oneprice_execution_stress_v1';F=R/'facts_v9';S=F/'full_20241031_once';B=O/'joint51_candidate_v9_facts';T=pd.Timestamp('2024-10-28');read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();checks=Counter();errors=[]
def check(k,x,y,ctx=None):
 checks[k]+=1
 if x!=y:errors.append(dict(check=k,actual=str(x),expected=str(y),context=ctx))
def economic_ast(p):
 out={}
 for n in ast.parse(Path(p).read_text()).body:
  if isinstance(n,ast.FunctionDef):out[n.name]=ast.dump(n,include_attributes=False)
  if isinstance(n,ast.ClassDef):
   for fn in n.body:
    if isinstance(fn,ast.FunctionDef) and not(n.name=='Engine' and fn.name=='run'):out[n.name+'.'+fn.name]=ast.dump(fn,include_attributes=False)
 return out
families=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END','OPEN_INTENTS','OPEN_RESERVATIONS','NO_FILLS'];chain=[]
for version in [7,8,9]:
 old=R/f'facts_v{version-1}'/'full_20241031_once';through=read(old/'DAY_LEDGER.json')[-1]['day'];new=R/f'facts_v{version}'/('checkpoint_'+through.replace('-',''));record={}
 for family in families:
  x=read(old/(family+'.json'));y=read(new/(family+'.json'));check('12_family_exact_extension_prefix',x,y,[version,family]);record[family]=len(x)
 b=O/f'joint51_candidate_v{version}_facts';check('fact_version_economics_AST_unchanged',economic_ast(b/'engine.py'),economic_ast(O/'joint51_candidate_v4_facts/engine.py'),version)
 driver=read(R/f'facts_v{version}'/'CHECKPOINT_DRIVER_SEAL.json');check('output_only_driver_hash',sha(driver['driver']),driver['driver_sha256'],version)
 frozen=read(R/f'facts_v{version}'/'FREEZE.json');check('frozen_scenario_core_equal_v4',frozen['scenario_hashes'],read(R/'facts_v4/FREEZE.json')['scenario_hashes'],version)
 chain.append(dict(version=version,through=through,exact_rows=record))
# Review the small driver independently: no algorithm override and exactly one run call.
driver_tree=ast.parse((R/'run_with_checkpoints.py').read_text());check('driver_has_no_function_or_class_override',any(isinstance(n,(ast.FunctionDef,ast.ClassDef)) for n in driver_tree.body),False)
calls=[n for n in ast.walk(driver_tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='run'];check('driver_one_existing_engine_run',len(calls),1);check('driver_run_only_output_arguments',{kw.arg for kw in calls[0].keywords},{'checkpoints','prior'})
# Audit every actual held or pending target, not merely the first lexicographic error.
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024');E=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1');manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
orders=read(S/'ORDERS.json');holdings=read(S/'HOLDINGS.json');pending=read(S/'PENDING_AT_END.json');attempts={x['sid']:x for x in read(S/'ATTEMPTS.json') if x['final_qty']};last_day=read(S/'DAY_LEDGER.json')[-1]['day'];held={}
for h in holdings:
 if h['day']==last_day:held[h['sid']]=held.get(h['sid'],0)+h['qty']
pmap={x['sid']:x for x in pending};targets=sorted(set(held)|set(pmap));events=read(E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json')+read(O/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json')+read(B/'ADDITIONAL_REVIEWED_EVENTS.json');evmap={(x['sid'],x['ex_date']):x for x in events};issues=[];all_targets=[];source_cache={};gap=None
for s in targets:
 m=manifest[s];path=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));z=pd.read_parquet(path);source_cache[s]=z;expected=attempts[s] if s in held else pmap[s];problems=[]
 if T not in z.index:problems.append('OPEN_MISSING')
 else:
  row=z.loc[T]
  if not np.isfinite(row.raw_open) or row.raw_open<=0:problems.append('OPEN_MISSING')
  else:
   if tuple(str(row[c]) for c in ['source_kind','source_path','segment_id'])!=tuple(expected['origin']):problems.append('SOURCE_CHANGE')
   f0=D(expected['factor']);f1=D(str(row.adjustment_factor));ev=evmap.get((s,str(T.date())));actions=[a for a in read(AS/'inputs-v1/actions'/(s+'.json'))['events'] if a['effective_date']==str(T.date())]
   if not f1.is_finite() or f1<=0:problems.append('FACTOR_INVALID')
   else:
    if actions and ev is None:problems.append('UNADMITTED_EQUITY_EVENT')
    if abs(f1/f0-1)>D('1e-11') and ev is None:problems.append('UNADMITTED_FACTOR_CHANGE')
    if ev and ('factor_old' in ev or 'factor_new' in ev):
     if 'factor_old' in ev and abs(f0/D(ev['factor_old'])-1)>D('1e-11'):problems.append('OLD_FACTOR_MISMATCH')
     if 'factor_new' in ev and abs(f1/D(ev['factor_new'])-1)>D('1e-11'):problems.append('NEW_FACTOR_MISMATCH')
 detail=dict(sid=s,held_qty=held.get(s,0),pending_seed=s in pmap,primary_issues=problems);all_targets.append(detail)
 if problems:issues.append(detail)
 if s=='300277.SZ':
  nextdates=z.index[z.index>T];missing=[d for d in ['2024-10-28','2024-10-29','2024-10-30','2024-10-31'] if pd.Timestamp(d) not in z.index]
  gap=dict(sid=s,held_qty=held[s],last_observed_before_stop=str(z.index[z.index<T][-1].date()),first_observed_after_stop=str(nextdates[0].date()) if len(nextdates) else None,missing_requested_remaining_days=missing,source_path=path,source_sha256=sha(path),actual_seed_trades=[x for x in orders if x['sid']==s and x['side']=='BUY_SEED']);check('gap_source_matches_frozen_manifest',sha(path),m['source_sha256'][path],s)
check('unique_actual_exposure_primary_blocker',issues,[dict(sid='300277.SZ',held_qty=100,pending_seed=False,primary_issues=['OPEN_MISSING'])]);check('actual_held_300277_retained',gap['held_qty'],100);check('gap_next_source_row',gap['first_observed_after_stop'],'2024-11-11');check('gap_no_remaining_requested_rows',gap['missing_requested_remaining_days'],['2024-10-28','2024-10-29','2024-10-30','2024-10-31']);check('last_real_300277_mark',gap['last_observed_before_stop'],'2024-10-25')
block=read(S/'UNCERTIFIED_DAY.json');check('recorded_blocker_primary_reason',block['reason'],'2024-10-28 300277.SZ OPEN_MISSING');check('no_partial_orders',block['partial_orders'],[])
for family in families:
 for row in read(S/(family+'.json')):
  if 'day' in row:check('no_uncertified_rows',row['day']<'2024-10-28',True,family)
# Independently trace all four no-fill tickets, including the two October additions.
nofill_details=[];intents=read(S/'OPEN_INTENTS.json');reservations=read(S/'OPEN_RESERVATIONS.json');candidates=read(S/'CANDIDATES.json');all_attempts=read(S/'ATTEMPTS.json');baseline_orders=read(B/'full_20241031_once/ORDERS.json')
for nf in read(S/'NO_FILLS.json'):
 s=nf['sid'];dt=nf['day'];t=nf['signal_day'];m=manifest[s];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));z=source_cache[s] if s in source_cache else pd.read_parquet(p);row=z.loc[pd.Timestamp(dt)];prices={k:str(row[k]) for k in ['raw_open','raw_high','raw_low','raw_close']};check('no_fill_all_four_raw_prices_equal',len({D(v) for v in prices.values()}),1,[s,dt]);check('positive_no_fill_raw_price',D(prices['raw_open'])>0,True,[s,dt]);check('no_fill_exact_source_hash',sha(p),m['source_sha256'][p],[s,dt])
 ii=[x for x in intents if x['row_type']=='ALLOCATION' and x['day']==dt and x['sid']==s and x['event']=='SEED'];rr=[x for x in reservations if x['day']==dt and x['sid']==s and x['kind']=='SEED'];cc=[x for x in candidates if x['phase']=='OPEN' and x['day']==dt and x['sid']==s and x['event']=='SEED'];check('no_fill_one_original_intent',len(ii),1,[s,dt]);check('no_fill_one_reservation',len(rr),1,[s,dt]);check('no_fill_original_intent_approved',ii[0]['decision'],'PASS',[s,dt]);check('no_fill_reserved_original_qty',(ii[0]['executed_q'],rr[0]['original_q'],rr[0]['reserved_q'],nf['qty']),(100,100,100,100),[s,dt]);check('no_fill_candidate_final_status',cc[0]['decision'],'NO_FILL_ONEPRICE_EXPOST',[s,dt]);check('no_fill_candidate_zero_execution',cc[0]['executed_q'],0,[s,dt])
 check('old_ticket_never_replayed',any(x['sid']==s and x['signal_day']==t and x['side']=='BUY_SEED' for x in orders),False,[s,t]);check('old_ticket_no_attempt',any(x['sid']==s and x['signal_day']==t for x in all_attempts),False,[s,t]);check('old_ticket_not_pending',any(x['sid']==s and x['signal_day']==t for x in pending),False,[s,t]);base_seed=next(x for x in baseline_orders if x['sid']==s and x['side']=='BUY_SEED' and x['signal_day']==t);desc=[x for x in baseline_orders if x['round_id']==base_seed['round_id'] and x['side']=='BUY_ADD']
 nofill_details.append(dict(sid=s,day=dt,signal_day=t,raw_prices=prices,source_path=p,source_sha256=sha(p),reserved_q=rr[0]['reserved_q'],reserved_cost=rr[0]['reserved_cost'],allocation_rank=rr[0]['rank'],baseline_round_id=base_seed['round_id'],baseline_descendant_ADD_count=len(desc),old_ticket_expired=True))
check('new_000506_exact_bar',next(x for x in nofill_details if x['sid']=='000506.SZ')['raw_prices'],dict(raw_open='2.04',raw_high='2.04',raw_low='2.04',raw_close='2.04'))
# Author final seal is evidence to verify, not a replacement for the checks above.
author=read(R/'FINAL_BOUNDED_RESEARCH_SEAL.json');author_check=[]
for v in author['versions']:
 for mm in v['output_manifests']:
  mp=Path(mm['path']);check('author_manifest_seal_hash',sha(mp),mm['sha256'],str(mp))
  for fn,h in read(mp).items():check('all_version_output_hash',sha(mp.parent/fn),h,str(mp.parent/fn))
report=dict(status='PASS' if not errors else 'FAIL',checks=dict(checks),check_count=sum(checks.values()),errors=errors,certified_through=last_day,planned_end='2024-10-31',completed_requested_horizon=False,extension_prefix_chain=chain,held_symbols=len(held),pending_seed_count=len(pending),actual_target_count=len(targets),primary_blockers=issues,gap=gap,no_fill_ticket_details=nofill_details,scope='Read-only independent source/preflight, prefix and no-fill ticket audit. No strategy run, price repair, suspension assumption or future-row substitution.',author_final_seal_sha256=sha(R/'FINAL_BOUNDED_RESEARCH_SEAL.json'))
for name,val in [('FINAL_BOUNDARIES',report),('ALL_20241028_ACTUAL_TARGETS',all_targets)]:
 dest=A/'facts_v9'/(name+'.json');assert not dest.exists();dest.write_text(json.dumps(val,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['checks','extension_prefix_chain','no_fill_ticket_details']},ensure_ascii=False,indent=2))
