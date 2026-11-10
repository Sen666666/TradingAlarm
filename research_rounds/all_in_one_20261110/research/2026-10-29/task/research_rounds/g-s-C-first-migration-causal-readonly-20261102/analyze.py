"""Saved actual event/lineage diagnosis only. No new account event or rule."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib
import pandas as pd
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-month-continuation-20261102'));import month_runtime as M
C=M.C;E=M.E;R=M.HERE
def read(p):return M.read(p)
def save(p,x):E.IO.write_json(p,x,encoder=E.encode)
def source_stock(inputs,sid,day):
 s=inputs.stock(sid,day,'CLOSE');return dict(day=day,known_at=C.X.LD.known(day),facts=s['facts'],stock_Q=s['retained_stock_Q'],core_Q=s['retained_core_event_Q'],CP1=s['canonical_receipt'],H1=s['H1'],PVR=s['PVR'],structure=s['structure'])
def risk(lock,mark,floor):return max(D(lock['remaining'])*max(D(0),mark-floor),D(lock['e0'])*D(lock['remaining'])/(D(lock['ratio'])*D(lock['q0'])))
def main():
 M.guard();identity=read(R/'POLICY_INPUT_IDENTITY.json');inputs=M.MonthInputs(identity['inputs']['2022']['path']);sec='URFI881141';jan=[];sold=[]
 for mode in ('C10','C_BATCH20'):
  root=R/'runs'/('2022-'+mode);op=read(root/'2022-01-07-OPEN.json');cl=read(root/'2022-01-07-CLOSE.json');a=op['account'];end=cl['account'];flow=read(root/'FIRST_MIGRATION.json')
  for f in flow['fills']:
   sid=f['security_id']
   if f['side']=='sell':
    p6=D(str(inputs.rows('raw',sid,'2022-01-06',True)['close']));p7=D(str(inputs.rows('raw',sid,'2022-01-07',True)['close']));sold.append(dict(mode=mode,sid=sid,name=inputs.meta[sid]['name'],qty=f['shares'],sell_price=D(f['gross_cny'])/f['shares'],Jan6_close=p6,Jan7_close=p7,close_to_close_return=p7/p6-1,post_actual_sale_mark_return=p7/(D(f['gross_cny'])/f['shares'])-1,not_counterfactual_account_PNL=True));continue
   lid=a['inventory_map'][f['receipt_id']]['layer'];meta=a['capital_meta'][str(lid)]
   if meta['sector']!=sec:continue
   z=next(z for z in a['layers'] if z['id']==lid);zz=next(z for z in end['layers'] if z['id']==lid);order=a['supports'][meta['order']];factor=D(a['market_factors'][sid]);floor=D(z['floor'])/factor;close=D(end['market_marks'][sid]);current_floor=D(zz['floor'])/D(end['market_factors'][sid]);locks=[l for l in end['policy']['locks'].values() if l['lot']==lid and l['remaining']]
   source5=source_stock(inputs,sid,'2022-01-05');source6=source_stock(inputs,sid,'2022-01-06');source7=source_stock(inputs,sid,'2022-01-07');raw=inputs.rows('raw',sid,'2022-01-07',True)
   jan.append(dict(mode=mode,layer=lid,sid=sid,name=inputs.meta[sid]['name'],role=meta['role'],pool=meta['pool'],purpose=meta['purpose'],qty=z['qty'],fill_price=D(f['gross_cny'])/f['shares'],gross=f['gross_cny'],buy_fee=f['fees_cny'],buy_cash_cost=D(f['gross_cny'])+D(f['fees_cny']),actual_open_floor=floor,I_floor_known_Jan6=D(source6['facts']['i_floor'])/factor,CP_floor_known_Jan6=D(order['receipt']['payload_json'] and json.loads(order['receipt']['payload_json'])['original_candidate'])/factor,actual_frozen_priority=order['priority'],source_Jan5=source5,source_Jan6=source6,source_Jan7_AFTER_OPEN=source7,Jan7_OHLC_later_observed={k:raw[k] for k in ('open','high','low','close')},close_mark=close,close_price_change_from_fill=close/(D(f['gross_cny'])/f['shares'])-1,new_layer_mark_PNL_after_buy_fee=D(z['qty'])*close-D(f['gross_cny'])-D(f['fees_cny']),close_floor=current_floor,exit_locks=locks,planned_exit_nominal_risk=sum((risk(l,close,current_floor) for l in locks),D(0)),actual_exit_sales=0,no_exit_realized_PNL=True))
  assert op['f1'][sec]==read(C.HERE/'runs'/('2022-'+mode)/'full/2022-01-06-CLOSE.json')['f1'][sec]
 industry=[]
 for day,path in [('2022-01-05',C.OLD/'runs/2022-C10-recovered/2022-01-05-CLOSE.json'),('2022-01-06',C.HERE/'runs/2022-C10/full/2022-01-06-CLOSE.json'),('2022-01-07',R/'runs/2022-C10/2022-01-07-CLOSE.json')]:
  x=read(path);ob=next(z for z in inputs.market_observations(day) if z['policy_scope']==sec);state=x['f1'][sec];industry.append(dict(day=day,known_at=C.X.LD.known(day),observation=ob,F1={k:v for k,v in state.items() if k not in ('prior_closes','prior_abs_returns','failure_log')},policy_scope=x['account']['policy']['scopes'][sec],global_scope=x['account']['policy']['scopes']['G'],ACT=x['account']['policy']['act'],industry_H1=inputs.rows('h1',sec,day,True)))
 legacy=next(Path(p) for p in C.X.LD.read(C.P.H.INPUT/'SOURCE_BINDINGS.json') if p.endswith('/'+sec+'.parquet'));assert C.P.sha(legacy)==C.X.LD.read(C.P.H.INPUT/'SOURCE_BINDINGS.json')[str(legacy)];lf=pd.read_parquet(legacy).loc['2022-01-04':'2022-01-07'];save(HERE/'JAN7.json',dict(industry=industry,industry_original_E0=C.X.LD.clean(lf.reset_index().to_dict('records')),new_layers=jan,sold_stock_opportunity_cost_context=sold,industry_G1='not available in this same-source industry-facts cache; not invented from F1 or stock G1',financial_events=0))
 ip=M.MonthInputs(identity['inputs']['2025_26']['path']);sid='601916.SH';bank=[]
 for mode in ('C10','C_BATCH20'):
  root=R/'runs'/('2025_26-'+mode);before=read(root/'import/IMPORT.json');op=read(root/'2025-07-04-OPEN.json');cl=read(root/'2025-07-04-CLOSE.json');old=read(C.HERE/'runs'/('2025_26-'+mode)/'full/2025-07-03-CLOSE.json');a=op['account'];old_a=old['account'];oldlayers=[z for z in old_a['layers'] if z['sid']==sid and z['qty']];newlayers=[z for z in a['layers'] if z['sid']==sid and z['qty']];newz=newlayers[-1];newmeta=a['capital_meta'][str(newz['id'])];oldz=oldlayers[0];oldmeta=old_a['capital_meta'][str(oldz['id'])];oldorder=old_a['supports'][oldmeta['order']];neworder=a['supports'][newmeta['order']];lastplan=old['results'][-1]
  bank.append(dict(mode=mode,old_layer=oldz,old_meta=oldmeta,old_order=oldorder,new_layer=newz,new_meta=newmeta,new_order=neworder,old_effective_floor=D(oldz['floor'])/D(old_a['market_factors'][sid]),new_core_floor=D(a['facts_floors'][sid])/D(a['market_factors'][sid]),before_exit_duties={k:v for k,v in old_a['exit_duties'].items() if v['sid']==sid},old_same_stock_Q=lastplan['projection']['Q'].get(sid),new_capital_receivers={s:q for s,q in lastplan['projection']['Q'].items() if q},old_funding_D=lastplan['projection']['D'],native_fills=[f for f in a['fills'] if f['security_id']==sid],source_Jul3=source_stock(ip,sid,'2025-07-03'),old_policy_core_epoch=old_a['core_epochs'].get(sid),new_policy_core_epoch=a['core_epochs'].get(sid),after_close_policy_scopes=dict(G=cl['account']['policy']['scopes']['G'],S=cl['account']['policy']['scopes'][newmeta['sector']]),actual_new_core_with_unused_CP1=neworder['receipt']['event_id'] not in a['policy']['consumed'],old_original_receipt_consumed=oldorder['receipt']['event_id'] in a['policy']['consumed']))
 save(HERE/'601916.json',dict(rows=bank,financial_events=0))
 rights=[]
 for ev in inputs.actions('2022-01-13')+inputs.actions('2022-01-27'):
  states=[]
  for mode in ('C10','C_BATCH20'):
   x=read(R/'runs'/('2022-'+mode)/'2022-01-07-CLOSE.json');a=x['account'];states.append(dict(mode=mode,shares=a['balance']['quantities'].get(ev['sid'],0),native_buy=ev['sid'] in a['buys'],native_exit=ev['sid'] in a['exits'],unsubmitted_positive_Q=x['active']['Q'].get(ev['sid'],0),raw_pending=any(i['sid']==ev['sid'] for i in x['pending'])))
  rights.append(dict(event=ev,current_states=states,future_holdings_unknown=True))
 save(HERE/'RIGHTS.json',dict(rows=rights,current_loader='loader.py:228 rejects non ordinary action even without position',original_runner='ix-a-share-entry-20261025/code/multi_runner.py:363 supports no-subscription audit/no cash or extra shares',financial_events=0))
 print('READ_ONLY_CAUSAL_READY',len(jan),len(bank),len(rights))
if __name__=='__main__':main()
