"""Actual native source sells -> settlements -> same-plan target buys.
Owner sets are batch-level support, not fictitious per-dollar attribution.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from datetime import datetime
import json
P=Path(__file__).resolve().parent;O=P/'analysis';Z=D(0)
def rd(p):return json.loads(Path(p).read_text())
def stamp(v):return datetime.fromisoformat(v).isoformat()
def main():
 names=rd(P/'full-August/metadata.json');allrows={}
 for cell in ['C10','C20','C10_R0','C20_R0']:
  q=rd(P/'runs'/cell/'PROGRESS.json');assert q['cursor']=='2025-08-29 15:10:00+08:00';x=rd(Path(q['checkpoint']).with_suffix('.json'));a=x['account'];g=x['goal_coverage'];trades={t['receipt_id']:t for t in a['trades']};batches={stamp(z['certificate']['known_at']):z for z in x['results']};rows=[]
  for oid,owner in a['funding_coverage']['order_goals'].items():
   original_at=owner['created_at'];batch=batches[stamp(original_at)];cert=batch['certificate'];cid=cert['certificate_id']
   sales=[trades[eid] for eid,v in g['sale_events'].items() if v['order']==oid and trades[eid]['at'].startswith('2025-08')]
   if not sales:continue
   ids=[z['settlement_id'] for z in sales];settled=[dict(settlement=s,**g['settled'][s]) for s in ids if s in g['settled']]
   assert all(s in g['receivables'] and g['receivables'][s]['origin_order']==oid for s in ids)
   buys=[]
   for eid,event in x['authority']['events'].items():
    ao=x['authority']['orders'][event['oid']]
    if ao['cid']==cid:buys.append(trades[eid])
   target_buys=[]
   for t in a['trades']:
    if t['side']!='buy' or not cert['Q'].get(t['security_id'],0) or not stamp(cert['known_at'])<=stamp(t['at'])<=stamp(cert['deadline']):continue
    m=a['capital_meta'][str(t['layer'])];s=a['supports'][m['order']]
    target_buys.append(dict(trade=t,role=m['role'],pool=m['pool'],purpose=m['purpose'],C_certificate=s.get('C_certificate'),same_certificate=s.get('C_certificate')==cid,source_settled_before_or_at_buy=any(stamp(z['at'])<=stamp(t['at']) for z in settled)))
   source=defaultdict(lambda:dict(shares=0,gross=Z,net=Z,fees=Z,reasons=[]))
   for s in sales:
    v=source[s['security_id']];v['shares']+=s['shares'];v['gross']+=D(s['gross_cny']);v['net']+=D(s['gross_cny'])-D(s['fees_cny']);v['fees']+=D(s['fees_cny']);v['reasons'].append(s['reason'])
   rows.append(dict(original_plan_at=original_at,certificate=cid,source_exit_order=oid,source_sales=[dict(sid=s,name=names[s]['name'],sector=names[s]['sector'],**v) for s,v in source.items()],actual_source_gross=sum((D(t['gross_cny']) for t in sales),Z),actual_source_net=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in sales),Z),actual_source_fills=sales,settlements=settled,owners=owner['goals'],planned_target_quantities={s:v for s,v in cert['Q'].items() if v},same_certificate_actual_C_buys=buys,actual_target_stock_buys_in_original_window_including_other_roles=target_buys,planned_D=cert['D'],same_stock_both_directions=bool(set(source)&{t['security_id'] for t in buys}),not_per_dollar_attribution=True,other_actual_cash_also_available=True))
  rows.sort(key=lambda z:-z['actual_source_gross']);allrows[cell]=rows
  (O/(cell+'-ACTUAL_FUNDING_FLOWS.json')).write_text(json.dumps(dict(definition='One row per native funding exit order with actual August sells, exact original plan and actual settlement ownership. Target buys are all SAME-certificate actual C buys, potentially shared by several source exits; do not sum repeated target buys across rows or claim dollar-level causality.',rows=rows),ensure_ascii=False,indent=2,default=str)+'\n')
 (O/'FUNDING_FLOW_SUMMARY.json').write_text(json.dumps({c:dict(source_orders=len(z),actual_source_gross=sum((r['actual_source_gross'] for r in z),Z),actual_source_net=sum((r['actual_source_net'] for r in z),Z),same_stock_both_directions_orders=sum(r['same_stock_both_directions'] for r in z),largest_orders=z[:3]) for c,z in allrows.items()},ensure_ascii=False,indent=2,default=str)+'\n')
 print('ACTUAL_FUNDING_FLOWS_READY',flush=True)
if __name__=='__main__':main()
