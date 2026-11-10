"""Frozen research-only M5: acquisition roles and incremental-evidence expansion."""
from pathlib import Path
import sys, importlib.util, inspect, json, copy
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent; ROOT=O.parent; BASE=ROOT/'mainline_candidate_v4_known_sector_fix_v2'
sp=importlib.util.spec_from_file_location('m5_frozen_m4',BASE/'engine.py');m4=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m4;sp.loader.exec_module(m4)
m3=m4.m3;D=m4.D;ZERO=m4.ZERO;INITIAL=m4.INITIAL;SLIP=m4.SLIP;pd=m4.pd;dec=m4.dec;day=m4.day;finite=m4.finite;sha=m4.sha;save=m4.save;read=m4.read;Blocked=m4.Blocked
class Data(m4.Data):
 def __init__(self,end='2024-10-08'):
  super().__init__(end)
  for p in [O/'engine.py',O/'CONTRACT.md']:self.hashes[str(p)]=sha(p)
class Engine(m4.Engine):
 def order(self,a,d,side,q,p,reason,**kw):
  fee=super().order(a,d,side,q,p,reason,**kw)
  if side.startswith('BUY'):
   phase=self._execution_requests[a['sid']]['allocation_phase'];role='INITIAL' if side=='BUY_SEED' and phase in ['EVENT','RESIDUAL'] else 'EXPANSION'
   self.orders[-1]['capital_role']=role
   lot=next(l for l in a['lots'] if l['id']==kw['lot_id']);lot['capital_role']=role
  return fee
 def classify_reference(self,d):
  ref=super().classify_reference(d);fixed=dict(ref['sector_value']);core={s:ZERO for s in self.d.sector_ids};stress=ZERO;nxt=self.next_day(d);buys={o.get('lot_id'):o for o in self.orders if o['side'].startswith('BUY')}
  for r in ref['rows']:
   a=self.active[r['sid']];l=next(x for x in a['lots'] if x['id']==r['lot_id']);role=l.get('capital_role',buys.get(l['id'],{}).get('capital_role'));assert role in ['INITIAL','EXPANSION'],('MISSING_ACQUISITION_ROLE',r['lot_id'])
   cq=r['qty'] if role=='INITIAL' and r['current_winner'] and not r['locked'] else 0;mobile=r['mobile_qty'] if role=='INITIAL' else 0;reason=r['donor_reason'] if role=='INITIAL' else None
   if role=='EXPANSION' and not r['unknown'] and not r['locked'] and nxt>pd.Timestamp(r['bought']) and r['M'] in [0,1]:
    qr=self.d.getmeta(r['sid'],nxt)[0];mobile=qr.sell_floor(r['qty'],self.quantity(a));reason='NON_MAINLINE_EXPANSION' if r['M']==0 else 'MAINLINE_EXPANSION_SURPLUS'
   if r['sector51'] in self._probe_receiver_sectors:mobile=0
   mark=r['raw_mark'];fee_stress=mobile*mark-(mobile*mark*(1-SLIP)-self.d.fee(r['sid'],nxt,mobile,mark*(1-SLIP),'sell')) if mobile else ZERO
   r.update(capital_role=role,core_qty=cq,core_value=cq*mark,mobile_qty=mobile,mobile_value=mobile*mark,frozen_qty=r['qty']-mobile,frozen_value=(r['qty']-mobile)*mark,mobile_sell_stress=fee_stress,donor_reason=reason)
   sec=r['sector51'];fixed[sec]-=mobile*mark;core[sec]+=cq*mark;stress+=fee_stress
  weights={};evidence={};prev=self.d.cal[self.d.cal.get_loc(d)-1]
  for sec,E in ref['E'].items():
   z=self.d.main[sec];ep=z.at[prev,'E'] if prev in z.index else None;known=finite(ep);innovation=max(ZERO,E-dec(ep)) if known else ZERO;weights[sec]=E+innovation;evidence[sec]=dict(E=E,previous_E=dec(ep) if known else None,previous_E_known=known,positive_increment=innovation if known else None,W=weights[sec])
  outside=sum((v for sec,v in fixed.items() if sec not in ref['E']),ZERO);budget=ref['NAV']-ref['reserve']-self.receivable-outside-stress
  ref.update(fixed=fixed,core=core,lower={sec:fixed[sec] for sec in ref['E']},stress=stress,outside_fixed=outside,budget_before_event=budget,budget=budget,frozen_lot_qty={r['lot_id']:r['frozen_qty'] for r in ref['rows']},W=weights,evidence=evidence)
  assert all(r['core_qty']<=r['frozen_qty'] for r in ref['rows']);return ref
 def finalize_reference(self,d,event_by_sector):
  ref=self.reference;reserved=sum(event_by_sector.values(),ZERO);budget=ref['budget_before_event']-reserved;free=budget-sum(ref['lower'].values(),ZERO);weights=ref['W'];lam=free/sum(weights.values(),ZERO) if weights and free>=0 else None
  status='INFEASIBLE_LOWER_EXCEEDS_BUDGET' if free<0 else 'NO_POSITIVE_E_M' if not weights else 'PASS';residual=dict(ref['fixed'])
  if status=='PASS':
   for s,w in weights.items():residual[s]+=lam*w
  total={s:residual[s]+event_by_sector.get(s,ZERO) for s in self.d.sector_ids};envelope={s:max(ZERO,residual[s]-ref['sector_value'][s]) if status=='PASS' and s in weights else ZERO for s in self.d.sector_ids}
  ref.update(budget=budget,event_reserve=reserved,event_by_sector=dict(event_by_sector),T_residual=residual,T=total,lambda_value=lam,status=status,envelope=envelope,expansion_budget=free)
  assert reserved<=max(ZERO,ref['budget_before_event']-sum(ref['lower'].values(),ZERO))
  if status=='PASS':assert abs(sum((residual[s] for s in weights),ZERO)-budget)<=D('1e-18')*max(D(1),abs(budget))
  self.capital_lots.extend(ref['rows'])
  for s in self.d.sector_ids:
   z=self.d.main[s].loc[d];ev=ref['evidence'].get(s,{})
   self.reference_log.append(dict(day=day(d),sector51=s,M=int(z.M),E=dec(z.E) if finite(z.E) else None,actual_value=ref['sector_value'][s],core=ref['core'][s],other_frozen=ref['fixed'][s]-ref['core'][s],fixed=ref['fixed'][s],T=total[s],T_mature_residual=residual[s],event_reserved=event_by_sector.get(s,ZERO),buy_envelope=envelope[s],budget_before_event=ref['budget_before_event'],event_reserve_total=reserved,budget=budget,stress=ref['stress'],receivable=self.receivable,outside_fixed=ref['outside_fixed'],status=status,lambda_value=lam,expansion_budget=free,W=ev.get('W'),positive_E_increment=ev.get('positive_increment'),previous_E=ev.get('previous_E'),previous_E_known=ev.get('previous_E_known')))

