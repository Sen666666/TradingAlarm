"""Every January native checkpoint/source and actual final state, saved only."""
from pathlib import Path
import pickle,json
import jan_r0 as X
E=X.E;P=X.HERE

def main():
 out=[]
 for mode in ['C10','C_BATCH20']:
  root=P/'runs'/mode;pr=X.read(root/'PROGRESS.json');cp=Path(pr['checkpoint']);r=X.Runner.restore(cp);side=X.read(cp.with_suffix('.provenance.json'));E.require(str(r.last_completed_event)=='2022-01-28 15:10:00+08:00','not January month end')
  E.require(json.loads(json.dumps(r.observable(r.last_completed_event),default=E.encode))==X.read(cp.with_suffix('.json')),'full restored observable differs')
  rows=[]
  for f in sorted(root.glob('20*-*.pkl')):
   z=X.read(f.with_suffix('.provenance.json'));b=z['binding'];E.require(X.sha(f)==z['checkpoint_sha256'] and z['engine_identity']==side['engine_identity'] and b['source']==r.source_binding() and b['account_class']==side['binding']['account_class'] and b['input_loader']==side['binding']['input_loader'],'actual saved checkpoint/source changed')
   g=b['execution_authorization'];E.require(g and X.sha(g['path'])==g['sha256'],'actual historical grant changed');rows.append(dict(path=str(f),sha256=z['checkpoint_sha256']))
  E.require(len(rows)==40 and len(r.events)==40 and len(r.authority.certificates)==19,'January source event/decision count differs')
  for k,v in r.source_binding().items():
   if Path(k).is_file():E.require(X.sha(k)==v,'source changed '+k)
  E.require(len(r.no_subscription_actions)==2,'source rights events missing')
  for k,z in r.no_subscription_actions.items():E.require(z['actual_cash']=='0' and z['actual_share_ratio']=='1','rights invented cash/share action')
  rejected=False
  try:r.execution_guard('2022-02-07','OPEN')
  except ValueError:rejected=True
  E.require(rejected,'February must remain forbidden');out.append(dict(mode=mode,checkpoints=rows,actual_final_restore_full_equal=True,R0_native_observers=True,rights_events=r.no_subscription_actions,February_rejected=True))
 X.save(P/'analysis/ARCHIVE_AND_FINAL_RESTORE.json',dict(passed=True,rows=out,event_checkpoints=80,financial_events=0));print('JAN_FINAL_ARCHIVES_PASS',80)
if __name__=='__main__':main()
