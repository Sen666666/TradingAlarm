"""Read immutable saved accounts; no event, step, planning, window or action call."""
from pathlib import Path
from dataclasses import asdict
import sys,json,gc,time
from datetime import datetime,timezone
import replay_runtime as X
E=X.E;M=X.M;ROOT=X.HERE;OLD=M.HERE
DATES={'engineering_main':('2025-07-22','2025-07-23'),'engineering_follow':('2025-07-23','2025-07-24'),'positive_Pingan':('2025-07-04','2025-07-07'),'positive_Guangsheng':('2025-07-30','2025-07-31')}

def main():
    t=time.monotonic();cases={};readouts={};source={};static=X.read(X.W/'g-s-C-approved-risk-execution-readonly-20261102/ALL_POSITIVE_C_AUTHORIZATIONS.json')
    for mode in ['C10','C_BATCH20']:
        for label,(day,nxt) in DATES.items():
            k=mode+'|'+day;p=OLD/'runs'/('2025_26-'+mode)/(day+'-CLOSE.pkl');side=p.with_suffix('.provenance.json')
            r=M.MonthRunner.restore(p);a=r.account;before=E.digest(X.snapshot(r));cid=r.active['certificate_id']
            E.require(r.last_completed_event==E.iso(day+'T15:10:00+08:00'),'wrong actual close')
            E.require(r.inputs.days[r.inputs.days.index(day)+1]==nxt,'not original next session')
            oldopen=p.parent/(nxt+'-OPEN.pkl');oldside=oldopen.with_suffix('.provenance.json');flow=p.parent/(nxt+'-OPEN-FLOW.json')
            E.require(oldopen.exists() and flow.exists(),'saved whole original opening required')
            oldrec=X.read(oldside);E.require(X.sha(oldopen)==oldrec['checkpoint_sha256'],'saved baseline OPEN bytes changed')
            rec=dict(label=label,mode=mode,checkpoint=str(p),checkpoint_sha256=X.sha(p),provenance_sha256=X.sha(side),cursor=str(r.last_completed_event),next_day=nxt,input_manifest=str(r.inputs.path),input_manifest_sha256=X.sha(r.inputs.path),baseline_open=str(oldopen),baseline_open_sha256=oldrec['checkpoint_sha256'],baseline_open_provenance_sha256=X.sha(oldside),baseline_flow=str(flow),baseline_flow_sha256=X.sha(flow))
            cases[k]=rec
            approved=[]
            for row in static['2025_26-'+mode]:
                if row['certificate_id']==cid and row['approved_qty']>0:
                    E.require(row['approved_qty']==r.active['Q'][row['sid']],'original positive stock authorization differs')
                    approved.append(row)
            pending=[dict(sid=i['sid'],sector=i['sector'],core=i['core'],i_valid=i['i_valid'],stock_q=i['stock_q'],receipt=i['receipt'].event_id if i['receipt'] else None,priority=i['priority'],deadline=i['deadline'],epoch=i['epoch'],I_floor=i['I_floor'],cp_floor=i.get('cp_floor')) for i in a.pending]
            sells={sid:dict(order=asdict(o),pure_opportunity=a._is_pure_funding_exit(sid),layers=[copy_duty for copy_duty in a.exit_duties.values() if copy_duty['sid']==sid]) for sid,o in a.exits.items()}
            actions=r.inputs.actions(nxt);preflight=[]
            for act in actions:
                err=None
                try:
                    r.inputs.check_action_support(act,[z['qty'] for z in a.live(act['sid'])])
                    ratio=E.D(act['split_ratio'])
                    if ratio!=1 and r.active['Q'].get(act['sid'],0):raise ValueError('active unsubmitted C split remains unsupported')
                except Exception as ex:err=repr(ex)
                preflight.append(dict(source=act,blocked=err is not None,reason=err))
            payments=[asdict(v) for v in a.dividends.values() if v.paid_at is not None and v.paid_at<=E.iso(nxt+'T09:30:00+08:00')]
            readouts[k]=dict(record=rec,old_binding=r.binding(),snapshot_hash=before,NAV=a.nav(r.last_completed_event),available=a.available,holdings=len(a.positions),layers=sum(z['qty']>0 for z in a.layers),intents=len(pending),actual_pending_buys=len(a.buys),sell_obligations=len(a.exits),resource_totals=a.totals(),positive_C_stock_authorizations=len(approved),active_certificate=cid,approved_rows=approved,pending_intents=pending,sell_obligations_full=sells,company_action_preflight=preflight,payments_due=payments,existing_order_history=len(r.authority.orders),old_filled_receipts=len(r.authority.events),snapshot_unchanged=before==E.digest(X.snapshot(r)),financial_events=0)
            E.require(readouts[k]['snapshot_unchanged'],'read-only preparation changed snapshot')
            E.require(not a.buys,'pre-import live C buy needs separate partial-risk authorization')
            source[str(p)]=rec['checkpoint_sha256'];source[str(side)]=rec['provenance_sha256'];source[str(oldopen)]=rec['baseline_open_sha256'];source[str(oldside)]=rec['baseline_open_provenance_sha256'];source[str(flow)]=rec['baseline_flow_sha256'];source[str(r.inputs.path)]=rec['input_manifest_sha256']
            X.save(ROOT/'readouts'/(mode+'-'+day+'.json'),readouts[k])
            print('PREPARED_OLD_STATE',k,'cash',round(a.available,2),'NAV',round(a.nav(r.last_completed_event),2),'intents',len(pending),'buys',len(a.buys),'sells',len(a.exits),'Crows',len(approved),flush=True)
            del r;gc.collect()
    X.save(ROOT/'REPLAY_INPUT_BINDING.json',dict(scope='READ_ONLY_FIXED_NEXT_OPEN_INPUTS',financial_events_authorized=False,cases=cases,sources=source,risk_adapter_sha256=X.RISK_SHA,original_input_refresh=False,selection='two fixed engineering closes plus preexisting Pingan/Guangsheng actual whole batches, both existing modes'))
    X.save(ROOT/'STATE_READINESS.json',dict(cases={k:{f:v[f] for f in ['NAV','available','holdings','layers','intents','actual_pending_buys','sell_obligations','positive_C_stock_authorizations','active_certificate','snapshot_hash','snapshot_unchanged','company_action_preflight']} for k,v in readouts.items()},financial_events=0,seconds=time.monotonic()-t,source_verified=True,at=datetime.now(timezone.utc).isoformat()))
    print('INPUT_BINDING_READY',X.sha(ROOT/'REPLAY_INPUT_BINDING.json'),'seconds',round(time.monotonic()-t,3),flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as e:
        import traceback
        X.save(ROOT/'PREPARE_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
