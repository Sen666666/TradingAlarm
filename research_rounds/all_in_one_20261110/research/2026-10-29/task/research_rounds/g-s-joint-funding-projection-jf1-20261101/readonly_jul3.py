"""Extract saved account resources; no account step, order or journal mutation."""
from projector import *
from dataclasses import asdict
from datetime import datetime
import importlib.util,time
O=Path(__file__).resolve().parent;BASE=O.parent/'g-s-historical-native-nextsession-20261101'
sys.path.insert(0,str(BASE));from gs_next_session import NextSessionRunner,H,original_guard,sha
spec=importlib.util.spec_from_file_location('jf1_saved_mutable_view',H.OLD/'export-recovery/audit_state.py') if hasattr(H,'OLD') else None
def save(p,x):N.IO.write_json(p,json.loads(json.dumps(x,default=str)))
def extract():
 cp=BASE/'run/2025_26/close/2025-07-03-CLOSE.pkl';r=NextSessionRunner.restore(cp);a=r.account
 before=digest(r.observable(r.last_completed_event));at=r.last_completed_event;deadline=r.next_open(at).replace(hour=15,minute=10)
 oldplan=r.lifecycle[-1]['allocation'];parts={x['lot']:x for x in oldplan['reductions']};assert len(parts)==16
 active={eid:e for eid,e in a.policy.locks.items() if e.remaining}
 assert len(active)==16 and {e.lot for e in active.values()}==set(parts)
 for eid,e in active.items():
  duty=a.exit_duties[eid];assert duty['requested_at']==at and duty['reasons']==['actionable_S_funding'] and e.remaining==parts[e.lot]['q']
 assert oldplan['coverage']['assets']==[] and not a.buys and not a.settlements
 actual=[];pref=[];lots=[];actual_lots=[]
 for z in a.layers:
  if not z['qty']:continue
  sid=z['sid'];m=a.capital_meta[z['id']];mark=a.market.prices[sid];floor=a.raw_floor(z);factor=a.facts.factor(sid,at)
  assert a.market.known[sid]<=at
  capital=D(z['qty'])*mark;locked=[e for e in active.values() if e.lot==z['id']];lockedq=sum(e.remaining for e in locked)
  risk=D(z['qty']-lockedq)*max(Z,mark-floor)+sum((e.charge(mark,floor) for e in locked),Z)
  row=dict(id=z['id'],sid=sid,qty=z['qty'],mark=mark,floor=floor,sector=m['sector'],pool=m['pool'],role=m['role'],capital=capital,risk=risk)
  actual.append(row);pre=dict(row,risk=D(z['qty'])*max(Z,mark-floor));pref.append(pre)
  sellable=sum(l.shares for l in a.positions[sid].lots if a._mapped_layer(l)==z['id'] and l.sellable_at<=r.next_open(at))
  lot=dict(pre,purpose=m['purpose'],holding_S=a.policy.allowed(m['sector'],'S',holding=True),locked_capital=Z,donor_eligible=True,
    sellable_qty=sellable,quantity=asdict(a.market.quantity(sid,r.next_open(at))),fees=asdict(a.market.fees(sid,r.next_open(at))))
  lots.append(lot);actual_lots.append(dict(lot,risk=risk,locked_capital=D(lockedq)*mark,donor_eligible=not locked))
 ds=[];intents={i['sid']:i for i in a.pending}
 for x in oldplan['demand']:
  sid=x['sid'];i=intents[sid];c=i['receipt'];assert c is not None and a.receipt_verified(c) and c.confirmed==at and c.event_id not in a.policy.consumed
  ds.append(dict(sid=sid,sector=i['sector'],priority=i['priority'],max_q=x['q'],mark=a.market.prices[sid],floor=max(i['I_floor'],D(i['cp_floor']))/a.facts.factor(sid,at),
   role='mobile',pool='confirmed',use='S',eligible=bool(i['stock_q'] and i['i_valid'] and a.policy.allowed(i['sector'],'S')),receipt_valid=True,
   receipt_id=c.event_id,known_at=str(at),price_known_at=str(a.market.known[sid]),deadline=str(i['deadline']),industry_target=a.policy.targets(i['sector']),quantity=asdict(a.market.quantity(sid,r.next_open(at))),fees=asdict(a.market.fees(sid,r.next_open(at)))))
 common=dict(at=str(at),deadline=str(deadline),decision_nav=a.policy.nd,nav=a.nav(at),available=a.available,pending_fees=Z,
   targets={sec:a.policy.targets(sec) for sec in a.policy.k},source_checkpoint=str(cp),source_checkpoint_sha256=sha(cp),source_input_sha256=sha(r.inputs.path))
 pre=dict(common,rows=pref,lots=lots,assets=[],view='EXPLICIT_PRE_ORIGINAL_16_REQUEST_PLANNING_VIEW',
   reconstruction='only omit precisely identified same-close new funding proposal metadata from resource risk; quantities/cash/marks/floors/fees/old history unchanged; not an executable state restore')
 assets=[]
 for sid,o in a.exits.items():
  q=o.remaining_target;p=a.market.prices[sid]*(ONE-SLIP);fees=sum(a._fee(o,a.market.fees(sid,r.next_open(at)),'sell',D(q)*p,shares=q).values(),Z)
  ps=[]
  for e in active.values():
   if e.sid==sid:
    z=next(z for z in a.layers if z['id']==e.lot);ps.append(dict(layer=e.lot,q=e.remaining,risk_release=e.charge(a.market.prices[sid],a.raw_floor(z))))
  assets.append(dict(id='EXIT|'+o.event_id,kind='pending_exit',amount=D(q)*p-fees,due_at=str(r.next_open(at)),parts=ps,cancel_pending=False,pure_funding=True,sequence=a.funding.order_goals[o.event_id]['sequence']))
 saved=dict(common,rows=actual,lots=actual_lots,assets=assets,view='ACTUAL_SAVED_STATE_16_REQUESTS_RETAINED',
   other_saved_goal_need=max(Z,oldplan['coverage']['all_saved_target_need']-oldplan['coverage']['raw_cash_need']))
 assert sum((num(z,'risk') for z in actual),Z)==D('59259.69430901510614617723245')
 assert digest(r.observable(r.last_completed_event))==before
 return pre,saved,ds,oldplan,dict(checkpoint_sha256=sha(cp),saved_state_risk=sum((num(z,'risk') for z in actual),Z),pre_request_ordinary_risk=sum((num(z,'risk') for z in pref),Z),
   only_new_request_lock_charge_difference=sum((num(z,'risk') for z in actual),Z)-sum((num(z,'risk') for z in pref),Z),actual_saved_state_unchanged=True,financial_events=0)
