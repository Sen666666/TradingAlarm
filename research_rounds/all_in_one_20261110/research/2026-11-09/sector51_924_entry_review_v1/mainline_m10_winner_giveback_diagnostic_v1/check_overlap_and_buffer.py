import json,hashlib
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
P=Path(__file__).parent;R=P.parent
old=R/'mainline_winner_giveback_diagnostic_v1/analyze.py';ns={'__file__':str(P/'check_overlap_and_buffer.py')};exec(compile(old.read_text().split('paths={')[0],str(old),'exec'),ns);read,fee=ns['read'],ns['fee'];hashes=ns['hashes'];data={};sales={};buyby={};cashlot={}
for label,rel in [('M7','mainline_m7_long_horizon_sealed_v2/once_20260630'),('M10','mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106')]:
 z={k:read(R/rel/(k+'.json')) for k in ['ORDERS','HOLDINGS','CANDIDATES','EQUITY_EVENTS']};data[label]=z;inv={};bb={};ss=defaultdict(list);cl=defaultdict(lambda:D(0))
 for o in z['ORDERS']:
  if o['side'].startswith('BUY'):
   lid=o['lot_id'];inv[lid]=o['qty'];bb[lid]=o;cl[lid,o['day']]+=D(o['cash_delta'])
  else:
   qtys=o.get('lot_quantities') or {lid:inv[lid] for lid in o['lots']};assert sum(qtys.values())==o['qty'],(label,o,qtys)
   for lid,q in qtys.items():
    inv[lid]-=q;assert inv[lid]>=0;cash=D(o['cash_delta'])*D(q)/D(o['qty']);cl[lid,o['day']]+=cash;ss[lid].append(dict(day=o['day'],qty=q,price=o['price'],allocated_fee=D(o['fee'])*D(q)/D(o['qty']),cash_delta=cash,reason=o.get('lot_reasons',{}).get(lid,o['reason']),aggregate_reason=o['reason'],order_seq=o['order_seq']))
 sales[label]=ss;buyby[label]=bb;cashlot[label]=cl
m7initial={ (o['sid'],o['round_id'].split('|')[-1],o['day']):o for o in buyby['M7'].values() if o.get('capital_role')=='INITIAL'}
comparison=[]
for lid,ss in sales['M10'].items():
 for sale in ss:
  if sale['reason']!='POSITIVE_CP_INITIAL_PROTECTION':continue
  b=buyby['M10'][lid];match=m7initial.get((b['sid'],b['round_id'].split('|')[-1],b['day']));bs=sales['M7'][match['lot_id']] if match else [];same=sum(s['qty'] for s in bs if s['day']==sale['day']);before=sum(s['qty'] for s in bs if s['day']<sale['day']);after=sum(s['qty'] for s in bs if s['day']>sale['day']);common=min(b['qty'],match['qty']) if match else 0;newextra=max(0,b['qty']-(match['qty'] if match else 0));classification='SAME_DAY_SAME_QTY' if same==sale['qty'] else 'EARLIER_THAN_M7' if after>=sale['qty'] else 'LATER_THAN_M7' if before>=sale['qty'] else 'MIXED_OR_ADDITIONAL_QTY'
  comparison.append(dict(sid=b['sid'],name=b['name'],round_id=b['round_id'],lot_id=lid,M10_buy_qty=b['qty'],M7_buy_qty=match['qty'] if match else None,M10_sale=sale,M7_sales=bs,same_day_M7_initial_qty=same,M7_sold_before_qty=before,M7_sold_after_qty=after,unmatched_extra_initial_buy_qty=newextra,classification=classification,same_day_same_price=all(s['price']==sale['price'] for s in bs if s['day']==sale['day']) if same else False))
# Reconstruct effective layered-pressure snapshots independently, PER LOT fees.
z=data['M10'];groups=defaultdict(list);og=defaultdict(list);eqg=defaultdict(list)
for h in z['HOLDINGS']:groups[h['round_id'],h['day']].append(h)
for o in z['ORDERS']:og[o['round_id']].append(o)
for e in z['EQUITY_EVENTS']:
 if e.get('round_id') and e['event']=='ACCRUE_NET80':eqg[e['round_id']].append(e)
