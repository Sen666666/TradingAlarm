"""Link recorded same-OPEN prior commitments only. No mark/state replay."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,hashlib,json,time
O=Path(__file__).resolve().parent;W=O.parents[1];SOURCES={}
def bind(p):p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def stream(p):
 with gzip.open(bind(p),'rt')as f:
  for x in f:yield json.loads(x)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def writer(n,rows):
 with gzip.open(O/n,'wt')as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False,default=str)+'\n')
def main():
 t=time.monotonic();bind(__file__);rows=list(stream(O/'CORE_SECTOR_REJECT_EVENTS.jsonl.gz'));snaps=read(O/'ORIGINAL_EXISTING_LAYER_SNAPSHOTS.json')
 meta=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
 orders={};counts=defaultdict(Counter);bound=0
 for w in ['long','strong']:
  root=W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair'
  with gzip.open(bind(root/'B.json.gz'),'rt')as f:b=json.load(f)
  audits={(x['at'][:10],x['sid']):x for x in b['audit']if x['kind']=='reserve'}
  real={x['order']:x for x in b['journal']if x['kind']=='real_reserve'}
  fills=defaultdict(list)
  for x in b['journal']:
   if x['kind']=='real_buy_fill':fills[x['budget_order']].append(x)
  wanted={x['funding_stream_index']:x for x in rows if x['window']==w};prefix=defaultdict(list);scprefix=defaultdict(list)
  for n,f in enumerate(stream(root/'funding.jsonl.gz')):
   if n%1000==0 and time.monotonic()-t>85:
    writer('CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.partial.jsonl.gz',rows);save('PREFIX_STATUS.json',dict(complete=False,bound=bound,seconds=time.monotonic()-t,limit_seconds=100));return
   if '09:30:00'not in f['at']:continue
   day=f['at'][:10]
   if n in wanted:
    x=wanted[n];assert x['at']==f['at']and x['sid']==f['sid'];sector=x['industry'];ss=snaps[x['snapshot_key']];old=ss['surviving_existing_layers_at_S0'];oldqty=sum(D(str(z['qty_after_original_actions_and_protection_exits']))for z in old)
    prior=list(scprefix[day,sector]);allprior=list(prefix[day]);pending=sorted({z['sid']for z in ss['previous_CLOSE_same_sector_layers']} & set(ss['CLOSE_account']['pending_sells']))
    x['original_sameOPEN_prior_commitments']=dict(all_prior_order_keys=allprior,same_sector_prior_order_keys=prior,
       same_sector_recorded_reserved_gross=str(sum((D(orders[k]['actual_reserved_gross'])for k in prior),D(0))),
       same_sector_recorded_reserved_buy_fees=str(sum((D(orders[k]['actual_reserved_buy_fee'])for k in prior),D(0))),
       scope='These are actual already-submitted ledger reservations before candidate; buy fills are consulted only after ALL native funding decisions. No full pre-candidate risk state reconstructed.',
       sameOPEN_new_filled_shares_sellable_today=False)
    x['inventory_vs_new_commitment_class']=('S0_no_old_inventory'if not oldqty else'S0_has_old_inventory')+('_with_prior_same_sector_new_orders'if prior else'_without_prior_same_sector_new_orders')
    x['old_lock_context']=dict(previous_CLOSE_pending_sell_sids_in_sector=pending,
       surviving_old_layers_with_prior_exit_reason=[z['layer']for z in old if z['previous_CLOSE_raw_layer'].get('reason')is not None],
       exact_S0_ExitOrder_remaining_and_sell_layers='NOT_SERIALIZED_FOR_ALL_DATES',
       note='Prior lock is not cancelled. Same-OPEN new orders/fills are not old sellable winners; new CA-share T+1/known lock needs ledger-level check.')
    counts[w]['events']+=1;counts[w][x['inventory_vs_new_commitment_class']]+=1;counts[w]['previous_CLOSE_old_sector_sell_lock_present']+=bool(pending);counts[w]['surviving_old_prior_exit_reason_present']+=bool(x['old_lock_context']['surviving_old_layers_with_prior_exit_reason']);bound+=1
   if f['result']=='reserved':
    a=audits[day,f['sid']];j=real[a['order_id']];assert j['role']==f['role']and int(j['shares'])==int(f['shares'])
    gross=D(a['gross_budget_cny']);fee=D(a['fee_reserved_cny']);assert gross==D(str(f['shares']))*D(f['price'])
    key=w+'|'+j['budget_order'];ff=fills[j['budget_order']]
    orders[key]=dict(window=w,OPEN=day,sector=meta[f['sid']]['sector_id'],funding_stream_index=n,
       sid=f['sid'],role=f['role'],shares=f['shares'],pool=f['pool'],price=f['price'],CP1_id=f.get('CP1_id'),
       order_id=a['order_id'],budget_order=j['budget_order'],actual_reserved_gross=str(gross),actual_reserved_buy_fee=str(fee),
       actual_reservation_audit=a,real_reserve_journal=j,actual_fills_after_all_funding=ff,
       later_filled_shares=str(sum((D(str(z['shares']))for z in ff),D(0))),
       final_native_budget_order=b['budget']['orders'].get(j['budget_order']),
       at_candidate_time='Submitted but not buy-filled yet in unchanged native opening sequence',
       cannot_assume_cancel_or_reuse=True,same_OPEN_new_buy_is_Tplus1=True)
    prefix[day].append(key);scprefix[day,meta[f['sid']]['sector_id']].append(key)
 assert bound==len(rows)
 first={}
 for x in sorted(rows,key=lambda r:(r['window'],r['OPEN'],r['funding_stream_index'])):
  ep=x['original_intent']['epoch'];assert ep is not None
  key='|'.join([x['window'],x['sid'],json.dumps(ep,separators=(',',':'))])
  if key not in first:first[key]=dict(group=key,window=x['window'],sid=x['sid'],source_I_epoch=ep,first_event_key=x['key'],raw_event_keys=[])
  first[key]['raw_event_keys'].append(x['key'])
 firstkeys={r['first_event_key']for r in first.values()}
 for x in rows:x['is_first_sector_reject_in_original_source_I_epoch']=x['key']in firstkeys
 writer('CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz',rows);save('ACTUAL_SAMEOPEN_RESERVE_COMMITMENTS.json',orders);save('FIRST_SOURCE_I_EPOCH_REJECT_INDEX.json',list(first.values()))
 save('PREFIX_CONTEXT_SUMMARY.json',dict(complete=True,raw_events=len(rows),first_source_I_epoch_events=len(first),first_by_window=dict(Counter(x['window']for x in first.values())),actual_reserved_orders=len(orders),counts={w:dict(c)for w,c in counts.items()},seconds=time.monotonic()-t,limit_seconds=100,new_marks=0,new_accounts=0,new_risk_states=0,scope='Only links original log commitments; post-funding fills are retrospective facts, not known/available capacity at rejected candidate time'))
 save('PREFIX_CONTEXT_SOURCE_SHA256.json',SOURCES);print('PREFIX_COMPLETE',bound,len(first),len(orders),time.monotonic()-t,flush=True)
if __name__=='__main__':main()
