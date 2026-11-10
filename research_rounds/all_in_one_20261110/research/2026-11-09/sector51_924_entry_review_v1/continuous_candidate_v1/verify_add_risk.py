"""Read-only replay captures actually used OPEN protections, never changes decisions."""
from pathlib import Path
from decimal import Decimal as D
import json,sys
sys.dont_write_bytecode=True
import pandas as pd
from engine import Data,Engine,O,day
E=Engine(Data());capt=[];original=E.order

def tap(a,d,side,q,p,reason,**kw):
 if side=='BUY_ADD':
  s=a['sid'];f=E.d.fee(s,d,q,p,'buy');cost=q*p+f;op=D(str(E.d.z(s,d)['raw_open']));fac=a['factor'];fl=max(a['ifloor'],a['cp']['floor']);rawfloor=fl/fac;sp=op*D('.9995');priorq=E.quantity(a)-q;postq=priorq+q;cashpre=a['cashflow'];cashpost=cashpre-cost;div=a['dividend']
  pre=cashpre+div+priorq*sp-E.d.fee(s,d,priorq,sp,'sell');newliq=q*sp-E.d.fee(s,d,q,sp,'sell')-cost;postliq=cashpost+div+postq*sp-E.d.fee(s,d,postq,sp,'sell');pp=rawfloor*D('.9995')
  newfloor=q*pp-E.d.fee(s,d,q,pp,'sell')-cost;wholefloor=cashpost+div+postq*pp-E.d.fee(s,d,postq,pp,'sell')
  layers=cashpost+div
  for lot in a['lots']:
   lp=(a['ifloor'] if lot['kind']=='SEED' else lot['floor'])/fac*D('.9995');layers+=lot['q']*lp-E.d.fee(s,d,lot['q'],lp,'sell')
  capt.append(dict(day=day(d),sid=s,name=E.d.names[s],round_id=a['id'],cp_id=a['cp']['id'],cp_receipt_day=a['cp']['date'],raw_open=str(op),execution_price=str(p),qty=q,buy_fee=str(f),all_in_cost=str(cost),attempt_net_before_ADD=str(pre),prior_qty=priorq,CP_floor_signal=str(a['cp']['floor']),I_floor_signal=str(a['ifloor']),new_ADD_floor_signal=str(fl),factor=str(fac),CP_floor_raw=str(a['cp']['floor']/fac),I_floor_raw=str(a['ifloor']/fac),new_ADD_floor_raw=str(rawfloor),new_layer_immediate_liquidation_PnL=str(newliq),whole_attempt_immediate_liquidation_PnL=str(postliq),new_layer_floor_liquidation_PnL=str(newfloor),whole_attempt_same_ADD_floor_liquidation_PnL=str(wholefloor),whole_attempt_each_layer_own_floor_separate_fees_PnL=str(layers),floor_note='Hypothetical continuous price fill at carried protection minus 5bp, not gap/limit guarantee'))
 return original(a,d,side,q,p,reason,**kw)
E.order=tap;E.run();orig=json.loads((O/'full_20241031_once/ORDERS.json').read_text());assert E.orders==orig
pd.DataFrame(capt).to_csv(O/'ADD_OPEN_PROTECTIONS_AND_DOWNSIDE.csv',index=False);(O/'ADD_OPEN_PROTECTIONS_AND_DOWNSIDE.json').write_text(json.dumps(capt,ensure_ascii=False,indent=2)+'\n')
print(pd.DataFrame(capt).to_string(index=False))
# Phase-scrub test: OPEN sees only raw_open, factor and source identity. No daily H/L/close/volume flags available.
d=Data();d.days=d.days[d.days<=pd.Timestamp('2024-09-20')];e=Engine(d).run();get=d.z
keys=['raw_open','adjustment_factor','source_kind','source_path','segment_id']
d.z=lambda s,t:dict(get(s,t)[keys]);t=pd.Timestamp('2024-09-23');e.economic_preflight(t,e.pending);e.accrue(t);e.exit_open(t);e.alloc_open(t,e.pending)
assert [r for r in e.orders if r['day']=='2024-09-23']==[r for r in orig if r['day']=='2024-09-23']
# Intentional held close invalidity: keep partial-day orders separately; certified outputs roll back completely.
d=Data('2024-09-23');d.raw['002736.SZ'].loc[pd.Timestamp('2024-09-23'),'price_eligible']=False;e=Engine(d).run();assert e.blockers and e.ledger[-1]['day']=='2024-09-20';assert all(r['day']<='2024-09-20' for r in e.orders);assert e.uncertified_day['partial_orders'];assert e.cash==D(e.ledger[-1]['cash'])
qa=dict(diagnostic_capture_exact_original_orders=True,OPEN_scrub_no_HLC_volume_eligibility_needed=True,invalid_CLOSE_rolls_back_entire_day=True,partial_orders_preserved_separately=True,no_strategy_parameter_change=True)
(O/'SUPPLEMENTAL_SYNTHETIC_QA.json').write_text(json.dumps(qa,indent=2)+'\n');print(qa)
