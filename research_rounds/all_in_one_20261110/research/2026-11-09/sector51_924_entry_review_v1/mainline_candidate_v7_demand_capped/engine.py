"""M7: current independent legal demand caps expansion targets. Research only."""
from pathlib import Path
import sys, importlib.util, inspect, json, copy
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent; ROOT=O.parent; BASE=ROOT/'mainline_candidate_v6_mature_round_cap'
sp=importlib.util.spec_from_file_location('m7_frozen_m6',BASE/'engine.py');m6=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m6;sp.loader.exec_module(m6)
m5=m6.m5;m4=m6.m4;m3=m6.m3;D=m6.D;ZERO=m6.ZERO;INITIAL=m6.INITIAL;SLIP=m6.SLIP;pd=m6.pd;dec=m6.dec;day=m6.day;finite=m6.finite;sha=m6.sha;save=m6.save;read=m6.read;Blocked=m6.Blocked
assert sha(BASE/'engine.py')=='5cdfa190071396559f1dbb97c9dd7fc4f89ec501766f2d63bbe3d2b3f24064e8'

def capped_water(weights,upper,budget):
 """Unique capped proportional allocation; K is not a lower bound."""
 assert set(weights)==set(upper)
 assert all(w>0 for w in weights.values()) and all(u>=0 for u in upper.values())
 target=min(max(ZERO,budget),sum(upper.values(),ZERO));remaining=target
 out={s:ZERO for s in weights};active=set(weights);lam=ZERO
 while active:
  lam=remaining/sum((weights[s] for s in sorted(active)),ZERO)
  capped=[s for s in sorted(active) if upper[s]<=lam*weights[s]]
  if not capped:
   for s in sorted(active):out[s]=lam*weights[s]
   break
  for s in capped:out[s]=upper[s];remaining-=upper[s];active.remove(s)
 # All capped: choose the smallest lambda satisfying every cap.
 if not active and weights:lam=max((upper[s]/weights[s] for s in weights),default=ZERO)
 tol=D('1e-18')*max(D(1),abs(target))
 assert abs(sum(out.values(),ZERO)-target)<=tol
 assert all(ZERO<=out[s]<=upper[s] for s in out)
 return out,lam,max(ZERO,budget-target)

class Data(m6.Data):
 def __init__(self,end='2024-10-08'):
  super().__init__(end)
  for p in [O/'engine.py',O/'CONTRACT.md']:self.hashes[str(p)]=sha(p)

