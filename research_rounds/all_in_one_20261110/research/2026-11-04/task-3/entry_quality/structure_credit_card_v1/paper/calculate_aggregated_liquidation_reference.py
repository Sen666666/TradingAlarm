"""Frozen arithmetic on nine independent saved original prefixes; no model imports."""
from pathlib import Path
from decimal import Decimal as D, getcontext
import csv, gzip, hashlib, json

getcontext().prec=50
O=Path(__file__).resolve().parent
Q=O.parents[1]
Z=D(0); SLIP=D('.0005')
SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False):
 p=Path(p);SOURCES[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return json.load(f)
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
protocol=read(O/'PROTOCOL_FREEZE.json')
inputs=read(O/'ORIGINAL_NINE_INPUTS.json')
book=read(Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz',True)
yn=read(Q/'mobile_unit_risk_revision_v1/yingxin/SIX_SINGLE_ORDER_ARITHMETIC.json')
hn=read(Q/'mobile_unit_risk_revision_v1/hainengda/THREE_ENTRY_PAPER_RESULTS.json')['rows']
hc=read(Q/'mobile_unit_risk_revision_v1/hainengda/ORIGINAL_OPEN_SLOT_CASH_BOUNDS.json')
cash_h=hc.get('rows',hc) if isinstance(hc,dict) else hc
if isinstance(cash_h,dict):cash_h=list(cash_h.values())
paper={x['layer']:x for x in yn+hn}
first={sid:next(x for x in inputs if x['sid']==sid) for sid in ['000620.SZ','002583.SZ']}
buys={x['layer']:x for x in book['trades'] if x['side']=='buy'}

def fee_notional(q,notional,schedule,side):
 if not q:return Z
 out=Z
 for c in schedule['components']:
  if c.get('side','both') not in ['both',side]:continue
  assert c.get('amount_basis','notional')=='notional' and c.get('rounding_unit') is None and c.get('maximum_local') is None
  out+=max(D(c.get('minimum_local','0')),notional*D(c['rate']))
 return out
def fee(q,p,schedule,side):return fee_notional(q,D(q)*p,schedule,side)
def floor_legal(n,u):return 0 if n<u['buy_minimum'] else u['buy_minimum']+(n-u['buy_minimum'])//u['buy_step']*u['buy_step']

def original_memory(sid,at):
 ids=set(protocol['selection'][sid]);P=Z;H=Z;bf=Z;sale_price_PL=Z;sf=Z;events=[]
 for ti,t in enumerate(book['trades']):
  if t['security_id']!=sid or t['at']>=at:continue
  if t['side']=='buy':
   if t['layer'] not in ids:continue
   f=D(t['fees_cny']);P-=f;bf+=f
   events.append(dict(book_trade_index=ti,at=t['at'],kind='actual_buy_fee',layer=t['layer'],change_P=-f))
  else:
   for pi,p in enumerate(t['parts']):
    if p['layer'] not in ids:continue
    qty=D(p['shares']);gross=qty*D(t['price']);sellfee=gross-D(p['net_cash']);price_PL=qty*(D(t['price'])-D(buys[p['layer']]['price']))
    P+=price_PL-sellfee;sale_price_PL+=price_PL;sf+=sellfee
    events.append(dict(book_trade_index=ti,part_index=pi,at=t['at'],kind='actual_realized_price_PL_less_sellfee',layer=p['layer'],shares=p['shares'],entry_gross_unit=buys[p['layer']]['price'],sell_price=t['price'],price_PL=price_PL,sell_fee=sellfee,change_P=price_PL-sellfee))
  H=max(H,P)
 return dict(P=P,high_water_P=H,D=H-P,cumulative_actual_buy_fee=bf,cumulative_sold_price_PL=sale_price_PL,cumulative_actual_sell_fee=sf,events=events)

def calc(x,clock,close_cap=None):
 sid=x['sid'];lid=x['layer'];p0=paper[lid];fi=x['original_frozen_intent'];auth=x['original_signal_authorization'];is_close=clock=='CLOSE'
 now=x['signal_at'] if is_close else x['actual_OPEN_at']
 if sid=='000620.SZ':
  F=D(p0['signal_factor'] if is_close else p0['OPEN_factor']);M=D(p0['gap_multiplier']);sch=p0['fee_schedule_CLOSE' if is_close else 'fee_schedule_OPEN'];u=p0['units_CLOSE' if is_close else 'units_OPEN'];mark=D(p0['raw_signal_close'] if is_close else p0['raw_OPEN']);stockcap=p0['new_signal_stockcap_qty' if is_close else 'OPEN_stockcap_qty'];cashcap=None if is_close else p0['same_original_slot_cash_necessary_qcap']
 else:
  F=D(p0['signal_factor'] if is_close else p0['OPEN_factor']);M=D(str(p0['two_s63_exp_multiplier']));sch=p0['dated_fee_signal' if is_close else 'dated_fee_OPEN'];u=p0['dated_quantity_signal' if is_close else 'dated_quantity_OPEN'];mark=D(p0['raw_signal_CLOSE'] if is_close else p0['raw_actual_OPEN']);stockcap=p0['stock10_signal_quantity_cap' if is_close else 'stock10_OPEN_quantity_cap'];cashcap=None
  if not is_close:
   cashrow=next(y for y in cash_h if y['layer']==lid)
   cashcap=cashrow['cash_only_legal_quantity_upper']
 assert D(auth['signal_factor'])==D(auth['fill_factor']), 'No new action/unit bridge inferred'
 first_nav=D(first[sid]['original_signal_authorization']['decision_NAV']);B=D('.0025')*first_nav
 memory=original_memory(sid,now)
 old=[];gross_old_risk=Z;old_stress_notional=Z;oldqty=0
 for live in x['original_live_layers_after_original_CLOSE_checks']:
  v=live['snapshot'];q=v['qty'];lidold=v['id'];entry=D(buys[lidold]['price'])
  assert q==buys[lidold]['shares'], 'Selected points have no partial/split quantity ambiguity'
  assert abs(D(str(v['unit_cost']))-entry)<D('1e-12'), 'Original gross cost matches saved adjusted unit'
  adjusted_h=D(v['last_core_line'] if v['kind']=='core' else v['floor']);h=adjusted_h/F;sale=min(mark,h)*M*(1-SLIP)
  ref=max(D(q)*entry,D(q)*mark);risk=ref-D(q)*sale
  old.append(dict(layer=lidold,role=v['role'],qty=q,raw_mark=mark,entry_gross_unit=entry,adjusted_h=adjusted_h,known_raw_h=h,stress_sell_price=sale,max_cost_or_mark_notional=ref,principal_and_giveback_risk_ex_fees=risk,saved_stock_structure=v.get('stock_structure'),saved_unrealized_context_only=live['held_unreal']))
  oldqty+=q;old_stress_notional+=D(q)*sale;gross_old_risk+=risk
 old_sell_fee=fee_notional(oldqty,old_stress_notional,sch,'sell');Rold=gross_old_risk+old_sell_fee
 # No original own-stock sale occurs between this signal snapshot and original reserve.
 intervening=[t for t in book['trades'] if t['security_id']==sid and t['side']=='sell' and x['signal_at']<t['at']<=x['actual_OPEN_at']]
 assert not intervening
 assert not x['original_pending_sells'], 'Pending responsibility would require separate original prefix evidence'
 assert all(D(v['snapshot'].get('dividend','0'))==0 for v in x['original_live_layers_after_original_CLOSE_checks'])
 hnew=D(fi['floor'])/F;newp=mark*(1+SLIP);new_sale=min(mark,hnew)*M*(1-SLIP);gap=newp-new_sale
 def total(q):
  newbf=fee(q,newp,sch,'buy');newsf=fee(q,new_sale,sch,'sell');newR=D(q)*gap+newsf
  return dict(q=q,D_before=memory['D'],candidate_buy_fee_entering_D_once=newbf,D_after_candidate_buyfee=memory['D']+newbf,R_old=Rold,new_R=newR,new_sell_fee=newsf,total_D_plus_R=memory['D']+newbf+Rold+newR,fits_B=memory['D']+newbf+Rold+newR<=B)
 bound=max(0,int((B-memory['D']-Rold)/gap)) if gap>0 else 0
 riskmax=0
 for q in range(floor_legal(bound,u),u['buy_minimum']-1,-u['buy_step']):
  if total(q)['fits_B']:riskmax=q;break
 local=min(riskmax,stockcap)
 if close_cap is not None:local=min(local,close_cap)
 if cashcap is not None:local=min(local,cashcap)
 conservative=min(local,x['original_quantity'])
 return dict(clock=clock,at=now,raw_mark=mark,s63=x['saved_causal_s63'],frozen_sigma_multiplier=M,factor=F,B_fixed=B,B_first_successful_signal_NAV=first_nav,B_first_reserve_layer=first[sid]['layer'],
  original_memory=memory,old_layers=old,old_qty=oldqty,old_stress_sale_notional=old_stress_notional,old_sell_fee_aggregated_once=old_sell_fee,R_old=Rold,
  original_new_qty=x['original_quantity'],original_new_qty_check=total(x['original_quantity']),zero_new_qty_check=total(0),risk_only_max_new_qty=riskmax,risk_max_check=total(riskmax),risk_next_legal_check=total(riskmax+u['buy_step'] if riskmax else u['buy_minimum']),
  stock10_necessary_cap=stockcap,original_slot_cash_necessary_cap=cashcap,CLOSE_frozen_cap=close_cap,conditional_cap=local,conditional_cap_check=total(local),no_expansion_of_original_funded_qty_cap=conservative,no_expansion_check=total(conservative),
  new_h_raw=hnew,new_buy_reference_price=newp,new_stress_sell_price=new_sale,dated_fee_schedule=sch,dated_quantity=u,
  grant_scope='CONDITIONAL_ONLY_OTHER_ORIGINAL_SECTOR_POOL_ROUTE_GATES_NOT_REBUILT',unverified=['Fresh logical stress sell grouping is a paper convention, not observed executable exit.', 'No pending/CA/new path state is constructed.','No proof of quantity beyond original actual grant.'])

results=[]
for x in inputs:
 c=calc(x,'CLOSE');o=calc(x,'OPEN',c['conditional_cap']);assert o['conditional_cap']<=c['conditional_cap']
 results.append(dict(sid=x['sid'],layer=x['layer'],signal=x['signal_at'][:10],OPEN=x['actual_OPEN_at'][:10],original_qty=x['original_quantity'],CLOSE=c,OPEN_check=o,
  original_structure_fields=dict(watch_epoch=x['original_signal_authorization']['watch_epoch'],stock_structure=x['saved_stock_structure_tokens_in_live_layers'],CP_E0_episode=None if x['original_market_CP_canonical'] is None else x['original_market_CP_canonical'].get('original_E0_episode_id')),
  path_scope='Independent original-prefix conditional arithmetic. Candidate quantities never carried into another row.'))
save('NINE_ORIGINAL_PREFIX_ARITHMETIC.json',results)
rows=[]
for r in results:
 c,o=r['CLOSE'],r['OPEN_check'];m=o['original_memory']
 rows.append(dict(sid=r['sid'],layer=r['layer'],signal=r['signal'],OPEN=r['OPEN'],original_q=r['original_qty'],fixed_B=o['B_fixed'],cumulative_actual_buy_fee=m['cumulative_actual_buy_fee'],cumulative_sold_price_PL=m['cumulative_sold_price_PL'],cumulative_actual_sell_fee=m['cumulative_actual_sell_fee'],D=o['original_memory']['D'],R_old_CLOSE=c['R_old'],R_old_OPEN=o['R_old'],original_q_total_CLOSE=c['original_new_qty_check']['total_D_plus_R'],original_q_total_OPEN=o['original_new_qty_check']['total_D_plus_R'],original_q_fits_OPEN=o['original_new_qty_check']['fits_B'],risk_only_CLOSE_cap=c['risk_only_max_new_qty'],CLOSE_frozen_cap=c['conditional_cap'],risk_only_OPEN_cap=o['risk_only_max_new_qty'],OPEN_conditional_cap=o['conditional_cap'],OPEN_no_original_expansion_cap=o['no_expansion_of_original_funded_qty_cap']))
with (O/'NINE_POINT_TABLE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save('CALCULATION_RECEIPT.json',dict(status='NINE_CORRECTED_COST_FLOOR_POINTS_COMPLETE',source_sha256=SOURCES,script_sha256=sha(__file__),protocol_sha256=sha(O/'PROTOCOL_FREEZE.json'),
  original_q_fails=[r['layer'] for r in results if not r['OPEN_check']['original_new_qty_check']['fits_B']],new_accounts=0,new_models=0,new_backtests=0,new_paths=0,old_pure_mark_version_executed=False))
print(json.dumps(rows,ensure_ascii=False,default=str))
