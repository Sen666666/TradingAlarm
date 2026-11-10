"""Explicitly authorized Jan3-only prefix. No Jan4/year execution authority.

The unchanged native event loop is called with a hard Jan3 finish after a
separate bounded authorization check. H.run_prepared's full-year gate remains
unchanged and its authorization file remains absent. Runtime trading class is
H.Continuation so the full-input Jan3 checkpoint can later resume unchanged.
"""
from pathlib import Path
from types import MappingProxyType
from datetime import datetime,timezone
from decimal import Decimal as D
import sys,copy,pickle,time,json,collections
import horizon_import as H
N,J,L,IO,E,O,P=H.N,H.J,H.L,H.IO,H.E,H.O,H.P
sys.path.insert(0,str(P));import execution_support as S
CUT='2023-01-03';AT=J.M.N.iso(CUT+'T15:10:00+08:00')
ROOT=O/'first-session';AUTH=ROOT/'FIRST_SESSION_AUTHORIZATION.json'

def save(p,x):IO.write_json(p,J.W.canon(x))

def authorization():
    value=dict(scope='PVR_SLOT1_Jan3_2023_bounded_physical_prefix_only',
        authority='Root delegation explicitly authorizes both full-input and physically truncated Jan3 branches only',
        parent_cursor=str(H.PARENT_AT),last_permitted_event=str(AT),branches=['full-input','physical-input'],
        native_adapter_sha256=H.sha(N.__file__),horizon_import_sha256=H.sha(H.__file__),
        import_binding_sha256=H.sha(H.DEFAULT_BINDING),controller_sha256=H.sha(__file__),
        parent_checkpoint_sha256=H.sha(P/'runs/2022/checkpoint.pkl'),
        import_gate_sha256=H.sha(O/'IMPORT_PREFLIGHT_GATE.json'),
        full_2023_account_path_authorized=False,no_Jan4_or_later=True,
        preserve_full_branch_checkpoint_for_future_resume=True)
    if AUTH.exists():
        old=H.read(AUTH);assert {k:v for k,v in old.items() if k!='created_at_UTC'}==value
        return old
    value['created_at_UTC']=datetime.now(timezone.utc).isoformat();save(AUTH,value);return value

def bounded_run(r,out,branch):
    a=H.read(AUTH)
    assert a['scope']=='PVR_SLOT1_Jan3_2023_bounded_physical_prefix_only'
    assert a['controller_sha256']==H.sha(__file__) and a['horizon_import_sha256']==H.sha(H.__file__)
    assert a['native_adapter_sha256']==H.ADAPTER_SHA==H.sha(N.__file__)
    assert a['import_binding_sha256']==H.sha(H.DEFAULT_BINDING)
    assert a['last_permitted_event']==str(AT) and branch in a['branches']
    assert not (O/'FULL_2023_RUN_AUTHORIZATION.json').exists()
    assert not (out/'DONE.json').exists(),'completed prefix must be restored, never rerun'
    assert r.horizon_last_completed==H.PARENT_AT
    inventory=r.next_event_inventory(CUT)
    assert inventory[0]['at']=='2023-01-03 09:30:00+08:00' and inventory[-1]['at']==str(AT)
    cursor=r._claim_cursor(H.PARENT_AT)
    try:
        with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):
            complete=H._run_original(r,out,120,resume_after=cursor,end=CUT)
        assert complete and r.horizon_last_completed==AT
    finally:r._cursor_claimed=False
    return inventory

def economic_state(r):
    x=E.observable(r)
    # The only excluded extra metadata describes input lookup coverage, not state.
    x['runner'].pop('horizon_transition',None)
    return x

def historical_append_proof(r,parent):
    result={}
    for k in ('daily','opportunities','funding','stage_events','balance_audit','rank_log'):
        old=parent['runner'][k];new=getattr(r,k)
        assert E.equal(old,new[:len(old)]),('historical stream overwritten',k)
        assert all(str(x.get('at') or x.get('day'))[:10]<=CUT for x in new[len(old):])
        result[k]=dict(before=len(old),after=len(new),appended=len(new)-len(old),historical_prefix_exact=True)
    for k in ('trades','journal','audit_log','decisions'):
        old=parent['accounts']['B'][k];new=getattr(r.accounts['B'],k)
        assert E.equal(old,new[:len(old)]),('historical account stream overwritten',k)
        for x in new[len(old):]:assert str(x.get('at') or x.get('day'))[:10]<=CUT
        result['account_'+k]=dict(before=len(old),after=len(new),appended=len(new)-len(old),historical_prefix_exact=True)
    assert len(r.daily)==len(parent['runner']['daily'])+1
    return result

