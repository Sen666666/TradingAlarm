"""Read-only funding decomposition and necessary bounds. No new allocation."""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
from collections import Counter,defaultdict
import copy,csv,gzip,hashlib,itertools,json,sys,time
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1];OLD=ROOT/'reentry_v1/funding_agent';PR=OLD/'private_projection'
sys.path.insert(0,str(PR));from rebuild_off import hydrate
from run_confirmed_min_first import load_intents
import component as P
J=P.J;LR=J.LR
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
SOURCES={};META={}
def source(p):p=Path(p);SOURCES[str(p)]=sha(p);return read(p)
def key(i):return P.B.bid(i)
def active(b):return [o for o in b.orders.values()if o.qty>0 and o.status in['open','cancel_pending']]
def move_recorded_lots(b,events):
 for event in events:
  if event['result']:
   moved=set(event['moved'])
   for lot in b.lots:
    if lot.batch in moved:lot.pool='confirmed'
  b.sectors[event['sector']].status=event['new_status']
def inventory(b):
 by={}
 for lot in b.lots:
  r=by.setdefault(lot.stock,dict(sid=lot.stock,name=META.get(lot.stock,{}).get('name'),sector=lot.sector,quantity=0,marked_capital=0.,nominal_stop_risk=0.,lots=[]))
  r['quantity']+=lot.qty;r['marked_capital']+=lot.qty*b.prices[lot.stock];r['nominal_stop_risk']+=lot.qty*max(0,b.prices[lot.stock]-lot.floor);r['lots'].append(lot)
 return sorted(by.values(),key=lambda x:-x['marked_capital'])
def frame(b,available,commitment):
 inv=inventory(b);orders=active(b);reserve=b.resources()[2];ten=b.decision_nav*D('.1')
 usable=min(float(available-ten),b.cash-reserve);free=min(float(available),b.cash-reserve)
 return dict(clock_scope=commitment,budget_cash_before_reservations=b.cash,available_after_submitted_or_planned_orders=available,
  reserved_cash_including_Fq=reserve,original_cash10_buffer=ten,original_cash10_basis='last decision NAV, not current budget NAV',
  discretionary_space_with_cash10=usable,free_cash_after_hard_responsibilities_optimistic_zero_extra_buffer=free,
  marked_stock_inventory=sum(x['marked_capital']for x in inv),inventory_nominal_stop_risk=sum(x['nominal_stop_risk']for x in inv),
  receivable_equity_not_available_cash=b.receivable_equity,budget_nav=b.nav,decision_nav=b.decision_nav,
  all_inventory=inv,inventory_is_not_cash=True,live_or_cancel_pending_orders=orders)
def predicate_sources():
 begin=P.NEW_ROUTE.index('   pc,pr,_=');end=P.NEW_ROUTE.index('   q=LR.maximum_quantity')
 base='def fixed_predicate(a,i,x,at,pool):\n b=a.budget;sid=i["sid"];sector=a.sector_by_sid[sid];s=b.sectors[sector];p=float(x["price"]);floor=float(x["floor"])\n'+''.join(line[2:]+'\n'for line in P.NEW_ROUTE[begin:end].splitlines())+' return allowed\n'
 assert base.count("a.available-a.current_nav*D('.1')")==1
 zero=base.replace("a.available-a.current_nav*D('.1')",'a.available')
 result=[]
 for name,src in [('original_cash10_fixed_predicate.py',base),('optimistic_zero_extra_buffer_fixed_predicate.py',zero)]:
  (OUT/name).write_text(src);env=dict(J.__dict__);exec(compile(src,str(OUT/name),'exec'),env);result.append(env['fixed_predicate'])
 return result

