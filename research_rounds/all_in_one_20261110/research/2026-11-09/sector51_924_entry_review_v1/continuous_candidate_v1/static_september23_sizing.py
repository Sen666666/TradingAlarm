from pathlib import Path
from decimal import Decimal as D
import json,sys
sys.dont_write_bytecode=True
import pandas as pd
from engine import Data,O
x=json.loads((O/'ADD_OPEN_PROTECTIONS_AND_DOWNSIDE.json').read_text());d=Data('2024-09-23');dt=pd.Timestamp('2024-09-23');rows=[]
base=json.loads((O/'full_20241031_once/DAY_LEDGER.json').read_text());b=next(r for r in base if r['day']=='2024-09-23');cash=D(b['cash']);mv=D(b['market_value']);oldcost=D(0);newcost=D(0)
for r in x:
 if r['day']!='2024-09-23':continue
 s=r['sid'];q=r['prior_qty'];qr,_,_=d.getmeta(s,dt);q=qr.buy_floor(q);p=D(r['execution_price']);f=d.fee(s,dt,q,p,'buy');cost=q*p+f;fp=D(r['new_ADD_floor_raw'])*D('.9995');sf=d.fee(s,dt,q,fp,'sell');risk=cost-q*fp+sf;p_pre=D(r['attempt_net_before_ADD']);cl=D(str(d.z(s,dt)['raw_close']));old=D(r['all_in_cost']);oldq=r['qty'];oldcost+=old;newcost+=cost;cash+=old-cost;mv-=(oldq-q)*cl
 rows.append(dict(sid=s,name=r['name'],raw_open=r['raw_open'],execution_price=str(p),existing_qty=r['prior_qty'],static_new_qty=q,buy_fee=str(f),all_in_cost=str(cost),prior_attempt_net_profit=str(p_pre),protect_raw=r['new_ADD_floor_raw'],sell_fee_at_protection=str(sf),incremental_floor_loss_R_new=str(risk),alpha_example='1',R_new_le_profit_pre=bool(risk<=p_pre),minimum_legal_qty=qr.buy_minimum,minimum_legal_lot_profit_covered=bool(risk<=p_pre),note='Static 2024-09-23 action comparison only; no subsequent path replay'))
summary=dict(date='2024-09-23',original_three_add_cost=str(oldcost),static_three_100share_add_cost=str(newcost),static_cash=str(cash),static_market_value=str(mv),static_NAV=str(cash+mv),static_weight_pct=str(100*mv/(cash+mv)),original_market_value=b['market_value'],original_NAV=b['NAV'],original_weight_pct=b['weight_pct'],changed_actions_only='Three actual Sep23 ADD quantities become 100 each; all actual seeds and pre-Sep23 cashflows held fixed',not_continuous_strategy_backtest=True,no_optimization=True)
pd.DataFrame(rows).to_csv(O/'STATIC_20240923_DOUBLING_AND_PROFIT_COVER.csv',index=False);(O/'STATIC_20240923_SIZING_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(pd.DataFrame(rows).to_string(index=False));print(json.dumps(summary))