def accounting(r,parent):
    a=r.accounts['B'];old=parent['accounts']['B'];d=r.daily[-1];br=r.balance_audit[-1]
    assert str(d['at'])==str(AT)
    keys=['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference',
          'capital_occupancy_difference','maximum_stock_quantity_difference']
    for k in keys:assert abs(D(str(br[k])))<D('.000001'),(k,br[k])
    assert all(abs(D(str(x)))<D('.000001') for x in br['pool_occupancy_difference'].values())
    trades=a.trades[len(old['trades']):];audit=a.audit_log[len(old['audit_log']):]
    splits=[x for x in audit if x['kind']=='split'];events=[]
    for n,x in enumerate(splits):events.append((str(x['at']),0,n,'split',x))
    for n,x in enumerate(trades):events.append((str(x['at']),1,n,'trade',x))
    quantities={s:p.shares for s,p in old['positions'].items()}
    for _,_,_,kind,x in sorted(events):
        if kind=='split':quantities[x['sid']]=int(D(quantities.get(x['sid'],0))*D(x['ratio']))
        else:quantities[x['security_id']]=quantities.get(x['security_id'],0)+(1 if x['side']=='buy' else -1)*x['shares']
    assert {s:q for s,q in quantities.items() if q}=={s:p.shares for s,p in a.positions.items()}
    assert old['fees_cny']+sum((x['fees_cny'] for x in trades),D(0))==a.fees_cny
    equity=sum((D(str(d[k])) for k in ['available','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory']),D(0))-D(str(d['payable']))
    assert equity==a.current_nav==D(str(d['nav']))
    for sid,pos in a.positions.items():
        assert sum(x.qty for x in a.budget.lots if x.stock==sid)==pos.shares
    return dict(passed=True,bridge=br,share_rebuild_from_parent_and_real_fills=True,
        fee_rebuild_from_parent_and_real_fills=True,explicit_equity_components_exact=True,
        inventory_marks='original as-of market marks; not independent external prices',
        native_available_cash_and_pool_mirror_assertions=True,
        parent_NAV=str(old['current_nav']),end_NAV=str(a.current_nav),available=str(a.available),
        new_fills=len(trades),new_buy_fills=sum(x['side']=='buy' for x in trades),
        new_sell_fills=sum(x['side']=='sell' for x in trades),new_splits=len(splits),
        new_fees=str(a.fees_cny-old['fees_cny']),end_receivables={k:d[k] for k in ['sale_receivable','dividend_receivable']},
        raw_native_settlement_and_action_audit=[x for x in audit if x['kind'] in ('settle','split','dividend','dividend_paid')])

