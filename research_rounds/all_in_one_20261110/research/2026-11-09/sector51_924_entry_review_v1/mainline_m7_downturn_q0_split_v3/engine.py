"""Frozen M7 extension with reviewed Q0-only split/cash bridge. No held split or suspension accounting."""
from pathlib import Path
import sys, importlib.util, inspect, json, copy, argparse, collections
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
BASE=O.parent/'mainline_candidate_v7_demand_capped'
sp=importlib.util.spec_from_file_location('extension_frozen_m7',BASE/'engine.py')
m7=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m7;sp.loader.exec_module(m7)
read=m7.read;save=m7.save;sha=m7.sha;day=m7.day;pd=m7.pd;Blocked=m7.Blocked
FROZEN_ENGINE='804d56f8b5a8e4b26d5a89caac5874c037911a38c339db9c6dfd5e99882aab6a'
assert sha(BASE/'engine.py')==FROZEN_ENGINE
# Admissions/source inventories describe the requested full horizon, not prefix state.
EXCLUDED={'SOURCE_HASHES','OUTPUT_HASHES','EVENT_ADMISSION'}
FAMILIES=sorted(p.stem for p in (BASE/'once_20241008').glob('*.json') if p.stem not in EXCLUDED)

def check_prefix(path):
 checks={}
 for n in FAMILIES:
  a=read(path/(n+'.json'));b=read(BASE/'once_20241008'/(n+'.json'))
  mode='exact_ordered'
  if a!=b and n=='AVAILABILITY_EVENTS':
   # Existing M2 emits only this diagnostic through unordered set iteration.
   assert collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in b),('PREFIX_MISMATCH',n)
   mode='full_record_multiset_unordered_diagnostic'
  else:assert a==b,('PREFIX_MISMATCH',n)
  checks[n]={'comparison':mode,'count':len(a) if hasattr(a,'__len__') else None}
 save(O/'M7_PREFIX_QA.json',dict(result='PASS',through='2024-10-08',m7_engine_sha256=FROZEN_ENGINE,families=checks,exclusions=sorted(EXCLUDED)))

SID='605499.SH';EX_DATE='2024-10-09';RECORD_DATE='2024-10-08'

FACT_PATH=O.parent/'retained_605499_split_cash_evidence_v1/Q0_ONLY_EVENT_FACTS.json'
FACT_SHA='f7e7ff5994fbefd843eaf3e378b1ab4b6b2df1baf62f67a9009f4f8c891b962d'
class Data(m7.Data):
 def __init__(self,end='2024-10-31'):
  super().__init__(end)
  assert sha(FACT_PATH)==FACT_SHA
  self.hashes[str(FACT_PATH)]=FACT_SHA
  records=read(FACT_PATH);assert len(records)==1
  ev=records[0];s=ev['sid'];dt=pd.Timestamp(ev['ex_date'])
  assert s==SID and ev['ex_date']==EX_DATE and ev['record_date']==RECORD_DATE
  assert ev['pay_date']==EX_DATE and ev['new_shares_sellable_at']==EX_DATE
  assert ev['admission_scope']=='ZERO_HOLDING_NEVER_SEEDED_RETAINED_TICKET_ONLY' and ev['held_split_supported'] is False
  assert m7.dec(ev['split_ratio'])==m7.D('1.30') and m7.dec(ev['d_source'])==m7.D('2.50') and ev['d_cash']==ev['d_source']
  paths=dict(ev['evidence_hashes'])
  for stem in ['source_fact','signal','local_action']:paths[ev[stem+'_path']]=ev[stem+'_sha256']
  paths[ev['notice']['pdf_path']]=ev['notice']['pdf_sha256']
  for path,h in paths.items():assert sha(Path(path))==h,('Q0_FACT_DRIFT',path);self.hashes[path]=h
  for path in [O/'engine.py',O/'CONTRACT.md',O/'synthetic_q0.py']:self.hashes[str(path)]=sha(path)
  if dt>self.end:return
  assert (s,dt) not in self.events
  terms=[a for a in self.actions[s]['events'] if a['effective_date']==EX_DATE];assert len(terms)==1
  assert m7.dec(terms[0]['split_ratio'])==m7.dec(ev['split_ratio']) and m7.dec(terms[0]['cash_per_old_share'])==m7.dec(ev['d_source'])
  z=self.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt]
  assert day(prev.name)==RECORD_DATE and m7.m3.valid(prev) and m7.m3.valid(cur)
  assert m7.m3.lineage(prev)==m7.m3.lineage(cur)==tuple(ev['source_lineage'])
  fo=m7.dec(prev.adjustment_factor);fn=m7.dec(cur.adjustment_factor);pc=m7.dec(prev.raw_close)
  assert abs(fo/m7.dec(ev['factor_old'])-1)<m7.D('1e-11') and abs(fn/m7.dec(ev['factor_new'])-1)<m7.D('1e-11')
  assert abs(fo*pc*m7.dec(ev['split_ratio'])/(pc-m7.dec(ev['d_source']))/fn-1)<m7.D('1e-11')
  self.events[(s,dt)]=dict(ev,q0_never_seeded_only=True)
  self.admission.append(dict(sid=s,ex_date=EX_DATE,event_id=ev['economic_event_id_candidate'],status='REVIEWED_Q0_ONLY_SPLIT_CASH',held_split_supported=False,factor_bridge_verified=True,not_PIT=True,not_production_admission=True))

