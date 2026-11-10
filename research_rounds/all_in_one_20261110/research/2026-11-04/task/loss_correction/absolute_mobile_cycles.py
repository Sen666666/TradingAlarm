"""Actual mobile flat-to-flat sleeves while core may survive; saved trades only."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime
import json
import absolute_retries as R
P,O,W,Z=R.P,R.O,R.W,R.Z
def save(n,x):R.save(n,x)
def main():
 summary={}
 for scope,root in [('2022_2023',P.parent/'pvr_pool_feasibility/continuation2023/run-2023'),('strong',P.parent/'pvr_pool_feasibility/runs/2025_26')]:
  b=R.gz(root/'pair/B.json.gz');ll=R.read(O/('PVR_NO60-'+scope+'-JOINED_ENTRIES.json'));lm={x['layer']:x for x in ll};q=defaultdict(int);sid={};roles={};cycles=Counter();evermobile=set();lidcycle={};groups=defaultdict(list);entries=[];lastmobileclose={};fraction=[]
  events=[(datetime.fromisoformat(t['at']),1,i,'trade',t) for i,t in enumerate(b['trades'])]+[(datetime.fromisoformat(a['at']),0,i,'split',a) for i,a in enumerate(b['audit']) if a['kind']=='split']
  for at,_,_,kind,t in sorted(events,key=lambda x:x[:3]):
   if kind=='split':
    for lid,v in list(q.items()):
     if sid[lid]==t['sid'] and v:
      exact=D(v)*D(t['ratio']);assert exact==int(exact),'fraction needs non-trade cost review';q[lid]=int(exact)
   elif t['side']=='buy':
    lid=t['layer'];s=t['security_id'];l=lm[lid];livecore=sum(v for k,v in q.items() if sid[k]==s and roles[k]=='core');livemobile=sum(v for k,v in q.items() if sid[k]==s and roles[k]=='mobile');assert livecore+livemobile==l['quantity_before']
    if l['role']=='mobile':
     if livemobile:category='expand_existing_live_mobile_sleeve'
     elif livecore and set(lastmobileclose.get(s,{}).get('surviving_core_layer_ids',[])) & {k for k,v in q.items() if v and sid[k]==s and roles[k]=='core'}:category='refill_mobile_after_mobile_flat_with_core_surviving'
     elif livecore:category='first_mobile_on_existing_core'
     else:category='flat_whole_stock_fresh_mobile'
     if not livemobile:cycles[s]+=1
     key=(s,cycles[s]);lidcycle[lid]=key;groups[key].append(lid);entries.append(dict(l,actual_mobile_cycle=cycles[s],actual_mobile_entry_class=category,actual_core_quantity_before=livecore,actual_mobile_quantity_before=livemobile,previous_actual_mobile_clearance=lastmobileclose.get(s)));evermobile.add(s)
    q[lid]=t['shares'];sid[lid]=s;roles[lid]=l['role']
   else:
    s=t['security_id'];before=sum(v for k,v in q.items() if sid[k]==s and roles[k]=='mobile')
    for z in t['parts']:q[z['layer']]-=z['shares'];assert q[z['layer']]>=0
    after=sum(v for k,v in q.items() if sid[k]==s and roles[k]=='mobile')
    if before and not after:lastmobileclose[s]=dict(at=t['at'],reasons=sorted({z['reason'] for z in t['parts'] if roles[z['layer']]=='mobile'}),remaining_core_quantity=sum(v for k,v in q.items() if sid[k]==s and roles[k]=='core'),surviving_core_layer_ids=[k for k,v in q.items() if v and sid[k]==s and roles[k]=='core'])
  assert all(q[x['id']]==x['qty'] for x in b['layers']);assert len(entries)==sum(x['role']=='mobile' for x in ll)
  em={x['layer']:x for x in entries};gg=[]
  for (s,cy),ids in groups.items():
   ls=[lm[lid] for lid in ids];first=em[ids[0]];cost=sum((R.n(l['cost']) for l in ls),Z);net=sum((R.n(l['net']) for l in ls),Z)
   gg.append(dict(sid=s,name=first['name'],mobile_cycle=cy,first_entry_class=first['actual_mobile_entry_class'],first_entry_signal=first['signal_day'],opened=first['opened'],layer_ids=ids,closed=not any(q[lid] for lid in ids),terminal_return_on_buycash=net/cost,terminal_tail30=net/cost>=D('.3'),original_cached_E0s=sorted({str(x['cached_E0_epoch']) for x in ls}),**R.agg(ls)))
  cohorts={k:R.agg([x for x in entries if x['actual_mobile_entry_class']==k]) for k in sorted({x['actual_mobile_entry_class'] for x in entries})};refills=[x for x in gg if x['first_entry_class']=='refill_mobile_after_mobile_flat_with_core_surviving']
  tails=[x for x in refills if x['terminal_tail30']]
  summary[scope]=dict(cohorts=cohorts,mobile_cycles=len(gg),refill_cycles_while_core_survives=len(refills),refill_cycles_terminal_negative=sum(x['net']<0 for x in refills),refill_cycle_all_layers=sum(x['layers'] for x in refills),refill_cycle_buy_cash=sum((x['buy_cash'] for x in refills),Z),refill_cycle_net=sum((x['net'] for x in refills),Z),refill_cycle_negative_net=sum((x['net'] for x in refills if x['net']<0),Z),refill_cycle_positive_net=sum((x['net'] for x in refills if x['net']>0),Z),refill_tail_cycles=len(tails),refill_tail_net=sum((x['net'] for x in tails),Z),actual_terminal_each_layer_quantity_exact=True,scope='mobile sleeve flat-to-flat differs from whole-stock flat; all fresh canonical receipts retained, no synthetic retry signal or economic counterfactual')
  save('PVR_NO60-'+scope+'-MOBILE_CYCLE_ENTRIES.json',entries);save('PVR_NO60-'+scope+'-MOBILE_CYCLES.json',gg)
 save('MOBILE_CYCLE_SUMMARY.json',summary);save('SOURCE_BINDING-MOBILE-CYCLES.json',dict(sources=R.SRC,script_sha256=R.sha(__file__),account_events=0,quantity_replay_only=True));print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))
if __name__=='__main__':main()
