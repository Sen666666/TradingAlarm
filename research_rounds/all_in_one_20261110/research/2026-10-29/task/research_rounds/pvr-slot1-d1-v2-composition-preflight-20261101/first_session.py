"""Explicit Apr1-only SC-D1 continuation validation; no Apr2/full path.

Both branches use the same frozen Composition class. Parent identity/source
are checked before adding the explicitly authorized controller/authorization
binding. The full-input Apr1 checkpoint is retained for direct later resume.
"""
from pathlib import Path
from datetime import datetime, timezone, time as dt
from types import MappingProxyType
import copy, json, pickle, time
import composition as A
E,J,L,N,IO,Q,O=A.E,A.J,A.L,A.N,A.IO,A.Q,A.O
import preflight as V
ROOT=O/'SC-April1-first-session'
AUTH=ROOT/'FIRST_SESSION_AUTHORIZATION.json'
PARENT=O/'preflight/SC-Q2-import/checkpoint.pkl'
PARENT_SHA='c596263bd0308d8eb9c10d9a3b9bb091185b00a488677124d7b2c0e38d4c333c'
PARENT_AT=J.M.N.iso('2026-03-31T15:10:00+08:00')
CUT='2026-04-01';AT=J.M.N.iso(CUT+'T15:10:00+08:00')

def save(path,value):IO.write_json(path,J.W.canon(value))

def authorize():
    value=dict(scope='SC_D1_April1_full_vs_physical_first_session_only',
        authority='Root explicit delegation authorizes Apr1 actions/payments/OPEN/CLOSE in both branches, no Apr2',
        parent_checkpoint_sha256=PARENT_SHA,parent_cursor=str(PARENT_AT),
        last_permitted_event=str(AT),composition_sha256=A.sha(O/'composition.py'),
        frozen_D1_v2_sha256=A.D1_SHA,frozen_PVR_sha256=A.PVR_SHA,
        controller_sha256=A.sha(__file__),branches=['full-input','physical-input'],
        preserve_full_input_checkpoint_for_future_resume=True,
        full_PVR_D1_and_SC_Q2_paths_authorized=False)
    if AUTH.exists():
        old=json.loads(AUTH.read_text());assert {k:v for k,v in old.items() if k!='created_at_UTC'}==value
        return old
    value['created_at_UTC']=datetime.now(timezone.utc).isoformat()
    save(AUTH,value);return value

def inventory(r):
    opens={x for x in r.market.sessions['A'] if PARENT_AT<x<=AT}
    closes={x for x in r.market.cutoffs if PARENT_AT<x<=AT}
    acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ)
          for d in r.actions_by_date}
    acts={x for x in acts if PARENT_AT<x<=AT}
    return [dict(at=str(x),action_date=x in acts,opening=x in opens,closing=x in closes)
            for x in sorted(opens|closes|acts)]

def restore_parent(shared,receipts,kw,parent,binding,old_freeze,session_freeze,out):
    r=A.Composition(shared,receipts,rank_mode='H1',enabled=True,horizon_binding=binding,**kw)
    r.source_freeze=dict(old_freeze)
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.restore(PARENT)==PARENT_AT
    a=r.accounts['B']
    checks={k:Q.equal(v,a.__dict__[k]) for k,v in parent['accounts']['B'].items()}
    assert all(checks.values()),[k for k,v in checks.items() if not v]
    assert len(a.pending)==119 and len(a.exits)==16 and not a.buys
    assert sum(x.delay_remaining==0 for x in a.exits.values())==6
    # Metadata extension only AFTER successful old checkpoint identity+freeze
    # restore. No old provenance is rewritten and no account state is reset.
    r.source_freeze=dict(session_freeze)
    return r,dict(passed=True,all_account_fields_exact=checks,
        pending_digest=Q.record_digest(a.pending),exits=J.W.canon(a.exits),
        cancelled_orders_preserved=sum(x.status=='cancelled' for x in a.budget.orders.values()),
        parent_SHA_verified_before_new_controller_binding=True)

def bounded_run(r,out,branch):
    auth=json.loads(AUTH.read_text())
    assert auth['scope']=='SC_D1_April1_full_vs_physical_first_session_only'
    assert auth['controller_sha256']==A.sha(__file__) and auth['composition_sha256']==A.sha(O/'composition.py')
    assert auth['parent_checkpoint_sha256']==A.sha(PARENT)==PARENT_SHA
    assert auth['last_permitted_event']==str(AT) and branch in auth['branches']
    events=inventory(r)
    assert events and events[-1]['at']==str(AT)
    assert all(x['at'][:10]==CUT for x in events)
    assert not (out/'DONE.json').exists(),'completed first-session prefix must be restored, never rerun'
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):
        assert r.run_prepared(out,120,resume_after=PARENT_AT,end=CUT)
    return events

