"""Separate-process terminal restore audit only; no market event invocation."""
from pathlib import Path
import argparse,gzip,json,pickle,time,os,traceback
import cycle2024_adapter as C
def main(policy):
 t=time.monotonic();root=C.root(policy);out=root/'run-2024';done=C.read(out/'DONE.json');assert done['completed']
 cp=out/'checkpoint.pkl';meta=C.read(cp.with_suffix('.json'));prov=C.read(cp.with_suffix('.provenance.json'))
 assert meta['at']==prov['last_completed_event']=='2024-12-31 15:10:00+08:00'
 assert C.sha(cp)==meta['sha256']==prov['checkpoint_sha256']
 exe=C.read(out/'EXECUTION_FREEZE.json')
 assert all(C.sha(p)==h for p,h in exe['entry_sources'].items())
 C.N.configure_scores(C.NEW_SCORE);shared,receipts,cp1,states,ir,identity=C.inputs()
 r=C.CLASSES[policy](shared,receipts,stock_cp=cp1,industry_states=states,industry_receipts=ir)
 r.source_freeze=dict(exe['checkpoint_source_freeze_preserved'])
 with C.IO.atomic_runner_outputs(r,C.L,root/'terminal-restore',canonicalize=C.J.W.canon):cursor=r.restore(cp)
 assert str(cursor)==meta['at']
 payload=pickle.loads(cp.read_bytes());old=payload['accounts']['B'];oldrunner=payload['runner'];a=r.accounts['B']
 ac={k:C.E.equal(v,a.__dict__[k])for k,v in old.items()};rc={k:C.E.equal(v,getattr(r,k))for k,v in oldrunner.items()}
 assert all(ac.values())and all(rc.values())
 assert len(r.episode_starts)==r.cycle_transition['lookup_new']
 with gzip.open(out/'pair/B.json.gz','rt')as f:book=json.load(f)
 fields={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits','audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
 assert all(C.J.W.canon(old[k])==book[v]for k,v in fields.items())
 b=a.budget;assert C.J.W.canon(dict(sectors=b.sectors,orders=b.orders,losses={str(k):v for k,v in b.losses.items()},consumed=sorted(b.consumed)))==book['budget']
 streams={}
 for field,file in {'daily':'daily','opportunities':'opportunities','funding':'funding','stage_events':'industry','balance_audit':'balances','rank_log':'rank-policy'}.items():
  left=C.E.record_digest(getattr(r,field));right=C.E.record_digest(C.E.file_rows(out/'pair'/(file+'.jsonl.gz')))
  assert left==right;streams[field]=left
 balance=a.balance(cursor,r.market.marks(cursor,a.positions))
 assert balance['nav']==a.current_nav==C.J.D(done['ending_NAV']['B'])==C.J.D(book['ending_NAV'])
 assert abs(b.nav-float(balance['nav']))<1e-6 and abs(b.cash-b.resources()[2]-float(a.available))<1e-6
 assert all(C.E.equal(v,a.__dict__[k])for k,v in old.items()),'read-only terminal validation mutated account'
 assert all(C.sha(p)==h for p,h in exe['entry_sources'].items())
 C.save(out/'TERMINAL_SEPARATE_PROCESS_RESTORE.json',dict(passed=True,separate_process=True,pid=os.getpid(),account_events=0,
  cursor=str(cursor),NAV=str(a.current_nav),checkpoint_sha256=C.sha(cp),all_account_fields_exact=ac,
  all_runner_fields_exact=rc,complete_book_exact=True,all6_streams_exact=streams,original_balance_budget_bridge_exact=True,
  audit_source_sha256=C.sha(__file__),sources_current_exact=True,pure_episode_lookup_size=len(r.episode_starts),seconds=time.monotonic()-t))
 print('TERMINAL2024_PASS',policy,round(time.monotonic()-t,2),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--policy',choices=['original','no60'],required=True);a=ap.parse_args()
 try:main(a.policy)
 except BaseException as e:C.save(C.root(a.policy)/'run-2024/TERMINAL_RESTORE_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),account_events=0));raise
