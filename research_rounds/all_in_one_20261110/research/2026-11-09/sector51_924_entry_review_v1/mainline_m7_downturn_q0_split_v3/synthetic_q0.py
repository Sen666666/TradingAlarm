"""Synthetic Q0 bridge tests; no historical strategy run."""
from pathlib import Path
import importlib.util,sys,copy,types,json
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('q0_engine_test',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
D=e.m7.D;sid=e.SID;dt=e.pd.Timestamp(e.EX_DATE);record=e.pd.Timestamp(e.RECORD_DATE);checks=[]
def ok(name,value=True):
 assert value,name
 checks.append(name)
def fixture():
 x=e.Engine.__new__(e.Engine);ev=dict(e.read(e.FACT_PATH)[0],q0_never_seeded_only=True);origin=tuple(ev['source_lineage'])
 z=e.pd.Series(dict(raw_open=211.79,raw_close=210.0,adjustment_factor=float(ev['factor_new']),source_kind=origin[0],source_path=origin[1],segment_id=origin[2]))
 x.d=types.SimpleNamespace(z=lambda s,d:z,action=lambda s,d:[dict(split_ratio='1.30',cash_per_old_share='2.50')],events={(sid,dt):ev})
 x.cash=D(1200000);x.receivable=D(0);x.active={};x.archive={};x.orders=[];x.claims={};x.snapshots={(sid,e.RECORD_DATE):dict(q=0,round=None)};x.transfer_plan=[]
 x.tickets={sid:dict(sid=sid,ticket_id='synthetic',ever_seeded=False,status='PAUSED',origin=origin,current_factor=D(ev['factor_old']),original_factor=D(ev['factor_old']),nav0=D(100000),budget=D(2000),original_ifloor=D(200),ifloor=D(200),signal_day='2024-09-26',plan=None,last_verified_day=e.RECORD_DATE)}
 x.quote_gaps={};x._preflight_excluded=set();x.availability=[];x.ticket_log=[];x.equity=[];x.last_targets=[]
 return x
x=fixture();before=copy.deepcopy(x.tickets[sid]);x.economic_preflight(dt,[])
ok('normal_retained_bridge_updates_factor',x.tickets[sid]['current_factor']==D(e.read(e.FACT_PATH)[0]['factor_new']))
ok('ticket_identity_nav_I_preserved',all(x.tickets[sid][k]==v for k,v in before.items() if k not in ['current_factor','last_verified_day']))
ok('preflight_no_entitlement',x.cash==D(1200000) and x.receivable==0 and not x.claims and not x.active and not x.archive and not x.orders)
x.accrue(dt);x.register_pay(dt)
ok('inherited_accrue_and_payment_zero',x.cash==D(1200000) and x.receivable==0 and not x.claims)
ok('only_zero_equity_diagnostics',all(r['record_qty']==0 and r['cash_delta']=='0' and r['receivable_delta']=='0' for r in x.equity))
x=fixture();x.snapshots={};x.register_pay(record);ok('record_explicit_zero_snapshot',x.snapshots[(sid,e.RECORD_DATE)]==dict(q=0,round=None) and not x.equity)
def reject(name,mutate,pending=None):
 x=fixture();mutate(x)
 try:x.economic_preflight(dt,pending or [])
 except e.Blocked:ok(name)
 else:raise AssertionError(name)
reject('missing_snapshot_blocks',lambda x:x.snapshots.clear())
reject('nonzero_record_qty_blocks',lambda x:x.snapshots[(sid,e.RECORD_DATE)].update(q=100))
reject('record_round_even_zero_blocks',lambda x:x.snapshots[(sid,e.RECORD_DATE)].update(round='old'))
reject('active_position_blocks',lambda x:x.active.update({sid:dict(sid=sid,lots=[dict(q=100)])}))
reject('historical_round_blocks',lambda x:x.archive.update({'old':dict(sid=sid,dividend=D(0))}))
reject('historical_order_blocks',lambda x:x.orders.append(dict(sid=sid)))
reject('prior_entitlement_blocks',lambda x:x.claims.update({(sid,dt):dict(amount=D(1))}))
reject('pending_request_blocks',lambda x:None,[dict(sid=sid)])
reject('ticket_plan_blocks',lambda x:x.tickets[sid].update(plan=dict(sid=sid)))
reject('transfer_request_blocks',lambda x:x.transfer_plan.append(dict(sid=sid)))
reject('ever_seeded_blocks',lambda x:x.tickets[sid].update(ever_seeded=True))
reject('cancelled_ticket_blocks',lambda x:x.tickets[sid].update(status='CANCELLED'))
reject('missing_ticket_blocks',lambda x:x.tickets.clear())
reject('unreviewed_event_blocks',lambda x:x.d.events[(sid,dt)].update(q0_never_seeded_only=False))
reject('changed_source_blocks',lambda x:x.tickets[sid].update(origin=('different','source','0')))
reject('wrong_old_factor_blocks',lambda x:x.tickets[sid].update(current_factor=D(1)))
reject('wrong_new_factor_blocks',lambda x:x.d.events[(sid,dt)].update(factor_new='2'))
# All four factor locations fail atomically on absent/nonfinite/nonpositive data.
for location in ['ticket','observed','event_old','event_new']:
 for value in [None,'NaN','Infinity','-Infinity','0','-1','invalid']:
  def mutate(x,location=location,value=value):
   if location=='ticket':x.tickets[sid]['current_factor']=value
   elif location=='observed':x.d.z(sid,dt)['adjustment_factor']=value
   elif location=='event_old':x.d.events[(sid,dt)]['factor_old']=value
   else:x.d.events[(sid,dt)]['factor_new']=value
  reject('invalid_factor_'+location+'_'+str(value),mutate)
for location in ['ticket','observed','event_old','event_new']:
 def remove(x,location=location):
  if location=='ticket':x.tickets[sid].pop('current_factor')
  elif location=='observed':x.d.z(sid,dt).drop('adjustment_factor',inplace=True)
  elif location=='event_old':x.d.events[(sid,dt)].pop('factor_old')
  else:x.d.events[(sid,dt)].pop('factor_new')
 reject('missing_factor_'+location,remove)
x=fixture();x.active={sid:dict(lots=[dict(q=100)])}
try:x.register_pay(record)
except e.Blocked:ok('record_holdings_stop_before_registration',x.snapshots[(sid,e.RECORD_DATE)]['q']==0)
else:raise AssertionError('record guard')
x=fixture();old=copy.deepcopy(x.__dict__);ok('other_date_guard_noop',e.q0_guard(x,record,[]) is None and x.tickets==old['tickets'])
# Existing atomic inventory snapshots every object changed by new guards/diagnostics.
src=e.source
ok('existing_atomic_inventory_covers_new_changes',all("'"+n+"'" in src for n in ['tickets','snapshots','cash','receivable','claims','equity']))
ok('all_non_boundary_methods_identical',all(e.self_check()['economic_method_identity'].values()))
# Force a later failure after the successful new bridge and verify full rollback.
class LateFailure(e.Engine):
 def exit_open(self,d):pass
 def alloc_open(self,d,pending):pass
 def close(self,d,prev):
  self.cash-=D(10);self.equity.append(dict(event='FORCED_PARTIAL'));raise e.Blocked('FORCED_AFTER_Q0_BRIDGE')
 def scan_restored_targets(self,d,pending):return []
f=fixture();x=LateFailure(f.d);x.tickets=copy.deepcopy(f.tickets);x.snapshots=copy.deepcopy(f.snapshots)
x.d.cal=e.pd.DatetimeIndex([record,dt]);x.d.days=e.pd.DatetimeIndex([dt])
before=copy.deepcopy(x.tickets)
import contextlib,io
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(x,False)
ok('forced_late_block_restores_ticket_factor',x.tickets==before)
ok('forced_late_block_restores_cash_equity_claims',x.cash==D(1200000) and x.receivable==0 and not x.equity and not x.claims and not x.ticket_log)
ok('forced_late_block_no_committed_day',not x.ledger and x.blockers==['FORCED_AFTER_Q0_BRIDGE'])
out=dict(result='PASS',checks=checks,total=len(checks),history_run=False,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'))
e.save(P/'SYNTHETIC_QA.json',out);print(json.dumps(out))
