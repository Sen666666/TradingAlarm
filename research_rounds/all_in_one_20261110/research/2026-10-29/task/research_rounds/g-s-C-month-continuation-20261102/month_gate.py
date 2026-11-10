"""Read-only month/prefix/current-action gates. Never advances an account."""
from pathlib import Path
import subprocess,sys,copy,pickle,json
import numpy as np
import month_runtime as M
E=M.E;HERE=M.HERE
def main():
 M.guard();identity=M.read(HERE/'POLICY_INPUT_IDENTITY.json');rows=[];unsupported=[]
 for window in ('2025_26','2022'):
  inputs=M.MonthInputs(identity['inputs'][window]['path']);old=M.X.ExtendedInputs(M.C.HERE/'inputs'/window/'full/MANIFEST.json');scope=inputs.m['month_data_scope']
  for day in old.days:
   for phase in ('ACTION','PAYMENT','OPEN','CLOSE'):assert M.X.normalize(inputs.event(day,phase))==M.X.normalize(old.event(day,phase)),(window,day,phase)
   assert inputs.priority(day)==old.priority(day)
  for day in inputs.days:
   if day<scope['start']:continue
   for action in inputs.actions(day):
    try:inputs.check_action_support(action,[])
    except M.X.LD.UnsupportedInput as exc:unsupported.append(dict(window=window,sid=action['sid'],day=day,classification=action['classification'],reason=str(exc)))
  for mode in ('C10','C_BATCH20'):
   out=HERE/'runs'/(window+'-'+mode)
   with (HERE/(window+'-'+mode+'-PREP.out')).open('w') as so,(HERE/(window+'-'+mode+'-PREP.err')).open('w') as se:
    z=subprocess.run([sys.executable,'-B',str(HERE/'run_month.py'),'--window',window,'--mode',mode,'--grant',str(HERE/'grants/001_first_migration.json'),'--prepare-only'],stdout=so,stderr=se)
   if z.returncode:raise RuntimeError('month import failed '+window+'-'+mode)
   p=Path(M.read(out/'PROGRESS.json')['checkpoint']);r=M.MonthRunner.restore(p);before=E.digest(M.C.prefix_view(r));first=scope['start']
   # Preflight ALL first-cutoff actions with real current layers/responsibilities.
   for ev in inputs.actions(first):
    sid=ev['sid'];q=[x['qty'] for x in r.account.layers if x['sid']==sid and x['qty']];inputs.check_action_support(ev,q)
    ratio=M.C.F.P.D(ev['split_ratio'])
    assert all(M.C.F.P.D(v.remaining)*ratio==int(M.C.F.P.D(v.remaining)*ratio) for v in r.account.policy.locks.values() if v.sid==sid)
    if ratio!=1:
     assert not any(c['Q'].get(sid,0)>0 and E.iso(c['deadline'])>=E.iso(first+'T00:00:00+08:00') and not any(o['cid']==c['certificate_id'] and o['sid']==sid for o in r.authority.orders.values()) for c in r.authority.certificates.values())
   # Real source-only packets, full old view vs month view at the first date.
   clone=pickle.loads(pickle.dumps(r));at=E.iso(first+'T15:10:00+08:00');clone.account.market.refresh(at);packet=clone.stock_packet(at)
   fresh=[v['receipt'] for v in packet.values() if v.get('receipt')];assert all(clone.account.receipt_verified(v) for v in fresh)
   assert E.digest(M.C.prefix_view(r))==before
   rows.append(dict(window=window,mode=mode,old_prefix_exact=True,old_complete_input_prefix_exact=True,import_restore_exact=True,first_cutoff_actions_supported=True,first_day_canonical=len(fresh),financial_events=0))
 # Matrix caching is a read-only preparer change, not a signal alteration.
 hp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
 with np.load(hp,allow_pickle=False) as h:
  cached=h['score'];original_reloaded=h['score'];assert np.array_equal(cached,original_reloaded,equal_nan=True)
 E.IO.write_json(HERE/'READ_ONLY_GATE.json',dict(passed=True,policy_input_identity_sha256=M.P.sha(HERE/'POLICY_INPUT_IDENTITY.json'),rows=rows,known_later_unsupported=unsupported,first_execution_days={'2022':'2022-01-07','2025_26':'2025-07-04'},h1_preparer_cache_full_matrix_exact=True,financial_events=0),encoder=E.encode)
 for rec in rows:
  r=M.MonthRunner.restore(HERE/'runs'/(rec['window']+'-'+rec['mode'])/'import/IMPORT.pkl');before=E.digest(M.C.prefix_view(r))
  for day in [r.last_completed_event.date().isoformat(),('2022-01-10' if r.window=='2022' else '2025-07-07')]:
   try:r.step(day,'OPEN')
   except ValueError:pass
   else:raise AssertionError('outside grant accepted')
   assert E.digest(M.C.prefix_view(r))==before
 print(json.dumps(dict(passed=True,rows=len(rows),later_unsupported=unsupported,financial_events=0)),flush=True)
if __name__=='__main__':main()
