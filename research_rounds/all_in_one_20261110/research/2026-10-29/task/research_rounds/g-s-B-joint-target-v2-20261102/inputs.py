"""Read original saved sources only; never step/replay the account."""
from selector import *
from dataclasses import asdict
sys.path.insert(0,str(W/'g-s-historical-native-nextsession-20261101'))
from gs_next_session import NextSessionRunner,original_guard
BASE=W/'g-s-historical-native-nextsession-20261101'
STATIC=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/g-s-static-capital-competition-v1')
def read(p):return json.loads(Path(p).read_text())
def case(k,day):
 index=read(STATIC/'PACKAGE_SHA256.json');p=STATIC/(k+'-COMPETITION.json');assert sha(p)==index[p.name]
 comp=read(p);rank={x['sid']:x for x in comp};cp=BASE/'run'/k/'close'/(day+'-CLOSE.pkl');r=NextSessionRunner.restore(cp);a=r.account;at=r.last_completed_event
 before=J.digest(r.observable(at));deadline=r.next_open(at).replace(hour=15,minute=10);old=r.lifecycle[-1]['allocation'];cuts={x['lot']:x for x in old['reductions']}
 active={eid:e for eid,e in a.policy.locks.items() if e.remaining}
 assert len(active)==len(cuts) and {e.lot for e in active.values()}==set(cuts)
 for eid,e in active.items():assert a.exit_duties[eid]['requested_at']==at and a.exit_duties[eid]['reasons']==['actionable_S_funding'] and e.remaining==cuts[e.lot]['q']
 assert not a.buys and not a.settlements and old['coverage']['assets']==[]
 rows=[];lots=[];actualrisk=Z;pre_risk=Z
 for ix,z in enumerate(a.layers):
  if not z['qty']:continue
  sid=z['sid'];m=a.capital_meta[z['id']];mark=a.market.prices[sid];floor=a.raw_floor(z);locked=[e for e in active.values() if e.lot==z['id']];qlock=sum(e.remaining for e in locked)
  assert a.market.known[sid]<=at
  ordinary=D(z['qty'])*max(Z,mark-floor);actualrisk+=D(z['qty']-qlock)*max(Z,mark-floor)+sum((e.charge(mark,floor) for e in locked),Z);pre_risk+=ordinary
  row=dict(id=z['id'],sid=sid,qty=z['qty'],mark=mark,floor=floor,sector=m['sector'],pool=m['pool'],role=m['role'],capital=D(z['qty'])*mark,risk=ordinary)
  rows.append(row)
  legal=bool(z['kind']!='core' and r.last_stock_state[sid]['i_valid'] is True and mark>floor and rank.get(sid,{}).get('existing_mobile'))
  sellable=sum(l.shares for l in a.positions[sid].lots if a._mapped_layer(l)==z['id'] and l.sellable_at<=r.next_open(at))
  lots.append(dict(row,purpose=m['purpose'],holding_S=a.policy.allowed(m['sector'],'S',holding=True),locked_capital=Z,donor_eligible=True,
    B_donor_eligible=legal,sellable_qty=sellable,quantity=asdict(a.market.quantity(sid,r.next_open(at))),fees=asdict(a.market.fees(sid,r.next_open(at))),fifo=ix,
    rank_key=[rank[sid]['priority_rank'],sid] if sid in rank else [10**9,sid],retention_legal=legal))
 base=dict(at=str(at),deadline=str(deadline),decision_nav=a.policy.nd,nav=a.nav(at),available=a.available,pending_fees=Z,rows=rows,lots=lots,assets=[],
   targets={s:a.policy.targets(s) for s in a.policy.k},account_id='G_S_R4_HISTORICAL|'+k,target_id='G_S_R4_HISTORICAL|'+k+'|capital-target-program',receipt_registry={},
   other_saved_goal_need=Z,analysis_only=True,source_checkpoint_sha256=sha(cp),source_input_sha256=sha(r.inputs.path))
 items={x['sid']:x for x in old['demand']};A=[];B=[];mother=[];pending={i['sid']:i for i in a.pending}
 for entry in comp:
  sid=entry['sid']
  if not entry['fresh_mobile']:continue
  i=pending[sid];c=i['receipt'];sec=i['sector'];assert c and a.receipt_verified(c) and c.confirmed==at and c.event_id not in a.policy.consumed and i['stock_q'] and i['i_valid']
  if a.policy.allowed(sec,'S'):use='S';target=a.policy.nd*D('.8');scope=sec
  elif a.policy.allowed('G','G'):use='G';target=a.policy.nd*D('.2');scope='G'
  else:raise AssertionError('frozen expansion mother drift')
  binding=dict(event_id=c.event_id,sid=c.sid,source=c.source,source_binding=c.source_binding,payload_sha256=c.payload_sha256,start=str(c.start),end=str(c.end),confirmed=str(c.confirmed),deadline=str(i['deadline']),structure=c.structure,scale=c.scale,market_context=a.policy.scopes[scope].context)
  base['receipt_registry'][c.event_id]=J.digest(binding)
  d=dict(sid=sid,sector=sec,priority=[entry['priority_rank'],sid],max_q=0,mark=a.market.prices[sid],floor=max(i['I_floor'],D(i['cp_floor']))/a.facts.factor(sid,at),role='mobile',pool='confirmed',use=use,
   eligible=True,receipt_valid=True,receipt_id=c.event_id,receipt_binding=binding,known_at=str(at),price_known_at=str(a.market.known[sid]),deadline=str(i['deadline']),industry_target=target,
   quantity=asdict(a.market.quantity(sid,r.next_open(at))),fees=asdict(a.market.fees(sid,r.next_open(at))))
  stock=sum((num(x,'capital') for x in rows if x['sid']==sid),Z);p=d['mark']*(ONE+SLIP)
  raw_budget=min(max(Z,a.policy.nd*D('.1')-stock),target)
  d['max_q']=J.rule(d['quantity']).buy_floor(int(raw_budget/p));B.append(d)
  if sid in items:
   aa=copy.deepcopy(d);aa.update(priority=list(i['priority']),max_q=items[sid]['q'],use='S',industry_target=a.policy.targets(sec));A.append(aa)
  mother.append(dict(sid=sid,name=entry['name'],sector=sec,rank=entry['competition_rank'],PVR=entry['PVR'],PVR_ready=entry['PVR_ready'],original_H1_rank=entry['original_H1_rank'],
    holding_mobile=entry['existing_mobile'],fresh=True,B_use=use,B_industry_ceiling=target,B_raw_budget=raw_budget,B_raw_max=d['max_q'],minimum=d['quantity']['buy_minimum'],
    A_raw_funding_max=items[sid]['q'] if sid in items else 0,A_scope_status='ORIGINAL_S_FUNDING_ITEM' if sid in items else 'NOT_IN_ORIGINAL_CLOSE_S_FUNDING_ITEMS_NOT_AN_OPENING_REJECTION',
    prior20_fill_capacity_upper=entry['candidate'].get('prior20_capacity_upper')))
 assert len(B)==(94 if k=='2025_26' else 29) and len(A)==len(items)
 assert {z['sid'] for z in lots if z['B_donor_eligible']}=={x['sid'] for x in comp if x['existing_mobile']}
 assert J.digest(r.observable(at))==before
 evidence=dict(common_point='AFTER_STOCK_F1_CLOSE_BEFORE_A_FUNDING_PLANNING_COMPARISON_ONLY',source_checkpoint=str(cp),source_checkpoint_sha256=sha(cp),static_competition_source=str(p if isinstance(p,Path) else STATIC/(k+'-COMPETITION.json')),
   static_competition_sha256=sha(STATIC/(k+'-COMPETITION.json')),actual_saved_risk=actualrisk,common_risk=pre_risk,only_same_close_A_lock_extra=actualrisk-pre_risk,
   actual_saved_funding_orders=len(active),actual_orders_not_cancelled=True,old_unreserved_planning_goals_preserved_in_source=old['coverage']['goals'],
   old_goal_additional_need_not_reused_as_current_new_authority=max(Z,old['coverage']['all_saved_target_need']-old['coverage']['raw_cash_need']),
   common_view_disclosure='Re-form CURRENT fresh conditional policy targets for BOTH hypotheses; no actual buy reserve/AR exists; do not install this view as account state or imply old exits cancelled. Old unreserved planning desires are not granted capital in either projection.',
   actual_account_unchanged=True,financial_events=0,A_scope='audited original CLOSE S-funding layer with JF2; not all next-OPEN G/T orders',B_scope='current fresh G/mature-S mobile target competition',
   same_financial_snapshot_for_A_B=J.digest(base),full_union=comp)
 return base,A,B,mother,evidence

def main():
 out=O/'inputs';out.mkdir(exist_ok=False);original_guard()
 for k,day in [('2025_26','2025-07-03'),('2022','2022-01-06')]:
  s,A,B,mother,evidence=case(k,day);save(out/(k+'.json'),dict(snapshot=s,A_demands=A,B_demands=B,mother=mother,evidence=evidence));print('INPUT_READY',k,len(A),len(B),flush=True)
if __name__=='__main__':main()
