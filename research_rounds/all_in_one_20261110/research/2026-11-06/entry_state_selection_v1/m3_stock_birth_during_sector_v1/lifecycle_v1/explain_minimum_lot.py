from pathlib import Path
from decimal import Decimal as D
import json,sys
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parent
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids']
def fee(q,p,fs,side,par):return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=par).values(),D(0))
d=pd.read_csv(O/'DECISIONS.csv');ev=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv')
x=d[d.decision.eq('CLOSE_MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE')].merge(ev[['event_id','raw_close','factor','i_floor']],on='event_id',validate='many_to_one')
rows=[]
for r in x.to_dict('records'):
 sid=r['sid'];day=r['day'];ident=market_identity_on(rules,sid,day,proxies);v=version_on(rules['fee_versions'][ident['venue']],day,proxies)['schedule'];fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**c) for c in v['components']));qr=QuantityRule(**version_on(rules['quantity_versions'][sid],day,proxies)['rule']);q=qr.buy_minimum;par=D(str(rules['security_metadata'][sid]['par_value']))
 op=D(str(r['raw_close']));fl=D(str(r['i_floor']))/D(str(r['factor']));px=op*D('1.0005')
 cost=q*px+fee(q,px,fs,'buy',par);risk=max(D(0),q*(px-fl*D('.9995'))+fee(q,px,fs,'buy',par)+fee(q,fl*D('.9995'),fs,'sell',par))
 reasons=[]
 if cost>24000:reasons.append('MIN_LOT_NOMINAL_GT24000')
 if risk>3000:reasons.append('MIN_LOT_PLAN_RISK_GT3000')
 if q>r['prior20_capacity']:reasons.append('MIN_LOT_CAPACITY')
 assert reasons
 r.update(minimum_quantity=q,minimum_buy_cash=float(cost),minimum_plan_loss=float(risk),reason='|'.join(reasons),floor_distance=1-float(fl/op))
 rows.append(r)
out=pd.DataFrame(rows);out.to_csv(O/'MINIMUM_LOT_REJECTION_DETAILS.csv',index=False)
out.groupby(['window','arm','event_type','reason']).size().rename('count').reset_index().to_csv(O/'MINIMUM_LOT_REJECTION_COUNTS.csv',index=False)
print(out.groupby(['window','arm','event_type','reason']).size().to_string())
print('\nNamed2026')
print(out[out.window.eq('2026H1_SEMI')&out.arm.eq('A_UNION_B')&out.sid.isin(['688498.SH','603061.SH','301611.SZ','688008.SH','688536.SH'])][['day','sid','name','PVR_score','raw_close','minimum_quantity','minimum_buy_cash','minimum_plan_loss','reason']].to_string(index=False))