class Engine(m6.Engine):
 def plan_requests(self,d,reqs):
  # This context is intentionally not persistent state. finally also handles Blocked.
  assert not hasattr(self,'_m7_raw_requests')
  self._m7_raw_requests=reqs
  try:return super().plan_requests(d,reqs)
  finally:del self._m7_raw_requests

 def independent_mature_demand(self,d):
  ref=self.reference;reqs=self._m7_raw_requests;nav=ref['NAV'];nxt=self.next_day(d)
  sv={s:self.qvalue(a,d,'raw_close') for s,a in self.active.items()}
  # EVENT reservations already exist; targets/cash/donor proceeds do not enter.
  for r in reqs:
   if r.get('allocation_phase')=='EVENT' and r.get('_ref_q',0)>0:
    s=r['sid'];sv[s]=sv.get(s,ZERO)+r['_reference_close_cost']
  demand={s:ZERO for s in self.d.sector_ids};details=[];seen=set()
  mature=[r for r in reqs if r.get('allocation_phase')=='MATURE']
  def key(r):
   sec=self.d.sid_sector[r['sid']]
   if r['kind']=='ADD':return (sec,0,r.get('cp_date',r['signal_day']),r['sid'])
   if r.get('score_known'):return (sec,1,*self.stock_key(r))
   return (sec,2,r['signal_day'],r['sid'])
  for r in sorted(mature,key=key):
   s=r['sid'];sec=self.d.sid_sector[s];ident=(s,r['kind'],r.get('cp_id') if r['kind']=='ADD' else None)
   before=sv.get(s,ZERO);q=0;cost=ZERO;caps={};p=None
   if ident in seen:reason='DUPLICATE_CURRENT_REQUEST'
   else:
    seen.add(ident)
    if sec not in ref['W'] or r['M']!=1 or r['E']<=0:reason='NOT_POSITIVE_E_MAINLINE'
    elif r['kind']=='SEED' and not r.get('score_known'):reason='REPRESENTATIVE_UNKNOWN'
    else:
     x=self.noncash(r,d,'raw_close',nav,sv);q=x['q'];p=x['p'];caps=x['caps'];reason=x['reason']
     if r['kind']=='ADD' and q:
      q=self.d.size(s,nxt,p,min(caps.values()),q)
      if not q:reason='ADD_NO_LEGAL_Q_NEXT_DATED_RULES'
     cost=q*p+self.d.fee(s,nxt,q,p,'buy') if q else ZERO
     # Match inherited planning's next-session dated quantity/fee re-sizing.
     # No 4% round slot and no target/reference/cash cap is added here.
     if q:sv[s]=before+cost;demand[sec]+=cost
   details.append(dict(day=day(d),sid=s,sector51=sec,kind=r['kind'],cp_id=r.get('cp_id'),signal_day=r['signal_day'],allocation_phase='MATURE',independent_q=q,independent_all_in_cost=cost,decision=reason,stock_value_before=before,stock_value_after=sv.get(s,ZERO),independent_caps=caps,price=p,planned_q=r['planned_q'],capacity=r['capacity'],excludes_reference_cash_and_donor_proceeds=True))
  return demand,details

 def finalize_reference(self,d,event_by_sector):
  ref=self.reference;reserved=sum(event_by_sector.values(),ZERO);budget=ref['budget_before_event']-reserved;free=budget-sum(ref['lower'].values(),ZERO);weights=ref['W']
  demand,details=self.independent_mature_demand(d)
  mobile={s:ref['sector_value'][s]-ref['fixed'][s] for s in self.d.sector_ids}
  upper={s:mobile[s]+demand[s] for s in weights}
  status='INFEASIBLE_LOWER_EXCEEDS_BUDGET' if free<0 else 'NO_POSITIVE_E_M' if not weights else 'PASS'
  x={s:ZERO for s in self.d.sector_ids};lam=None;unallocated=max(ZERO,free)
  if status=='PASS':allocated,lam,unallocated=capped_water(weights,upper,free);x.update(allocated)
  residual={s:ref['fixed'][s]+x[s] for s in self.d.sector_ids}
  total={s:residual[s]+event_by_sector.get(s,ZERO) for s in self.d.sector_ids}
  envelope={s:max(ZERO,x[s]-mobile[s]) if status=='PASS' and s in weights else ZERO for s in self.d.sector_ids}
  ref.update(budget=budget,event_reserve=reserved,event_by_sector=dict(event_by_sector),T_residual=residual,T=total,lambda_value=lam,status=status,envelope=envelope,expansion_budget=free,D=demand,K=mobile,U={s:mobile[s]+demand[s] for s in self.d.sector_ids},X=x,unallocated_expansion_budget=unallocated,independent_demand_details=details)
  assert reserved<=max(ZERO,ref['budget_before_event']-sum(ref['lower'].values(),ZERO))
  assert all(v>=0 for v in mobile.values())
  self.capital_lots.extend(ref['rows'])
  for s in self.d.sector_ids:
   z=self.d.main[s].loc[d];ev=ref['evidence'].get(s,{})
   self.reference_log.append(dict(day=day(d),sector51=s,M=int(z.M),E=dec(z.E) if finite(z.E) else None,actual_value=ref['sector_value'][s],core=ref['core'][s],other_frozen=ref['fixed'][s]-ref['core'][s],fixed=ref['fixed'][s],T=total[s],T_mature_residual=residual[s],event_reserved=event_by_sector.get(s,ZERO),buy_envelope=envelope[s],budget_before_event=ref['budget_before_event'],event_reserve_total=reserved,budget=budget,stress=ref['stress'],receivable=self.receivable,outside_fixed=ref['outside_fixed'],status=status,lambda_value=lam,expansion_budget=free,W=ev.get('W'),positive_E_increment=ev.get('positive_increment'),previous_E=ev.get('previous_E'),previous_E_known=ev.get('previous_E_known'),D=demand[s],K=mobile[s],U=mobile[s]+demand[s],X=x[s],unallocated_expansion_budget=unallocated,independent_demand_details=[r for r in details if r['sector51']==s]))

# Exact inherited atomic state/log inventory, with new diagnostics inside reference.
source=inspect.getsource(m4.run_loop);exec(compile(source,'M7_atomic_loop','exec'),globals())
if __name__=='__main__':
 ap=read(O/'CONTRACT_APPROVAL.json');assert ap['approved'] and ap['engine_sha256']==sha(O/'engine.py') and ap['contract_sha256']==sha(O/'CONTRACT.md');assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert not (O/'RUN_STARTED.json').exists()
 data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')));save(O/'RUN_STARTED.json',dict(end='2024-10-08',time=str(pd.Timestamp.now(tz='UTC'))));e=run_loop(Engine(data));e.export(O/'once_20241008');save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None));print(json.dumps(read(O/'RUN_STATUS.json')))
