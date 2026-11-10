"""Read saved actual-event checkpoints only. No event/window/step invocation.

Reuse frozen provenance/source + already verified certificate origin; do not
re-run the unchanged expensive C solver merely to summarize an actual fill.
"""
from pathlib import Path
from dataclasses import asdict
import argparse,pickle
import replay_runtime as X
E=X.E

def read_verified(p,kind):
    p=Path(p);s=X.read(p.with_suffix('.provenance.json'));E.require(X.sha(p)==s['checkpoint_sha256'],'saved checkpoint SHA differs')
    r=pickle.loads(p.read_bytes());E.require(r.binding()==s['binding'] and E.IO.runner_identity(r)==s['engine_identity'],'actual source/engine identity differs')
    E.require(type(r) is (X.ReplayRunner if kind=='diagnostic' else X.M.MonthRunner),'wrong actual checkpoint class')
    r.account.owner=r;r.assert_observers();return r

def comparison(r,checkpoint):
    cell=X.read(X.HERE/'REPLAY_INPUT_BINDING.json')['cases'][r.replay_import['case']]
    phase=r.last_phase
    # ACTION stores an ACTION cursor but original last_phase remains the close.
    phase='ACTION' if r.last_completed_event.hour==0 else 'OPEN'
    old=Path(cell['baseline_open']) if phase=='OPEN' else Path(cell['baseline_open']).with_name(cell['next_day']+'-ACTION.pkl')
    base=read_verified(old,'baseline');E.require(base.last_completed_event==r.last_completed_event,'different event cursor')
    exact=E.digest(X.snapshot(r))==E.digest(X.snapshot(base))
    if not r.keep_approved_risk:E.require(exact,'OFF original entire actual-event state differs')
    cid=r.active['certificate_id'];at=E.iso(cell['next_day']+'T00:00:00+08:00');rows=[]
    def execution(account,sid):
        os=[(oid,m) for oid,m in account.supports.items() if m.get('C_certificate')==cid and m['original_intent']['sid']==sid]
        E.require(len(os)<=1,'multiple C order per stock authority')
        if not os:return dict(order=None,reserved=0,filled=0,fills=[],amendments=[])
        oid,m=os[0];au=[v for v in account.audit_log if v.get('kind')=='reserve' and v.get('order_id')==oid];E.require(len(au)==1,'reserve identity missing')
        fs=[f for f in account.fills if f.receipt_id in account.inventory_map and account.capital_meta[account.inventory_map[f.receipt_id]['layer']]['order']==oid]
        return dict(order=oid,reserved=au[0]['target_shares'],filled=sum(f.shares for f in fs),fills=[asdict(f) for f in fs],amendments=[v for v in account.native_callbacks if v.get('kind')=='amend_before_fill' and v.get('order')==oid],reserved_gross=au[0]['gross_budget_cny'])
    for sid,q in r.active['Q'].items():
        if q:
            proof=X.R.approved_payload(X.old_view(r),cid,sid,full_verify=False)
            rows.append(dict(sid=sid,original_approved=proof,baseline=execution(base.account,sid),actual_branch=execution(r.account,sid),permanent_risk=r.risk.approvals.get(cid+'|'+sid)))
    current=[asdict(f) for f in r.account.fills if f.at>=at];bf=[asdict(f) for f in base.account.fills if f.at>=at]
    result=dict(scope='read-only actual one-event diagnostic; no continuous strategy return',case=r.replay_import['case'],risk='on' if r.keep_approved_risk else 'off',phase=phase,cursor=r.last_completed_event,
        checkpoint=str(Path(checkpoint).resolve()),checkpoint_sha256=X.sha(checkpoint),baseline_checkpoint=str(old),baseline_checkpoint_sha256=X.sha(old),
        origin_checkpoint_sha256=r.replay_import['parent_checkpoint_sha256'],off_complete_original_state_identity=exact if not r.keep_approved_risk else None,
        source_engine_and_all_financial_bridges=True,financial_events_invoked_by_analysis=0,C_authorization_rows=rows,
        actual_all_fills=current,baseline_all_fills=bf,actual_bridge=r.account.bridge(r.last_completed_event),baseline_bridge=base.account.bridge(base.last_completed_event),
        rejections_this_session=[v for v in r.account.rejections if v.get('at') is not None and v['at']>=at],
        actual_sell_obligations={s:asdict(o) for s,o in r.account.exits.items()},original_D_not_recomputed=r.active['D']==base.active['D'])
    return result
