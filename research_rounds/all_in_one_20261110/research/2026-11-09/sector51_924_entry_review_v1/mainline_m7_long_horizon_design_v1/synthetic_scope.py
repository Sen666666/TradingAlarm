from pathlib import Path
import importlib.util,sys,types,json
P=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('scope_test',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
x=e.Engine.__new__(e.Engine);x.d=types.SimpleNamespace(cal=e.pd.DatetimeIndex(['2026-06-26','2026-06-29','2026-06-30']))
for i in range(2):ok('known_next_session_'+str(i),x.next_day(x.d.cal[i])==e.v6.Engine.next_day(x,x.d.cal[i]))
try:x.next_day(x.d.cal[-1])
except e.Blocked as ex:ok('terminal_missing_calendar_atomic_block',str(ex)=='2026-06-30 NEXT_SESSION_CALENDAR_UNAVAILABLE')
else:raise AssertionError('terminal')
qa=e.self_check();ok('all_other_methods_identical',all(qa['economic_method_identity'].values()));ok('only_one_prefix_export',e.new_dates=="['2024-10-31']");ok('loop_identical_except_checkpoints',e.source.replace(e.new_dates,e.old_dates)==e.old_source)
# The inherited loop catches Blocked and restores snapshotted economic state.
ok('same_atomic_restore_boundary',"except Blocked as ex:" in e.source and "for k,v in snap.items():setattr(e,k,v)" in e.source)
class TerminalFail(e.Engine):
 def economic_preflight(self,d,pending):pass
 def accrue(self,d):pass
 def exit_open(self,d):pass
 def alloc_open(self,d,pending):self.cash-=e.v6.D(10)
 def close(self,d,prev):self.next_day(d)
 def scan_restored_targets(self,d,pending):return []
y=TerminalFail(types.SimpleNamespace(cal=x.d.cal,days=x.d.cal[-1:]))
import contextlib,io
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(y,False)
ok('terminal_guard_restores_partial_cash',y.cash==e.v6.D(1200000) and not y.ledger and y.blockers==['2026-06-30 NEXT_SESSION_CALENDAR_UNAVAILABLE'])
result=dict(result='PASS',total=len(checks),checks=checks,history_run=False,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'))
e.save(P/'SYNTHETIC_QA.json',result);print(json.dumps(result))
