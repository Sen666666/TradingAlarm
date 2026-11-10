"""Future explicit-grant entry. Preparation does NOT call this execution path."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import argparse,traceback,time
import replay_runtime as X
E=X.E

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--risk',choices=['off','on'],required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--prepare-only',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--authorization',type=Path)
    a=p.parse_args();E.require(a.prepare_only != a.execute,'choose prepare-only OR explicitly granted execute')
    if a.execute:
        # Hard permission gate before checkpoint import/any financial callback.
        E.require(a.authorization is not None,'no financial authorization supplied')
        g=X.read(a.authorization);E.require(g.get('parent_approved') is True and g.get('financial_events_authorized') is True,'NOT AUTHORIZED; readiness only')
    r=None;t=time.perf_counter()
    try:
        r=X.import_case(a.case,a.risk=='on',a.out/'import')
        if a.prepare_only:
            X.save(a.out/'PREPARED.json',dict(financial_events=0,cursor=r.last_completed_event,case=a.case,risk=a.risk,source=r.source_binding(),no_OPEN_invoked=True));return
        r.bind_execution(a.authorization);r.checkpoint(a.out/'AUTHORIZED_IMPORT.pkl')
        day=r.replay_import['next_day'];start=datetime.now(timezone.utc).isoformat();oldfill=len(r.account.fills)
        before=dict(available=r.account.available,exits={s:asdict(o) for s,o in r.account.exits.items()},buys={s:asdict(o) for s,o in r.account.buys.items()},active=r.active,account_bridge=r.account.bridge(r.last_completed_event))
        X.save(a.out/'STARTED.json',dict(at=start,case=a.case,risk=a.risk,day=day,scope='same original close, one next OPEN only; not continuous strategy PnL',before=before))
        if r.inputs.actions(day):
            r.corporate_actions(day);r.checkpoint(a.out/(day+'-ACTION.pkl'));X.save(a.out/(day+'-ACTION.json'),r.observable(r.last_completed_event))
        r.step(day,'OPEN');X.save(a.out/'ACTUAL_OPEN_COMPARISON.json',X.opening_comparison(r));r.checkpoint(a.out/(day+'-OPEN.pkl'));X.save(a.out/(day+'-OPEN.json'),r.observable(r.last_completed_event))
        X.save(a.out/'COMPLETED.json',dict(actual_start=start,actual_complete=datetime.now(timezone.utc).isoformat(),seconds=time.perf_counter()-t,new_fills=[asdict(f) for f in r.account.fills[oldfill:]],bridge=r.account.bridge(r.last_completed_event),risk_book=r.risk.__dict__,no_CLOSE_no_later_day=True))
    except BaseException as err:
        a.out.mkdir(parents=True,exist_ok=True);X.save(a.out/'ERROR.json',dict(action='fixed next OPEN preparation/execution',error=repr(err),traceback=traceback.format_exc(),last_cursor=r.last_completed_event if r else None,no_auto_replay=True))
        if r:r.checkpoint(a.out/'FAILED_WORKING_STATE.pkl')
        raise
if __name__=='__main__':main()