snaps={}
for (rid,dt),hs in groups.items():
 cash=sum((D(o['cash_delta']) for o in og[rid] if o['day']<=dt),D(0));div=sum((D(e['receivable_delta']) for e in eqg[rid] if e['day']<=dt),D(0));pro={}
 for h in hs:
  raw=D(h['effective_protection_signal'])/D(h['factor']);px=raw*D('.9995');pro[h['lot_id']]=dict(qty=h['qty'],kind=h['kind'],signal=h['effective_protection_signal'],factor=h['factor'],raw_floor=raw,proceeds=h['qty']*px-fee(h['sid'],dt,h['qty'],px))
 snaps[rid,dt]=dict(day=dt,cashflow=cash,dividend=div,lots=pro,net=cash+div+sum((v['proceeds'] for v in pro.values()),D(0)))
ad=[c for c in z['CANDIDATES'] if c.get('event')=='M10_INITIAL_CP_ADMISSION' and c['decision']=='ADOPT'];first={}
for c in ad:first.setdefault(c['lot_id'],c)
cross=[]
for lid,a in first.items():
 rid=a['round_id'];dates=sorted(dt for rr,dt in snaps if rr==rid);active=[snaps[rid,dt] for dt in dates if dt>a['day'] and lid in snaps[rid,dt]['lots']];neg=[sn for sn in active if sn['net']<=0]
 if not neg:continue
 now=neg[0];dt=now['day'];pdt=max(d for d in dates if d<dt);prev=snaps[rid,pdt];ops=[o for o in og[rid] if o['day']==dt];divdelta=now['dividend']-prev['dividend'];components=[]
 for ll in sorted(set(now['lots'])|set(prev['lots'])):
  pp=prev['lots'].get(ll,{});nn=now['lots'].get(ll,{});cashdelta=cashlot['M10'][ll,dt];floorchange=nn.get('proceeds',D(0))-pp.get('proceeds',D(0));components.append(dict(lot_id=ll,kind=buyby['M10'][ll]['side'],bought=buyby['M10'][ll]['day'],previous=pp,current=nn,day_cashflow=cashdelta,floor_proceeds_change=floorchange,net_buffer_change=cashdelta+floorchange))
 assert abs(sum((c['net_buffer_change'] for c in components),D(0))+divdelta-(now['net']-prev['net']))<D('1e-18'),(rid,dt,components,now,prev)
 cross.append(dict(sid=a['sid'],round_id=rid,initial_lot_id=lid,first_adoption_day=a['day'],first_adoption_layer_net=a['layered_pressure_after']['net'],first_nonpositive_day=dt,previous_day=pdt,previous_layer_net=prev['net'],current_layer_net=now['net'],dividend_change=divdelta,day_orders=ops,exact_lot_buffer_components=components))
res=dict(classification_counts=dict(Counter(c['classification'] for c in comparison)),economic_exit_matches=comparison,adopted_lots=len(first),later_nonpositive_active_initial_lots=len(cross),later_nonpositive_rounds=len(set(c['round_id'] for c in cross)),buffer_recrossings=cross,source_hashes=hashes,limits=['Matched INITIAL identity by sid + round signal date + actual buy date, then exact quantities and execution price; mixed-order fee allocation can differ even at same price.','Buffer recrossing counts only completed CLOSE snapshots AFTER first adoption while adopted INITIAL still survives. OPEN gap losses on exit day may never appear as negative CLOSE pressure.','Per-lot net_buffer_change = same-day allocated order cashflow + change in hypothetical effective-floor proceeds (per-lot fee). Summed components + round dividend delta exactly equal pressure-net change; this is accounting decomposition, not strategy counterfactual.'])
(P/'OVERLAP_AND_BUFFER.json').write_text(json.dumps(res,ensure_ascii=False,indent=2,default=str))
print(json.dumps(res,ensure_ascii=False,default=str))
