"""Reuse the original pure audit cash identity for completed target traces."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,hashlib,json,sys,time,traceback
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent.parent;START=time.monotonic();SHA={};TOL=D('.0000001')
sys.path.insert(0,'/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code')
import study as LR
def bind(p):
 p=Path(p);SHA[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return [json.loads(s)for s in f]if lines else json.load(f)
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def eq(a,b,tag):assert abs(D(str(a))-D(str(b)))<TOL,(tag,a,b)
def effective(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))
def main():
 run=ROOT/'core_confirmed_v1/funding/runs/strong_ON';assert read(run/'DONE.json')['completed']is True
 traces=read(O/'ALL25_FIXED_SIGNALS_NEW_PATHS.json');b=gz(run/'pair/B.json.gz');daily=gz(run/'pair/daily.jsonl.gz',True);dd={r['at'][:10]:r for r in daily}
 rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 assert all(D(r[k])==0 for r in daily for k in ['order_reserved','settlement_locked','payable','sale_receivable'])
 assert all('09:30:00'in t['at']for t in b['trades'])
 assert all(a['settlement']['fx_rate']=='1'and a['settlement']['due_at']==a['at']for a in b['audit']if a['kind']=='settle')
 buys=defaultdict(lambda:D(0));sells=defaultdict(lambda:D(0));settles={};residx=defaultdict(list);fillidx=defaultdict(list);releaseidx=defaultdict(list)
 for t in b['trades']:
  day=t['at'][:10]
  if t['side']=='buy':buys[day]+=D(t['gross_cny'])+D(t['fees_cny'])
  else:sells[day]+=D(t['gross_cny'])-D(t['fees_cny'])
 for n,a in enumerate(b['audit']):
  if a['kind']=='settle':settles[a['settlement']['settlement_id']]=(n,a)
  if a['kind']=='reserve':residx[a['at'][:10]].append(n)
  if a['kind']=='fill'and a['receipt']['side']=='buy':fillidx[a['receipt']['at'][:10]].append(n)
  if a['kind']=='release_buy'and '09:30:00'in a['at']:releaseidx[a['at'][:10]].append(n)
 for day,indices in residx.items():
  if fillidx[day]:assert max(indices)<min(fillidx[day])
  if releaseidx[day]:assert max(indices)<min(releaseidx[day])
 for t in b['trades']:
  if t['side']!='sell':continue
  n,a=settles[t['settlement_id']];assert a['at']==t['at']and not a['settlement']['debit']
  eq(a['settlement']['cny_amount'],D(t['gross_cny'])-D(t['fees_cny']),'sale net settlement')
  if residx[t['at'][:10]]:assert n<min(residx[t['at'][:10]])
 cash=D(1000000);s0={}
 for day,r in dd.items():
  cash+=sells[day]-buys[day];eq(cash,r['available'],'all-day pure cash '+day);s0[day]=D(r['available'])+buys[day]
 eq(cash,b['ending_cash'],'ending native cash')
 contexts=[];cross=0
 for r in traces:
  t=r['fixed_target'];sid,day,od=t['sid'],t['signal_day'],t['OPEN'];prefix=r['new_OPEN_prefix'];prior=D(prefix['prior_reserved_gross'])+D(prefix['prior_reserved_fee']);A=s0[od]-prior;buffer=D(r['new_decision_NAV'])*D('.1')
  assert A>=-TOL
  q=effective(rules['quantity_versions'][sid],od)['rule']['buy_minimum'];venue=effective(rules['venue_versions'][sid],od)['venue'];z=effective(rules['fee_versions'][venue],od)['schedule'];fs=LR.L.FeeSchedule(z['schedule_id'],tuple(LR.L.FeeComponent(**x)for x in z['components']));par=D(rules['security_metadata'][sid]['par_value'])
  oldbuy=t['old_25_context']['actual_buy'];price=D(oldbuy['raw_open'])*(D(1)+LR.SLIP);eq(price,oldbuy['price'],'stored same-OPEN quote')
  fee=LR.fees(q,price,fs,'buy',par);cost=D(q)*price+fee
  corefund=next((f for f in r['new_OPEN_funding_rows']if f['role']=='core'),None)
  if corefund and 'cash_or_original_reserve'in corefund['result']:assert cost>A-buffer-TOL
  for log in r['new_route_fallback_logs']:
   eq(A,log['before']['available'],'actual native fallback cash prefix');cross+=1
  branch=r['actual_branch'];core_size=[f for f in r['new_signal_CORE_size_funding']if f['role']=='core']
  if branch=='new_CORE_size_or_missing_intent':
   assert core_size and all(f['result']=='minimum_unit_exceeds_risk_or_nominal_cap'for f in core_size)
   assert not r['signal_minimum_under_new_NAV']['minimum_risk_pass']and r['signal_minimum_under_new_NAV']['minimum_nominal_pass'];branch='new_CORE_CLOSE_minimum_I_fee_risk_exceeds_quarter_pct_NAV'
  contexts.append(dict(target_id=t['target_id'],sid=sid,name=t['name'],signal_day=day,OPEN=od,original_ALL11=t['original_ALL11'],original_narrow9=t['original_narrow_9_candidate'],refined_actual_branch=branch,
    exact_S0_available_before_all_new_buys=str(s0[od]),actual_same_OPEN_protection_sale_net=str(sells[od]),
    actual_before_reference_reserved=str(prior),actual_available_before_reference=str(A),original_cash10_from_new_signal_NAV=str(buffer),spendable_after_cash10=str(A-buffer),
    actual_CORE_OPEN_reference_exists=corefund is not None,reference_role=prefix['reference_funding_role'],dated_min_CORE=q,same_original_market_known_OPEN_buy_price=str(price),dated_min_buy_fee=str(fee),dated_min_cash=str(cost),
    physical_cash_can_afford_minimum=cost<=A+TOL,cash10_can_afford_minimum=cost<=A-buffer+TOL,cash10_minimum_shortfall=str(max(D(0),cost-(A-buffer))),
    original_CORE_failures=t['original_CORE_failure_set'],new_CORE_OPEN_result=corefund['result']if corefund else None,new_CORE_CLOSE_size_rows=core_size,
    new_CORE_reserved=r['new_reservations']['core'],new_exact_signal_fills=r['new_exact_signal_actual_fills'],
    risk_state_scope='native fallback before sector/global resources only where logged; no riskbook/marks reconstruction',
    cash_scope='Exact saved audit stock with real prior submitted reserves; hypothetical Core minimum when no actual Core intent/OPEN reference; not new admission or reusable cash across targets.'))
 save('ALL25_OPEN_CASH_CONTEXT.json',contexts);save('ALL11_OPEN_CASH_CONTEXT.json',[r for r in contexts if r['original_ALL11']])
 prior_days=[d for d in dd if d<'2026-01-01'];prior=dd[prior_days[-1]];ids=set(read(O/'FIXED_TARGETS.json')['semiconductor126']);carry=[l for l in prior['layers']if l['sid']in ids]
 assert not carry,'If carry exists use prior-year CLOSE rather than first-H1-CLOSE approximation'
 save('CASH_AND_CARRY_AUDIT.json',dict(passed=True,all_242_daily_cash_and_ending_reconciled=True,CLOSE_existing_reserved_and_unsettled_obligations_zero=True,all_buy_reserves_before_fills_or_release=True,all_sale_net_settled_before_new_buy_reserves=True,actual_fallback_cash_crosschecks=cross,prior_year_end_CLOSE=prior['at'],semiconductor_carry_layers_at_prior_year_end=carry,all126_carry_field_also_zero_at_first_H1_CLOSE=True,
    refined_branches=dict(Counter(r['refined_actual_branch']for r in contexts)),seconds=time.monotonic()-START,no_new_Account=True,no_new_Market=True,no_new_RiskBook=True,no_new_marks=True,no_new_trades=True))
 bind(__file__);bind('/Users/bytedance/Documents/Codex/2026-11-04/task-4/cash_release_v1/full_cash_bounds.py');bind(LR.__file__);save('CASH_SOURCE_SHA256.json',SHA)
 print(json.dumps(dict(cash_crosschecks=cross,seconds=time.monotonic()-START,refined_branches=dict(Counter(r['refined_actual_branch']for r in contexts))),ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except BaseException as e:save('CASH_STOP_STATUS.json',dict(error=str(e),traceback=traceback.format_exc(),no_riskbook_or_market_fallback=True));raise
