"""Two bounded fresh1m NO_AR6 research paths, explicit root grant required.

No live endpoints, source changes, scope extension or automatic error retry.
Per-event flow is compact; exact full terminal/month checkpoints are losslessly
compressed. A failing optional CLOSE remains failed, never silently rerun.
"""
from pathlib import Path
from dataclasses import asdict,is_dataclass
from datetime import datetime,timezone
import argparse,json,time,pickle,gzip,hashlib,os,traceback
import adapter_v2 as A
E=A.E
def norm(x):return json.loads(json.dumps(x,default=E.encode))
def gz_json(path,x):
    p=Path(path);tmp=p.with_name(p.name+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=3) as f:json.dump(x,f,ensure_ascii=False,default=E.encode)
    os.replace(tmp,p)
def checkpoint(r,out,name):
    raw=pickle.dumps(r,pickle.HIGHEST_PROTOCOL);p=out/(name+'.pkl.gz');tmp=p.with_name(p.name+'.tmp')
    with gzip.open(tmp,'wb',compresslevel=1) as f:f.write(raw)
    os.replace(tmp,p);A.save(out/(name+'.provenance.json'),dict(checkpoint=str(p),packed_sha256=A.sha(p),raw_sha256=hashlib.sha256(raw).hexdigest(),cursor=r.last_completed_event,binding=r.binding(),engine_identity=E.IO.runner_identity(r)))
    A.save(out/'PROGRESS.json',dict(checkpoint=str(p),provenance=str(out/(name+'.provenance.json')),cursor=r.last_completed_event,phase=r.last_phase))
    return p
def restore(rec):
    p=Path(rec['checkpoint']);s=A.read(rec['provenance']);E.require(A.sha(p)==s['packed_sha256'],'compressed CP bytes changed')
    raw=gzip.decompress(p.read_bytes());E.require(hashlib.sha256(raw).hexdigest()==s['raw_sha256'],'uncompressed CP bytes changed')
    r=pickle.loads(raw);r.account.owner=r;E.require(r.binding()==s['binding'] and E.IO.runner_identity(r)==s['engine_identity'],'restore identity changed')
    r.assert_observers()
    # Saved pure projections are reverified under immutable trusted bodies.
    for c in r.authority.certificates.values():r.verify_native(c)
    return r