def append_proof(r,parent):
    result={}
    for k in ('daily','opportunities','funding','stage_events','balance_audit','rank_log'):
        old=parent['runner'][k];new=getattr(r,k)
        assert Q.equal(old,new[:len(old)]),('old history overwritten',k)
        appended=new[len(old):]
        assert all(str(x.get('at') or x.get('day'))[:10]==CUT for x in appended)
        result[k]=dict(before=len(old),after=len(new),appended=len(appended),old_prefix_exact=True)
    for k in ('trades','journal','audit_log','decisions','d1_audit'):
        old=parent['accounts']['B'][k];new=getattr(r.accounts['B'],k)
        assert Q.equal(old,new[:len(old)]),('old account history overwritten',k)
        assert all(str(x.get('at') or x.get('day'))[:10]==CUT for x in new[len(old):])
        result['account_'+k]=dict(before=len(old),after=len(new),appended=len(new)-len(old),old_prefix_exact=True)
    assert result['daily']['appended']==1
    return result

def accounting(r,parent):
    a=r.accounts['B'];old=parent['accounts']['B'];d=r.daily[-1];br=r.balance_audit[-1]
    assert str(d['at'])==str(AT)
    for k in ('independent_NAV_difference','budget_NAV_difference','spendable_difference',
              'reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'):
        assert abs(J.D(str(br[k])))<J.D('.000001'),(k,br[k])
    assert all(abs(J.D(str(v)))<J.D('.000001') for v in br['pool_occupancy_difference'].values())
    trades=a.trades[len(old['trades']):];audit=a.audit_log[len(old['audit_log']):]
    splits=[x for x in audit if x['kind']=='split'];events=[]
    for n,x in enumerate(splits):events.append((str(x['at']),0,n,'split',x))
    for n,x in enumerate(trades):events.append((str(x['at']),1,n,'trade',x))
    qty={s:p.shares for s,p in old['positions'].items()}
    for _,_,_,kind,x in sorted(events):
        if kind=='split':qty[x['sid']]=int(J.D(qty.get(x['sid'],0))*J.D(x['ratio']))
        else:qty[x['security_id']]=qty.get(x['security_id'],0)+(1 if x['side']=='buy' else -1)*x['shares']
    assert {s:q for s,q in qty.items() if q}=={s:p.shares for s,p in a.positions.items()}
    assert old['fees_cny']+sum((x['fees_cny'] for x in trades),J.D(0))==a.fees_cny
    equity=sum((J.D(str(d[k])) for k in ('available','order_reserved','settlement_locked',
        'sale_receivable','dividend_receivable','inventory')),J.D(0))-J.D(str(d['payable']))
    assert equity==a.current_nav==J.D(str(d['nav']))
    return dict(passed=True,bridge=br,share_rebuild_from_parent_fills_and_splits=True,
        fee_rebuild_from_parent_fills=True,explicit_equity_components_exact=True,
        inventory_uses_original_asof_marks_not_an_independent_price_source=True,
        end_NAV=str(a.current_nav),end_available=str(a.available),
        fills=len(trades),buy_fills=sum(x['side']=='buy' for x in trades),
        sell_fills=sum(x['side']=='sell' for x in trades),new_fees=str(a.fees_cny-old['fees_cny']),
        splits=len(splits),cash_receivable_equity_components={k:d[k] for k in
          ('available','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory','payable')},
        native_settlement_and_action_audit=[x for x in audit if x['kind'] in
          ('settle','split','dividend_accrual','dividend','dividend_paid')])

