"""Only stress attributes differ; original frozen selector/controller/ledger."""
from pathlib import Path
import sys,importlib.util,copy,time,json,gzip,traceback,collections,pickle
from dataclasses import replace
from datetime import timedelta
import numpy as np
O=Path(__file__).resolve().parent;PREV=O.parent/'mainline-forward-Q1-20261031'
s=importlib.util.spec_from_file_location('pressure_frozen_Q1',PREV/'continuation.py');C=importlib.util.module_from_spec(s);sys.modules[s.name]=C;s.loader.exec_module(C);M,T,X=C.M,C.T,C.X
D=M.D;Z=D(0)
def migration_guard(state):
 a=state['account'];assert not a['buys'] and not a['exits'] and not a['daily_delay_credit'],'existing funded/waiting orders need separately reviewed migration semantics'
def actor(seed,shared,policy,refs,stress):
 r=C.Actor(seed,shared,policy,refs);a=r.accounts['T3'];a.cost_multiplier=2 if stress=='cost2' else 1;a.delay_events=1 if stress=='delay1' else 0
 assert not a.add_enabled and not a.add_credits
 expected=copy.deepcopy(seed['account']);expected.update(label='T3',rank_policy='T3',cost_multiplier=a.cost_multiplier,delay_events=a.delay_events)
 assert X.fingerprint({k:v for k,v in a.__dict__.items() if k not in X.EXCLUDE})==X.fingerprint(expected)
 return r
def ledger_tests():
 p=Path(M.C.L.__file__).parent;f=M.load('pressure_fixture_ledger',p/'test_sector_account.py');assert f.SectorAccount is M.C.L.SectorAccount
 L=f.SectorAccount;tests=[]
 def ok(name,x):assert x,name;tests.append(dict(test=name,passed=True))
 a=L(delay_events=1);a.reserve_budget(quote=f.quote(),clock=f.CLOCK,gross_budget_cny=1500);o=a.buys['A'];ok('unwaited_native_order_has_one_credit_to_spend',o.delay_remaining==1);w=f.window();ok('first_eligible_window_waits',a.fill_buy('A',w) is None and o.delay_remaining==0);used=len(a.used_events);ok('same_window_cannot_fill_or_wait_twice',a.fill_buy('A',w) is None and len(a.used_events)==used)
 restored=pickle.loads(pickle.dumps(a));ok('already_spent_wait_not_reset_on_restart',restored.buys['A'].delay_remaining==0 and restored.used_events==a.used_events);at=f.T+timedelta(days=1,hours=8);a.expire_day_buys(at);ok('zero_fill_day_expiry_releases_and_retains_native_credit',not a.buys and a.available==a.initial_cash and a.daily_delay_credit=={'A'});a.expire_day_buys(at+timedelta(days=1));ok('no_new_order_does_not_keep_old_credit_alive',not a.daily_delay_credit)
 a=L(delay_events=1);a.reserve_budget(quote=f.quote(),clock=f.CLOCK,gross_budget_cny=1500);a.expire_day_buys(at);ok('no_eligible_event_no_free_wait_credit',not a.daily_delay_credit)
 a=L();a.reserve_budget(quote=f.quote(),clock=f.CLOCK,gross_budget_cny=2500);a.fill_buy('A',f.window(capacity=100));q=a.quantity('A');paid=a.fees_cny;a.expire_day_buys(at);ok('partial_expiry_keeps_real_shares_no_full_rearm',q==100 and a.quantity('A')==100 and not a.buys and not a.daily_delay_credit and paid==a.fees_cny)
 from types import SimpleNamespace
 i=dict(sid='A',kind='core',floor=D('8'),cap=1000,budget=D('4000'),risk_budget=D('500'),quote=f.quote(fees=f.MINIMUM),weight=1)
 M.C.activate(SimpleNamespace(cost_multiplier=1));n,_=M.LR.preview(copy.deepcopy(i),D(10),D(1),f.RULE,f.MINIMUM);M.C.activate(SimpleNamespace(cost_multiplier=2));c,_=M.LR.preview(copy.deepcopy(i),D(10),D(1),f.RULE,f.MINIMUM);ok('cost2_rechecks_frozen_budget_and_never_adds_shares',c['maxq']<=n['maxq']<=i['cap'] and D(c['maxq'])*c['price']<=i['budget']);M.C.activate(SimpleNamespace(cost_multiplier=1))
 fake=dict(account=dict(buys={'partial':'not silently migrated'},exits={},daily_delay_credit=set()))
 try:migration_guard(fake);raise AssertionError('expected blocked ambiguous boundary')
 except AssertionError as e:ok('unexpected_boundary_order_stops_instead_of_guessing','expected blocked' not in str(e))
 return tests
def normal_equal(r,root,name,end):
 old=C.obj(root/'results'/f'{name}.json.gz');ds=[dict(z,account='T3') for z in C.rows(root/'results/daily.jsonl.gz') if z['account']==name and z['at'][:10]<=end];a=r.accounts['T3'];assert X.canon(r.daily)==X.canon(ds)
 for key,got in [('trades',a.trades),('decisions',a.decisions),('audit',a.audit_log)]:
  exp=[z for z in old[key] if (z.get('at') or z.get('receipt',{}).get('at') or z.get('receivable',{}).get('ex_at') or '')[:10]<=end];assert X.canon(got)==X.canon(exp),(name,key)
