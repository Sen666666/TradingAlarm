"""Compare saved independent OPEN projections; no policy execution or new PnL."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import gzip,hashlib,json
OUT=Path(__file__).resolve().parent;FUND=OUT.parent
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/runs/2025_26/pair')
with gzip.open(root/'B.json.gz','rt')as f:book=json.load(f)
rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
meta=rules['security_metadata'];s0={k[:10]:v['state']for k,v in read(FUND/'PREOPEN_EXACT_STATE.json').items()}
focus=read(FUND/'ALL16_RECEIPTS_WITH_REAL_RESOURCES.json');allc=[];old50=[];batches=[];targets=[];allorders=[]
def sid_info(sid):return dict(name=meta[sid]['name'],industry=meta[sid]['industry'],sector=meta[sid]['sector_id'])
def focus_confirmed_resources(f,xs,on,day):
 s=s0[day];key='B|'+f['signal_day']+'T15:10:00+08:00|'+f['sid']+'|mobile'
 ordered=sorted(xs,key=lambda i:(i['rank'],i['role']!='core'));positions={'B|'+i['clock']['decision_at']+'|'+i['sid']+'|'+i['role']:n for n,i in enumerate(ordered)}
 prior=[o for o in on['first_pass']if positions[o['key']]<positions[key]];sector=s['sector_by_sid'][f['sid']]
 active=[o for o in s['orders'].values()if o['qty']>0 and o['status']in['open','cancel_pending']]
 lots=[l for l in s['lots']if l['sector']==sector];old=[o for o in active if o['sector']==sector];same=[o for o in prior if s['sector_by_sid'][o['sid']]==sector]
 paid=sum((D(o['gross'])+D(o['fee'])for o in prior),D(0));available=D(s['available_exact'])-paid;reserve=sum(o['qty']*(o['limit']+o['fee_per_share'])for o in active)+float(paid)
 spend=min(float(available-D(s['decision_nav'])*D('.1')),s['cash']-reserve)
 ref=f['reference'];fee=float(D(ref['open_min_buy_fee']));cap=float(D(ref['min_quantity'])*D(ref['open_execution_price']));risk=float(D(ref['open_min_stop_risk']))
 pending_fees=sum(o['qty']*o['fee_per_share']for o in active)+sum(float(D(o['fee']))for o in prior);nav=s['nav']-pending_fees-fee
 sc=sum(l['qty']*s['prices'][l['stock']]for l in lots)+sum(o['qty']*o['limit']for o in old)+sum(float(D(o['gross']))for o in same)
 sr=sum(l['qty']*max(0,s['prices'][l['stock']]-l['floor'])for l in lots)+sum(o['qty']*max(0,o['limit']-o['floor'])for o in old)+sum(o['quantity']*max(0,float(D(o['price'])-D(o['floor'])))for o in same)
 frac=(.02,.1,.2)[s['sectors'][sector]['level']];fail=[]
 if cap+fee>spend+1e-9:fail.append('cash_or_original_reserve')
 if sc+cap>frac*nav+1e-9:fail.append('sector_capital')
 if sr+risk>.01*nav+1e-9:fail.append('sector_risk')
 if cap>.1*float(D(s['decision_nav']))+1e-9:fail.append('stock_capital')
 migration=[m for m in on['migrations']if m['candidate']==key and m['phase']=='evaluation'];assert len(migration)==1 and migration[0]['result']is True
 return dict(method='arithmetic of saved S0 plus original-sequence ON first_pass prefix; no new route/projection',
  migration=migration[0],available_pools=['probe','confirmed'],prior_first_pass_orders=len(prior),prior_first_pass_paid_cny=str(paid),
  available_cny=str(available),spendable_above_original_reserve=spend,minimum_cash=cap+fee,sector_capital=sc,sector_risk=sr,
  sector_capital_headroom=frac*nav-sc,sector_risk_headroom=.01*nav-sr,minimum_nominal_stop_risk=risk,confirmed_minimum_failures_code_order=fail)
def original_paths(order):
 layers=[]
 for layer in book['layers']:
  m=book['metadata'][str(layer['id'])]
  if m.get('budget_order')!=order['key']:continue
  cash=D(layer['cash']);div=D(layer['dividend']);closed=layer['qty']==0
  layers.append(dict(layer=layer['id'],opened=layer['opened'],closed=layer['closed'],exit_reason=layer['reason'],initial_qty=layer['initial_qty'],ending_qty=layer['qty'],
   original_cash_balance_cny=str(cash),original_dividend_cny=str(div),original_closed_net_cny=str(cash+div)if closed else None,
   original_open_layer_cash_plus_dividend_not_profit=str(cash+div)if not closed else None,original_terminal_mark_not_loaded=True))
 fills=[x for x in book['journal']if x['kind']=='real_buy_fill'and x['budget_order']==order['key']]
 original_reserves=[x for x in book['journal']if x['kind']=='real_reserve'and x['budget_order']==order['key']]
 native_ids={x['order']for x in original_reserves}
 expiry=[x for x in book['audit']if x['kind']in['buy_day_expiry','release_buy']and x.get('order_id')in native_ids]
 return dict(original_order=order,actual_original_buy_fills=fills,layers=layers,actual_original_fill_occurred=bool(fills),
  original_fill_status='no_actual_buy_fill'if not fills else'original_buy_filled_all_layers_closed'if all(x['ending_qty']==0 for x in layers)else'original_buy_filled_with_remaining_position',
  original_expiry_and_released_reservation=expiry,
  all_original_layers_closed=bool(layers)and all(x['ending_qty']==0 for x in layers),
  whole_original_closed_layers_net_reference_cny=str(sum((D(x['original_closed_net_cny'])for x in layers if x['original_closed_net_cny']is not None),D(0))),
  old_full_path_reference_only=True,not_new_policy_profit_or_opportunity_loss=True,no_proportional_PnL_imputation=True)
for pp in sorted(OUT.glob('PREVIEWS_2026-*.json')):
 day=pp.stem[9:];xs=read(pp);off=read(OUT/('OFF_'+day+'.json'));on=read(OUT/('ON_'+day+'.json'));a={x['key']:x for x in off['orders']};b={x['key']:x for x in on['orders']};reject={x['key']:x['reason']for x in on['rejected']}
 before_by={(x['sid'],x['role']):x for x in off['attempts']};hold=Counter()
 for lot in s0[day]['lots']:hold[lot['stock']]+=lot['qty']
 def entry_kind(sid):
  if hold[sid]>0:return 'existing_original_hold_ADD'
  if any(t['security_id']==sid and t['side']=='buy'and t['at'][:10]<day for t in book['trades']):return 'flat_actual_original_reentry'
  return 'first_original_account_participation'
 for i in xs:
  sid=i['sid'];key='B|'+i['clock']['decision_at']+'|'+sid+'|'+i['role'];old=a.get(key);new=b.get(key);raw=before_by[(sid,i['role'])]
  status='not_reserved_both'
  if old is None and new is not None:status='added_intent'
  elif old is not None and new is None:status='lost_original_intent'
  elif old and new:
   status='shrunk_original_intent'if new['quantity']<old['quantity']else'increased_original_intent'if new['quantity']>old['quantity']else'unchanged_quantity'
  row=dict(opening=day,key=key,sid=sid,**sid_info(sid),role=i['role'],rank=i['rank'],original_held_qty=hold[sid],entry_kind=entry_kind(sid),
   original_frozen_cap=i['cap'],original_frozen_budget=i['budget'],CP1_id=i['CP1_id'],status=status,
   OFF_order=old,ON_order=new,OFF_result=raw.get('result','original_skip'),ON_result='reserved'if new else reject.get(key),
   quantity_delta=(new['quantity']if new else 0)-(old['quantity']if old else 0),
   gross_delta=str((D(new['gross'])if new else D(0))-(D(old['gross'])if old else D(0))),
   fee_delta=str((D(new['fee'])if new else D(0))-(D(old['fee'])if old else D(0))),
   pool_changed=bool(old and new and old['pool']!=new['pool']))
  allc.append(row)
  if old:old50.append(dict(comparison=row,original_path_reference=original_paths(old)))
 for order in on['orders']:allorders.append(dict(opening=day,**order,**sid_info(order['sid']),entry_kind=entry_kind(order['sid'])))
 common=set(a)&set(b);batches.append(dict(opening=day,intents=len(xs),OFF_orders=len(a),ON_orders=len(b),added=len(set(b)-set(a)),lost=len(set(a)-set(b)),
  shrunk=sum(b[k]['quantity']<a[k]['quantity']for k in common),increased=sum(b[k]['quantity']>a[k]['quantity']for k in common),pool_changes=sum(b[k]['pool']!=a[k]['pool']for k in common),
  OFF_gross=str(sum((D(o['gross'])for o in a.values()),D(0))),ON_gross=str(sum((D(o['gross'])for o in b.values()),D(0))),OFF_fees=off['fees'],ON_fees=on['fees'],
  OFF_nominal_risk=off['nominal_risk'],ON_nominal_risk=on['nominal_risk'],OFF_available=off['available'],ON_available=on['available'],
  gross_fee_and_risk_are_independent_OPEN_reservations_not_actual_financial_paths=True))
 for f in focus:
  if f['next_open']!=day:continue
  if f['original_frozen_intent']is None:
   targets.append(dict(sid=f['sid'],name=f['name'],signal_day=f['signal_day'],opening=day,status='no_original_intent_still_not_planned',original_close_sizing=f['close_no_plan'],ON_order=None));continue
  key='B|'+f['signal_day']+'T15:10:00+08:00|'+f['sid']+'|mobile';r=next(x for x in allc if x['key']==key)
  targets.append(dict(sid=f['sid'],name=f['name'],signal_day=f['signal_day'],opening=day,status='newly_reserved_private'if key in b else'still_rejected',ON_order=b.get(key),ON_reason=reject.get(key),
   confirmed_first_pass_state=focus_confirmed_resources(f,xs,on,day),comparison=r))
save('ON_ALL4172_CANDIDATE_COMPARISONS.json',allc);save('ON_ORIGINAL50_ORDER_OPPORTUNITY_REFERENCES.json',old50);save('ON_ALL161_ORDERS.json',allorders);save('ON_ALL16_FOCUS.json',targets);save('ON_BATCH_COMPARISON.json',batches)
added=[x for x in allc if x['status']=='added_intent'];lost=[x for x in allc if x['status']=='lost_original_intent'];shrunk=[x for x in allc if x['status']=='shrunk_original_intent']
groups={}
for name,rs in [('added',added),('lost',lost),('shrunk',shrunk)]:
 groups[name]=dict(intents=len(rs),unique_stocks=len({x['sid']for x in rs}),roles=dict(Counter(x['role']for x in rs)),industries=dict(Counter(x['industry']for x in rs)),
  entry_kind=dict(Counter(x['entry_kind']for x in rs)),OFF_pools=dict(Counter(x['OFF_order']['pool']for x in rs if x['OFF_order'])),ON_pools=dict(Counter(x['ON_order']['pool']for x in rs if x['ON_order'])))
summary=dict(independent_OPENs=13,intents=4172,OFF_orders=50,ON_orders=len(allorders),ON_unique_stocks=len({x['sid']for x in allorders}),groups=groups,
 original_focus_OPEN_rejects=15,focus_newly_reserved=sum(x['status']=='newly_reserved_private'for x in targets),focus_still_rejected=sum(x['status']=='still_rejected'for x in targets),focus_no_intent=1,
 OFF_aggregate_gross_independent_OPENS=str(sum((D(x['OFF_gross'])for x in batches),D(0))),ON_aggregate_gross_independent_OPENS=str(sum((D(x['ON_gross'])for x in batches),D(0))),
 OFF_aggregate_buy_fees_independent_OPENS=str(sum((D(x['OFF_fees'])for x in batches),D(0))),ON_aggregate_buy_fees_independent_OPENS=str(sum((D(x['ON_fees'])for x in batches),D(0))),
 OFF_new_reserved_nominal_stop_risk_independent_OPENs=str(sum((D(x['comparison']['OFF_order']['quantity'])*max(D(0),D(x['comparison']['OFF_order']['price'])-D(x['comparison']['OFF_order']['floor']))for x in old50),D(0))),
 ON_new_reserved_nominal_stop_risk_independent_OPENs=str(sum((D(x['quantity'])*max(D(0),D(x['price'])-D(x['floor']))for x in allorders),D(0))),
 original50_fill_status=dict(Counter(x['original_path_reference']['original_fill_status']for x in old50)),
 all_fee_comparisons_are_reserved_Fq_not_actual_paid_commissions=True,
 lost_original_orders=[dict(sid=x['sid'],name=x['name'],opening=x['opening'],role=x['role'],pool=x['OFF_order']['pool'],quantity=x['OFF_order']['quantity'],ON_reason=x['ON_result'])for x in lost],
 independent_snapshots_do_not_carry_new_positions_forward=True,not_a_continuous_account=True,no_new_PnL=True,no_proportional_old_PnL_imputation=True)
save('ON_SUMMARY.json',summary)
sources={str(root/'B.json.gz'):sha(root/'B.json.gz'),str(Path(__file__)):sha(__file__)}
freeze=read(OUT/'INPUT_SOURCES_SHA256.json');code={p:h for p,h in freeze.items()if p.endswith('.py')}
assert all(sha(p)==h for p,h in code.items());save('ON_POST_SOURCE_AUDIT.json',dict(passed=True,original_code_hashes=code,analysis_sources=sources,projection_used_no_market_reads=True))
print(json.dumps(summary,ensure_ascii=False,indent=2))
