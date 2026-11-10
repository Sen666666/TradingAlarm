"""Thin full-window entry; no execution without matching root approval file."""
from pathlib import Path
import argparse,gc,json,time,traceback
import native_adapter as A
N,J,L,S,IO=A.N,A.J,A.L,A.S,A.IO
O=A.O;WINDOWS=['2022','2025_26'];CARD=O/'FULL_ECONOMIC_CARD.txt';MANIFEST=O/'ECONOMIC_SOURCE_FREEZE.json'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):IO.write_json(p,J.W.canon(x))
def sources():
 r=A.source_freeze()
 for p in [CARD,Path(__file__),O/'native_preflight.py',O/'native_cross_process_restart.py',O/'native_affected_checks.py']:
  r[str(p)]=N.sha(p)
 return r
def prepare():
 gate=read(O/'native-readiness/GATE.json');assert gate['passed']
 cross=read(O/'native-readiness/CROSS_PROCESS_RESTART.json');assert cross['passed']and cross['separate_process']
 assert read(O/'native-readiness/AFFECTED_NATIVE_BUDGET_CHECKS.json')['passed']
 for p,h in gate['source_freeze'].items():assert N.sha(p)==h,('technical source changed',p)
 value=dict(policy=A.POLICY,scope='full_financial_paths',windows=WINDOWS,sources=sources(),
  original_baseline_root=str(A.W/'pvr-slot1-native-readiness-20261101/runs'),
  technical_gate_sha256=N.sha(O/'native-readiness/GATE.json'),cross_process_gate_sha256=N.sha(O/'native-readiness/CROSS_PROCESS_RESTART.json'),
  card_sha256=N.sha(CARD),execution_has_not_been_authorized_by_preparation=True)
 if MANIFEST.exists():assert read(MANIFEST)==value,'existing economics source manifest changed'
 else:save(MANIFEST,value)
 template=dict(approved=False,scope='full_financial_paths',policy=A.POLICY,windows=WINDOWS,
  source_freeze_sha256=N.sha(MANIFEST),technical_gate_sha256=value['technical_gate_sha256'],cross_process_gate_sha256=value['cross_process_gate_sha256'])
 save(O/'PROPOSED_ROOT_AUTHORIZATION.json',template)
 print('PREPARED_ONLY',str(MANIFEST),flush=True)
def execute(args):
 assert args.authorization_file and args.execute
 freeze=read(MANIFEST);auth=read(args.authorization_file)
 assert auth['approved']is True and auth['scope']=='full_financial_paths'and auth['policy']==A.POLICY and auth['windows']==WINDOWS
 assert auth['source_freeze_sha256']==N.sha(MANIFEST)
 assert auth['technical_gate_sha256']==freeze['technical_gate_sha256']==N.sha(O/'native-readiness/GATE.json')
 assert auth['cross_process_gate_sha256']==freeze['cross_process_gate_sha256']==N.sha(O/'native-readiness/CROSS_PROCESS_RESTART.json')
 assert sources()==freeze['sources'],'prepared full financial sources changed'
 N.configure_scores();selected=WINDOWS if args.window=='both'else[args.window]
 if args.resume_checkpoint:assert len(selected)==1,'resume must select one window'
 for window in selected:
  t=time.monotonic();out=O/'runs'/window;assert not(out/'DONE.json').exists(),'completed economic path cannot repeat'
  if not args.resume_checkpoint:assert not(out/'checkpoint.pkl').exists()and not(out/'FAILURE.json').exists(),'existing partial/failure requires explicit review/resume; never silently repeat'
  out.mkdir(parents=True,exist_ok=True)
  try:
   old=S.O
   try:S.O=out;value=S.inputs(window)
   finally:S.O=old
   shared,receipts,cp,states,ir,identity=value
   original_gate=read(A.W/'pvr-slot1-native-readiness-20261101/PREFLIGHT_GATE.json')
   assert S.canonical_identity(identity)==original_gate['input_identities'][window]
   r=A.Runner(shared,receipts,**S.kwargs(cp,states,ir));r.source_freeze=dict(freeze['sources']);a=r.accounts['B']
   assert a.available==a.current_nav==a.initial_cash==J.D(1000000)
   assert not a.positions and not a.trades and not a.buys and not a.exits and not a.core_epoch and not a.budget.orders and not a.budget.stock_requests and not a.budget.losses
   save(out/'FRESH_INITIAL_STATE.json',dict(window=S.WINDOWS[window][:2],initial_cash=str(a.initial_cash),positions=0,orders=0,stock_requests=0,losses=0,
    warm_industry_consumed_receipts=len(a.budget.consumed),warm_market_stage_same_original=True,old_baseline_account_not_imported=True,
    requested_resume=str(args.resume_checkpoint)if args.resume_checkpoint else None))
   last=None
   if args.resume_checkpoint:
    assert args.resume_checkpoint.resolve().parent==out.resolve(),'only own same-window checkpoint can resume'
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):last=r.restore(args.resume_checkpoint)
   save(out/'RUN_METADATA.json',dict(policy=A.POLICY,source_freeze=freeze['sources'],source_manifest_sha256=N.sha(MANIFEST),card_sha256=N.sha(CARD),
    authorization_file=str(args.authorization_file),authorization_sha256=N.sha(args.authorization_file),fixed_input_identity=S.canonical_identity(identity),
    fresh_initial_cash=1000000,resume_after=str(last)if last else None,original_baseline_readonly=True,
    observer='unchanged native complete logs and daily independent cashflow/NAV/stock/pool bridge'))
   print('ECONOMIC_STARTED',window,'resume_after',last,flush=True)
   with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):
    completed=r.run_prepared(out,args.seconds_per_window,resume_after=last,end=S.WINDOWS[window][1])
   assert sources()==freeze['sources']
   save(out/'TIMING.json',dict(completed=completed,total_seconds=time.monotonic()-t,original_run_seconds=r.run_seconds if completed else None))
   print('ECONOMIC_SAVED',window,'completed',completed,'seconds',round(time.monotonic()-t,2),flush=True)
   if not completed:return
   del r,shared,receipts,cp,states,ir;gc.collect()
  except BaseException as e:
   save(out/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False,prior_checkpoint_preserved=True));raise
def main():
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--authorization-file',type=Path)
 p.add_argument('--window',choices=['both']+WINDOWS,default='both');p.add_argument('--resume-checkpoint',type=Path);p.add_argument('--seconds-per-window',type=float,default=600)
 args=p.parse_args();assert args.prepare!=args.execute,'choose prepare OR explicitly authorized execute'
 if args.prepare:prepare()
 else:execute(args)
if __name__=='__main__':main()
