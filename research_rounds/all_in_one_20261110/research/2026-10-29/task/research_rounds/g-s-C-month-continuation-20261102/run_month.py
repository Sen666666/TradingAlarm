"""One reusable continuous runner. Execution ends at the explicit grant cutoff."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
import argparse,json,time,traceback
import month_runtime as M
E=M.E;HERE=M.HERE
def save(p,x):E.IO.write_json(p,x,encoder=E.encode)
def snap(r,out,name):
 p=out/(name+'.pkl');r.checkpoint(p);save(out/(name+'.json'),r.observable(r.last_completed_event));return p
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['2022','2025_26'],required=True);ap.add_argument('--mode',choices=['C10','C_BATCH20'],required=True);ap.add_argument('--grant',type=Path,required=True);ap.add_argument('--prepare-only',action='store_true');a=ap.parse_args()
 out=HERE/'runs'/(a.window+'-'+a.mode);out.mkdir(parents=True,exist_ok=True);r=None;t=time.perf_counter()
 try:
  M.guard();progress=out/'PROGRESS.json'
  if progress.exists():
   pp=M.read(progress);E.require(M.P.sha(pp['checkpoint'])==pp['sha256'],'progress bytes changed');r=M.MonthRunner.restore(pp['checkpoint']);r.accept_grant(a.grant)
  else:
   r=M.import_account(a.window,a.mode,a.grant,out/'import');p=out/'import/IMPORT.pkl';save(progress,dict(checkpoint=str(p),sha256=M.P.sha(p),cursor=r.last_completed_event,phase='IMPORT'))
  if a.prepare_only:save(out/'PREPARED.json',dict(old_prefix_exact=True,cursor=r.last_completed_event,financial_events=0));return
  days=M.read(HERE/'MONTH_INPUT_FREEZE.json')['windows'][a.window]['days'];cutoff=r.execution_grant_record['cutoff']
  save(out/'STARTED.json',dict(actual_at=datetime.now(timezone.utc).isoformat(),cursor=r.last_completed_event,cutoff=cutoff,grant=r.execution_grant_record))
  for day in days:
   if day>cutoff:break
   phases=(['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']
   for phase in phases:
    at=E.iso(day+('T00:00:00+08:00' if phase=='ACTION' else 'T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
    if r.last_completed_event>=at:continue
    et=time.perf_counter();before=snap(r,out,'BEFORE_EVENT');oldfill=len(r.account.fills);cash=r.account.available
    funding={sid:dict(order=o.event_id,pure=r.account._is_pure_funding_exit(sid)) for sid,o in r.account.exits.items()};before_book=r.budget.dumps()
    if phase=='ACTION':r.corporate_actions(day)
    else:r.step(day,phase)
    if phase=='CLOSE':E.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','optional stage incomplete; preserve necessary stage, no auto-retry')
    p=snap(r,out,day+'-'+phase);new=r.account.fills[oldfill:];sales=[f for f in new if f.side=='sell' and funding.get(f.security_id,{}).get('pure')]
    record=dict(day=day,phase=phase,cursor=r.last_completed_event,seconds=time.perf_counter()-et,fills=[asdict(f) for f in new],healthy_funding_sells=[asdict(f) for f in sales],before_available=cash,after_available=r.account.available,after_balance=r.account.bridge(at),budget_before=before_book,budget_after=r.budget.dumps(),cutoff=cutoff)
    save(out/(day+'-'+phase+'-FLOW.json'),record)
    if sales and not (out/'FIRST_MIGRATION.json').exists():save(out/'FIRST_MIGRATION.json',record)
    if phase=='CLOSE' and (out/'FIRST_MIGRATION.json').exists() and M.read(out/'FIRST_MIGRATION.json')['day']==day:save(out/'FIRST_MIGRATION_FOLLOWUP_CLOSE.json',record)
    save(progress,dict(checkpoint=str(p),sha256=M.P.sha(p),cursor=r.last_completed_event,phase=phase))
    print('COMPLETED_EVENT',a.window,a.mode,day,phase,'newfills',len(new),'seconds',round(record['seconds'],3),flush=True)
  save(out/'STOPPED_AT_CUTOFF.json',dict(cursor=r.last_completed_event,cutoff=cutoff,actual_at=datetime.now(timezone.utc).isoformat(),seconds=time.perf_counter()-t,checkpoint=M.read(progress),no_further_financial_event=True))
 except BaseException as exc:
  save(out/'ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc(),last_cursor=r.last_completed_event if r else None,no_auto_replay=True))
  if r:E.IO.write_pickle(out/'FAILED_WORKING_STATE.pkl',r)
  raise
if __name__=='__main__':main()