def q0_guard(e,d,pending):
 if day(d)!=EX_DATE:return None
 def require(v,reason):
  if not v:raise Blocked(f'{day(d)} {SID} Q0_SPLIT_SCOPE_{reason}')
 t=e.tickets.get(SID);snap=e.snapshots.get((SID,RECORD_DATE))
 require(t is not None and t.get('ever_seeded') is False and t.get('status') not in ('CANCELLED','CONSUMED'),'LIVE_NEVER_SEEDED_TICKET_REQUIRED')
 require(SID not in e.active,'ACTIVE_POSITION')
 require(not any(a['sid']==SID for a in e.archive.values()),'HISTORICAL_ROUND')
 require(not any(o['sid']==SID for o in e.orders),'HISTORICAL_ORDER')
 require(snap is not None and snap.get('q')==0 and snap.get('round') is None,'EXPLICIT_ZERO_RECORD_SNAPSHOT_REQUIRED')
 require(not any(k[0]==SID for k in e.claims),'EXISTING_ENTITLEMENT')
 require(not any(r['sid']==SID for r in pending) and t.get('plan') is None,'PENDING_REQUEST')
 require(not any(r['sid']==SID for r in e.transfer_plan),'TRANSFER_REQUEST')
 z=e.d.z(SID,d);ev=e.d.events.get((SID,d))
 require(ev is not None and ev.get('q0_never_seeded_only') is True,'REVIEWED_Q0_EVENT_REQUIRED')
 require(tuple(m7.m3.lineage(z))==tuple(t.get('origin') or ()),'SOURCE_CHANGED')
 def checked_factor(value,label):
  try:v=m7.dec(value)
  except (ArithmeticError,TypeError,ValueError):
   raise Blocked(f'{day(d)} {SID} Q0_SPLIT_SCOPE_{label}_MISSING_OR_INVALID') from None
  require(v.is_finite() and v>0,label+'_MISSING_OR_INVALID')
  return v
 current=checked_factor(t.get('current_factor'),'TICKET_FACTOR')
 observed=checked_factor(z.get('adjustment_factor'),'OBSERVED_FACTOR')
 old=checked_factor(ev.get('factor_old'),'EVENT_OLD_FACTOR')
 new=checked_factor(ev.get('factor_new'),'EVENT_NEW_FACTOR')
 require(abs(current/old-1)<=m7.D('1e-11'),'OLD_FACTOR')
 require(abs(observed/new-1)<=m7.D('1e-11'),'NEW_FACTOR')
 return copy.deepcopy(t)

