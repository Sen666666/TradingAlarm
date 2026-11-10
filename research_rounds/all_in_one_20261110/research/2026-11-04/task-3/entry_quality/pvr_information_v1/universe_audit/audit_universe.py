"""Inventory frozen candidate logs and financing coverage, no feature export/account."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip,hashlib,time,math
HERE=Path(__file__).resolve().parent;E=HERE.parents[1];ROOT=E/'trend_exit_controls_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');OUT=HERE/'results_v1';SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def stream(p):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with gzip.open(p,'rt') as f:
  for s in f:yield json.loads(s)
def save(n,x):
 with (OUT/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def key(day,sid,role):return (day,sid,role)
if __name__=='__main__':
 assert not OUT.exists();OUT.mkdir(parents=True);begin=time.monotonic()
 universe={x['symbol'] for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};assert len(universe)==1709
 answer={}
 for win in ['2022_2024','strong']:
  run=ROOT/'runs/BASELINE'/win;pair=run/'pair';meta=read(run/'RUN_METADATA.json');assert meta['arm']=='BASELINE' and not meta['yearly_reset']
  for source in [W/'pvr-slot1-native-readiness-20261101/native_rank.py',W/'case-stage-ledger-20261031/v3/joint_v3.py',W/'case-stage-ledger-20261031/v3/launch_v3.py',W/'account-risk-ablation-20261031/adapter.py',W/'account-risk-ablation-20261031/route_without_account_check.py']:
   assert sha(source)==meta['source_freeze'][str(source)];SRC[str(source)]=sha(source)
  book=read(pair/'B.json.gz',gz=True);daily=read(pair/'daily.jsonl.gz',gz=True,lines=True);days=[x['at'][:10] for x in daily];dayprev={d:days[i-1] for i,d in enumerate(days) if i}
  decisions={x['at'][:10]:x for x in book['decisions']};pending={};bysd=defaultdict(dict);pending_roles=Counter();core_events=set();mobile_events=set();sourceunknown=Counter()
  for day,d in decisions.items():
   for i in d['intents']:
    k=key(day,i['sid'],i['role']);assert k not in pending;pending[k]=i;bysd[day,i['sid']][i['role']]=i;pending_roles[i['role']]+=1;assert i['cap']>0 and not i.get('size_reject')
    if i['role']=='core':
     if i['epoch'] is None:sourceunknown['pending_core_epoch_missing']+=1
     else:core_events.add((i['sid'],json.dumps(i['epoch'],separators=(',',':'))))
    else:
     if i.get('CP1_id') is None:sourceunknown['pending_mobile_canonical_receipt_missing']+=1
     else:mobile_events.add((i['sid'],i['CP1_id']))
  rank={};rank_ready=Counter();rolepatterns=Counter();bydayrank=Counter();first_unknown=[]
  for r in stream(pair/'rank-policy.jsonl.gz'):
   assert r['account']=='B';k=(r['day'],r['sid']);assert k not in rank;rank[k]=r;assert set(r['roles'])==set(bysd[k]);assert len(r['roles'])==len(set(r['roles']))
   assert r['PVR_ready']==(r['PVR'] is not None and math.isfinite(r['PVR']));rank_ready['known' if r['PVR_ready'] else 'UNKNOWN_kept_original_slot']+=1
   if not r['PVR_ready']:
    assert r['final_slot']==r['original_slot'] and r['priority_rank']==r['original_H1_rank']
    if len(first_unknown)<12:first_unknown.append(r)
   for role,i in bysd[k].items():assert i['priority_rank']==r['priority_rank']==i['rank'] and i['original_H1_rank']==r['original_H1_rank'] and i['PVR_ready']==r['PVR_ready'] and i['PVR_score']==r['PVR']
   rolepatterns['+'.join(sorted(r['roles']))]+=1;bydayrank[r['day']]+=1
  assert set(rank)==set(bysd)
  funding=read(pair/'funding.jsonl.gz',gz=True,lines=True);fund_close=defaultdict(list);fund_open=defaultdict(list);fund_open_reasons=Counter();fund_close_reasons=Counter();open_unmapped=[]
  for f in funding:
   assert f['account']=='B';at=f['at'];day=at[:10]
   if '15:10:00' in at:fund_close[key(day,f['sid'],f['role'])].append(f);fund_close_reasons[f['result']]+=1
   elif '09:30:00' in at:
    if day not in dayprev:open_unmapped.append(f);continue
    k=key(dayprev[day],f['sid'],f['role']);assert k in pending,('OPEN event absent from prior qualified pending',win,f);fund_open[k].append(f);fund_open_reasons[f['result']]+=1
   else:raise AssertionError(('Unexpected funding clock',f))
  reserves={};fills=defaultdict(list)
  for j in book['journal']:
   if j['kind']=='real_reserve':
    signal=j['budget_order'].split('|')[1][:10];k=key(signal,j['sid'],j['role']);assert k in pending;reserves[k]=j
   elif j['kind']=='real_buy_fill':
    k=key(j['signal_at'][:10],j['sid'],j['role']);assert k in pending;fills[k].append(j)
  assert sum(map(len,fills.values()))==len([t for t in book['trades'] if t['side']=='buy'])
  statuses=Counter();status_roles=defaultdict(Counter);status_samples=defaultdict(list)
  for k,i in pending.items():
   day,sid,role=k
   if k in fills:status='actual_fill'
   elif k in reserves:status='actual_reserved_without_fill'
   elif fund_open.get(k):status='OPEN_logged_rejection_or_no_fill'
   elif day==days[-1]:status='right_censored_no_following_OPEN_in_book'
   elif any((day,sid,other) in reserves for other in ['core','mobile'] if other!=role):status='same_stock_other_role_reserved_native_done_skip'
   else:status='UNKNOWN_no_OPEN_funding_event_keep_in_mother'
   statuses[status]+=1;status_roles[status][role]+=1
   if len(status_samples[status])<5:status_samples[status].append(dict(day=day,sid=sid,role=role,CP1_id=i.get('CP1_id'),epoch=i.get('epoch'),cap=i['cap'],OPEN_logs=fund_open.get(k,[])))
  counts=Counter();barriers=Counter();qstates=Counter();opp_roles=Counter();role_nominal_gap=Counter();gap_causes=Counter();barfree_mobile_events=set();all_mobile_events=set();source_field_absence=Counter();seen_day=None;seenset=set();opdays=Counter();rank_seen=set();barfree_seen=set();barfree_missing_rank_samples=[]
  def flush():
   if seen_day is not None:assert seenset==universe,('Incomplete opportunity grid day',win,seen_day,len(seenset))
  for o in stream(pair/'opportunities.jsonl.gz'):
   assert o['account']=='B';day=o['day'];sid=o['sid'];sd=(day,sid)
   if day!=seen_day:flush();seen_day=day;seenset=set()
   assert sid not in seenset;seenset.add(sid);counts['full_opportunity_stock_days']+=1;opdays[day]+=1
   for q in ['core_Q','mobile_Q']:qstates[q+':'+('UNKNOWN' if o[q] is None else str(o[q]))]+=1
   for why in o['barriers']:barriers[why]+=1
   for role in o['roles']:
    opp_roles['raw_role:'+role]+=1
    if role=='core':source_field_absence['opportunity_core_role_epoch_not_stored']+=1
    else:
     assert o['CP1_id'];all_mobile_events.add((sid,o['CP1_id']))
   if o['roles']:counts['raw_stock_days_with_roles']+=1
   free=bool(o['roles']) and not o['barriers']
   if free:
    counts['barrier_free_stock_days_with_roles']+=1;barfree_seen.add(sd)
    for role in o['roles']:
     opp_roles['barrier_free_role:'+role]+=1
     if role=='mobile':barfree_mobile_events.add((sid,o['CP1_id']))
     if key(day,sid,role) not in pending:
      role_nominal_gap[role]+=1;events=fund_close.get(key(day,sid,role),[])
      gap_causes['CLOSE_size_reject_logged' if events else 'UNKNOWN_no_CLOSE_size_record_quote_or_floor_gate']+=1
      for f in events:gap_causes['reason:'+f['result']]+=1
    if sd not in rank:
     counts['barrier_free_stock_days_not_in_pending_rank']+=1
     if len(barfree_missing_rank_samples)<10:barfree_missing_rank_samples.append(o)
   if sd in rank:
    assert free;assert set(rank[sd]['roles'])<=set(o['roles']);rank_seen.add(sd)
    for role in rank[sd]['roles']:
     if role=='mobile':assert pending[key(day,sid,role)]['CP1_id']==o['CP1_id']
  flush();assert set(opdays)==set(days);assert counts['full_opportunity_stock_days']==1709*len(days);assert rank_seen==set(rank)
  filled_sd={(d,s) for d,s,r in fills};reserve_sd={(d,s) for d,s,r in reserves}
  answer[win]=dict(calendar_CLOSEs=len(days),frozen_stocks=1709,mothers=dict(counts),opportunity_roles=dict(opp_roles),opportunity_three_valued_Q=dict(qstates),opportunity_barrier_occurrences_not_unique_rows=dict(barriers),
   pending_rank_stock_days=len(rank),pending_intent_role_rows=len(pending),pending_roles=dict(pending_roles),pending_rank_roles_patterns=dict(rolepatterns),pending_PVR_status=dict(rank_ready),all_original_pending_and_rank_stockdays_exact=True,
   actual_reserved_intent_keys=len(reserves),actual_reserved_stock_days=len(reserve_sd),actual_fill_intent_keys=len(fills),actual_fill_layers=sum(map(len,fills.values())),actual_fill_stock_days=len(filled_sd),
   pending_intent_funding_status=dict(statuses),pending_intent_funding_status_by_role={k:dict(v) for k,v in status_roles.items()},OPEN_funding_event_results=dict(fund_open_reasons),CLOSE_nominal_size_rejection_results=dict(fund_close_reasons),unmapped_OPEN_funding_events=open_unmapped,
   barrier_free_roles_removed_before_pending=dict(role_nominal_gap),barrier_free_pre_pending_gap_causes=dict(gap_causes),
   causal_event_dedup_descriptive=dict(pending_core_stock_native_watch_epoch_keys=len(core_events),pending_mobile_stock_canonicalCP_keys=len(mobile_events),raw_mobile_stock_CP_keys=len(all_mobile_events),barrier_free_mobile_stock_CP_keys=len(barfree_mobile_events),missing_pending_source_ids=dict(sourceunknown),nonpending_core_source_epoch_field_missing=dict(source_field_absence)),
   samples=dict(PVR_UNKNOWN_kept=first_unknown,barrier_free_missing_pending=barfree_missing_rank_samples,funding={k:v for k,v in status_samples.items()}),
   per_original_CLOSE=dict(opportunity_counts=dict(opdays),pending_rank_stock_counts=dict(bydayrank)),
   keys_binding=dict(pending_stock_days_sha256=hashlib.sha256(json.dumps(sorted(rank),separators=(',',':')).encode()).hexdigest(),pending_role_keys_sha256=hashlib.sha256(json.dumps(sorted(pending),separators=(',',':')).encode()).hexdigest()),
   semantics='Full grid -> source role qualification/barriers -> quote/floor and nominal lot/CORE sizing -> pending/rank at decision CLOSE -> next OPEN actual financing/route/reserve -> actual fill. Resource-fundability under a different ordering is not identified by log membership. Dedup keys are repeated causal-event descriptions, not independent trades.')
  print('FINISHED',win,counts,len(rank),len(pending),dict(rank_ready),dict(statuses),flush=True)
 save('UNIVERSE_COUNTS_AND_CLOCK_AUDIT.json',answer);save('VALIDATION.json',dict(status='PASS_ORIGINAL_OPPORTUNITY_PENDING_RANK_AND_FUNDING_INVENTORY',elapsed_seconds=time.monotonic()-begin,full_feature_exports=0,new_accounts=0,new_financial_paths=0,all_1709_by_968_original_grid_preserved=True,known_pre_pending_filters_explicit=True,unknowns_preserved=True,rank_is_not_all_market_feasible_candidates=True))
 SRC[str(Path(__file__).resolve())]=sha(__file__);save('SOURCE_SHA256.json',SRC);save('DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