def main():
 prep=time.monotonic();tests=ledger_tests();assert M.read(PREV/'COMPLETION.json')['passed'];assert all(M.sha(p)==h for p,h in M.read(PREV/'FREEZE.json')['sha256'].items());seed=T.original_seed();migration_guard(seed);X.configure();shared=M.context();refs=M.read(PREV/'RAW_MARKET_REFERENCES.json');boundary=dict(held=len(seed['account']['positions']),pending_intents=len(seed['account']['pending']),buys=len(seed['account']['buys']),sells=len(seed['account']['exits']),credit=list(seed['account']['daily_delay_credit']),earliest_intents=sorted({i['clock'].earliest_execution_at.isoformat() for i in seed['account']['pending']}));prefix='2025-10-15';gates=[]
 for pol,root,name in [('RAW',C.ABS,'RAW'),('ATT',C.ATT,'T3')]:
  r=actor(seed,shared,pol,refs,'normal');r.run_from('2025-09-30',prefix);normal_equal(r,root,name,prefix);gates.append(dict(policy=pol,normal_off_exact=True))
 small=C.physical_view(shared,prefix);measured=[]
 for pol in ['RAW','ATT']:
  for stress in ['cost2','delay1']:
   r=actor(seed,shared,pol,refs,stress);r.run_from('2025-09-30',prefix);z=actor(seed,small,pol,refs,stress);z.run_from('2025-09-30',prefix);assert X.canon(C.observable(r))==X.canon(C.observable(z));measured.append(dict(policy=pol,stress=stress,closes=len(r.daily),seconds=r.run_seconds,prefix_exact=True))
 # Sequential unchanged executor, measured short segment, with original Q1
 # full-path timings also shown rather than promising an invented speed.
 estimate=sum(z['seconds']/z['closes']*116 for z in measured)
 M.save(O/'GATE.json',dict(passed=True,preparation_seconds=time.monotonic()-prep,tests=tests,normal_off=gates,boundary=boundary,prefix=prefix,pressure_prefix=measured,short_segment_extrapolation_seconds=estimate,estimate_excludes_output=True,existing_normal_four_half_paths_seconds=122.0129190827715))
 print('GATE_PASSED',dict(prep_seconds=time.monotonic()-prep,estimate_seconds=estimate,measured=measured),flush=True)
 files=[O/'PROTOCOL.txt',O/'pressure.py',PREV/'continuation.py',C.ATT/'attention.py',C.ABS/'seed.chk',PREV/'FREEZE.json',PREV/'RAW_MARKET_REFERENCES.json',C.ABS/'recovery.csv'];M.save(O/'FREEZE.json',dict(before_four_paths=True,paths=[f'{p}_{s}' for s in ['cost2','delay1'] for p in ['RAW','ATT']],same_normal_boundary=True,sha256={str(p):M.sha(p) for p in files}))
 if estimate>240:M.save(O/'BUDGET_PREFLIGHT.json',dict(blocked=True,estimated_run_seconds=estimate,budget_seconds=240,reason='short-segment measured estimate above authorized budget; no economic path started'));print('BUDGET_PREFLIGHT_BLOCK',estimate,flush=True);return
 timer=time.monotonic();progress=[];ends={}
 for stress in ['cost2','delay1']:
  for pol in ['RAW','ATT']:
   remaining=240-(time.monotonic()-timer);key=pol+'_'+stress
   if remaining<45:M.save(O/'BUDGET_BLOCK.json',dict(completed=progress,remaining_seconds=remaining,pending=key));return
   print('START',key,'remaining',remaining,flush=True);r=actor(seed,shared,pol,refs,stress)
   try:r.run_from('2025-09-30','2026-03-31',remaining)
   except BaseException:r.dump(O/key/'failed-partial');raise
   r.dump(O/key/'results');ends[key]=C.pack(r,'2026-03-31');a=r.accounts['T3'];progress.append(dict(path=key,run_seconds=r.run_seconds,NAV=str(a.current_nav)));M.save(O/'PROGRESS.json',progress);nav=np.r_[float(seed['account']['current_nav']),[float(z['nav']) for z in r.daily]];print('PRESSURE_RESULT',key,dict(return_suffix=float(nav[-1]/nav[0]-1),DD=float((1-nav/np.maximum.accumulate(nav)).max()),NAV=float(nav[-1]),seconds=r.run_seconds,total_seconds=time.monotonic()-timer),flush=True)
 C.write_checkpoint(O/'end-2026-03-31.chk',ends);M.save(O/'ECONOMIC_DONE.json',dict(passed=True,paths=4,run_seconds=sum(p['run_seconds'] for p in progress),with_output_seconds=time.monotonic()-timer,progress=progress,normal_reused=True,no_new_variant=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
