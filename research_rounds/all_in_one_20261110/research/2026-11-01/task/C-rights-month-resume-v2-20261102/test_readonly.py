"""Current OPEN clock, old completion clock: recompute without observing ledger."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import copy,json,pickle
from legacy_readonly_v2 import serialized_readonly
O=Path(__file__).resolve().parent
class Clock:
 def __init__(self):self.as_of=datetime.fromisoformat('2022-01-13T09:30:00+08:00');self.calls=[]
 def observe(self,at):
  if at<self.as_of:raise ValueError('Account events cannot run backwards')
  self.calls.append(at);return at
current=SimpleNamespace(account=Clock(),last_completed_event=datetime.fromisoformat('2022-01-13T00:00:00+08:00'),cash=123,qty=999,trusted={'old':{'snapshot':{'qty':22},'source':'fixed-old'}})
tests={}
try:current.account.observe(current.last_completed_event)
except ValueError:tests['old_backward_observation_reproduced']=True
before=pickle.dumps(current,pickle.HIGHEST_PROTOCOL)
view=SimpleNamespace(account=None,trusted=copy.deepcopy(current.trusted))
def genuine(v,c):
 assert v.account is None and c['source']==v.trusted['old']['source'];q=v.trusted['old']['snapshot']['qty'];v.trusted['old']['snapshot']['qty']=111;return q
result=serialized_readonly(current,view,{'source':'fixed-old'},genuine)
tests['frozen_snapshot_qty_not_current_qty']=result==22
tests['complete_current_graph_exact']=pickle.dumps(current,pickle.HIGHEST_PROTOCOL)==before
tests['advanced_clock_retained']=current.account.as_of.hour==9 and current.account.as_of.minute==30
tests['last_completed_not_prematurely_advanced']=current.last_completed_event.hour==0
tests['no_ledger_observation']=current.account.calls==[]
def bad(v,c):current.qty=0
try:serialized_readonly(current,view,{},bad)
except ValueError:tests['actual_mutation_rejected']=True
assert all(tests.values()),tests
(O/'SYNTHETIC_READONLY.json').write_text(json.dumps(dict(passed=True,no_historical_events=True,tests=tests),indent=2)+'\n');print('SYNTHETIC_PASS',len(tests),flush=True)
if __name__=='__main__':
 import resume_runtime_v2 as C
 rows=[]
 for arm in ['2022-C10','2022-C_BATCH20']:
  x=C.guard();origin=x['import_sources'][arm+'|full']
  if origin['kind']=='IMPORT':r=C.OLD.ContinuationRunner.restore(origin['checkpoint'],registry_sha=origin['registry_sha256'])
  else:r=C.A.ActionRunner.restore(origin['checkpoint'],registry_sha=x['parent_registry_sha256'])
  # Disposable TEST ONLY: simulate the active OPEN clock without a market,
  # order, settlement, fill or registered financial event.
  r.__class__=C.ContinuationRunner;r.account.as_of=datetime.fromisoformat('2022-01-13T09:30:00+08:00');r.account.last_cursor=r.account.as_of
  fields=C.FP.snapshot(r);raw=pickle.dumps(r,pickle.HIGHEST_PROTOCOL)
  for cert in r.authority.certificates.values():
   solved=r.verify_native(cert);assert C.E.digest(solved)==cert['projection_hash']
  assert pickle.dumps(r,pickle.HIGHEST_PROTOCOL)==raw and C.FP.snapshot(r)==fields
  rows.append(dict(arm=arm,simulated_OPEN_reentry=True,current_account_clock=str(r.account.as_of),last_completed=str(r.last_completed_event),all_fields_exact=len(fields),old_certificates_recomputed=len(r.authority.certificates),historical_events=0,not_registered=True));print('REAL_CERT_OPEN_REENTRY_PASS',arm,flush=True)
 (O/'REAL_CERT_READONLY.json').write_text(json.dumps(dict(passed=True,rows=rows,no_historical_events=True),indent=2)+'\n')
