from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,pandas as pd,hashlib
O=Path(__file__).resolve().parent;R=O/'full_20241031_once';read=lambda p:json.loads(p.read_text());policies=read(O/'SUSPENSION_POLICY.json')['policies'];orders=read(R/'ORDERS.json');cp=read(R/'CP_EVENTS.json');held=read(R/'HOLDINGS.json');ledger=read(R/'DAY_LEDGER.json');pre=read(R/'PREFLIGHT_CHECKS.json');rows=[]
for p in policies:
 for l in ledger:
  d=l['day']
  if d not in p['covered_dates']:continue
  hs=[h for h in held if h['day']==d and h['sid']==p['sid']]
  if not hs:continue
  q=sum(h['qty'] for h in hs);mv=sum((D(h['market_value']) for h in hs),D(0));assert mv==q*D(p['raw_mark']);assert all(h['stale'] and not h['tradable'] and not h['observed_bar'] and h['mark_source_day']==p['mark_source_day'] for h in hs)
  assert not [x for x in orders if x['day']==d and x['sid']==p['sid']];assert not [x for x in cp if x['day']==d and x['sid']==p['sid']]
  checks=[x for x in pre if x['day']==d and x['sid']==p['sid']];assert len(checks)==1 and checks[0]['status']=='OFFICIAL_SUSPENSION_ANCHOR_ONLY' and checks[0]['effective_actions']==0
  rows.append(dict(day=d,sid=p['sid'],qty=q,raw_mark=p['raw_mark'],mark_source_day=p['mark_source_day'],market_value=str(mv),stale=True,tradable=False,orders=0,CP_events=0,locked_exits=[h['locked_exit'] for h in hs]))
for l in ledger:
 stale=sum((D(x['market_value']) for x in rows if x['day']==l['day']),D(0))
 if stale:assert D(l['stale_market_value'])==stale and l['net_liquidation_NAV'] is None and not l['whole_account_liquidation_available']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in read(O/'FREEZE.json')['hashes'].items())
(O/'SUSPENSION_POSITION_DAILY.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(rows).to_csv(O/'SUSPENSION_POSITION_DAILY.csv',index=False)
proof=dict(result='PASS_SELF_ACCOUNTING_BOUNDARY',certified_through=ledger[-1]['day'],account_days=len(ledger),whole_account_net_liquidation_available=ledger[-1]['net_liquidation_NAV'] is not None,stale_assets_last_day=ledger[-1].get('stale_market_value','0'),position_rows=rows,preflight_by_day={d:dict(Counter(x['status'] for x in pre if x['day']==d)) for d in sorted({x['day'] for x in pre})},no_suspended_order_or_CP_events=True,freeze_hashes_still_match=True,blockers=read(R/'BLOCKERS.json'))
(O/'SUSPENSION_BOUNDARY_SELF_CHECK.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof,ensure_ascii=False))