def main():
 out=O/'jul3';out.mkdir(exist_ok=False);start=time.monotonic();original_guard();s,saved,ds,old,evidence=extract()
 save(out/'INPUT.json',dict(pre_request_view=s,actual_saved_state=saved,demands=ds,evidence=evidence))
 Q={d['sid']:d['max_q'] for d in ds};full=preview(s,ds,Q);full_saved=preview(saved,ds,Q)
 assert not full['validation']['ok'] and not full_saved['validation']['ok']
 assert any('account_risk6' in r for r in full['validation']['violations'])
 # Frozen original selector produces the exact old donor quantities and fees.
 assert [(x['layer'],x['q']) for x in full['donors']['rows']]==[(x['lot'],x['q']) for x in old['reductions']]
 assert sum((x['net'] for x in full['donors']['rows']),Z)==sum((D(x['estimated_net']) for x in old['reductions']),Z)
 final=solve(s,ds);saved_final=solve(saved,ds)
 save(out/'ORIGINAL_FULL_REJECTED.json',full);save(out/'ACTUAL_SAVED_FULL_REJECTED.json',full_saved)
 save(out/'FINAL_CERTIFICATE.json',final);save(out/'ACTUAL_SAVED_CERTIFICATE.json',saved_final)
 save(out/'SUMMARY.json',dict(passed=True,evidence=evidence,original_full_q=Q,final_Q=final['Q'],new_D=final['donors']['rows'],final_state=final['validation']['terminal'],
   conditional=final['validation'].get('conditional'),all_constraints_passed=final['validation']['ok'],whole_quantity_trials=len(final['trace']),original_selector_exact=True,
   actual_saved_state_result=dict(Q=saved_final['Q'],new_D=saved_final['donors']['rows'],old_pending_requests_retained=len(saved['assets']),warning='old 16 requests remain actual obligations; not retroactively removed'),seconds=time.monotonic()-start,financial_events=0))
 print(json.dumps(dict(passed=True,Q=final['Q'],new_D=final['donors']['rows'],trials=len(final['trace']),financial_events=0),default=str),flush=True)
if __name__=='__main__':main()