class Engine(m7.Engine):
 def register_pay(self,d):
  if day(d)==RECORD_DATE and (SID in self.active or any(k[0]==SID for k in self.claims)):
   raise Blocked(f'{day(d)} {SID} Q0_SPLIT_RECORD_ENTITLEMENT_FORBIDDEN')
  return super().register_pay(d)
 def economic_preflight(self,d,pending):
  balances=(self.cash,self.receivable,copy.deepcopy(self.claims),sum(self.quantity(a) for a in self.active.values()),sum(a['dividend'] for a in self.archive.values()))
  before=q0_guard(self,d,pending)
  super().economic_preflight(d,pending)
  if before is not None:
   if balances!=(self.cash,self.receivable,self.claims,sum(self.quantity(a) for a in self.active.values()),sum(a['dividend'] for a in self.archive.values())):raise Blocked(f'{day(d)} {SID} Q0_SPLIT_ENTITLEMENT_MUTATION')
   after=self.tickets[SID]
   if {k:v for k,v in before.items() if k not in ('current_factor','last_verified_day')}!={k:v for k,v in after.items() if k not in ('current_factor','last_verified_day')}:
    raise Blocked(f'{day(d)} {SID} Q0_SPLIT_TICKET_IDENTITY_MUTATED')
   self.equity.append(dict(day=day(d),sid=SID,event='Q0_SPLIT_BRIDGE_VERIFIED_NO_ENTITLEMENT',record_qty=0,ex_preexecution_qty=0,cash_delta='0',receivable_delta='0',share_delta=0,ticket_id=after['ticket_id'],factor_old=str(before['current_factor']),factor_new=str(after['current_factor']),original_NAV=str(after['nav0']),original_I=str(after['original_ifloor'])))

 def export(self,path):
  super().export(path)
  if Path(path).name=='checkpoint_20241008':check_prefix(path)

# Run loop is byte-identical source, rebinding only output path and export subclass.
source=inspect.getsource(m7.m4.run_loop)
exec(compile(source,'UNCHANGED_M7_ATOMIC_LOOP','exec'),globals())

def self_check():
 methods={n:getattr(Engine,n) is getattr(m7.Engine,n) for n in dir(m7.Engine) if not n.startswith('__') and callable(getattr(m7.Engine,n)) and n not in ('export','economic_preflight','register_pay')}
 assert all(methods.values())
 assert len(FAMILIES)>=30 and 'REFERENCE_AT_END' in FAMILIES
 assert run_loop.__code__.co_code==m7.run_loop.__code__.co_code and run_loop.__code__.co_consts==m7.run_loop.__code__.co_consts
 return dict(result='PASS',economic_method_identity=methods,atomic_loop_source_identical=True,prefix_families=FAMILIES,suspension_changes_installed=False,q0_guard_only_preflight_override=True,history_run=False)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],required=True);args=ap.parse_args()
 save(O/'STATIC_QA.json',self_check())
 if args.mode=='run':
  approval=read(O/'CONTRACT_APPROVAL.json')
  assert approval['approved'] and approval['engine_sha256']==sha(O/'engine.py') and approval['contract_sha256']==sha(O/'CONTRACT.md')
  assert read(O/'SYNTHETIC_QA.json')['result']=='PASS'
  assert not (O/'RUN_STARTED.json').exists()
  assert read(BASE/'RUN_STATUS.json')['days']==20 and not read(BASE/'RUN_STATUS.json')['blockers']
  data=Data(end='2024-10-31')
  save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,m7_engine_sha256=FROZEN_ENGINE,wrapper_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')))
  save(O/'RUN_STARTED.json',dict(end='2024-10-31',time=str(pd.Timestamp.now(tz='UTC'))))
  e=run_loop(Engine(data));e.export(O/'once_20241031')
  save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,prefix_pass=(O/'M7_PREFIX_QA.json').exists(),planned_end='2024-10-31',completed_horizon=bool(e.ledger and e.ledger[-1]['day']=='2024-10-31' and not e.blockers)))
  print(json.dumps(read(O/'RUN_STATUS.json')))
