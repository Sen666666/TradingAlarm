"""One root-granted remaining2023 continuation; no automatic recovery/replay."""
from pathlib import Path
import argparse,json,time,traceback
import horizon_adapter as H
A,N,J,L,IO,O=H.A,H.N,H.J,H.L,H.IO,H.O
AUTH=O/'FULL_2023_RUN_AUTHORIZATION.json';ROOT=O/'run-2023';CP=O/'first-session/full-input/checkpoint.pkl'
CURSOR=J.M.N.iso('2023-01-03T15:10:00+08:00');MANIFEST=O/'PROPOSED_FULL_EXECUTION_FREEZE.json'
def save(p,x):IO.write_json(p,J.W.canon(x))
def prepare():
 gate=H.read(O/'TECHNICAL_GATE.json');cross=H.read(O/'CROSS_PROCESS_GATE.json')
 assert gate['passed']and cross['passed']and cross['separate_process']
 frozen=gate['sources'];assert all(H.sha(p)==h for p,h in frozen.items())
 value=dict(policy=A.POLICY,scope='ONE_NO60_own2022_2023_continuation',resume_checkpoint=str(CP),resume_checkpoint_sha256=H.sha(CP),
  resume_after=str(CURSOR),end=H.END,checkpoint_source_freeze_preserved=frozen,
  launcher_sha256=H.sha(__file__),card_sha256=H.sha(O/'FULL_2023_CARD.txt'),
  horizon_adapter_sha256=H.sha(H.__file__),native_adapter_sha256=H.sha(A.__file__),binding_sha256=H.sha(H.BINDING),
  technical_gate_sha256=H.sha(O/'TECHNICAL_GATE.json'),cross_process_gate_sha256=H.sha(O/'CROSS_PROCESS_GATE.json'),
  full_year_execution_authorized_by_prepare=False)
 if MANIFEST.exists():assert H.read(MANIFEST)==value,'prepared execution source changed'
 else:save(MANIFEST,value)
 save(O/'PROPOSED_FULL_2023_AUTHORIZATION.json',dict(approved=False,scope=value['scope'],
  launcher_sha256=value['launcher_sha256'],horizon_adapter_sha256=value['horizon_adapter_sha256'],native_adapter_sha256=value['native_adapter_sha256'],
  binding_sha256=value['binding_sha256'],execution_manifest_sha256=H.sha(MANIFEST),resume_checkpoint_sha256=value['resume_checkpoint_sha256'],
  resume_after=value['resume_after'],end=value['end'],technical_gate_sha256=value['technical_gate_sha256'],cross_process_gate_sha256=value['cross_process_gate_sha256']))
 print('PREPARED_ONLY',str(MANIFEST),flush=True)
def execute():
 t=time.monotonic();auth=H.read(AUTH);manifest=H.read(MANIFEST)
 assert auth['approved']is True and auth['scope']=='ONE_NO60_own2022_2023_continuation'
 assert auth['execution_manifest_sha256']==H.sha(MANIFEST)
 assert auth['launcher_sha256']==manifest['launcher_sha256']==H.sha(__file__)
 assert auth['horizon_adapter_sha256']==H.sha(H.__file__)and auth['native_adapter_sha256']==H.sha(A.__file__)
 assert auth['binding_sha256']==H.sha(H.BINDING)
 assert auth['resume_checkpoint_sha256']==manifest['resume_checkpoint_sha256']==H.sha(CP)
 assert auth['resume_after']==str(CURSOR)and auth['end']==H.END
 assert auth['technical_gate_sha256']==H.sha(O/'TECHNICAL_GATE.json')and auth['cross_process_gate_sha256']==H.sha(O/'CROSS_PROCESS_GATE.json')
 assert manifest['card_sha256']==H.sha(O/'FULL_2023_CARD.txt')
 assert not(ROOT/'DONE.json').exists()and not(ROOT/'checkpoint.pkl').exists()and not(ROOT/'failure/ENTRY_ERROR.json').exists(),'completed/partial/failed path requires separate review; do not repeat'
 N.configure_scores(H.SCORES)
 old=H.save
 try:H.save=lambda path,value:save(ROOT/'input-readiness'/Path(path).name,value);shared,receipts,cp,states,ir,identity=H.inputs()
 finally:H.save=old
 loaded=time.monotonic();frozen=manifest['checkpoint_source_freeze_preserved'];assert all(H.sha(p)==h for p,h in frozen.items())
 fullfreeze=dict(frozen,**{str(Path(__file__)):H.sha(__file__),str(AUTH):H.sha(AUTH),str(MANIFEST):H.sha(MANIFEST),str(O/'FULL_2023_CARD.txt'):H.sha(O/'FULL_2023_CARD.txt')})
 save(ROOT/'EXECUTION_FREEZE.json',dict(checkpoint_source_freeze_preserved=frozen,entry_sources=fullfreeze,identity=identity))
 r=H.Continuation(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):assert r.restore(CP)==CURSOR
 a=r.accounts['B']
 save(ROOT/'RESTORED_START.json',dict(cursor=str(CURSOR),NAV=str(a.current_nav),cash=str(a.available),pending_intents=len(a.pending),
  pending_buys=len(a.buys),pending_exits=len(a.exits),unpaid_dividend_AR=str(a.balance(CURSOR,r.market.marks(CURSOR,a.positions))['dividend_receivable']),
  own2022_parent=str(H.PARENT/'checkpoint.pkl'),resume_checkpoint_sha256=H.sha(CP),source_freeze_preserved=True,
  original_PVR_baseline_not_imported=True,first_session_not_replayed=True,runtime_identity=IO.runner_identity(r),input_load_seconds=loaded-t))
 print('NO60_2023_RESTORED',a.current_nav,'load',round(loaded-t,2),flush=True)
 with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):done=r.run_prepared(ROOT,600,resume_after=CURSOR,end=H.END)
 assert all(H.sha(p)==h for p,h in fullfreeze.items())
 save(ROOT/'TIMING.json',dict(completed=done,input_load_seconds=loaded-t,total_seconds=time.monotonic()-t,
  event_loop_seconds=getattr(r,'run_seconds',None),ending_NAV=str(a.current_nav),exactly_one_remaining2023_path=True,Jan3_replays=0,baseline_replays=0))
 print('NO60_2023_COMPLETE'if done else'NO60_2023_CHECKPOINTED_LIMIT',a.current_nav,round(time.monotonic()-t,2),flush=True)
def main():
 global entry_action
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args();assert a.prepare!=a.execute
 entry_action='prepare'if a.prepare else'execute'
 if a.prepare:prepare()
 else:execute()
if __name__=='__main__':
 try:main()
 except BaseException as e:save(ROOT/'failure/ENTRY_ERROR.json'if globals().get('entry_action')=='execute'else O/'PREPARE_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),Jan3_must_not_repeat=True,automatic_recovery=False));raise
