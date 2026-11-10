"""Seven independent original-prefix arithmetic previews, not an account path."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,math,shutil
O=Path(__file__).resolve().parent;Q=O.parents[1];V=Q/'structure_risk_position_review_v2/cases';SRC={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');contract=O.parent/'designer/MINIMUM_MATH_CONTRACT.md';SRC[str(contract)]=sha(contract)
def version(xs,day):return next(r for r in xs if r['from']<=day and (r['to'] is None or day<r['to']))
def fee(q,p,schedule,side):return notionalfee(D(q)*p,q,schedule,side)
def notionalfee(gross,q,schedule,side):
 if q==0:return Z
 z=Z
 for c in schedule['components']:
  if c.get('side','both') not in ['both',side]:continue
  b=gross if c.get('amount_basis','notional')=='notional' else D(q)
  v=max(D(c.get('minimum_local','0')),b*D(c['rate']))
  assert c.get('maximum_local') is None and c.get('rounding_unit') is None,'outside these fixed schedules'
  z+=v
 return z
configs=[('688146.SH','strong','2026-04-21','2026-04-22','CP_SEED'),('688146.SH','strong','2026-04-30','2026-05-06','CP_ADD'),('000620.SZ','2022_2024','2022-01-10','2022-01-11','CORE_SEED'),('000620.SZ','2022_2024','2022-01-21','2022-01-24','CP_ADD'),('000620.SZ','2022_2024','2022-01-24','2022-01-25','CP_ADD'),('688146.SH','strong','2026-04-22','2026-04-23','HELD_I_INCREMENT'),('000620.SZ','2022_2024','2022-01-14','2022-01-17','HELD_I_INCREMENT')]
loaded={};results=[]
for sid,w,day,od,source in configs:
 if sid not in loaded:
  case=read(V/(sid.replace('.','_')+'_DAILY_PAPER_INPUTS.json'));book=read(Q/'trend_exit_controls_v1/runs/BASELINE'/w/'pair/B.json.gz',True);loaded[sid]=(case,book)
 case,book=loaded[sid];d=next(x for x in case['days'] if x['day']==day);nd=next(x for x in case['days'] if x['day']==od);root='2026-04-03' if sid=='688146.SH' else '2022-01-06'
 originres=min((a for a in book['audit'] if a.get('kind')=='reserve' and a.get('sid')==sid and a['decision_at'][:10]>=root),key=lambda a:a['at']);origin=originres['decision_at'][:10];ori=next(x for x in case['days'] if x['day']==origin);B=D(ori['original_account']['NAV'])*D('.0025')
 bt={t['layer']:t for t in book['trades'] if t['side']=='buy' and t['security_id']==sid};original=next((t for t in bt.values() if t['signal_at'][:10]==day),None)
 actual_intent=next((x for x in d['original_intents'] if original and x['role']==('core' if original['kind']=='core' else 'mobile')),None)
 heldI=source=='HELD_I_INCREMENT';floor_a=D(str(d['original_stock_facts']['i_floor'])) if heldI else D(actual_intent['floor']);Fclose=D(str(d['original_stock_facts']['factor']));Fopen=D(str(nd['original_stock_facts']['factor']));hclose=floor_a/Fclose;hopen=floor_a/Fopen
 Mclose=D(str(d['original_bar']['raw_close']));Mopen=D(original['raw_open']) if original else D(str(nd['original_bar']['raw_open']));pclose=D(actual_intent.get('reference_price',str(Mclose*D('1.0005')))) if actual_intent and source=='CORE_SEED' else Mclose*D('1.0005');popen=Mopen*D('1.0005')
 venue=version(rules['venue_versions'][sid],od)['venue'];schedule=version(rules['fee_versions'][venue],od)['schedule'];units=version(rules['quantity_versions'][sid],od)['rule'];minq=units['buy_minimum'];step=units['buy_step']
 paidfees=Z;grossprofit=Z;grossloss=Z;paidrights=Z;fee_parts=[];real_parts=[]
 for tr in book['trades']:
  if tr['security_id']!=sid or tr['at'][:10]>day:continue
  if tr['side']=='buy' and tr['signal_at'][:10]>=root:
   paidfees+=D(tr['fees_cny']);fee_parts.append(dict(layer=tr['layer'],at=tr['at'],buyfee=tr['fees_cny']))
  elif tr['side']=='sell':
   for a in tr['parts']:
    if a['layer'] not in bt or bt[a['layer']]['signal_at'][:10]<root:continue
    buy=bt[a['layer']];sold_basis=D(buy['gross_cny'])*D(a['shares'])/D(buy['shares']);gross=D(a['shares'])*D(tr['price'])-sold_basis;sellfee=D(a['shares'])*D(tr['price'])-D(a['net_cash']);grossprofit+=max(Z,gross);grossloss+=max(Z,-gross);paidfees+=sellfee;real_parts.append(dict(layer=a['layer'],at=tr['at'],gross_basis=sold_basis,gross_pnl=gross,sellfee=sellfee))
 debt=max(Z,grossloss+paidfees-grossprofit-paidrights)
 live=[]
 for l in d['original_live_layers']:
  buy=bt[l['layer']];assert int(l['qty'])==buy['shares'],'these fixed prefixes have no partial/share action'
  live.append(dict(layer=l['layer'],q=int(l['qty']),gross_basis=D(buy['gross_cny']),floor_adjusted=D(l['guard_after_original_CLOSE_adjusted'])))
 pending=bool(d['original_CLOSE_specific_exit_requests']) or any(l['original_layer_exit_latched_at_CLOSE'] for l in d['original_live_layers'])
 def cost(q,p,M,F,h):
  # All selected nonpending same-sid layers are one prospective liquidation
  # order, even where the individual reference prices differ.
  ll=[dict(x,exit_price=min(M,x['floor_adjusted']/F)*D('.9995')) for x in live]
  if q:ll.append(dict(layer='candidate',q=q,gross_basis=D(q)*p,exit_price=min(p,h)*D('.9995')))
  totalq=sum(x['q'] for x in ll);sell_notional=sum((D(x['q'])*x['exit_price'] for x in ll),Z);sellfee=notionalfee(sell_notional,totalq,schedule,'sell');k=Z;parts=[]
  for x in ll:
   sf=sellfee*D(x['q'])/D(totalq);kl=max(Z,x['gross_basis']-D(x['q'])*x['exit_price']+sf);k+=kl;parts.append(dict(layer=x['layer'],q=x['q'],gross_basis=x['gross_basis'],plan_net_before_fee=D(x['q'])*x['exit_price'],allocated_sellfee=sf,kappa=kl))
  bf=fee(q,p,schedule,'buy');return dict(D_before=debt,unpaid_candidate_buyfee=bf,kappa_sum=k,total=debt+bf+k,sell_group_fee=sellfee,parts=parts)
 def maxrisk(p,M,F,h,sourcecap=None):
  if debt>B:return 0,cost(0,p,M,F,h),'D_ALREADY_EXCEEDS_SHARED_B'
  diff=p-min(p,h)*D('.9995');assert diff>0
  bound=int(B/diff)+1
  if sourcecap is not None:bound=min(bound,sourcecap)
  feasible=[q for q in range(minq,bound+1,step) if cost(q,p,M,F,h)['total']<=B]
  q=max(feasible,default=0);return q,cost(q,p,M,F,h),'LOCAL_FEASIBLE' if q else 'NO_LEGAL_MINIMUM_UNIT_WITHIN_SHARED_B'
 qclose,closecost,reasonclose=maxrisk(pclose,Mclose,Fclose,hclose);qopen,opencost,reasonopen=maxrisk(popen,Mopen,Fopen,hopen)
 origcap=None if heldI else int(actual_intent['cap']);grossbudget=None if heldI else D(actual_intent['budget']);frozen=min(qclose,origcap) if origcap is not None else qclose
 open_budget_cap=None
 if grossbudget is not None:
  n=int(grossbudget/popen);open_budget_cap=0 if n<minq else minq+(n-minq)//step*step
 local_bound=min(frozen,open_budget_cap) if open_budget_cap is not None else frozen
 qlocal,localcost,reason=maxrisk(popen,Mopen,Fopen,hopen,local_bound)
 if pending:qlocal=0;reason='ORIGINAL_SAME_STOCK_EXIT_PENDING'
 cp=d['original_CP_cache'].get('receipt');opps=d['original_opportunities'];coreq=opps[0].get('core_Q') if opps else None;confirmed=all(l['saved_native_layer']['pool']=='confirmed' for l in d['original_live_layers']) if live else None
 risk=next(a for a in book['audit'] if a['kind']=='risk_checkpoint' and a['at'][:10]==day);nav=D(d['original_account']['NAV']);peak=D(risk['peak']);A=max(Z,nav-D('.8')*peak);inv=D(d['original_account']['inventory']);lower=D('.36')*inv
 identity='NEW_TYPED_I_BRANCH_NOT_IMPLEMENTED_NOT_A_REAL_GRANT' if heldI else 'ORIGINAL_SOURCE_AND_HOLDING_LINE'
 r=dict(sid=sid,window=w,decision=day,nextOPEN=od,source=source,opportunity_key=[sid,d['original_stock_facts']['segment_id'],root],origin_signal_day=origin,origin_signal_NAV=ori['original_account']['NAV'],origin_first_original_successful_reserve=originres,
  B=B,D_before=debt,D_components=dict(gross_loss=grossloss,gross_profit=grossprofit,actual_paid_fees=paidfees,paid_rights=paidrights,buyfee_parts=fee_parts,sell_parts=real_parts),
  signal_rawclose=Mclose,signal_buy_reference=pclose,next_rawOPEN=Mopen,next_buy_price=popen,holding_floor_adjusted=floor_a,holding_floor_raw_CLOSE=hclose,holding_floor_raw_OPEN=hopen,dated_units=units,dated_fee_schedule=schedule,
  original_actual_buy=original,original_frozen_intent=actual_intent,existing_original_layers=live,q_CLOSE_risk_only=qclose,original_frozen_source_cap=origcap,frozen_local_cap=frozen,q_OPEN_risk_only=qopen,OPEN_original_gross_budget_quantity_cap=open_budget_cap,q_local_after_source_and_frozen_caps=qlocal,local_reason=reason,local_cost_at_q=localcost,
  local_minimum_unit_cost=cost(minq,popen,Mopen,Fopen,hopen),next_legal_q_after_local=qlocal+step if qlocal else minq,next_legal_cost=cost(qlocal+step if qlocal else minq,popen,Mopen,Fopen,hopen),
  original_CP_state=cp,original_i_buy=d['original_stock_facts']['i_buy'],original_up_reasons=d['original_G1']['up_reasons'],original_core_Q=coreq,original_held_pools=[l['saved_native_layer']['pool'] for l in d['original_live_layers']],all_current_original_held_layers_confirmed=confirmed,original_pending=pending,typed_source_status=identity,
  CLOSE_reference_account=dict(NAV=nav,ACTpeak=peak,A=A,inventory=inv,available_cash=d['original_account']['available_cash'],order_reserved=d['original_account']['order_reserved'],AR=d['original_account']['dividend_receivable'],nominal_mark_floor_risk=d['original_account']['native_reported_account_mark_risk'],G2_no_fee_market_value_lower_bound=lower,lower_bound_exceeds_CLOSE_A=lower>A,scope='SIGNAL_CLOSE_ONLY_NOT_OPEN_DENIAL'),
  OPEN_full_portfolio_pressure='UNVERIFIED_NO_NEW_LOADER',final_disposition='DENY_ZERO_SHARED_BUDGET_EXHAUSTED' if debt>B else 'DENY_ZERO_LOCAL_MINIMUM_UNIT' if qlocal==0 else 'CONDITIONAL_LOCAL_CAP_NOT_FINAL_GRANT',cash_capacity_sector_global_gates='NOT_ALL_VERIFIED_FOR_EXACT_OPEN_PREFIX',independent_single_prefix=True,no_sequence_or_return_claim=True)
 results.append(r)
save('SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json',results)
if (O/'FIRST_THREE_LOCAL_NUMBERS.json').exists() and not (O/'FIRST_THREE_SUPERSEDED_SAME_GUARD_FEE_GROUP.json').exists():shutil.copyfile(O/'FIRST_THREE_LOCAL_NUMBERS.json',O/'FIRST_THREE_SUPERSEDED_SAME_GUARD_FEE_GROUP.json')
save('FIRST_THREE_SCOPE_CORRECTION.json',dict(reason='Initial risk-only preview omitted frozen source cap and grouped exit fees by equal guard. Final frozen card has one same-sid prospective group even different prices. Initial outputs retained; no q significance rescue.',current='SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json',cases=[dict(sid=r['sid'],day=r['decision'],q_risk_only=r['q_OPEN_risk_only'],sourcecap=r['original_frozen_source_cap'],local_cap=r['q_local_after_source_and_frozen_caps']) for r in results[:3]]))
save('LOCAL_SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=sha(__file__),no_models=True,no_new_accounts=True,no_new_loader=True,only_fixed_seven_prefixes=True))
print(json.dumps([dict(sid=r['sid'],decision=r['decision'],source=r['source'],B=str(r['B']),D=str(r['D_before']),close_risk=r['q_CLOSE_risk_only'],sourcecap=r['original_frozen_source_cap'],open_risk=r['q_OPEN_risk_only'],local=r['q_local_after_source_and_frozen_caps'],reason=r['local_reason'],minunit_cost=str(r['local_minimum_unit_cost']['total']),close_pressure=str(r['CLOSE_reference_account']['G2_no_fee_market_value_lower_bound']),closeA=str(r['CLOSE_reference_account']['A'])) for r in results],ensure_ascii=False))
