from pathlib import Path
from decimal import Decimal as D
import json,gzip,ast,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
p=R/'act_only_ablation_continuous_v1/run/pair/PVR.json.gz';a=json.load(gzip.open(p,'rt'));r=R/'act_only_ablation_continuous_v1/analysis/STOCK_ROUNDS.csv';z=pd.read_csv(r,dtype=str);z=z[z.account.eq('PVR')&z.opened.str.startswith('2022-01-05')];rows=[]
for x in z.itertuples():
 ids=ast.literal_eval(x.layer_ids);core=int(x.initial_layer);cash=D(0);first=D(0);buys=0;sells=0
 for t in a['trades']:
  if t['side']=='buy' and t.get('layer') in ids:
   v=-(D(t['gross_cny'])+D(t['fees_cny']));cash+=v;buys+=1
   if t['layer']==core:first+=v
  if t['side']=='sell':
   for part in t.get('parts',[]):
    if part['layer'] in ids:
     v=D(part['net_cash']);cash+=v;sells+=1
     if part['layer']==core:first+=v
 assert D(x.booked_dividend_accrual)==0 and D(x.ending_quantity)==0 and D(x.split_events)==0
 assert abs(cash-D(x.pnl))<D('0.00000001') and abs(first-D(x.initial_layer_pnl))<D('0.00000001')
 rows.append(dict(sid=x.sid,round_id=x.round_id,original_layer_ids=x.layer_ids,closed=x.closed,buy_fills=buys,sell_parts=sells,cash_net=str(cash),first_layer_cash_net=str(first),full_win=cash>0,first_win=first>0,source_round_full_exact_within_1e8=True,source_round_first_exact_within_1e8=True))
pd.DataFrame(rows).to_csv(O/'INDEPENDENT_ACTUAL_CASH_RECONCILIATION.csv',index=False)
summary=dict(closed=52,full_W=sum(x['full_win'] for x in rows),first_W=sum(x['first_win'] for x in rows),full_net=str(sum(D(x['cash_net']) for x in rows)),first_net=str(sum(D(x['first_layer_cash_net']) for x in rows)),dividends=0,splits=0,ending_quantity=0,method='All actual buy gross+fees by original round layer IDs, all actual sell parts net_cash; no simulation, all retained',initial_diagnostic_note='First ad hoc inspection assumed every trade has layer; sell trades instead contain parts. It failed before producing a result. This cash audit uses actual sell-part net_cash, never drops sells without top-level layer.',source_hashes={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [p,r]})
(O/'CASH_RECONCILIATION_QA.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
