"""Post-run per-lot realized price/fee PnL, excluding dividends. No strategy import."""
import argparse,json
from pathlib import Path
from decimal import Decimal as D
O=Path(__file__).resolve().parent;ap=argparse.ArgumentParser();ap.add_argument('run');a=ap.parse_args();P=O.parent/a.run/'once_20241031';read=lambda n:json.loads((P/(n+'.json')).read_text());orders=read('ORDERS');last=read('DAY_LEDGER')[-1]['day'];lots={};rows=[];Z=D(0)
for t in orders:
 if t['side'].startswith('BUY'):
  assert t['lot_id'] not in lots;lots[t['lot_id']]=dict(buy=t,remaining=t['qty']);continue
 qmap=t.get('lot_quantities') or {k:lots[k]['remaining'] for k in t['lots']}
 assert sum(qmap.values())==t['qty'],t
 allocated=Z
 for i,(k,q) in enumerate(qmap.items()):
  lot=lots[k];assert q<=lot['remaining'];b=lot['buy'];cost=-D(b['cash_delta'])*q/b['qty'];proceeds=D(t['cash_delta'])-allocated if i==len(qmap)-1 else D(t['cash_delta'])*q/t['qty'];allocated+=proceeds;lot['remaining']-=q
  if t['day']>'2024-10-08':rows.append(dict(day=t['day'],sid=t['sid'],name=t['name'],sector51=t['sector51'],lot_id=k,buy_day=b['day'],kind=b['side'],capital_role=b.get('capital_role','UNKNOWN'),qty=q,buy_all_in_allocated=str(cost),sell_net_allocated=str(proceeds),realized_price_fee_pnl=str(proceeds-cost),reason=t['reason'],lot_remaining_after=lot['remaining']))
summary=[]
for kind in ['BUY_SEED','BUY_ADD']:
 for role in ['INITIAL','EXPANSION','UNKNOWN']:
  rr=[r for r in rows if r['kind']==kind and r['capital_role']==role];loss=[r for r in rr if D(r['realized_price_fee_pnl'])<0]
  summary.append(dict(kind=kind,capital_role=role,sold_lot_parts=len(rr),net_price_fee_pnl=str(sum((D(r['realized_price_fee_pnl']) for r in rr),Z)),losing_parts=len(loss),loss_sum=str(sum((D(r['realized_price_fee_pnl']) for r in loss),Z))))
res=dict(through=last,summary=summary,rows=rows,caveats=['This is realized sold-lot price/fee PnL only, excluding dividends allocated at round level.','Lot quantities follow actual order lot_quantities; ordinary full-layer exits use remaining named lot quantities.','A profitable whole round may still contain a losing expansion layer. Partial sells are not independent failed rounds.','No hypothetical exit cost is charged to still-open lots.'])
out=O/(a.run+'__'+last);(out/'POST1008_REALIZED_LOT_PRICE_FEE_PNL.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))
