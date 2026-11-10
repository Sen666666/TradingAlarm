"""Saved-state accounting attribution; imports no financial runner."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import hashlib,json
O=Path(__file__).resolve().parent;BASE=O.parent/'C-2022-month-native-baseline-20261102'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);READS={};EPS=D('0.00000001')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);READS[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def eq(a,b):assert abs(a-b)<EPS,(a,b)
def total(rows,k):return sum((D(x[k]) for x in rows),Z)
def key(z):return (z['sid'],z['signal_at'],z['opened'],z['role'],z['pool'],z['purpose'],z['epoch_json'],z['receipt_event'],z['receipt_source'])
def main():
 names=read(W/'g-s-C-month-continuation-20261102/inputs/2022/metadata.json')
 sectors=read(BASE/'analysis/INDUSTRY_NAMES.json')['mapping']
 short=read(W/'g-s-C-short-difference-readonly-20261102/ATTRIBUTION.json')['2022']
 allrows={};states={};summaries={};stockresults={};curves={}
 for mode in ['C10','C_BATCH20']:
  arm='2022-'+mode;x=read(O/(arm+'-EXTRACT.json'));check=read(O/(arm+'-EXTRACT-CHECKS.json'));assert check['passed'] and check['complete_state_unchanged'];a=x['account'];states[mode]=x
  summaries[mode]=read(BASE/'analysis'/(arm+'-SUMMARY.json'))
  stocks={z['sid']:z for z in read(BASE/'analysis'/(arm+'-STOCK_PNL.json'))};stockresults[mode]=stocks
  curves[mode]=read(BASE/'analysis'/(arm+'-NAV.json'))
  buys={t['layer']:t for t in a['trades'] if t['side']=='buy'};sold=defaultdict(list);remain=defaultdict(int)
  for l in a['layers']:remain[l['sid']]+=l['qty']
  for t in a['trades']:
   if t['side']=='sell':
    for part in t['parts']:sold[part['layer']].append(dict(at=t['at'],receipt_id=t['receipt_id'],raw_open=t['raw_open'],price=t['price'],**part))
  rows=[]
  for l in a['layers']:
   lid=l['id'];b=buys[lid];m=a['capital_meta'][str(lid)];s=a['supports'][m['order']];i=s['original_intent'];receipt=s.get('receipt') or {};legs=sold[lid]
   assert D(m['ratio'])==1
   soldqty=sum(v['shares'] for v in legs);assert soldqty+l['qty']==b['shares']
   sf=sum((D(v['fee_cny']) for v in legs),Z);sn=sum((D(v['net_cash']) for v in legs),Z)
   buyfee=D(b['fees_cny']);soldbf=buyfee*D(soldqty)/b['shares'];remainingbf=buyfee-soldbf
   mark=D(stocks[l['sid']]['end_market_value'])/remain[l['sid']] if l['qty'] else Z
   realized=sn-D(soldqty)*D(m['unit_cost'])-soldbf
   unrealized=mark*l['qty']-D(l['qty'])*D(m['unit_cost'])-remainingbf
   assert D(l['dividend'])==0,'dividend allocation requires explicit source'
   for leg in legs:
    leg['original_duty_evidence']=[dict(duty_id=eid,**d) for eid,d in a['exit_duties'].items() if d['layer']==lid and d['requested_at']<leg['at'] and set(d['reasons'])&set(leg['reason'].split(','))]
    assert leg['original_duty_evidence'],'sale without saved original duty'
   z=dict(arm=arm,layer=lid,sid=l['sid'],name=names[l['sid']]['name'],sector=m['sector'],industry=sectors[m['sector']],opened=l['opened'],signal_at=l['signal_at'],role=m['role'],pool=m['pool'],purpose=m['purpose'],epoch_json=json.dumps(i.get('epoch'),sort_keys=True),receipt_event=receipt.get('event_id'),receipt_source=receipt.get('source'),C_certificate=s.get('C_certificate'),priority=s['priority'],buy_receipt=b['receipt_id'],buy_qty=b['shares'],buy_gross=D(b['gross_cny']),buy_fee=buyfee,buy_raw_open=b['raw_open'],buy_price=b['price'],sold_qty=soldqty,end_qty=l['qty'],sell_fee=sf,sell_legs=legs,realized_net=realized,unrealized_net=unrealized,net=realized+unrealized,gross=realized+unrealized+buyfee+sf)
   rows.append(z)
  eq(total(rows,'realized_net'),D(summaries[mode]['realized_net']));eq(total(rows,'unrealized_net'),D(summaries[mode]['unrealized_net']));eq(total(rows,'buy_fee')+total(rows,'sell_fee'),D(summaries[mode]['fees']))
  for sid,st in stocks.items():
   zz=[z for z in rows if z['sid']==sid]
   for k in ['realized_net','unrealized_net']:eq(total(zz,k),D(st[k]))
  allrows[mode]=rows
 save('ALL_LAYERS.json',allrows)
 keys={mode:defaultdict(list) for mode in allrows}
 for mode,rows in allrows.items():
  for z in rows:keys[mode][key(z)].append(z)
 short_by={tuple(z['key']):z for z in short['entry_details']};details=[]
 for k in sorted(set(keys['C10'])|set(keys['C_BATCH20']),key=str):
  aa=keys['C10'].get(k,[]);bb=keys['C_BATCH20'].get(k,[])
  A={f:total(aa,f) for f in ['buy_qty','buy_gross','buy_fee','sell_fee','net','gross','realized_net','unrealized_net']};B={f:total(bb,f) for f in A}
  old=D(short_by.get(k,{}).get('net_delta',0));delta=B['net']-A['net'];z=(aa or bb)[0]
  details.append(dict(key=k,sid=k[0],name=z['name'],industry=z['industry'],signal_at=z['signal_at'],opened=z['opened'],C10=A,C20=B,net_delta=delta,gross_delta=B['gross']-A['gross'],Jan12_delta=old,change_since_Jan12=delta-old,classification='same_entry_different_quantity' if aa and bb and A['buy_qty']!=B['buy_qty'] else 'same_entry_equal_quantity' if aa and bb else 'different_entry_or_role',C10_layers=[z['layer'] for z in aa],C20_layers=[z['layer'] for z in bb]))
 # Every short entry must survive in the final authoritative layer history.
 assert set(short_by)<=set(keys['C10'])|set(keys['C_BATCH20'])
 save('MATCHED_ENTRIES.json',details)
 stock=[]
 for sid in sorted(set(stockresults['C10'])|set(stockresults['C_BATCH20'])):
  A=stockresults['C10'].get(sid,{});B=stockresults['C_BATCH20'].get(sid,{})
  dz={k:D(B.get(k,0))-D(A.get(k,0)) for k in ['realized_net','unrealized_net']};delta=sum(dz.values(),Z)
  zz=[v for v in details if v['sid']==sid];eq(delta,total(zz,'net_delta'))
  fee_delta=sum((z['C20']['buy_fee']+z['C20']['sell_fee']-z['C10']['buy_fee']-z['C10']['sell_fee'] for z in zz),Z)
  stock.append(dict(sid=sid,name=names[sid]['name'],sector=names[sid]['sector'],industry=sectors[names[sid]['sector']],C10_net=sum((D(A.get(k,0)) for k in dz),Z),C20_net=sum((D(B.get(k,0)) for k in dz),Z),net_delta=delta,**dz,dividend_delta=Z,fee_delta_already_in_net=fee_delta,Jan12_delta=total(zz,'Jan12_delta'),change_since_Jan12=total(zz,'change_since_Jan12')))
 stock.sort(key=lambda z:z['net_delta']);save('STOCK_BRIDGE.json',stock)
 bysec=defaultdict(list)
 for v in stock:bysec[v['sector']].append(v)
 industry=[dict(sector=s,industry=sectors[s],stocks=len(bysec[s]),**{k:total(bysec[s],k) for k in ['C10_net','C20_net','net_delta','realized_net','unrealized_net','dividend_delta','fee_delta_already_in_net','Jan12_delta','change_since_Jan12']}) for s in sectors]
 save('INDUSTRY_BRIDGE.json',sorted(industry,key=lambda z:z['net_delta']))
 groups=defaultdict(list)
 for v in details:groups[v['signal_at'][:10]].append(v)
 batches=[dict(decision_day=day,entry_keys=len(v),stocks=len({z['sid'] for z in v}),**{k:total(v,k) for k in ['net_delta','gross_delta','Jan12_delta','change_since_Jan12']},C10_net=sum((z['C10']['net'] for z in v),Z),C20_net=sum((z['C20']['net'] for z in v),Z),realized_net_delta=sum((z['C20']['realized_net']-z['C10']['realized_net'] for z in v),Z),unrealized_net_delta=sum((z['C20']['unrealized_net']-z['C10']['unrealized_net'] for z in v),Z),dividend_delta=Z,fee_delta_already_in_net=sum((z['C20']['buy_fee']+z['C20']['sell_fee']-z['C10']['buy_fee']-z['C10']['sell_fee'] for z in v),Z)) for day,v in sorted(groups.items())]
 save('ENTRY_BATCH_BRIDGE.json',dict(definition='Group each entire actual layer lifecycle by its original signal decision date; no subsequent replacement chain is relabelled as an initial-cohort causal effect.',rows=batches))
 A=summaries['C10'];B=summaries['C_BATCH20'];net=D(B['final_NAV'])-D(A['final_NAV']);rd=D(B['realized_net'])-D(A['realized_net']);ud=D(B['unrealized_net'])-D(A['unrealized_net']);div=D(B['recognized_dividend'])-D(A['recognized_dividend']);feesaved=D(A['fees'])-D(B['fees']);gross=total(details,'gross_delta')
 eq(rd+ud+div,net);eq(gross+feesaved+div,net);eq(total(stock,'net_delta')+div,net);eq(total(batches,'net_delta')+div,net);eq(total(details,'Jan12_delta'),D(short['wealth_delta_C20_minus_C10']))
 nav=[]
 ca={z['at']:z for z in curves['C10'] if z['phase']=='CLOSE'};cb={z['at']:z for z in curves['C_BATCH20'] if z['phase']=='CLOSE'};assert ca.keys()==cb.keys()
 for at in sorted(ca):nav.append(dict(at=at,C10_NAV=ca[at]['NAV'],C20_NAV=cb[at]['NAV'],delta=D(cb[at]['NAV'])-D(ca[at]['NAV'])))
 save('DAILY_DELTA.json',nav)
 selected=[z['sid'] for z in sorted(stock,key=lambda z:abs(z['net_delta']),reverse=True)[:12]]
 chains={sid:dict(name=names[sid]['name'],stock_bridge=next(z for z in stock if z['sid']==sid),actual_layers={m:[z for z in allrows[m] if z['sid']==sid] for m in allrows},decisions={m:[dict(at=v['at'],Q=v['projection']['Q'].get(sid),trace=[t for t in v['projection']['trace'] if t['sid']==sid],D=v['projection']['D'],donor_rows=v['projection']['donors']['rows'],budget_after=v['projection']['budget_after']) for v in states[m]['results'] if 'projection' in v and (sid in v['projection']['Q'] or sid in v['projection']['D'])] for m in allrows}) for sid in selected}
 save('ACTUAL_CHAINS.json',chains)
 bridge=dict(C20_minus_C10=net,net_realized_delta=rd,net_unrealized_delta=ud,dividend_delta=div,fees_already_included=True,alternative_gross_price_delta=gross,alternative_fee_saving_add_once=feesaved,Jan12_advantage=D(short['wealth_delta_C20_minus_C10']),Jan12_to_Jan28_relative_change=net-D(short['wealth_delta_C20_minus_C10']),positive_stock_deltas=sum((z['net_delta'] for z in stock if z['net_delta']>0),Z),negative_stock_deltas=sum((z['net_delta'] for z in stock if z['net_delta']<0),Z),stock_union=len(stock),industry_denominator=len(sectors),initial_migration_Jan06_cohort=next(z for z in batches if z['decision_day']=='2022-01-06'),all_entry_batches=batches)
 save('EXACT_BRIDGE.json',bridge)
 assert all(sha(p)==h for p,h in READS.items()),'source changed during read-only analysis'
 save('CHECKS.json',dict(passed=True,financial_events=0,no_2025_account_loaded_or_advanced=True,all_layer_stock_industry_batch_and_NAV_bridges_exact=True,Jan12_to_month_end_bridge_exact=True,fees_counted_once=True,all_original_inputs_unchanged=True,full_stock_union=len(stock),all_industries=90))
 save('READ_INPUTS.json',READS)
 print(json.dumps(bridge,default=str,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
