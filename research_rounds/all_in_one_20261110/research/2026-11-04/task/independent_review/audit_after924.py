"""Saved-layer wealth across fixed Oct8 boundary; no economic counterfactual."""
from decimal import Decimal as D
from collections import defaultdict,Counter
import json
import audit_pvr_saved as I
Z=D(0);O=I.TASK/'loss_correction/continuation2024_layers';BASE=I.TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024';CUT='2024-10-08'
def close(a,b):assert abs(D(str(a))-D(str(b)))<D('.00000001'),(a,b)
def main():
 src=I.read(O/'AFTER_924_LAYER_WEALTH_SOURCE.json')
 for p,h in src['sources'].items():assert I.sha(p)==h
 assert I.sha(I.TASK/'loss_correction/bridge_924_after.py')==src['script_sha256']
 result=I.read(O/'AFTER_924_LAYER_WEALTH_BRIDGE.json');campaigns=I.read(I.HERE/'PVR_2024_INDEPENDENT_AUDIT_CAMPAIGNS.json');answer={}
 for ref,side,key in [('PVR_BASELINE','original','PVR_SLOT1'),('PVR_NO60','no60','PVR_NO_CONFIRMED60')]:
  root=BASE/side/'run-2024/pair';b=I.read(root/'B.json.gz');daily=I.rows(root/'daily.jsonl.gz');cut=next(r for r in daily if r['at'][:10]==CUT);active={l['id']:l for l in cut['layers']};raw={l['id']:l for l in b['layers']}
  buys={t['layer']:t for t in b['trades']if t['side']=='buy'};assert len(buys)==sum(t['side']=='buy'for t in b['trades'])==len(raw)
  actions={};seen=set()
  for c in campaigns[key]:
   for j,lid in enumerate(c['layers']):actions[lid]='add_to_existing_stock'if j else'fresh_reentry_after_actual_flat'if c['sid']in seen else'first_actual_participation'
   seen.add(c['sid'])
  cash0=defaultdict(lambda:Z);cash1=defaultdict(lambda:Z);qty=defaultdict(int)
  events=[(t['at'],1,j,'trade',t)for j,t in enumerate(b['trades'])]+[(x['at'],0,j,'split',x)for j,x in enumerate(b['audit'])if x['kind']=='split']
  for stamp,_,_,kind,t in sorted(events,key=lambda x:x[:3]):
   if kind=='split':
    if stamp[:10]<=CUT:
     for lid,l in raw.items():
      if l['sid']==t['sid']and qty[lid]:
       q=D(qty[lid])*D(t['ratio']);assert q==int(q);qty[lid]=int(q)
    continue
   if t['side']=='buy':
    changes=[(t['layer'],-D(t['gross_cny'])-D(t['fees_cny']))]
    if stamp[:10]<=CUT:qty[t['layer']]+=t['shares']
   else:
    changes=[(x['layer'],D(x['net_cash']))for x in t['parts']]
    if stamp[:10]<=CUT:
     for x in t['parts']:qty[x['layer']]-=x['shares'];assert qty[x['layer']]>=0
   for lid,v in changes:
    cash1[lid]+=v
    if stamp[:10]<=CUT:cash0[lid]+=v
  assert {lid:q for lid,q in qty.items()if q}=={lid:x['qty']for lid,x in active.items()}
  rows=result[ref]['all_layer_rows'];assert {x['layer']for x in rows}==set(raw)
  groups=defaultdict(list)
  for r in rows:
   lid=r['layer'];l=raw[lid];close(l['cash'],cash1[lid]);close(r['buycash'],D(buys[lid]['gross_cny'])+D(buys[lid]['fees_cny']));assert r['action']==actions[lid]
   terminal=cash1[lid]+D(l['dividend'])+(D(l['qty'])*I.price(l['sid'],'2024-12-31')if l['qty']else Z)
   if buys[lid]['at'][:10]>CUT:cohort='new_fill_after_boundary';before=Z
   elif qty[lid]:
    cohort='actually_held_at_boundary';a=active[lid];close(a['cash'],cash0[lid]);before=cash0[lid]+D(a['dividend'])+D(qty[lid])*I.price(l['sid'],CUT)
   else:cohort='already_closed_at_boundary';before=cash0[lid]+D(l['dividend'])
   assert r['cohort']==cohort;close(r['boundary_wealth'],before);close(r['terminal_lifecycle_net'],terminal);close(r['after_boundary_wealth_change'],terminal-before);groups[cohort].append(r)
  for g,rr in groups.items():
   expected=result[ref]['groups'][g];assert expected['layers']==len(rr)and expected['stocks']==len({r['sid']for r in rr})
   close(expected['after_boundary_wealth_change'],sum((D(r['after_boundary_wealth_change'])for r in rr),Z))
  new=groups['new_fill_after_boundary'];assert len(new)==sum(t['side']=='buy'and t['at'][:10]>CUT for t in b['trades'])
  for a,x in result[ref]['newfill_actions'].items():
   rr=[r for r in new if r['action']==a];assert len(rr)==x['layers'];close(sum((D(r['after_boundary_wealth_change'])for r in rr),Z),x['after_boundary_wealth_change'])
  close(sum((D(r['boundary_wealth'])for r in rows),Z),D(cut['nav'])-1000000)
  close(sum((D(r['after_boundary_wealth_change'])for r in rows),Z),D(b['ending_NAV'])-D(cut['nav']))
  answer[ref]={'passed':True,'held_at_Oct8':result[ref]['groups']['actually_held_at_boundary'],'post_Oct8_buys_layers_fills':len(new),'post_Oct8_actions':result[ref]['newfill_actions'],'actual_phase_wealth_change':result[ref]['actual_after_wealth_change']}
 out={'passed':True,'arms':answer,'source_SHA_checks':len(src['sources']),'reviewer_source_SHA256':I.sha(__file__),'reviewer_account_events':0,'scope':'Each buy layer equals one actual buy fill in these saved books. First/add/reentry independently tied to actual stock-flat campaigns; every cashflow, split-adjusted boundary layer qty and frozen raw mark reconstructed. Per-layer dividend allocation uses saved native layer records while total claims/NAV are separately independently audited; not a second per-layer dividend entitlement calculation. Fixed Oct8 wealth subtraction, not a future trading rule, ordinary/tail membership attribution or profit from deleting new trades.'}
 (I.HERE/'PVR_AFTER924_LAYER_WEALTH_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps(out,indent=2,default=str))
if __name__=='__main__':main()
