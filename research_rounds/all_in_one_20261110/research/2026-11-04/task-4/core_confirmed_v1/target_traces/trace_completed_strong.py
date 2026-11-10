"""Read complete native outputs after explicit root DONE; no engine imports."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import argparse,gzip,hashlib,json,time,traceback
O=Path(__file__).resolve().parent;ROOT=O.parent.parent;SHA={}
def bind(p):
 p=Path(p)
 if str(p)not in SHA:SHA[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return p
def read(p):return json.loads(bind(p).read_text())
def stream(p):
 with gzip.open(bind(p),'rt')as f:
  for line in f:yield json.loads(line)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def epoch(x):return tuple(x)if x is not None else None
def budget_key(day,sid,role):return 'B|'+day+'T15:10:00+08:00|'+sid+'|'+role
def main(run):
 started=time.monotonic();run=Path(run).resolve()
 # This is the first new-run read. Do not open any economic file before DONE.
 done=read(run/'DONE.json');assert done['completed']is True,'Incomplete new economic run is forbidden'
 fixed=read(O/'FIXED_TARGETS.json');targets=fixed['targets25'];semis=fixed['semiconductor126'];ids=set(semis)
 for p,h in read(O/'PREPARATION_SOURCE_SHA256.json').items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,('prepared source changed',p)
 pair=run/'pair';book=read_gzip_book(pair/'B.json.gz');daily={r['at'][:10]:r for r in stream(pair/'daily.jsonl.gz')};dec={r['at'][:10]:r for r in book['decisions']}
 wanted={(t['signal_day'],t['sid'])for t in targets};ops={}
 for r in stream(pair/'opportunities.jsonl.gz'):
  if(r['day'],r['sid'])in wanted:ops[r['day'],r['sid']]=r
 assert len(ops)==len(wanted)
 fund=defaultdict(list);by_open=defaultdict(list);fund_index={}
 for index,r in enumerate(stream(pair/'funding.jsonl.gz')):
  fund[r['at'][:10],r['sid']].append(dict(r,stream_index=index))
  if '09:30:00'in r['at']:by_open[r['at'][:10]].append(dict(r,stream_index=index));fund_index[r['at'][:10],r['sid'],r['role']]=index
 logs=defaultdict(list)
 for r in stream(pair/'core-confirmed.jsonl.gz'):logs[r['signal_day'],r['sid']].append(r)
 proofs=defaultdict(list)
 for r in stream(pair/'core-proof.jsonl.gz'):proofs[r['signal_day'],r['sid']].append(r)
 layers={int(r['id']):r for r in book['layers']};core_fills=defaultdict(list);by_budget=defaultdict(list)
 for j in book['journal']:
  if j['kind']=='real_buy_fill':
   by_budget[j['budget_order']].append(j)
   if j['role']=='core':core_fills[j['sid']].append(j)
 reserve_audit={a['order_id']:a for a in book['audit']if a['kind']=='reserve'}
 reservations={};reserve_by_open=defaultdict(list)
 for j in book['journal']:
  if j['kind']!='real_reserve':continue
  od=j['at'][:10];idx=fund_index.get((od,j['sid'],j['role']));assert idx is not None
  a=reserve_audit[j['order']];bo=book['budget']['orders'][j['budget_order']]
  r=dict(j,funding_stream_index=idx,sector=bo['sector'],episode=bo['episode'],attempt=bo['attempt'],gross=a['gross_budget_cny'],buy_fee=a['fee_reserved_cny'],actual_fills=by_budget[j['budget_order']],same_OPEN_new_Tplus1=True)
  reservations[j['budget_order']]=r;reserve_by_open[od].append(r)
 for od in reserve_by_open:reserve_by_open[od].sort(key=lambda x:x['funding_stream_index'])
 traces=[]
 for t in targets:
  sid,day,od=t['sid'],t['signal_day'],t['OPEN'];op=ops[day,sid];ds=daily[day];d=dec[day];ep=epoch(t['source_I_epoch']);cp=t['canonical_receipt_id']
  current_layers=[l for l in ds['layers']if l['sid']==sid];same_core=[l for l in current_layers if l['kind']=='core'and epoch(l.get('epoch'))==ep]
  prior_core=[j for j in core_fills[sid]if j['at']<=day+' 23:59:59'and epoch(layers[int(j['layer'])].get('epoch'))==ep]
  new_intents=[i for i in d['intents']if i['sid']==sid];core_intent=next((i for i in new_intents if i['role']=='core'),None)
  signal_rows=[r for r in fund[day,sid]if '15:10:00'in r['at']]
  opening_rows=[r for r in fund[od,sid]if '09:30:00'in r['at']];core_row=next((r for r in opening_rows if r['role']=='core'),None)
  core_key=budget_key(day,sid,'core');mobile_key=budget_key(day,sid,'mobile');reserves={role:reservations.get(k)for role,k in [('core',core_key),('mobile',mobile_key)]}
  exact_signal_fills=[]
  for role,k in [('core',core_key),('mobile',mobile_key)]:
   for j in by_budget[k]:
    ll=layers[int(j['layer'])];same_epoch=epoch(ll.get('epoch'))==ep;receipt_exact=(j.get('CP1_id')==cp)
    # Native untyped probe CORE does not consume CP; source-I+same signal still
    # identifies it. Never use an old layer ID to locate the new one.
    assert same_epoch,(t['target_id'],'new same-signal source-I mismatch')
    if role=='mobile'or j.get('pool')=='confirmed':assert receipt_exact
    exact_signal_fills.append(dict(j,source_I_epoch=ll.get('epoch'),matches_fixed_source_I=True,receipt_exact=receipt_exact))
  if same_core:branch='earlier_same_I_CORE_present_at_signal'
  elif op['held']:branch='held_without_same_I_CORE_blocks_new_CORE'
  elif not d['on']:branch='new_ACT_paused'
  elif prior_core:branch='same_I_CORE_epoch_consumed_after_prior_fill'
  elif op['barriers']:branch='new_signal_barriers'
  elif op['core_Q']is not True:branch='new_CORE_Q_not_true'
  elif core_intent is None:branch='new_CORE_size_or_missing_intent'
  elif reserves['core']is not None:branch='new_CORE_reserved_and_filled'if by_budget[core_key]else'new_CORE_reserved_but_unfilled'
  elif core_row:branch='new_CORE_OPEN_rejected'
  else:branch='new_CORE_intent_no_OPEN_record_unknown'
  context_row=core_row or next((r for r in opening_rows if r['role']=='mobile'),None)
  prefix=[r for r in reserve_by_open[od]if context_row and r['funding_stream_index']<context_row['stream_index']]
  sector=op['sector'];same_sector=[r for r in prefix if r['sector']==sector]
  minimum=t['old_25_context']['signal_minimum_CORE_necessary'];newnav=D(d['nav']);needed=D(minimum['fee_inclusive_risk_to_I']);nominal=D(minimum['minimum_gross'])
  traces.append(dict(fixed_target=t,new_signal_opportunity=op,new_decision_NAV=d['nav'],new_ACT_on=d['on'],new_same_stock_layers_at_signal=current_layers,
    earlier_same_I_CORE_present=bool(same_core),earlier_same_I_CORE_fill_receipts=prior_core,new_CORE_epoch_consumed_by_prior_actual_CORE_fill=bool(prior_core),
    new_pending_sell_at_signal=sid in ds['pending_sells'],new_original_roles_and_barriers=dict(roles=op['roles'],barriers=op['barriers']),
    new_signal_intents=new_intents,new_signal_CORE_proofs=proofs[day,sid],new_signal_CORE_size_funding=signal_rows,new_OPEN_funding_rows=opening_rows,
    first_unique_OPEN_failure='NOT_INFERRED_FROM_MERGED_TAGS',new_route_fallback_logs=logs[day,sid],new_reservations=reserves,new_exact_signal_actual_fills=exact_signal_fills,
    actual_branch=branch,signal_minimum_under_new_NAV=dict(original_same_market_reference_min_fee_risk=str(needed),new_quarter_pct_budget=str(newnav*D('.0025')),minimum_risk_pass=needed<=newnav*D('.0025'),minimum_gross=str(nominal),new10pct_nominal=str(newnav*D('.1')),minimum_nominal_pass=nominal<=newnav*D('.1'),scope='Original same signal source/reference/dated min reused; no new quote, not OPEN admission.'),
    new_OPEN_prefix=dict(reference_funding_role=context_row['role']if context_row else None,reference_stream_index=context_row['stream_index']if context_row else None,CORE_point_exists=core_row is not None,prior_actual_reservations=prefix,prior_same_sector_actual_reservations=same_sector,prior_reserved_gross=str(sum((D(x['gross'])for x in prefix),D(0))),prior_reserved_fee=str(sum((D(x['buy_fee'])for x in prefix),D(0))),exact_pre_CORE_cash_risk_source='native core-confirmed log.before only where present; otherwise UNKNOWN_NOT_RECONSTRUCTED',same_OPEN_new_orders_are_not_sellable_old_inventory=True),
    same_day_MOBILE_suppressed_by_CORE_reservation=bool(reserves['core']and any(i['role']=='mobile'for i in new_intents)and reserves['mobile']is None),
    scope='Same source-I/CP signal trace plus earlier true CORE participation; not incremental policy PnL.'))
 save('ALL25_FIXED_SIGNALS_NEW_PATHS.json',traces);save('ALL11_FIXED_SIGNALS_NEW_PATHS.json',[r for r in traces if r['fixed_target']['original_ALL11']])
 # All126, including no participation, with H2 CORE carried into H1 explicit.
 h1days=[d for d in daily if '2026-01-01'<=d<='2026-06-30'];stockrows=[]
 for sid,meta in semis.items():
  holdings=[]
  for day in h1days:
   ls=[l for l in daily[day]['layers']if l['sid']==sid];qty=daily[day]['positions'].get(sid,0)
   holdings.append(dict(day=day,quantity=qty,core_quantity=sum(l['qty']for l in ls if l['kind']=='core'),Mobile_quantity=sum(l['qty']for l in ls if l['kind']!='core'),pending_sell=sid in daily[day]['pending_sells'],layer_states=ls,account_NAV=daily[day]['nav']))
  buys=[j for js in by_budget.values()for j in js if j['sid']==sid and '2026-01-01'<=j['at'][:10]<='2026-06-30']
  sells=[t for t in book['trades']if t['side']=='sell'and t['security_id']==sid and '2026-01-01'<=t['at'][:10]<='2026-06-30']
  carried=[l for l in holdings[0]['layer_states']if l['opened'][:10]<'2026-01-01']if holdings else[]
  stockrows.append(dict(sid=sid,name=meta['name'],all_H1_daily_actual_holdings=holdings,H1_actual_buy_fills=buys,H1_actual_sell_trades=sells,carried_from_2025_layers=carried,
    H1_holding_CLOSE_days=sum(bool(r['quantity'])for r in holdings),H1_CORE_holding_CLOSE_days=sum(bool(r['core_quantity'])for r in holdings),H1_Mobile_holding_CLOSE_days=sum(bool(r['Mobile_quantity'])for r in holdings),
    old25_stock=sid in {t['sid']for t in targets},weights_and_open_PnL='NOT_COMPUTED_NO_NEW_MARKS; use completed root finance output'))
 assert len(stockrows)==126
 save('ALL126_NEW_H1_PARTICIPATION.json',stockrows)
 summary=dict(target_layers=25,target_stocks=18,fixed_11=11,by_actual_branch=dict(Counter(r['actual_branch']for r in traces)),
   fixed11_branches=dict(Counter(r['actual_branch']for r in traces if r['fixed_target']['original_ALL11'])),fixed9_branches=dict(Counter(r['actual_branch']for r in traces if r['fixed_target']['original_narrow_9_candidate']is True)),fixed2_sector_risk_branches=dict(Counter(r['actual_branch']for r in traces if r['fixed_target']['original_ALL11']and r['fixed_target']['original_narrow_9_candidate']is False)),
   semiconductor126=126,new_H1_ever_held_stocks=sum(r['H1_holding_CLOSE_days']>0 for r in stockrows),new_H1_ever_CORE_stocks=sum(r['H1_CORE_holding_CLOSE_days']>0 for r in stockrows),
   new_H1_bought_stocks=sum(bool(r['H1_actual_buy_fills'])for r in stockrows),new_H1_buy_fills=sum(len(r['H1_actual_buy_fills'])for r in stockrows),
   earlier_CORE_not_called_failed_repair=True,closed_native_run=str(run),seconds=time.monotonic()-started,new_Account=0,new_Market=0,new_RiskBook=0,new_marks=0,new_trades=0)
 save('SUMMARY.json',summary);SHA[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('SOURCE_SHA256.json',SHA);print(json.dumps(summary,ensure_ascii=False,indent=2))
def read_gzip_book(p):
 with gzip.open(bind(p),'rt')as f:return json.load(f)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--root-done-notice',action='store_true',required=True);a=p.parse_args()
 try:main(a.run)
 except BaseException as e:save('STOP_STATUS.json',dict(error=str(e),traceback=traceback.format_exc(),no_new_account=True,no_new_market=True));raise