def main():
 global META
 started=time.monotonic();s0raw={k[:10]:v for k,v in source(OLD/'PREOPEN_EXACT_STATE.json').items()}
 native_pre={(r['at'][:10],r['intent']['sid']):r for r in source(OLD/'PRE_CANDIDATE_EXACT_STATE.json')}
 all16=source(OLD/'ALL16_RECEIPTS_WITH_REAL_RESOURCES.json');original={ (r['sid'],r['signal_day']):r for r in all16 }
 on_focus=source(PR/'ON_ALL16_FOCUS.json');focus=[r for r in on_focus if r['status']=='still_rejected'];assert len(focus)==14
 contexts={r['comparison']['key']:r['original_path_reference']for r in source(PR/'ON_ORIGINAL50_ORDER_OPPORTUNITY_REFERENCES.json')}
 root_context={(r['OPEN'],r['sid']):r for r in source(ROOT/'reentry_v1/OLD50_ORIGINAL_OUTCOME_CONTEXT.json')['rows']}
 META=source(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json'))['security_metadata']
 bookpath=P.O/'runs/2025_26/pair/B.json.gz';SOURCES[str(bookpath)]=sha(bookpath)
 with gzip.open(bookpath,'rt')as f:book=json.load(f)
 reserves={x['budget_order']:x for x in book['journal']if x['kind']=='real_reserve'}
 baseline={};mother=[];S0=[]
 for day in sorted(s0raw):
  pp=PR/('PREVIEWS_'+day+'.json');SOURCES[str(pp)]=sha(pp);xs=load_intents(pp);by={key(i):i for i in xs};order={key(i):n for n,i in enumerate(sorted(xs,key=P.B.key))}
  off=source(PR/('OFF_'+day+'.json'));on=source(PR/('ON_'+day+'.json'));b=hydrate(s0raw[day]['state'])
  assert P.digest([b.view(),[P.B.intent_view(i)for i in xs]])==off['input_sha256']
  baseline[day]=dict(xs=xs,by=by,order=order,off=off,on=on,state=b)
  f=frame(b,b.available_exact,'actual original S0 after protection exits/settlement, before first new admission')
  assert not active(b);S0.append(dict(opening=day,frame=f,source_intents=len(xs),original_old_live_or_cancel_pending_orders=0,
   new_same_OPEN_orders_not_submitted_yet_at_this_anchor=True))
  for i in xs:mother.append(dict(opening=day,key=key(i),sid=i['sid'],role=i['role'],rank=i['rank'],H1_score=i.get('score'),H1_rank=i.get('original_H1_rank'),
   PVR_score=i.get('PVR_score'),CP1_id=i.get('CP1_id'),preview_failure=i['_preview_failure'],preview_minimum=i['_preview']['minq']if i['_preview']else None))
 assert len(mother)==4172 and len(baseline)==13
 original_pred,zero_pred=predicate_sources();records=[];frames={}
 def order_detail(o,by,kind,day):
  i=by[o.oid];x=i['_preview'];q=o.qty;fees=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value)
  return dict(budget_order=o.oid,sid=o.stock,sector=o.sector,pool=o.pool,role=o.role,quantity=q,status=o.status,commitment=kind,
   rank=i['rank'],original_H1_rank=i.get('original_H1_rank'),H1_score=i.get('score'),PVR_score=i.get('PVR_score'),PVR_ready=i.get('PVR_ready'),
   CP1_id=i.get('CP1_id'),canonical_CP1_trace=i.get('CP1_trace'),floor_continuous=i['floor'],floor_raw=x['floor'],known_open=x['known_open'],planned_price=x['price'],
   gross=D(q)*x['price'],reserved_fee=fees,nominal_stop_risk=q*max(0.,float(x['price']-x['floor'])),
   protection_risk_including_fees=LR.protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value),original_core_risk_budget=i.get('risk_budget'),
   historical_original_native_submission_same_key=reserves.get(o.oid),current_anchor_has_native_submitted_order=kind=='OFF_native_already_submitted_same_OPEN',
   same_key_original_actual_path=contexts.get(o.oid),
   existing_root_original_lifecycle_context=root_context.get((day,o.stock))if o.oid in contexts else None,
   outcome_is_hindsight_evaluation_only_not_decision_input=True,ON_plan_is_not_a_cancellable_real_order=kind=='ON_unsubmitted_private_first_pass_plan')
 for target in focus:
  day=target['opening'];sid=target['sid'];data=baseline[day];i=data['by'][target['comparison']['key']];x=i['_preview'];at=i['clock'].earliest_execution_at;k=key(i)
  src=original[(sid,target['signal_day'])];record=dict(sid=sid,name=target['name'],signal_day=target['signal_day'],opening=day,key=k,
   target=dict(rank=i['rank'],H1_score=i.get('score'),H1_rank=i.get('original_H1_rank'),PVR_score=i.get('PVR_score'),CP1_id=i['CP1_id'],CP1_trace=i['CP1_trace'],
    floor_continuous=i['floor'],floor_raw=x['floor'],known_open=x['known_open'],planned_price=x['price'],dated_rule=x['rule'],minimum=x['minq'],
    minimum_gross=D(x['minq'])*x['price'],minimum_buy_fee=LR.fees(x['minq'],x['price'],x['schedule'],'buy',i['quote'].par_value),
    minimum_nominal_stop_risk=D(x['minq'])*(x['price']-x['floor']),original_held_quantity=0),
   blocked_stock_previous_original_closed_layers=[dict(layer=l['id'],opened=l['opened'],closed=l['closed'],initial_qty=l['initial_qty'],exit_reason=l['reason'],
    whole_original_closed_net_cny=D(l['cash'])+D(l['dividend']),reference_only_not_future_signal_profit=True)
    for l in book['layers']if l['sid']==sid and l['closed']is not None and J.M.N.iso(l['closed'].replace(' ','T'))<=at])
  # OFF is native pre-candidate data. Its earlier orders really were submitted.
  offb=hydrate(native_pre[(day,sid)]['state']);move_recorded_lots(offb,src['exact_open_responsibility']['migration_observation'])
  assert P.AccountView(offb).quantity(sid)==0
  # ON is only a reconstruction of the saved first-pass prefix, not a new plan.
  onb=copy.deepcopy(data['state']);prefix=[o for o in data['on']['first_pass']if data['order'][o['key']]<data['order'][k]]
  prior_events=[m for m in data['on']['migrations']if data['order'][m['candidate']]<data['order'][k]or(m['candidate']==k and m['phase']=='evaluation')]
  move_recorded_lots(onb,prior_events);paid=D(0)
  for o in prefix:
   j=data['by'][o['key']];xx=j['_preview'];sector=onb.sector_by_sid[o['sid']];s=onb.sectors[sector]
   onb.orders[o['key']]=P.MOD.Order(o['key'],o['sid'],sector,s.episode,o['pool'],o['quantity'],float(D(o['price'])),float(D(o['floor'])),float(D(o['fee'])/D(o['quantity'])),
    role=o['role'],created_bar=J.ordinal(j['clock'].decision_at.date()),expiry_bar=J.ordinal(at.date()),attempt=s.attempt)
   onb.prices.setdefault(o['sid'],float(D(o['price'])));paid+=D(o['gross'])+D(o['fee'])
  onb.available_exact=data['state'].available_exact-paid
  for label,b in [('OFF_native',offb),('ON_private_first_pass',onb)]:
   a=P.AccountView(b);assert a.quantity(sid)==0;f=frame(b,a.available,'native submitted pre-candidate'if label=='OFF_native'else'unsubmitted saved ON first-pass prefix')
   f['listed_order_status_is_actual_native_commitment']=label=='OFF_native'
   assert abs(b.cash-b.resources()[2]-float(a.available))<1e-6
   assert abs(b.nav-b.cash-f['marked_stock_inventory']-b.receivable_equity)<1e-6
   details=[order_detail(o,data['by'],'OFF_native_already_submitted_same_OPEN'if label=='OFF_native'else'ON_unsubmitted_private_first_pass_plan',day)for o in active(b)]
   minq=x['minq'];fee=LR.fees(minq,x['price'],x['schedule'],'buy',i['quote'].par_value);need=D(minq)*x['price']+fee;routes=[]
   for pool in ['probe','confirmed']:
    ten=original_pred(a,i,x,at,pool)(minq,True);zero=zero_pred(a,i,x,at,pool)(minq,True)
    routes.append(dict(pool=pool,original_cash10_failures_code_order=ten,optimistic_zero_extra_buffer_failures_code_order=zero,
     non_cash_gates_unmodified=True))
   union=','.join(sorted({c for r in routes for c in r['original_cash10_failures_code_order']}))
   expected=src['exact_open_responsibility']['native_result']if label=='OFF_native'else target['ON_reason'];assert union==expected,(label,day,sid,union,expected)
   d=dict(frame=f,prior_orders=details,minimum_cash_including_buy_fee=need,
    cash10_minimum_shortfall=max(0.,float(need)-f['discretionary_space_with_cash10']),
    hard_cash_shortfall_even_after_optimistic_buffer_removal=max(0.,float(need)-f['free_cash_after_hard_responsibilities_optimistic_zero_extra_buffer']),
    minimum_cash_buffer_reduction_necessary=max(0.,float(need)-f['discretionary_space_with_cash10']),
    routes=routes,individual_minimum_only_not_shared_allocation=True,
    individual_optimistic_cash_only_reachable=any(not r['optimistic_zero_extra_buffer_failures_code_order']for r in routes))
   if label=='ON_private_first_pass':assert abs(f['discretionary_space_with_cash10']-target['confirmed_first_pass_state']['spendable_above_original_reserve'])<1e-6
   record[label]=d;frames[(label,day,sid)]=(b,a,i)
  records.append(record)
 save('ALL14_FUNDING_DECOMPOSITION.json',records);save('ALL13_S0_OBLIGATIONS.json',S0);save('ALL4172_MOTHER_INDEX.json',mother)
 csvrows=[]
 for r in records:
  d=dict(name=r['name'],signal_day=r['signal_day'],opening=r['opening'],rank=r['target']['rank'],H1_rank=r['target']['H1_rank'],PVR_score=r['target']['PVR_score'],
   minimum_cash=r['target']['minimum_gross']+r['target']['minimum_buy_fee'])
  for label,prefix in [('OFF_native','OFF'),('ON_private_first_pass','ON')]:
   v=r[label];f=v['frame'];d.update({prefix+'_stock_inventory':f['marked_stock_inventory'],prefix+'_reserved_cash':f['reserved_cash_including_Fq'],
    prefix+'_available':f['available_after_submitted_or_planned_orders'],prefix+'_cash10_buffer':f['original_cash10_buffer'],prefix+'_cash10_space':f['discretionary_space_with_cash10'],
    prefix+'_qmin_cash_gap':v['cash10_minimum_shortfall'],prefix+'_zero_extra_buffer_confirmed_rejects':','.join(v['routes'][1]['optimistic_zero_extra_buffer_failures_code_order']),
    prefix+'_zero_extra_buffer_individual_necessary':v['individual_optimistic_cash_only_reachable']})
  csvrows.append(d)
 with(OUT/'ALL14_FUNDING_DECOMPOSITION.csv').open('w')as f:
  writer=csv.DictWriter(f,fieldnames=list(csvrows[0]));writer.writeheader();writer.writerows(csvrows)
 # At each OPEN, multiple focus minima must share the same cash and sector risk.
 groups=[]
 for label in ['OFF_native','ON_private_first_pass']:
  for day in sorted({x['opening']for x in records}):
   rs=sorted([x for x in records if x['opening']==day],key=lambda r:baseline[day]['order'][r['key']]);b,a,first=frames[(label,day,rs[0]['sid'])]
   prefixes=[{o['budget_order']: (o['quantity'],o['pool'])for o in r[label]['prior_orders']}for r in rs]
   assert all(p==prefixes[0]for p in prefixes),'joint bound needs an explicit intervening commitment ledger'
   outcomes=[]
   for size in range(len(rs)+1):
    for subset in itertools.combinations(rs,size):
     need=sum((r[label]['minimum_cash_including_buy_fee']for r in subset),D(0));pending_fees=sum(o.qty*o.fee_per_share for o in active(b));fees=sum(float(r['target']['minimum_buy_fee'])for r in subset)
     nav=b.nav-pending_fees-fees;fail=[]
     if float(need)>min(float(a.available),b.cash-b.resources()[2])+1e-9:fail.append('shared_hard_cash')
     for sector in {b.sector_by_sid[r['sid']]for r in subset}:
      selected=[r for r in subset if b.sector_by_sid[r['sid']]==sector];sc,sr,_=b.resources(sector=sector);frac=(.02,.1,.2)[b.sectors[sector].level]
      if sc+sum(float(r['target']['minimum_gross'])for r in selected)>frac*nav+1e-9:fail.append('shared_confirmed_sector_capital')
      if sr+sum(float(r['target']['minimum_nominal_stop_risk'])for r in selected)>.01*nav+1e-9:fail.append('shared_sector_risk')
     outcomes.append(dict(targets=[r['sid']for r in subset],count=size,minimum_cash=need,necessary_confirmed_bundle_failures=fail))
   groups.append(dict(basis=label,opening=day,focus_targets=[r['sid']for r in rs],same_frozen_prefix_proved=True,hard_cash_available=min(float(a.available),b.cash-b.resources()[2]),
    subsets=outcomes,maximum_count_meeting_joint_necessary_confirmed_conditions=max(x['count']for x in outcomes if not x['necessary_confirmed_bundle_failures']),
    no_other_candidate_removed_or_resource_order_changed=True,not_full4172_shared_projection=True,not_guaranteed_executable=True))
 save('SHARED_FOCUS_MINIMUM_NECESSARY_BOUNDS.json',groups)
 summary=dict(remaining_focus=14,remaining_focus_OPENs=12,complete_mother_OPENs=13,complete_intents=4172,
  all13_S0_carried_real_live_or_cancel_pending_orders=0,
  individual_zero_extra_buffer_minimum_necessary_counts={label:sum(r[label]['individual_optimistic_cash_only_reachable']for r in records)for label in ['OFF_native','ON_private_first_pass']},
  shared_focus_confirmed_minimum_necessary_max_counts={label:sum(g['maximum_count_meeting_joint_necessary_confirmed_conditions']for g in groups if g['basis']==label)for label in ['OFF_native','ON_private_first_pass']},
  individual_bounds_not_additive=True,no_submitted_order_cancelled=True,no_inventory_liquidation=True,no_dynamic_reserve_parameter_selected=True,
  zero_extra_buffer_is_only_an_optimistic_bound_after_existing_available_balance_obligations=True,full4172_cash_floor_projection_started=False,
  seconds=time.monotonic()-started,new_accounts=0,new_restores=0,new_policy_paths=0)
 save('SUMMARY.json',summary);SOURCES.update(P.source_hashes());SOURCES[str(Path(__file__))]=sha(__file__);save('SOURCE_SHA256.json',SOURCES)
 assert all(sha(p)==h for p,h in SOURCES.items());print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