def check_PVR_July7_reuse(shared,receipts,kw):
    path=O/'preflight/PVR-D1-full-source/checkpoint.pkl'
    p=pickle.loads(path.read_bytes())
    for name,h in p['source_freeze'].items():assert A.sha(name)==h,('PVR prefix source drift',name)
    r=A.Composition(shared,receipts,rank_mode='PVR_SLOT1',enabled=True,
        horizon_binding=p['runner']['composition_binding']['horizon'],**kw)
    r.source_freeze=copy.deepcopy(p['source_freeze'])
    with IO.atomic_runner_outputs(r,L,ROOT/'PVR-July7-restore-only',canonicalize=J.W.canon):
        at=r.restore(path)
    assert str(at)=='2025-07-07 15:10:00+08:00'
    assert all(Q.equal(v,r.accounts['B'].__dict__[k]) for k,v in p['accounts']['B'].items())
    assert all(Q.equal(v,getattr(r,k)) for k,v in p['runner'].items())
    assert r.composition_binding['horizon']['end']=='2026-06-30'
    result=dict(passed=True,directly_reusable=True,new_import_platform_needed=False,
        checkpoint=str(path),sha256=A.sha(path),cursor=str(at),source_freeze_exact=True,
        actual_engine_identity_verified=True,all_live_account_and_runner_fields_exact=True,
        pending_intents=len(r.accounts['B'].pending),retained_buys=len(r.accounts['B'].buys),
        exit_obligations=len(r.accounts['B'].exits),next_events_begin='2025-07-08',
        input_horizon_already_full_July2025_June2026=True,
        future_resume_rule='same class/mode/binding/source_freeze, run_prepared(resume_after=cursor,end=2026-06-30) after separate authorization',
        new_account_events_executed=0)
    save(ROOT/'PVR_JULY7_REUSE_GATE.json',result)
    return result