def resource_view(r,at):
    a=r.account;rows=a.resources();tot=a.totals(rows)
    # Exact principal/giveback requires basis by layer; retain raw rows, marks,
    # layer unit costs separately for independent analysis instead of guessing.
    return dict(rows=rows,totals=tot,policy_nd=a.policy.nd,scopes={k:asdict(v) if is_dataclass(v) else v for k,v in a.policy.scopes.items()},
                ACT=a.policy.act,incident=a.policy.incident,incidents=a.policy.incidents,
                permissions={k:{u:a.policy.allowed(k,u) for u in (['G'] if k=='G' else ['T','S'])} for k in a.policy.scopes},
                held_quantities={s:a.quantity(s) for s in a.market.sectors if a.quantity(s)},
                prices={s:a.market.prices[s] for s in a.market.sectors if a.quantity(s)},
                sector_by_sid={s:a.market.sectors[s] for s in a.market.sectors if a.quantity(s)},
                pending_orders=a.buys,exit_orders=a.exits)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['2022','2025_26'],required=True);ap.add_argument('--authorization',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    g=A.read(a.authorization)
    E.require(g.get('parent_approved') is True and g.get('continuous_financial_path_authorized') is True and g['runtime_sha256']==A.sha(A.__file__) and g['entry_sha256']==A.sha(__file__) and g['window']==a.window and g['ablation_enabled'] is True and g['branch']=='full','root financial grant required before account construction')
    expected_end='2022-01-28' if a.window=='2022' else '2025-08-29';E.require(g['end']==expected_end and g['initial_cash']=='1000000','only two reviewed scopes')
    gate=A.read(A.HERE/'TECHNICAL_READINESS.json');E.require(g['technical_readiness_sha256']==A.sha(A.HERE/'TECHNICAL_READINESS.json') and gate['passed'],'independent reviewed technical gate required')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);E.require(not (out/'COMPLETED.json').exists() and not (out/'ERROR.json').exists(),'completed or failed paths never automatically replay')
    t=time.perf_counter();r=None
    try:
        if (out/'PROGRESS.json').exists():r=restore(A.read(out/'PROGRESS.json'))
        else:
            r=A.Runner(a.window,ablation_enabled=True,branch='full');r.bind_grant(a.authorization)
            checkpoint(r,out,'INITIAL');A.save(out/'STARTED.json',dict(started_at=datetime.now(timezone.utc).isoformat(),load_seconds=time.perf_counter()-t,source=r.source_binding(),binding=r.binding()))
        E.require(r.execution_grant['sha256']==A.sha(a.authorization),'cannot switch current grant on resume')
        flow=out/'FLOW.jsonl'
        if flow.exists():
            last=None
            with flow.open(encoding='utf-8') as f:
                for line in f:
                    if line.strip():last=json.loads(line)
            if last:E.require(E.iso(last['at'].replace(' ','T'))<=r.last_completed_event,'FLOW leads saved checkpoint after interruption; stop for explicit reconciliation, no automatic duplicate replay')
        for day in r.inputs.days:
            if not g['start']<=day<=g['end']:continue
            for phase in ((['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']):
                at=E.iso(day+('T00:00:00+08:00' if phase=='ACTION' else 'T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
                if r.last_completed_event is not None and at<=r.last_completed_event:continue
                nf=len(r.account.fills);nt=len(r.account.trades);nr=len(r.results);et=time.perf_counter()
                if phase=='ACTION':r.corporate_actions(day)
                else:r.step(day,phase)
                if phase=='CLOSE':E.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','STOP: optional CLOSE incomplete; no retry authorized')
                r.assert_observers();bridge=r.account.bridge(at)
                record=dict(day=day,at=at,phase=phase,seconds=time.perf_counter()-et,bridge=bridge,new_fills=r.account.fills[nf:],new_trades=r.account.trades[nt:],
                    projection=[dict(at=z['at'],Q=z['projection']['Q'],D=z['projection']['D'],validation=z['projection']['validation']) for z in r.results[nr:]])
                if phase=='CLOSE':record['resources']=resource_view(r,at)
                with flow.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False,default=E.encode)+'\n');f.flush();os.fsync(f.fileno())
                # One rolling exact checkpoint per completed CLOSE supports
                # interruption without writing a full history JSON each day.
                if phase=='CLOSE':checkpoint(r,out,'LATEST')
                print('EVENT',a.window,day,phase,'NAV',bridge['nav'],'fills',len(r.account.fills)-nf,'sec',round(time.perf_counter()-et,2),flush=True)
        E.require(r.last_completed_event.date().isoformat()==g['end'],'bounded path did not reach exact end')
        p=checkpoint(r,out,'FINAL');gz_json(out/'FINAL.json.gz',r.observable(r.last_completed_event));gz_json(out/'TRUSTED.json.gz',r.trusted)
        rr=restore(A.read(out/'PROGRESS.json'));E.require(norm(rr.observable(rr.last_completed_event))==norm(r.observable(r.last_completed_event)),'terminal restart complete observable mismatch')
        A.save(out/'COMPLETED.json',dict(window=a.window,start=g['start'],end=g['end'],initial_cash='1000000',total_seconds=time.perf_counter()-t,final_cursor=r.last_completed_event,final_nav=r.account.nav(r.last_completed_event),final_observable=str(out/'FINAL.json.gz'),checkpoint=str(p),source=r.source_binding(),authorization_sha256=A.sha(a.authorization),terminal_restart_exact=True,unpaid_dividends_separate=True,new_policy='only account_risk6 veto removed; actual risk still measured',development_current_survivor_pool=True))
    except BaseException as ex:
        A.save(out/'ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc(),cursor=r.last_completed_event if r else None,no_auto_retry=True))
        if r:
            checkpoint(r,out,'FAILED')
            gz_json(out/'FAILED.json.gz',r.observable(r.last_completed_event))
        raise
if __name__=='__main__':main()