def main():
    begun=time.monotonic();assert H.read(O/'IMPORT_PREFLIGHT_GATE.json')['passed']
    assert not (O/'FULL_2023_RUN_AUTHORIZATION.json').exists()
    IO.prepare_targets(dict(authorization=AUTH,full=ROOT/'full-input/pair',physical=ROOT/'physical-input/pair',
        failure=ROOT/'failure/ERROR.json',checkpoint=ROOT/'full-input/checkpoint.pkl'),directory_keys={'full','physical'})
    authorization();N.configure_scores(O/'SCORES_MANIFEST.json')
    # Redirect only derived input-loader logging so old readiness artifacts stay immutable.
    oldsave=H.save
    try:
        H.save=lambda path,value:save(ROOT/'input-readiness'/Path(path).name,value)
        t=time.monotonic();shared,receipts,cp,states,ir,identity=H.inputs();load=time.monotonic()-t
    finally:H.save=oldsave
    frozen=H.source_freeze();frozen.update({str(Path(__file__).resolve()):H.sha(__file__),str(AUTH.resolve()):H.sha(AUTH)})
    save(ROOT/'FIRST_SESSION_SOURCE_FREEZE.json',frozen)
    parent=pickle.loads((P/'runs/2022/checkpoint.pkl').read_bytes())
    kw=S.kwargs(cp,states,ir);r=H.Continuation(shared,receipts,**kw);r.source_freeze=dict(frozen)
    proof=r.import_verified_parent();save(ROOT/'FULL_PARENT_IMPORT_PROOF.json',proof)
    original79=copy.deepcopy(r.accounts['B'].pending)
    assert E.equal(original79,parent['accounts']['B']['pending'])
    out=ROOT/'full-input'
    if (out/'DONE.json').exists():
        with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.restore(out/'checkpoint.pkl')==AT
        inventory=r.next_event_inventory(CUT) if r.horizon_last_completed==H.PARENT_AT else H.read(ROOT/'FULL_EVENT_INVENTORY.json')
    else:
        inventory=bounded_run(r,out,'full-input');save(ROOT/'FULL_EVENT_INVENTORY.json',inventory)
    print('JAN3_FULL_SAVED',str(r.accounts['B'].current_nav),len(r.accounts['B'].trades)-len(parent['accounts']['B']['trades']),flush=True)
    full_append=historical_append_proof(r,parent);full_accounting=accounting(r,parent)
    save(ROOT/'FULL_ACCOUNTING_GATE.json',full_accounting)
    # Restrict every native input view and the actual score values, not just the loop end.
    phy,rr,pk=S.physical_inputs(shared,receipts,cp,states,ir,CUT)
    fullscores=N.SCORES;cutscore=copy.copy(fullscores)
    cutscore.values=MappingProxyType({s:MappingProxyType({d:v for d,v in rs.items() if d<=CUT}) for s,rs in fullscores.values.items()})
    calls=[]
    def past_only(sid,day):
        assert day<=CUT,'future PVR read in physical branch'
        calls.append((sid,day));return N.FrozenScores.at(cutscore,sid,day)
    cutscore.at=past_only;N.SCORES=cutscore
    try:
        q=H.Continuation(phy,rr,**pk);q.source_freeze=dict(frozen)
        qproof=q.import_verified_parent();save(ROOT/'PHYSICAL_PARENT_IMPORT_PROOF.json',qproof)
        assert E.equal(q.accounts['B'].pending,original79)
        assert all(qproof['all_account_fields_equal'].values()) and all(qproof['all_strategy_fields_equal'].values())
        physical=ROOT/'physical-input'
        if (physical/'DONE.json').exists():
            with IO.atomic_runner_outputs(q,L,physical,canonicalize=J.W.canon):assert q.restore(physical/'checkpoint.pkl')==AT
        else:assert bounded_run(q,physical,'physical-input')==inventory
        assert E.equal(economic_state(q),economic_state(r)),'full vs physical economic state differs'
        past={k:v for k,v in r.episode_starts.items() if v<=AT.date().toordinal()}
        assert q.episode_starts==past,'industry lookup past prefix differs'
        assert q.rank_log==r.rank_log
        physical_append=historical_append_proof(q,parent);physical_accounting=accounting(q,parent)
        assert full_append==physical_append
        save(ROOT/'PHYSICAL_ACCOUNTING_GATE.json',physical_accounting)
    finally:N.SCORES=fullscores
    restarted=H.Continuation(shared,receipts,**kw);restarted.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(restarted,L,ROOT/'restart',canonicalize=J.W.canon):
        assert restarted.restore(out/'checkpoint.pkl')==AT
    assert E.equal(economic_state(restarted),economic_state(r)) and restarted.episode_starts==r.episode_starts
    assert all(i['rank']==i['priority_rank'] and 'original_H1_rank' in i for i in restarted.accounts['B'].pending)
    assert all(H.sha(p)==h for p,h in frozen.items())
    result=dict(passed=True,scope='Jan3 bounded continuation technical prefix only',Jan4_or_later_account_events=0,
        branches=['full-input','physical-input'],last_completed_event=str(AT),
        full_input_checkpoint_reusable_without_rerunning_Jan3=str(out/'checkpoint.pkl'),
        full_checkpoint_sha256=H.sha(out/'checkpoint.pkl'),parent_sha256_unchanged=H.sha(P/'runs/2022/checkpoint.pkl'),
        original79_frozen_intents_exact_before_OPEN=True,complete_economic_state_and_event_streams_exact=True,
        all_historical_streams_append_only=full_append,industry_lookup_past_prefix_exact=True,
        physical_future_PVR_absent_and_reader_guarded=True,physical_score_reads=len(calls),
        physical_max_score_date=max((d for s,d in calls),default=None),
        full_input_restart_complete_state_exact=True,full_accounting=full_accounting,
        end_pending_intents=len(r.accounts['B'].pending),native_source_sha256=H.sha(N.__file__),
        horizon_source_sha256=H.sha(H.__file__),controller_sha256=H.sha(__file__),
        authorization_sha256=H.sha(AUTH),sources=frozen,
        seconds=dict(input_load=load,full_prefix=r.run_seconds,physical_prefix=q.run_seconds,total=time.monotonic()-begun),
        full_year_authorization_absent=True,financial_full_year_paths_started=0)
    save(ROOT/'FIRST_SESSION_GATE.json',result)
    print('JAN3_PHYSICAL_RESTART_PASS',result['seconds'],flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        save(ROOT/'failure/ERROR.json',dict(type=type(e).__name__,reason=str(e),scope='Jan3 only; preserve completed full-input prefix'));raise
