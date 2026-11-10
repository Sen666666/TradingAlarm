"""Exactly two authorized original-origin G/S two-session technical paths."""
from historical_binding import *
import argparse,traceback,time,subprocess,difflib

def save_json(path,x):IO.write_json(path,LD.clean(x),encoder=N.encode)
def snapshot(r,out,label):
 at=r.last_completed_event;cp=Path(out)/(label+'.pkl');r.checkpoint(cp)
 state=r.observable(at);save_json(Path(out)/(label+'.json'),state)
 return LD.digest(LD.clean(state))
def execute(r,out,days):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 for day in days:
  phases=(['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']
  for phase in phases:
   clock='T00:00:00+08:00' if phase=='ACTION' else ('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00')
   at=iso(day+clock)
   IO.write_pickle(out/'BEFORE_EVENT.pkl',r)
   save_json(out/'CURSOR.json',dict(next_at=at,phase=phase,last_completed=r.last_completed_event))
   try:
    if phase=='ACTION':r.corporate_actions(day)
    else:r.step(day,phase)
    h=snapshot(r,out,day+'-'+phase)
    print('COMPLETED',r.window,day,phase,h[:12],len(r.account.fills),flush=True)
   except BaseException as e:
    IO.write_pickle(out/'FAILED_WORKING_STATE.pkl',r)
    save_json(out/'ERROR.json',dict(action='financial prefix event or its export',target_at=at,last_completed=r.last_completed_event,
      error=repr(e),traceback=traceback.format_exc(),before_state=str(out/'BEFORE_EVENT.pkl'),no_automatic_retry=True))
    raise
 return r

def worker(checkpoint,out,second):
 r=HistoricalRunner.restore(checkpoint);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 save_json(out/'RESTORED.json',dict(at=r.last_completed_event,state_sha256=LD.digest(LD.clean(r.observable(r.last_completed_event))),binding=r.binding()))
 if second<=r.last_completed_event.date().isoformat():raise ValueError('resume day already completed')
 r=execute(r,out,[second]);save_json(out/'DONE.json',dict(completed=True,actual_completed_at=datetime.now().astimezone().isoformat(),state_sha256=LD.digest(LD.clean(r.observable(r.last_completed_event)))))

def summary(r):
 a=r.account;at=r.last_completed_event
 return dict(window=r.window,at=at,NAV=a.nav(at),available=a.available,orders_reserved=len([x for x in a.audit_log if x['kind']=='reserve']),
 fills=len(a.fills),buy_fills=sum(f.side=='buy' for f in a.fills),positions=len(a.positions),pending_intents=len(a.pending),pending_buys=len(a.buys),pending_sells=len(a.exits),
 K=list(a.policy.k),losses=a.policy.losses,actual_fees=a.fees_cny,action_sources=len(r.action_log),dividend_receivables=a.balance(at,a.market.marks(at,a.positions))['dividend_receivable'],
 receipt_consumed=len(a.policy.consumed),daily=[dict(at=e['at'],phase=e['phase'],nav=e['bridge']['nav'],available=e['bridge']['available'],inventory=e['bridge']['inventory'],positions=len(e['bridge']['quantities'])) for e in r.events],
 blockers=[dict(at=m['at'],candidate_stocks=sum(s['preliminary'] for s in m['stocks']),stock_blocked=1709-sum(s['preliminary'] for s in m['stocks'])) for m in r.mapping])

def main():
 assert LD.read(O/'mapping-fixture-002/GATE.json')['passed']
 root=O/'runs';root.mkdir(exist_ok=False)
 targets={k:root/k for k in ('failure','2022','2025_26')};IO.prepare_targets(targets,directory_keys=tuple(targets))
 frozen={str(p):sha(p) for p in O.glob('*.py')}
 save_json(O/'FULL_PREFIX_AUTHORIZATION.json',dict(parent_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',financial_scope={'2022':['2022-01-04','2022-01-05'],'2025_26':['2025-07-01','2025-07-02']},
    fixed_original_initial_cash='1000000',policy='G_S_V2_R4',frozen=FROZEN,sources=frozen,technical_replicas_only=True,no_other_financial_dates=True))
 save_json(root/'STARTED.json',dict(actual_started_at=datetime.now().astimezone().isoformat(),pid=__import__('os').getpid()))
 results=[]
 try:
  for window in ('2022','2025_26'):
   out=root/window;first,second=LD.read(INPUT/window/'MANIFEST.json')['days']
   r=HistoricalRunner(window);r=execute(r,out/'primary',[first]);cp=out/'primary'/(first+'-CLOSE.pkl')
   before=LD.digest(LD.clean(r.observable(r.last_completed_event)))
   # Only the remaining second session executes in a new process. No first-day
   # event is repeated on the authoritative continuation.
   subprocess.run([sys.executable,'-B',str(Path(__file__)),'resume',str(cp),str(out/'primary-resume'),second],check=True)
   restored=LD.read(out/'primary-resume/RESTORED.json');assert restored['state_sha256']==before
   r=HistoricalRunner.restore(out/'primary-resume'/(second+'-CLOSE.pkl'))
   assert len(r.account.fills)>0,'all-zero economic prefix is not an admission gate'
   # Wrong source binding must be rejected without executing an event.
   bad=out/'wrong-binding.pkl';IO.write_bytes(bad,cp.read_bytes());side=json.loads(cp.with_suffix('.provenance.json').read_text());side['binding']['frozen']['R4']='0'*64;IO.write_json(bad.with_suffix('.provenance.json'),side)
   try:HistoricalRunner.restore(bad)
   except ValueError:pass
   else:raise AssertionError('wrong source checkpoint accepted')
   # This is the SAME policy and sessions with genuine next-session input rows
   # present. It is only a physical truncation check, not another strategy.
   q=HistoricalRunner(window,O/'full-input-fixtures'/window/'MANIFEST.json');q=execute(q,out/'full-input-technical',[first,second])
   for day in (first,second):
    for phase in ('OPEN','CLOSE'):
     pdir=out/('primary' if day==first else 'primary-resume')
     assert LD.read(pdir/(day+'-'+phase+'.json'))==LD.read(out/'full-input-technical'/(day+'-'+phase+'.json')),(window,day,phase,'physical input prefix differs')
   assert LD.clean(r.observable(r.last_completed_event))==LD.clean(q.observable(q.last_completed_event))
   record=summary(r);record.update(physical_prefix_all_four_events_exact=True,crossprocess_restore_full_state_exact=True,wrong_source_rejected=True)
   save_json(out/'SUMMARY.json',record);results.append(record)
  assert frozen=={str(p):sha(p) for p in O.glob('*.py')},'source changed while running'
  save_json(root/'DONE.json',dict(completed=True,actual_completed_at=datetime.now().astimezone().isoformat(),results=results,new_policies=1,authoritative_prefixes=2,technical_replicas='same exact sessions and policy, verification only'))
 except BaseException as e:
  save_json(root/'failure/ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),automatic_rerun=False,actual_failed_at=datetime.now().astimezone().isoformat()))
  raise
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='resume':worker(sys.argv[2],sys.argv[3],sys.argv[4])
 else:main()
