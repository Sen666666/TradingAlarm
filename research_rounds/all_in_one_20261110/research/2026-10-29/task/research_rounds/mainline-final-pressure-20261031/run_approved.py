"""Resume passed gates; authorized four paths, 300s runs + 60s output/audit."""
import pressure as P
import time,copy,traceback
import numpy as np
O,M,C,T,X=P.O,P.M,P.C,P.T,P.X
def main():
 start=time.monotonic();g=M.read(O/'GATE.json');assert g['passed'] and len(g['tests'])==10 and all(z['passed'] for z in g['tests']);f=M.read(O/'FREEZE.json');assert all(M.sha(p)==h for p,h in f['sha256'].items());seed=T.original_seed();P.migration_guard(seed);X.configure();shared=M.context();refs=M.read(P.PREV/'RAW_MARKET_REFERENCES.json');load_seconds=time.monotonic()-start
 M.save(O/'APPROVED_RUN_FREEZE.json',dict(passed_Gate_reused=True,no_preflight_repeated=True,pure_run_budget_seconds=300,output_audit_budget_seconds=60,same_four_paths=f['paths'],sha256={str(O/'run_approved.py'):M.sha(O/'run_approved.py'),str(O/'FREEZE.json'):M.sha(O/'FREEZE.json')},cache_load_seconds=load_seconds));print('CACHE_READY_NO_GATE_RERUN',load_seconds,flush=True)
 progress=[];running=0;output=0
 for stress in ['cost2','delay1']:
  for pol in ['RAW','ATT']:
   key=pol+'_'+stress;print('START',key,'run_budget_remaining',300-running,flush=True);r=P.actor(seed,shared,pol,refs,stress)
   try:r.run_from('2025-09-30','2026-03-31',300-running)
   except BaseException:r.dump(O/key/'failed-partial');raise
   running+=r.run_seconds;t=time.monotonic();r.dump(O/key/'results');C.write_checkpoint(O/key/'end-2026-03-31.chk',{key:C.pack(r,'2026-03-31')});output+=time.monotonic()-t;a=r.accounts['T3'];nav=np.r_[float(seed['account']['current_nav']),[float(z['nav']) for z in r.daily]];z=dict(path=key,run_seconds=r.run_seconds,NAV=str(a.current_nav),suffix_return=float(nav[-1]/nav[0]-1),DD=float((1-nav/np.maximum.accumulate(nav)).max()),pure_run_cumulative=running,output_cumulative=output);progress.append(z);M.save(O/'PROGRESS.json',progress);print('PRESSURE_RESULT',z,flush=True)
 M.save(O/'ECONOMIC_DONE.json',dict(passed=True,paths=4,pure_run_seconds=running,output_checkpoint_seconds=output,cache_load_seconds=load_seconds,wall_since_cache_ready=time.monotonic()-start-load_seconds,normal_reused=True,preflight_reused=True,progress=progress));print('FOUR_DONE',running,output,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'APPROVED_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
