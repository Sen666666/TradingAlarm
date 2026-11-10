"""Read-only complete saved-event audit. No strategy/consumer imports or economics.
Only reads sealed ledger/market artifacts and writes new research files in this directory.
'Actual BUY' below means an executed saved conditional-proxy action, never a broker fill.
"""
from pathlib import Path
from collections import defaultdict, Counter
import ast, csv, hashlib, json, math
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
J=R/'independent_channel_joint_economic_v1'
O=Path(__file__).resolve().parent
H={}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p):
 p=Path(p).resolve(); h=sha(p)
 if str(p) in H: assert H[str(p)]==h, ('SOURCE_CHANGED',str(p))
 H[str(p)]=h
 return p
def js(p): return json.loads(src(p).read_text())
def cs(p): return list(csv.DictReader(src(p).open()))
def day(v): return '' if v is None or pd.isna(v) else str(v)[:10]
def val(v): return None if v is None or (not isinstance(v,(list,dict,tuple)) and pd.isna(v)) else v
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,pd.Timestamp):return day(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def dump(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def csvout(n,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with (O/n).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for row in rows:w.writerow({k:json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else clean(v) for k,v in row.items()})
def clock(d,seq):return {'day':d,'sequence':seq} if d else None
def relation(a,b):
 if not a or not b:return 'UNKNOWN'
 return 'AFTER' if a>b else 'SAME_DAY' if a==b else 'BEFORE'
def same(a,b):return 'UNKNOWN' if not a or not b else 'SAME' if a==b else 'DIFFERENT'
def groupdups(rows,key):
 g=defaultdict(list)
 for r in rows:
  if r.get(key):g[str(r[key])].append(r['round_id'])
 return {k:v for k,v in g.items() if len(v)>1}

src(__file__)
seal=js(J/'FINAL_RUN_SEAL.json')
seal_checks={}
for k,h in {**seal['code_sha256'],**seal['files']}.items():
 p=src(J/k);assert H[str(p)]==h,('FROZEN_SEAL_MISMATCH',str(p))
 seal_checks[k]=h
for p in [J/'joint_engine.py',J/'joint_policy.py',J/'execution_book.py',J/'market_adapter.py',R/'independent_channel_probe_preflight_v1/core.py']:
 src(p)
cols=['sid','day','identity','root_day','receipt_id','born','failed','receipt','new_frontier',
 'phase','confirmed_now','confirmed_at','C','Q','R','F','S_old','S_new','E0','I','old_i_epoch',
 'old_epoch_lineage_known','old_epoch_lineage_reason','old_i_buy','old_i_target','old_e0_target']
daily=pd.read_parquet(src(R/'independent_channel_full1709_preflight_v1/overlap/DAILY_OVERLAP.parquet'),columns=cols)
daily['day']=daily.day.dt.strftime('%Y-%m-%d')
assert not daily.duplicated(['sid','day']).any()
md={(r['sid'],r['day']):r for r in daily.to_dict('records')}
receipt=pd.read_parquet(src(R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'),
 columns=['sid','day','identity','root_day','receipt_id','phase','confirmed_at'])
receipt['day']=receipt.day.dt.strftime('%Y-%m-%d')
rc={(r['sid'],r['day']):r for r in receipt.to_dict('records')}
events=[];timeline=[];unknown_rows=[];q0_rows=[];controls=[];all_books=[];summaries={};failures=[];details={}
for year in (2022,2024):
 p=J/f'economic_{year}'
 rounds=cs(p/'joint/ROUNDS.csv');actions=cs(p/'joint/ACTIONS.csv')
 rr={r['round_id']:r for r in rounds};assert len(rr)==len(rounds)
 for n in ('REGISTRATIONS.csv','CLAIM_LEDGER.csv','END_STATES.csv'):
  if (p/'joint'/n).exists():src(p/'joint'/n)
 for n in ('CLAIMS.json','BRIDGES.json','SOURCE_HASHES.json'):
  src(p/'joint'/n)
 books=js(p/'EXECUTION_BOOKS.json');offers=js(p/'OFFER_AUDIT.json')
 ab=js(p/'AB_DECISION_AUDIT.json');frozen=js(p/'FROZEN_RESPONSIBILITIES.json');pa=js(p/'PRICE_AUDIT.json')
 src(p/'ECONOMIC_LOOP_COMPLETE.json')
 buy=[a for a in actions if a['side']=='buy_core'];exitrows=[a for a in actions if a['side']=='sell_all']
 bb={a['round_id']:a for a in buy};ee={a['round_id']:a for a in exitrows}
 assert len(bb)==len(buy) and len(ee)==len(exitrows)
 assert set(books)=={rid for rid in bb if rr[rid]['owner_lane']=='PRICE'}
 acts=defaultdict(list)
 for i,a in enumerate(actions):acts[a['round_id']].append((i,a))
 # Reconcile every round's quantity before declaring sell_all an actual flat transition.
 for rid,ls in acts.items():
  inventory=0
  for i,a in ls:
   q=int(float(a['q'])); before=inventory
   inventory+=q if a['side'].startswith('buy') else -q
   assert inventory>=0,(rid,'NEGATIVE_INVENTORY')
   if a['side']=='buy_core':assert before==0
   if a['side']=='sell_all':assert before==q and inventory==0
   if a['side']=='sell_add':assert inventory>0,('SELL_ADD_NOT_FLAT',rid)
   timeline.append(dict(year=year,sid=a['sid'],round_id=rid,owner_lane=rr[rid]['owner_lane'],
    action_row=i,day=a['day'],market_phase='OPEN',side=a['side'],q=q,inventory_before=before,
    inventory_after=inventory,is_full_exit=a['side']=='sell_all',signal_day=a['signal_day'],
    reason=a['reason'],evidence_domain='CONDITIONAL_FULL_FILL_PROXY_NOT_BROKER'))
  assert int(float(rr[rid]['core_qty'] or 0))+int(float(rr[rid]['add_qty'] or 0))==inventory
 prev={};prev_price={};ordinal=Counter();pordinal=Counter();ev=[]
 for a in sorted(buy,key=lambda a:(a['sid'],a['day'],a['round_id'])):
  rid=a['round_id'];r=rr[rid];sid=r['sid'];sig=r['signal_day'];m=md[(sid,sig)]
  old=prev.get(sid);oldprice=prev_price.get(sid);ordinal[sid]+=1
  root=ast.literal_eval(r['price_root']) if r['price_root'] else None
  canonical_market=(sid,str(m['identity']),day(m['root_day'])) if pd.notna(m['root_day']) else None
  e=dict(year=year,window=r['window'],sid=sid,name=r['name'],round_id=rid,owner_lane=r['owner_lane'],
   all_buy_ordinal=ordinal[sid],entry_day=a['day'],entry_phase='OPEN',entry_qty=int(float(a['q'])),
   signal_day=sig,signal_known_at=clock(sig,100),event_id=r['event_id'],event_type=r['event_type'],
   status=r['status'],status_day=r['status_day'],full_exit_day=ee.get(rid,{}).get('day'),
   full_exit_reason=ee.get(rid,{}).get('reason'),price_root=root,
   market_price_root_at_signal=canonical_market,market_phase=m['phase'],
   market_confirmed_at=clock(day(m['confirmed_at']),100),
   market_new_frontier=m['new_frontier'],market_receipt=m['receipt'],market_legacy_receipt_id=m['receipt_id'],
   market_C=m['C'],market_Q=m['Q'],market_R=m['R'],market_F=m['F'],market_S_new=m['S_new'],
   I_epoch=val(m['old_i_epoch']),I_epoch_lineage_known=m['old_epoch_lineage_known'],
   I_epoch_lineage_reason=m['old_epoch_lineage_reason'],I_target=m['old_i_target'],
   E0_target=m['old_e0_target'],i_buy=m['old_i_buy'],
   prev_round_id=old['round_id'] if old else None,prev_lane=old['owner_lane'] if old else None,
   prev_entry_day=old['entry_day'] if old else None,prev_signal_day=old['signal_day'] if old else None,
   prev_full_exit_day=old['full_exit_day'] if old else None,
   transition=old['owner_lane']+'->'+r['owner_lane'] if old else 'FIRST_WINDOW_BUY',
   prev_price_root=old['price_root'] if old else None,
   prev_I_epoch=old['I_epoch'] if old else None,
   I_epoch_vs_previous_buy=same(val(m['old_i_epoch']),old['I_epoch']) if old else 'FIRST_WINDOW_BUY',
   source_outcome_net_pnl_unmodified=r['net_pnl'],
   source_outcome_net_return_unmodified=r['net_return_on_buy_cash'],
   actual_broker_order='NOT_PROVIDED',actual_broker_ack='NOT_PROVIDED',actual_broker_fill='NOT_PROVIDED')
  if old:
   assert old['full_exit_day'],('BUY_WITHOUT_PREVIOUS_FULL_EXIT',old,rid)
   assert old['full_exit_day']<=sig<a['day'],('EXIT_SIGNAL_ENTRY_CLOCK',rid)
   e['prev_exit_known_at']=old.get('exit_terminal_known_at') or {'day':old['full_exit_day'],'phase':'OPEN_SAVED_ACTION_NO_BROKER_ACK'}
  if root:
   pordinal[sid]+=1;book=books[rid];pt=book['parents']['Role.PROBE']['target']
   assert tuple(pt['root_id'])==root==canonical_market
   assert (sid,sig) in rc
   assert tuple(pt['signal_receipt_id'][0])==root and pt['signal_receipt_id'][1]==sig
   assert m['receipt'] and m['new_frontier']
   assert int(pt['target_Q'])==int(float(a['q']))==book['parents']['Role.PROBE']['filled_F']
   assert pt['registered_known_at']==clock(a['day'],20)
   pe=[z for z in book['events'] if z['event']=='proxy_target_registered' and z.get('parent_id')==pt['parent_id']]
   assert len(pe)==1
   paid=[z for z in pa if z['round_id']==rid and z.get('role')=='PROBE' and z['event']=='PROXY_FULL_FILL_NOT_ACTUAL']
   assert len(paid)==1 and paid[0]['target_Q']==pt['target_Q']
   sell_orders=[z for z in book['orders'].values() if z['side']=='SELL']
   exit_clock=sell_orders[-1]['terminal_known_at'] if rid in ee else None
   if exit_clock:assert exit_clock==clock(ee[rid]['day'],40)
   retirement=[z for z in book['events'] if z['event']=='proxy_root_retired']
   e.update(price_buy_ordinal=pordinal[sid],canonical_receipt_id=pt['signal_receipt_id'],
    receipt_known_at=clock(sig,100),root_born_known_at=clock(root[2],100),
    root_birth_vs_previous_full_exit=relation(root[2],old['full_exit_day']) if old else 'FIRST_WINDOW_BUY',
    root_identity_vs_previous_price_owner=same(root,old['price_root']) if old and old['owner_lane']=='PRICE' else 'PREVIOUS_OWNER_NOT_PRICE' if old else 'FIRST_WINDOW_BUY',
    first_window_price_root_before_window_start=(root[2]<('2022-01-01' if year==2022 else '2024-09-01')) if not old else None,
    price_participation='REPEAT_PRICE' if oldprice else 'FIRST_PRICE_AFTER_AB' if old else 'FIRST_WINDOW_PRICE',
    prev_actual_price_round_id=oldprice['round_id'] if oldprice else None,
    prev_actual_price_root=oldprice['price_root'] if oldprice else None,
    prev_actual_price_I_epoch=oldprice['I_epoch'] if oldprice else None,
    I_epoch_vs_previous_price_buy=same(e['I_epoch'],oldprice['I_epoch']) if oldprice else 'FIRST_PRICE',
    canonical_root_vs_previous_price_buy=same(root,oldprice['price_root']) if oldprice else 'FIRST_PRICE',
    probe_parent_id=pt['parent_id'],fixed_target_Q=pt['target_Q'],filled_F=book['parents']['Role.PROBE']['filled_F'],
    target_registered_known_at=pt['registered_known_at'],proxy_fill_known_at=clock(a['day'],30),
    proxy_complete_known_at=clock(a['day'],40),exit_terminal_known_at=exit_clock,
    retired_known_at=retirement[0]['known_at'] if retirement else None,
    current_book_unknown=book['responsibility']['unknown'],current_book_retired=book['responsibility']['retired'],
    current_book_owner_locked=book['responsibility']['owner_locked'],current_book_held=book['responsibility']['held_qty'],
    previous_actual_price_parent_reused=pt['parent_id']==oldprice['probe_parent_id'] if oldprice else False)
   assert not old or relation(root[2],old['full_exit_day']) in ('AFTER','SAME_DAY')
   all_books.append(e)
   prev_price[sid]=e
  prev[sid]=e;ev.append(e)
 events+=ev
 # No unknown path can be silently released to issue later BUY or a later registration.
 for r in rounds:
  if 'UNKNOWN' not in r['status']:continue
  later_buy=[a['round_id'] for a in buy if a['sid']==r['sid'] and a['day']>=r['status_day'] and a['round_id']!=r['round_id']]
  later_reg=[z['round_id'] for z in rounds if z['sid']==r['sid'] and z['signal_day']>=r['status_day'] and z['round_id']!=r['round_id']]
  resp=books.get(r['round_id'],{}).get('responsibility',{})
  assert not later_buy and not later_reg
  if r['round_id'] in books:assert resp['unknown'] and resp['owner_locked']
  unknown_rows.append(dict(year=year,round_id=r['round_id'],sid=r['sid'],lane=r['owner_lane'],
    status=r['status'],unknown_day=r['status_day'],had_actual_proxy_buy=r['round_id'] in bb,
    later_actual_buy_rounds=later_buy,later_registration_rounds=later_reg,
    book_present=r['round_id'] in books,final_responsibility=resp,assertion='PASS_LOCKED_NO_REENTRY'))
 # q0 is never a submitted zero fill, and later same-root initial success is first use.
 for r in rounds:
  if r['status']!='PRECHECK_Q0_NO_SUBMIT':continue
  assert r['round_id'] not in books and r['round_id'] not in bb
  root=ast.literal_eval(r['price_root'])
  later=[e for e in ev if e['price_root']==root and e['entry_day']>r['status_day']]
  assert len(later)<=1
  if later:assert later[0]['signal_day']>r['signal_day']
  q0_rows.append(dict(year=year,round_id=r['round_id'],sid=r['sid'],root=root,signal_day=r['signal_day'],
    q0_day=r['status_day'],target_created=False,order_submitted=False,broker_zero_fill_evidence=False,
    later_same_root_buy_round=later[0]['round_id'] if later else None,
    later_same_root_receipt=later[0]['canonical_receipt_id'] if later else None,
    later_same_root_signal=later[0]['signal_day'] if later else None,
    later_same_root_entry=later[0]['entry_day'] if later else None,
    classification='NO_SUBMIT_THEN_FRESH_RECEIPT_FIRST_ROOT_USE' if later else 'NO_LATER_SAME_ROOT_BUY'))
 # Same signal controls preserve every raw PRICE receipt, whether or not selected.
 abm={(z['sid'],day(z['day'])):z for z in ab};offg=defaultdict(list)
 for z in offers:offg[(z['sid'],day(z['day']))].append(z)
 rby={(r['sid'],r['signal_day']):r for r in rounds}
 assert len(rby)==len(rounds)
 for key,og in offg.items():
  raw=[z for z in og if z['owner_lane']=='PRICE' and z['result']=='APPLICATION']
  if not raw:continue
  assert len(raw)==1
  ar=abm.get(key);selected=rby.get(key)
  suppress=any(z['result']=='SUPPRESSED_BY_AB_VALID_CLOSE' for z in og)
  legal=bool(ar and ar.get('decision_before_joint')=='PASS_TO_JOINT_QUEUE')
  actual=selected and selected['round_id'] in bb
  if suppress:
   assert legal and (not selected or selected['owner_lane']=='AB')
  if selected and selected['owner_lane']=='PRICE':assert not legal and not suppress
  c=dict(year=year,sid=key[0],signal_day=key[1],price_request_id=raw[0]['request_id'],
    price_receipt_id=raw[0]['receipt_id'],AB_event_id=ar.get('event_id') if ar else None,
    AB_decision_before_joint=ar.get('decision_before_joint') if ar else 'NO_AB_EVENT',
    AB_stock_state_before=ar.get('stock_state_before') if ar else None,
    AB_valid_close=legal,price_suppressed_by_legal_AB=suppress,
    selected_round_id=selected['round_id'] if selected else None,
    selected_lane=selected['owner_lane'] if selected else None,
    selected_status=selected['status'] if selected else None,
    had_actual_buy=bool(actual),actual_entry_day=bb[selected['round_id']]['day'] if actual else None,
    all_offer_results=[dict(lane=z['owner_lane'],result=z['result']) for z in og])
  controls.append(c)
 eb=[e for e in ev if e['owner_lane']=='PRICE'];re=[e for e in eb if e['prev_round_id']]
 summary=dict(all_registered=len(rounds),all_actual_proxy_buy=len(ev),all_actual_sell_all=len(ee),
  actual_buy_lanes=dict(Counter(e['owner_lane'] for e in ev)),actual_transitions=dict(Counter(e['transition'] for e in ev)),
  PRICE_actual_buy=len(eb),PRICE_reentries_after_any_lane=len(re),
  PRICE_reentry_root_birth_relation=dict(Counter(e['root_birth_vs_previous_full_exit'] for e in re)),
  PRICE_repeat_any_previous_PRICE=sum(e['price_participation']=='REPEAT_PRICE' for e in eb),
  PRICE_repeat_I_epoch_relation=dict(Counter(e['I_epoch_vs_previous_price_buy'] for e in eb if e['price_participation']=='REPEAT_PRICE')),
  PRICE_reentry_I_epoch_previous_any_relation=dict(Counter(e['I_epoch_vs_previous_buy'] for e in re)),
  PRICE_reentry_phase=dict(Counter(e['market_phase'] for e in re)),
  PRICE_reentry_signal_vs_exit=dict(Counter(relation(e['signal_day'],e['prev_full_exit_day']) for e in re)),
  PRICE_first_window_root_before_start=sum(e['first_window_price_root_before_window_start'] is True for e in eb),
  PRICE_first_window_count=sum(e['transition']=='FIRST_WINDOW_BUY' for e in eb),
  root_duplicates=groupdups(eb,'price_root'),receipt_duplicates=groupdups(eb,'canonical_receipt_id'),
  probe_parent_duplicates=groupdups(eb,'probe_parent_id'),
  selected_signal_duplicates=groupdups(ev,'event_id'),
  unknown_all=sum('UNKNOWN' in r['status'] for r in rounds),
  unknown_PRICE=sum('UNKNOWN' in r['status'] and r['owner_lane']=='PRICE' for r in rounds),
  unknown_after_positive_buy=sum('UNKNOWN' in r['status'] and r['round_id'] in bb for r in rounds),
  PRICE_unknown_after_positive_buy=sum('UNKNOWN' in r['status'] and r['round_id'] in bb and r['owner_lane']=='PRICE' for r in rounds),
  q0_no_submit=sum(r['status']=='PRECHECK_Q0_NO_SUBMIT' for r in rounds),
  q0_later_same_root_first_buy=sum(q['year']==year and q['later_same_root_buy_round'] is not None for q in q0_rows),
  legal_AB_suppression=sum(c['year']==year and c['price_suppressed_by_legal_AB'] for c in controls),
  legal_AB_suppressed_then_selected_no_buy=sum(c['year']==year and c['price_suppressed_by_legal_AB'] and bool(c['selected_round_id']) and not c['had_actual_buy'] for c in controls),
  sell_add_not_flat=sum(a['side']=='sell_add' for a in actions),
  actual_broker_fills_provided=0,negative_assertions=[])
 for k in ['root_duplicates','receipt_duplicates','probe_parent_duplicates','selected_signal_duplicates']:assert not summary[k]
 summaries[str(year)]=summary
 details[str(year)]=dict(rounds=rr,books=books,actions=actions)
assert not groupdups(all_books,'price_root')
assert not groupdups(all_books,'canonical_receipt_id')
assert not groupdups(all_books,'probe_parent_id')
# Read-source outcome labels only, with no filtered or counterfactual P&L calculation.
named={'605020.SH','002031.SZ','600126.SH','002126.SZ','605118.SH'}
cases=[e for e in events if (e['sid'] in named or e.get('root_birth_vs_previous_full_exit')=='SAME_DAY')]
case_full=[]
for e in cases:
 d=details[str(e['year'])];rid=e['round_id'];old=e['prev_round_id']
 case_full.append(dict(event=e,source_round=d['rounds'][rid],source_actions=[a for a in d['actions'] if a['round_id']==rid],
  prior_source_round=d['rounds'].get(old),prior_source_actions=[a for a in d['actions'] if a['round_id']==old],
  execution_book=d['books'].get(rid),prior_execution_book=d['books'].get(old)))
changed=[p for p,h in H.items() if sha(p)!=h]
assert not changed
csvout('ALL_ACTUAL_BUY_EVENTS.csv',events)
csvout('ALL_ACTUAL_ACTION_SEQUENCE.csv',sorted(timeline,key=lambda x:(x['year'],x['sid'],x['day'],x['action_row'])))
csvout('PRICE_REENTRY_EVENTS.csv',[e for e in events if e['owner_lane']=='PRICE' and e['prev_round_id']])
csvout('UNKNOWN_LOCK_ASSERTIONS.csv',unknown_rows)
csvout('Q0_FRESH_RECEIPT_FIRST_USE.csv',q0_rows)
csvout('SAME_SIGNAL_AB_PRICE_CONTROLS.csv',controls)
csvout('CASES.csv',cases)
dump('CASE_CLOCKS_COMPLETE.json',case_full)
dump('SUMMARY.json',summaries)
dump('SOURCE_HASHES.json',H)
dump('QA.json',dict(result='PASS_FULL_SAVED_EVENT_IDENTITY_AUDIT',all_sources_unchanged=True,
 sealed_files_reverified=len(seal_checks),sealed_production_code_reverified=len(seal['code_sha256']),
 all_actual_buy_events=len(events),all_action_events=len(timeline),all_PRICE_reentries=sum(e['owner_lane']=='PRICE' and bool(e['prev_round_id']) for e in events),
 cross_window_root_reuse=0,cross_window_receipt_reuse=0,cross_window_probe_parent_reuse=0,
 buy_after_unresolved_UNKNOWN=0,register_after_unresolved_UNKNOWN=0,duplicate_selected_stock_signal=0,
 sell_add_misclassified_as_flat=0,economic_runs=0,consumer_imports=0,filtered_or_counterfactual_pnl_runs=0,
 strategy_parameter_changes=0,only_new_research_outputs_written=True))
print(json.dumps(summaries,ensure_ascii=False,indent=2))
print('OUTPUT',str(O),flush=True)