def main():
    start=time.monotonic()
    IO.prepare_targets(dict(auth=AUTH,full=ROOT/'full-input/pair',physical=ROOT/'physical-input/pair',
        checkpoint=ROOT/'full-input/checkpoint.pkl',failure=ROOT/'failure/ERROR.json'),directory_keys={'full','physical'})
    assert json.loads((O/'PREFLIGHT_GATE.json').read_text())['passed']
    auth=authorize();N.configure_scores()
    loaded=time.monotonic();shared,receipts,cp,states,ir,identity=A.S.inputs('2025_26');load=time.monotonic()-loaded
    kw=A.S.kwargs(cp,states,ir)
    assert A.sha(PARENT)==PARENT_SHA
    parent=pickle.loads(PARENT.read_bytes());oldfreeze=parent['source_freeze']
    for name,h in oldfreeze.items():assert A.sha(name)==h,('parent frozen source drift',name)
    binding=parent['runner']['composition_binding']['horizon']
    assert binding['input_identity']==A.S.canonical_identity(identity)
    frozen=dict(oldfreeze);frozen.update({str(Path(__file__).resolve()):A.sha(__file__),str(AUTH.resolve()):A.sha(AUTH)})
    save(ROOT/'FIRST_SESSION_SOURCE_FREEZE.json',frozen)
    original_files={str(x):A.sha(x) for x in [PARENT,PARENT.with_suffix('.json'),PARENT.with_suffix('.provenance.json'),
        A.D1/'runs/B_diag/checkpoint.pkl',A.D1/'runs/B_diag/checkpoint.provenance.json']}
    print('APRIL1_INPUTS_READY',round(load,3),flush=True)
    full,proof=restore_parent(shared,receipts,kw,parent,binding,oldfreeze,frozen,ROOT/'restore-parent-full')
    save(ROOT/'FULL_PARENT_RESTORE_PROOF.json',proof)
    out=ROOT/'full-input'
    if (out/'DONE.json').exists():
        with IO.atomic_runner_outputs(full,L,out,canonicalize=J.W.canon):assert full.restore(out/'checkpoint.pkl')==AT
        events=json.loads((ROOT/'EVENT_INVENTORY.json').read_text())
    else:events=bounded_run(full,out,'full-input');save(ROOT/'EVENT_INVENTORY.json',events)
    fullappend=append_proof(full,parent);fullaccounting=accounting(full,parent)
    save(ROOT/'FULL_ACCOUNTING_GATE.json',fullaccounting)
    print('APRIL1_FULL_SAVED',fullaccounting['end_NAV'],fullaccounting['fills'],flush=True)
    phy,rr,pk=A.S.physical_inputs(shared,receipts,cp,states,ir,CUT)
    scores=N.SCORES;cutscore=copy.copy(scores)
    cutscore.values=MappingProxyType({s:MappingProxyType({d:v for d,v in rows.items() if d<=CUT})
        for s,rows in scores.values.items()});calls=[]
    def past_only(sid,day):
        assert day<=CUT,'physical score accessed future date'
        calls.append((sid,day));return N.FrozenScores.at(cutscore,sid,day)
    cutscore.at=past_only;N.SCORES=cutscore
    try:
        physical,proof=restore_parent(phy,rr,pk,parent,binding,oldfreeze,frozen,ROOT/'restore-parent-physical')
        save(ROOT/'PHYSICAL_PARENT_RESTORE_PROOF.json',proof)
        po=ROOT/'physical-input'
        if (po/'DONE.json').exists():
            with IO.atomic_runner_outputs(physical,L,po,canonicalize=J.W.canon):assert physical.restore(po/'checkpoint.pkl')==AT
        else:assert bounded_run(physical,po,'physical-input')==events
        assert Q.equal(V.observable(full),V.observable(physical)),'full/physical economic state mismatch'
        # Every mutable strategy field as well, apart from source-derived lookup
        # coverage and measured run time. No account/ACT/receipt/exit field omitted.
        keys=set(full.__dict__)-{'bundle','market','facts','accounts','cp','pv','matrix','matrix_days',
            'industry_rows','industry_cp','receipts','actions_by_date','episode_starts','run_seconds'}
        assert keys==set(physical.__dict__)-{'bundle','market','facts','accounts','cp','pv','matrix','matrix_days',
            'industry_rows','industry_cp','receipts','actions_by_date','episode_starts','run_seconds'}
        assert all(Q.equal(getattr(full,k),getattr(physical,k)) for k in keys)
        assert physical.episode_starts=={k:v for k,v in full.episode_starts.items() if v<=J.ordinal(CUT)}
        assert all(Q.equal(v,physical.accounts['B'].__dict__[k]) for k,v in full.accounts['B'].__dict__.items() if k not in ('market','facts'))
        assert append_proof(physical,parent)==fullappend
        physicalaccounting=accounting(physical,parent);save(ROOT/'PHYSICAL_ACCOUNTING_GATE.json',physicalaccounting)
    finally:N.SCORES=scores
    restarted=A.Composition(shared,receipts,rank_mode='H1',enabled=True,horizon_binding=binding,**kw)
    restarted.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(restarted,L,ROOT/'restart',canonicalize=J.W.canon):assert restarted.restore(out/'checkpoint.pkl')==AT
    assert Q.equal(V.observable(full),V.observable(restarted))
    assert all(Q.equal(v,restarted.accounts['B'].__dict__[k]) for k,v in full.accounts['B'].__dict__.items() if k not in ('market','facts'))
    pvrreuse=check_PVR_July7_reuse(shared,receipts,kw)
    assert all(A.sha(p)==h for p,h in original_files.items())
    assert all(A.sha(p)==h for p,h in frozen.items())
    result=dict(passed=True,scope='SC-D1 April1 bounded continuation technical check',
        no_April2_or_later_events=True,full_financial_paths=0,
        full_checkpoint=str(out/'checkpoint.pkl'),full_checkpoint_sha256=A.sha(out/'checkpoint.pkl'),
        full_provenance_sha256=A.sha(out/'checkpoint.provenance.json'),cursor=str(AT),
        original_119_intents_16_exit_obligations_exact_before_events=True,
        complete_economic_state_and_strategy_fields_full_vs_physical_exact=True,
        history_append_proof=fullappend,accounting=fullaccounting,
        full_input_restart_all_native_fields_exact=True,industry_lookup_past_prefix_exact=True,
        H1_no_PVR_score_reads=len(calls)==0,physical_score_read_count=len(calls),
        end_pending_intents=len(full.accounts['B'].pending),end_exit_obligations=len(full.accounts['B'].exits),
        end_active_buy_orders=len(full.accounts['B'].buys),
        end_exit_delay_remaining_counts={str(n):sum(x.delay_remaining==n for x in full.accounts['B'].exits.values()) for n in (0,1)},
        old_checkpoint_files_unchanged=original_files,source_freeze=frozen,
        PVR_July7_checkpoint_directly_reusable=pvrreuse['directly_reusable'],
        seconds=dict(input_load=load,full=full.run_seconds,physical=physical.run_seconds,total=time.monotonic()-start),
        further_financial_event_permission_required=True)
    save(ROOT/'FIRST_SESSION_GATE.json',result)
    print('APRIL1_PHYSICAL_RESTART_PASS',result['seconds'],flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as ex:
        save(ROOT/'failure/ERROR.json',dict(type=type(ex).__name__,reason=str(ex),
            scope='SC April1 only; preserve successful full-input checkpoint; no April2'));raise