def replace_once(s,a,b):
 assert s.count(a)==1,('HOOK_NOT_UNIQUE',a);return s.replace(a,b)
# Preserve all M4 planning/execution; only classify donor roles and permit partial expansion SEED.
src=inspect.getsource(m4.Engine.plan_transfers)
src=replace_once(src,' def plan_transfers','def plan_transfers')
src=replace_once(src,"tier=0 if r['kind']=='SEED' else 1 if r['donor_reason']=='WEAK_SECTOR_ADD_LAYER' else 2","tier=0 if r['capital_role']=='INITIAL' else 1 if r['M']==0 else 2")
src=replace_once(src,"q=maxq if r['kind']=='SEED' and maxq==r['qty'] else 0 if r['kind']=='SEED' else self.sell_quantity(s,nxt,p,gap,maxq,self.quantity(a))","q=(maxq if maxq==r['qty'] else 0) if r['capital_role']=='INITIAL' else self.sell_quantity(s,nxt,p,gap,maxq,self.quantity(a))")
ns=dict(globals());exec(compile(src,'M5_donor_plan_hooks','exec'),ns);Engine.plan_transfers=ns['plan_transfers']
src=inspect.getsource(m3.Engine.execute_transfers);src=replace_once(src,' def execute_transfers','def execute_transfers')
src=replace_once(src,"if l['kind']=='SEED':q=maxq if maxq==l['q'] else 0","if l['capital_role']=='INITIAL':q=maxq if maxq==l['q'] else 0")
exec(compile(src,'M5_donor_execution_hook','exec'),ns);Engine.execute_transfers=ns['execute_transfers']
# Same atomic state/log inventory as M4. Only redirect output directory; new role fields live in snapshotted lots/orders.
src=inspect.getsource(m4.run_loop);exec(compile(src,'M5_atomic_loop','exec'),globals())
if __name__=='__main__':
 assert read(O/'CONTRACT_APPROVAL.json')['approved'];assert read(O/'CONTRACT_APPROVAL.json')['engine_sha256']==sha(O/'engine.py');assert read(O/'CONTRACT_APPROVAL.json')['contract_sha256']==sha(O/'CONTRACT.md');assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert not (O/'RUN_STARTED.json').exists()
 data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')));save(O/'RUN_STARTED.json',dict(end='2024-10-08',time=str(pd.Timestamp.now(tz='UTC'))));e=run_loop(Engine(data));e.export(O/'once_20241008');save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None));print(json.dumps(read(O/'RUN_STATUS.json')))
