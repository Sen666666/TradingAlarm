"""Recreate only original saved-state boundary; no new strategy economics."""
from pathlib import Path
import argparse,sys,time,json,gzip,hashlib,traceback
O=Path(__file__).resolve().parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1')
sys.path.insert(0,str(OLD));import load_inputs as V
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):IO.write_json(p,J.W.canon(v))
def gz(p):return json.load(gzip.open(p,'rt'))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--day',required=True);z=ap.parse_args();day=z.day
 win,cp=('2022_2024','2022-12-30') if day=='2024-09-24' else ('strong','2025-12-31')
 assert day in ['2024-09-24','2026-01-15']
 src=OLD/'runs/BASELINE'/win;checkpoint=src/f'checkpoint-{cp}.pkl';out=O/'boundaries'/day
 assert not out.exists(),'Do not overwrite or automatically replay completed/partial boundary'
 out.mkdir(parents=True);begin=time.monotonic()
 try:
  meta=read(checkpoint.with_suffix('.json'));assert sha(checkpoint)==meta['sha256']
  for p,h in meta['source_freeze'].items():assert sha(p)==h,('source drift',p)
  save(out/'RESTORE_CARD.json',dict(scope='original historical state reconstruction only; inherited biased history, not causal portfolio result',day=day,original_checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),checkpoint_metadata=meta,script_sha256=sha(__file__),original_files_readonly=True))
  print('LOAD_INPUTS',day,flush=True)
  shared,receipts,cpv,states,ir,identity=V.inputs(win)
  print('INPUTS_READY',day,round(time.monotonic()-begin,1),flush=True)
  r=A.Runner(shared,receipts,stock_cp=cpv,industry_states=states,industry_receipts=ir)
  r.source_freeze=dict(meta['source_freeze'])
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):
   last=r.restore(checkpoint)
   print('ORIGINAL_GUARDED_RESTORE_PASS',day,str(last),flush=True)
   completed=r.run_prepared(out,1200,resume_after=last,end=day)
  assert completed
  a=r.accounts['B'];book=gz(src/'pair/B.json.gz')
  expected=[x for x in book['trades'] if str(x.get('at',''))[:10]<=day]
  checks={'all_trades_prefix':J.W.canon(a.trades)==expected}
  for field,name in [('audit_log','audit'),('journal','journal'),('decisions','decisions')]:
   exp=[x for x in book[name] if str(x.get('at',''))[:10]<=day]
   checks['all_'+name+'_prefix']=J.W.canon(getattr(a,field))==exp
  for attr,name in [('daily','daily'),('funding','funding'),('opportunities','opportunities'),('stage_events','industry'),('balance_audit','balances'),('rank_log','rank-policy')]:
   with gzip.open(src/'pair'/(name+'.jsonl.gz'),'rt') as f:
    exp=[x for line in f if str((x:=json.loads(line)).get('at',x.get('day','')))[:10]<=day]
   checks['all_'+name+'_prefix']=J.W.canon(getattr(r,attr))==exp
  save(out/'SAVED_PREFIX_EQUALITY.json',dict(passed=all(checks.values()),checks=checks,through=day,last_event=str(last),ending_cash=str(a.available),ending_nav=str(a.current_nav),pending=len(a.pending),layers=sum(x['qty']>0 for x in a.layers),original_checkpoint_sha256=sha(checkpoint),reconstructed_checkpoint_sha256=sha(out/'checkpoint.pkl'),seconds=time.monotonic()-begin,hidden_state='Native guarded continuation with all saved event streams equal; complete original hidden state at target date was not independently saved.'))
  assert all(checks.values()),checks
  print('BOUNDARY_EXACT',day,'seconds',round(time.monotonic()-begin,1),'NAV',str(a.current_nav),flush=True)
 except BaseException as e:
  save(out/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False));raise
if __name__=='__main__':main()

