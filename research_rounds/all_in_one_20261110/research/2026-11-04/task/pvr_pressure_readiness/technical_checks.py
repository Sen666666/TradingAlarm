"""Affected contracts and bounded native prefix only, never a full path."""
from pathlib import Path
from types import SimpleNamespace as NS
import copy,gzip,json,pickle,time,traceback,sys
import pressure_adapter as A
J,N,L,IO,S,Q=A.J,A.N,A.L,A.IO,A.S,A.Q
O=A.O;CUT='2025-07-03';SPLIT='2025-07-02'
STREAMS=[('daily','daily'),('funding','funding'),('opportunities','opportunities'),('stage_events','industry'),('balance_audit','balances'),('rank_log','rank-policy')]
def save(name,x):IO.write_json(O/name,J.W.canon(stable(x)))
def stable(x):
    if isinstance(x,(set,frozenset)):return sorted((stable(v) for v in x),key=lambda v:json.dumps(J.W.canon(v),sort_keys=True))
    if isinstance(x,dict):return {k:stable(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [stable(v) for v in x]
    return x
def observable(r):
    excluded={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date','episode_starts','run_seconds','source_freeze'}
    return J.W.canon(stable(dict(accounts={k:{f:v for f,v in a.__dict__.items() if f not in ('market','facts','budget','d1_calendar')} for k,a in r.accounts.items()},
        budgets={k:vars(a.budget) for k,a in r.accounts.items()},runner={k:(vars(v) if k=='b0' else v) for k,v in r.__dict__.items() if k not in excluded})))
def frozen():
    z=A.source_freeze()
    for p in (Path(__file__),O/'cross_process_restart.py'):z[str(p)]=N.sha(p)
    return z
def binding(identity):return dict(start='2025-07-01',end='2026-06-30',input_identity=S.canonical_identity(identity),scope='original full input; bounded technical prefix')
def construct(mode,shared,receipts,kw,horizon):
    cls={'cost1_OFF':A.CostRunner,'cost2_OFF':A.CostRunner,'cost2_ON':A.No60CostRunner,'D1_OFF':A.D1Runner,'D1_ON':A.No60D1Runner}[mode]
    opts=dict(cost=1 if mode=='cost1_OFF' else 2) if mode.startswith('cost') else dict(horizon_binding=copy.deepcopy(horizon))
    return cls(shared,receipts,**opts,**kw)
def run(r,name,end=CUT,after=None):
    out=O/'prefix'/name;assert not (out/'DONE.json').exists(),'completed technical prefix not silently repeated'
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out,120,end=end,resume_after=after)
    return r
def eventday(x):
    value=x.get('at') or x.get('day') or x.get('receipt',{}).get('at')
    assert value is not None;return str(value)[:10]
def saved_streams(r,parent):
    result={}
    for field,name in STREAMS:
        with gzip.open(parent/(name+'.jsonl.gz'),'rt') as f:rows=[json.loads(x) for x in f]
        old=[x for x in rows if eventday(x)<=CUT]
        assert J.W.canon(getattr(r,field))==old,('old saved stream mismatch',field)
        result[field]=len(old)
    with gzip.open(parent/'B.json.gz','rt') as f:book=json.load(f)
    for field,key in [('trades','trades'),('journal','journal'),('audit_log','audit'),('decisions','decisions')]:
        old=[x for x in book[key] if eventday(x)<=CUT]
        assert J.W.canon(getattr(r.accounts['B'],field))==old,('old saved account stream mismatch',field)
        result[field]=len(old)
    return result
def affected():
    # Original fixture uses the short import name; bind the verified same module.
    sys.modules.setdefault('d1_runner',A.E)
    assert sys.modules['d1_runner'] is A.E
    F=A.A.load('pvr_pressure_D1_fixtures',A.A.D1/'test_real_pair.py');T=F.T;D=J.D
    # Source involution proves every non-pool amendment token is unchanged.
    assert A.AMEND_NO60.replace(A.AMEND_NEW,A.AMEND_OLD)==A.AMEND_SOURCE
    import inspect,textwrap
    original=textwrap.dedent(inspect.getsource(J.Runner.opening))
    assert A.E.R.OPENING.replace("self.market.window(sid,at,'sell',a.cost_multiplier)","self.market.window(sid,at,'sell',1)").replace("self.market.window(sid,at,'buy',a.cost_multiplier)","self.market.window(sid,at,'buy',1)")==original
    detail=[]
    def fixture(on,pool='confirmed'):
        r,a,i,t,c,t1,prices,cap,unavailable=F.setup(ref='B_diag',late=True)
        if on:a.__class__=A.No60D1Account;a.budget.__class__=A.B.NoConfirmed60Budget
        r.opening(a,t);o=a.buys['A'];bo=a.budget.orders[a.order_bridge[o.order_id]]
        bo.pool=pool
        F.closing(r,a,c)
        a.d1_enabled=False;a.delay_events=0
        # Explicit pre-existing inventory fixture; not a policy admission.
        oldbase=T.BASE
        try:
            # The original helper fills at BASE+1day; keep monotone fixture time.
            T.BASE=t1-F.P.timedelta(days=1)
            for k in range(7 if pool=='confirmed' else 2):T.legacy(a,'OLD'+str(k),'X'+str(k),9000,pool=pool,floor='9.999')
        finally:T.BASE=oldbase
        a.d1_enabled=True;a.delay_events=1;a.fixture_state['price']=D(10)
        return r,a,i,t1,bo
    for on in (False,True):
        r,a,i,t1,bo=fixture(on)
        consumed=set(a.budget.consumed);q=a.buys['A'].remaining_shares;p=a.buys['A'].remaining_budget_cny
        result=a.amend_d1('A',t1,D(10),T.T.RULE,T.T.MINIMUM)
        assert result is on
        if on:
            assert a.buys['A'].remaining_shares<=q and a.buys['A'].remaining_budget_cny<=p
            assert a.budget.consumed==consumed
        else:assert 'pool_capital' in a.d1_audit[-1]['reason']
        detail.append(dict(case='confirmed_above60',No60=on,accepted=result))
    r,a,i,t1,bo=fixture(True,pool='probe')
    assert not a.amend_d1('A',t1,D(10),T.T.RULE,T.T.MINIMUM)
    assert 'pool_capital' in a.d1_audit[-1]['reason']
    detail.append(dict(case='probe10_retained',accepted=False))
    r,a,i,t1,bo=fixture(True)
    assert not a.amend_d1('A',t1,D(9),T.T.RULE,T.T.MINIMUM)
    assert a.d1_audit[-1]['reason']=='open_at_or_below_protection'
    detail.append(dict(case='frozen_protection_retained',accepted=False))
    # Reuse actual native cost ledger fixture; no old output writer invoked.
    C=A.A.load('pvr_pressure_cost_fixtures',A.W/'execution-pressure-preflight-20261031/test_cost_adapter.py')
    case=C.Tests('test_cost2_real_buy_and_sell_fee_slip_and_cash_bridge')
    case.test_cost2_real_buy_and_sell_fee_slip_and_cash_bridge()
    save('AFFECTED_GATE.json',dict(passed=True,details=detail,amendment_single_predicate_only=True,
        cost_opening_exact_two_window_arguments_only=True,cost2_real_native_buy_sell_fee_slip_cash_bridge=True,
        historical_events=0,full_economic_paths=0))
def main():
    begin=time.monotonic();assert not (O/'PREFIX_GATE.json').exists()
    affected();N.configure_scores()
    shared,receipts,cp,states,ir,identity=A.read_inputs('2025_26');kw=S.kwargs(cp,states,ir);h=binding(identity);z=frozen()
    save('SOURCE_FREEZE.json',dict(before_native_events=True,sources=z,input_identity=S.canonical_identity(identity),binding=h))
    reports={}
    for mode in ('cost1_OFF','D1_OFF','cost2_OFF','cost2_ON','D1_ON'):
        r=construct(mode,shared,receipts,kw,h);r.source_freeze=dict(z);run(r,mode)
        reports[mode]=dict(days=len(r.daily),fills=len(r.accounts['B'].trades),OPEN=2,CLOSE=3,NAV=str(r.accounts['B'].current_nav))
        if mode=='cost1_OFF':reports[mode]['saved_identity']=saved_streams(r,A.W/'pvr-slot1-native-readiness-20261101/runs/2025_26/pair')
        if mode=='D1_OFF':reports[mode]['saved_identity']=saved_streams(r,A.A.O/'run-PVR-D1/pair')
        if mode.endswith('_ON'):
            expected=observable(r);save('prefix/'+mode+'/OBSERVABLE.json',expected)
            phy,rr,pk=S.physical_inputs(shared,receipts,cp,states,ir,CUT);scores=N.SCORES
            def past(sid,day):assert day<=CUT;return scores.at(sid,day)
            N.SCORES=NS(manifest_sha256=scores.manifest_sha256,at=past)
            try:
                p=construct(mode,phy,rr,pk,h);p.source_freeze=dict(z);run(p,mode+'-physical')
                assert observable(p)==expected,mode+' physical state mismatch'
            finally:N.SCORES=scores
            split=construct(mode,shared,receipts,kw,h);split.source_freeze=dict(z);run(split,mode+'-split',SPLIT)
            restored=construct(mode,shared,receipts,kw,h);restored.source_freeze=dict(z)
            with IO.atomic_runner_outputs(restored,L,O/'prefix'/(mode+'-resumed'),canonicalize=J.W.canon):at=restored.restore(O/'prefix'/(mode+'-split/checkpoint.pkl'))
            assert observable(restored)==observable(split)
            run(restored,mode+'-resumed',after=at);assert observable(restored)==expected
            reports[mode]['physical_and_sameprocess_state_exact']=True
            wrong=construct(mode.replace('_ON','_OFF'),shared,receipts,kw,h);wrong.source_freeze=dict(z)
            try:
                with IO.atomic_runner_outputs(wrong,L,O/'prefix'/(mode+'-wrong-policy'),canonicalize=J.W.canon):wrong.restore(O/'prefix'/(mode+'-split/checkpoint.pkl'))
            except (ValueError,AssertionError):reports[mode]['wrong_policy_rejected']=True
            else:raise AssertionError('wrong policy accepted')
        save('PARTIAL_PREFIX_STATUS.json',reports)
        print('TECHNICAL_PREFIX',mode,reports[mode],flush=True)
    assert all(N.sha(p)==v for p,v in z.items())
    save('PREFIX_GATE.json',dict(passed=True,reports=reports,cut=CUT,source_count=len(z),seconds=time.monotonic()-begin,
        full_economic_paths=0,cross_process_restart_still_required=True,economic_execution_authorized=False))
if __name__=='__main__':
    try:main()
    except BaseException as e:save('FAILURE.json',dict(reason=str(e),traceback=traceback.format_exc(),full_economic_paths=0));raise
