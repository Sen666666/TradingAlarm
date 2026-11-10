"""Read-only direct-restore readiness and precise PVR-D1 audit addendum."""
from pathlib import Path
from datetime import datetime,time as dt
import ast, collections, copy, gzip, json, pickle, shlex, sys, time
import composition as A
import run_SC_D1_Q2 as C
J,L,N,IO,Q,O=A.J,A.L,A.N,A.IO,A.Q,A.O
ROOT=O/'SC-D1-Q2-readiness'

def read(path):return json.loads(Path(path).read_text())
def rows(path):
    with gzip.open(path,'rt') as f:return [json.loads(x) for x in f]
def save(path,value):IO.write_json(path,J.W.canon(value))

def event_bounds(r,after,end):
    finish=J.M.N.iso(end+'T15:10:00+08:00')
    opens={x for x in r.market.sessions['A'] if after<x<=finish}
    closes={x for x in r.market.cutoffs if after<x<=finish}
    acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ) for d in r.actions_by_date}
    acts={x for x in acts if after<x<=finish}
    return [dict(at=str(x),opening=x in opens,closing=x in closes,action_date=x in acts)
        for x in sorted(opens|closes|acts)]

def main():
    begin=time.monotonic()
    assert not C.AUTH.exists(),'no future financial authorization should be created by readiness'
    guard={}
    try:C.require_authorization()
    except AssertionError as ex:guard['missing_authorization_rejected_before_loading_or_account']=str(ex)
    else:raise AssertionError('future SC financial path unexpectedly authorized')
    N.configure_scores();load=time.monotonic()
    shared,receipts,cp,states,ir,identity=A.S.inputs('2025_26');loading=time.monotonic()-load
    parent=pickle.loads(C.PARENT.read_bytes());assert A.sha(C.PARENT)==C.PARENT_SHA
    freeze=parent['source_freeze'];assert all(A.sha(p)==h for p,h in freeze.items())
    binding=parent['runner']['composition_binding']['horizon']
    assert binding['input_identity']==A.S.canonical_identity(identity)
    r=A.Composition(shared,receipts,rank_mode='H1',enabled=True,horizon_binding=binding,
        **A.S.kwargs(cp,states,ir));r.source_freeze=copy.deepcopy(freeze)
    with IO.atomic_runner_outputs(r,L,ROOT/'direct-restore-only',canonicalize=J.W.canon):
        assert r.restore(C.PARENT)==C.AT
        actual_identity=IO.runner_identity(r)
    account=r.accounts['B'];old=parent['accounts']['B']
    ac={k:Q.equal(v,account.__dict__[k]) for k,v in old.items()}
    rc={k:Q.equal(v,getattr(r,k)) for k,v in parent['runner'].items()}
    assert all(ac.values()) and all(rc.values())
    assert len(account.pending)==270 and len(account.exits)==11 and not account.buys
    assert sum(o.delay_remaining==0 for o in account.exits.values())==10
    pending=[dict(sid=i['sid'],role=i['role'],rank=i['rank'],score=i['score'],
        decision_at=i['clock'].decision_at,earliest_execution_at=i['clock'].earliest_execution_at,
        CP1_id=i.get('CP1_id'),epoch=i.get('epoch'),budget=i['budget'],cap=i['cap'],floor=i['floor'])
        for i in account.pending]
    save(ROOT/'ALL_270_FROZEN_PENDING_KEYS.json',pending)
    save(ROOT/'ALL_11_NATIVE_EXIT_OBLIGATIONS.json',account.exits)
    future=event_bounds(r,C.AT,'2026-06-30')
    assert future and all(x['at'][:10]>='2026-04-02' for x in future)
    assert sum(x['closing'] for x in future)==59 and len(r.daily)==183
    save(ROOT/'REMAINING_EVENT_INVENTORY.json',future)
    a=account;last=r.daily[-1]
    state=dict(cursor=str(C.AT),NAV=str(a.current_nav),original_initial_cash=str(a.initial_cash),
        cash_receivable_equity_components={k:last[k] for k in ('available','order_reserved','settlement_locked',
            'sale_receivable','dividend_receivable','inventory','payable')},
        actual_stocks=len(a.positions),actual_live_layers=sum(x['qty']>0 for x in a.layers),
        positions={s:p.shares for s,p in a.positions.items()},
        pending_intents=len(a.pending),unique_pending_stocks=len({i['sid'] for i in a.pending}),
        pending_roles=dict(collections.Counter(i['role'] for i in a.pending)),
        pending_all_object_digest=Q.record_digest(a.pending),native_exit_obligations=len(a.exits),
        native_exit_delay_remaining_counts=dict(collections.Counter(str(x.delay_remaining) for x in a.exits.values())),
        active_buy_orders=len(a.buys),historical_D1_order_records=len(a.d1_orders),
        historical_D1_exit_records=len(a.d1_exits),historical_D1_audit_records=len(a.d1_audit),
        budget_cancelled_historical_orders=sum(x.status=='cancelled' for x in a.budget.orders.values()),
        risk_state=a.risk_state,core_epochs=len(a.core_epoch),
        consumed_receipts=len(a.budget.consumed),shared_loss_record_only=a.budget.shared_loss,
        old_daily_rows=len(r.daily),old_fill_records=len(a.trades),
        source_mode=dict(rank=r.rank_mode,delay_enabled=r.d1_enabled,account_risk_cap=a.d1_account_cap),
        next_event=future[0],last_event=future[-1],remaining_market_sessions=sum(x['closing'] for x in future),
        all_account_fields_preserved=ac,all_saved_runner_fields_preserved=rc)
    save(ROOT/'CONTINUOUS_INITIAL_STATE.json',state)
    command=shlex.join([sys.executable,'-B',str(O/'run_SC_D1_Q2.py'),'--execute'])
    requirements=dict(scope=C.SCOPE,root_approved='MUST be provided by later root authorization',
        parent_checkpoint_sha256=C.PARENT_SHA,composition_sha256=C.COMPOSITION_SHA,
        controller_sha256=A.sha(C.__file__),resume_strictly_after=str(C.AT),end='2026-06-30',
        only_one_SC_continuation=True,SC_April1_independent_audit_reviewed='MUST be true after review',
        write_to=str(C.AUTH),not_an_authorization=True)
    save(ROOT/'FUTURE_AUTHORIZATION_REQUIREMENTS.json',requirements)
    source=dict(frozen_April1_sources=freeze,new_prepared_controller_sha256=A.sha(C.__file__),
        readiness_controller_sha256=A.sha(__file__),input_identity=A.S.canonical_identity(identity),
        scores_manifest_sha256=N.SCORES.manifest_sha256,
        parent_checkpoint_sha256=A.sha(C.PARENT),parent_provenance_sha256=A.sha(C.PARENT.with_suffix('.provenance.json')))
    save(ROOT/'SOURCE_AND_INPUT_SHA256.json',source)
    save(ROOT/'READY.json',dict(passed=True,readiness_only=True,new_account_events=0,
        exact_future_command=command,authorization_file_absent=True,guards=guard,
        direct_native_restore=True,new_recovery_or_import_platform=False,
        preserve_270_intents_11_exits_and_all_delay_state=True,
        no_configure_d1_after_restore=True,no_cash_positions_ACT_loss_or_receipt_reset=True,
        first_remaining_event=future[0],remaining_sessions=59,
        actual_runtime_identity=actual_identity,
        seconds=dict(input_load=loading,total=time.monotonic()-begin)))

    # Exact money fields and event boundaries for the already completed PVR-D1.
    comparison=read(O/'analysis/2025_26/COMPARISON.json');money={}
    roots={'normal':A.P/'runs/2025_26','D1':O/'run-PVR-D1'}
    for ref,root in roots.items():
        ds=rows(root/'pair/daily.jsonl.gz');real=comparison[ref]['actual_realized_unrealized_dividends']
        money[ref]=dict(**real,terminal_dividend_receivable=ds[-1]['dividend_receivable'],
            terminal_sale_receivable=ds[-1]['sale_receivable'],terminal_settlement_locked=ds[-1]['settlement_locked'],
            terminal_available=ds[-1]['available'],terminal_inventory=ds[-1]['inventory'],
            first_decision_close=ds[0]['at'],terminal_close=ds[-1]['at'],daily_closes=len(ds),
            book_sha256=A.sha(root/'pair/B.json.gz'))
    prefix=read(O/'run-PVR-D1/PREFIX_REUSE_PROOF.json')
    all_events=event_bounds(r,J.M.N.iso('2025-07-01T15:09:59+08:00'),'2026-06-30')
    after_prefix=event_bounds(r,J.M.N.iso(prefix['cursor']),'2026-06-30')
    save(ROOT/'PVR_D1_AUDIT_MONEY_AND_BOUNDARY_ADDENDUM.json',dict(
        precise_financial_fields=money,open_layer_category_is_not_actual_unrealized=True,
        recognized_dividends_include_unpaid_AR=True,
        reused_July7_identity_and_stream_proof=prefix,
        prefix_provenance=read(O/'preflight/PVR-D1-full-source/checkpoint.provenance.json'),
        first_full_window_event=all_events[0],last_full_window_event=all_events[-1],
        first_event_after_reused_prefix=after_prefix[0],technical_prefix_reexecuted=False,
        full_remaining_authorization=read(O/'run-PVR-D1/FULL_RUN_AUTHORIZATION.json'),
        actual_start=read(O/'run-PVR-D1/ACTUAL_START.json'),completion=read(O/'run-PVR-D1/EXECUTION_STATUS.json')))
    print('SC_Q2_ZERO_EVENT_READY',state['NAV'],state['pending_roles'],future[0],flush=True)
    print('PREPARED_COMMAND_NOT_RUN',command,flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as ex:
        save(ROOT/'failure/ERROR.json',dict(type=type(ex).__name__,reason=str(ex),new_account_events=0));raise
