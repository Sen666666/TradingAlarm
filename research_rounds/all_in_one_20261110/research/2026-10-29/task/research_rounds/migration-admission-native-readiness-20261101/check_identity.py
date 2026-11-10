"""ONLY the authorized original-policy native identity check, July1..July2.

No decoupled historical advancement. The physical-cut side repeats this same
minimal original-policy prefix solely to check data causality.
"""
from pathlib import Path
import gzip,json,time,copy,hashlib,types
import native_adapter as N
J=N.J;L=N.BASE.L;IO=N.IO;O=N.O;CUT='2025-07-02'
OLD=O.parent/'account-risk-ablation-20261031/run/prefix-full-source/pair'

def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]

def event_day(x):
    # Native fill audit timestamps live inside the actual FillReceipt.
    value=x.get('at') or x.get('day')
    if value is None and isinstance(x.get('receipt'),dict):value=x['receipt'].get('at')
    assert value is not None,('unlocated original native event time',x)
    return str(value)[:10]

def stable_sets(x):
    # Sets are compared by membership, while every ordered event/list stays ordered.
    if isinstance(x,(set,frozenset)):
        return sorted((stable_sets(v) for v in x),key=lambda v:json.dumps(J.W.canon(v),sort_keys=True))
    if isinstance(x,dict):return {k:stable_sets(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [stable_sets(v) for v in x]
    return x

def observable(r):
    # All native state, not just NAV; immutable market inputs are checked by hash.
    return J.W.canon(stable_sets(dict(daily=r.daily,opportunities=r.opportunities,funding=r.funding,
        industry=r.stage_events,balances=r.balance_audit,
        accounts={k:{key:val for key,val in a.__dict__.items() if key not in ('market','facts','budget')}
                  for k,a in r.accounts.items()},
        budgets={k:vars(a.budget) for k,a in r.accounts.items()})))

def main():
    t=time.monotonic();root=O/'identity-only';root.mkdir(parents=True,exist_ok=True)
    try:
        assert json.loads((O/'NATIVE_GATE.json').read_text())['passed']
        IO.prepare_targets(dict(checkpoint=root/'checkpoint.pkl',prefix_full=root/'prefix-full-source/pair',
                               prefix_physical=root/'prefix-physical-source/pair',failure=root/'failure/ERROR.json'),
                           directory_keys={'prefix_full','prefix_physical'})
        shared,receipts,cp,states,ir,identity=L.inputs('universe')
        loaded=time.monotonic();print('INPUTS_READ',round(loaded-t,3),flush=True)
        assert len(identity['account_ids'])==1709 and len(identity['sector_ids'])==90
        freeze=N.source_freeze()
        for p in (L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',L.U/'FREEZE.json',J.M.O/'recovery.csv',J.M.P/'h1.npz'):
            freeze[str(p.resolve())]=L.sha(p)
        for name in ('daily','funding','opportunities','industry','balances','B'):
            p=OLD/(name+('.json.gz' if name=='B' else '.jsonl.gz'));freeze[str(p.resolve())]=L.sha(p)
        kwargs=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
        r=N.CoupledRunner(shared,receipts,**kwargs);r.source_freeze=dict(freeze)
        checkpoint=root/'prefix-full-source/checkpoint.pkl'
        resumed_existing=checkpoint.exists()
        with IO.atomic_runner_outputs(r,L,root,canonicalize=J.W.canon):
            if resumed_existing:
                assert r.restore(checkpoint)==J.M.N.iso(CUT+'T15:10:00+08:00')
            else:assert r.run_prepared(root/'prefix-full-source',90,end=CUT)
        first=time.monotonic();print('ORIGINAL_POLICY_PREFIX_DONE',round(first-loaded,3),flush=True)
        checks={};counts={}
        for field,name in [('daily','daily'),('funding','funding'),('opportunities','opportunities'),('stage_events','industry'),('balance_audit','balances')]:
            original=[x for x in rows(OLD/(name+'.jsonl.gz')) if event_day(x)<=CUT]
            actual=J.W.canon(getattr(r,field));checks[name]=actual==original;counts[name]=len(actual)
            assert checks[name],('saved original event mismatch',name)
        book=json.load(gzip.open(OLD/'B.json.gz','rt'));a=r.accounts['B']
        for field,saved in [('trades','trades'),('journal','journal'),('audit_log','audit'),('decisions','decisions')]:
            old=[x for x in book[saved] if event_day(x)<=CUT]
            checks[field]=J.W.canon(getattr(a,field))==old;counts[field]=len(old)
            assert checks[field],('saved original native mismatch',field)
        original_state=observable(r)
        physical=J.W.physical(shared,CUT)
        physical_kwargs=dict(stock_cp={s:f.loc[:CUT] for s,f in cp.items()},
                             industry_states={s:[x for x in z if x['day']<=CUT] for s,z in states.items()},
                             industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=CUT})
        cut_receipts={s:{d:x for d,x in z.items() if d<=CUT} for s,z in receipts.items()}
        p=N.CoupledRunner(physical,cut_receipts,**physical_kwargs);p.source_freeze=dict(freeze)
        with IO.atomic_runner_outputs(p,L,root/'prefix-physical-source',canonicalize=J.W.canon):
            if (root/'prefix-physical-source/checkpoint.pkl').exists():
                assert p.restore(root/'prefix-physical-source/checkpoint.pkl')==J.M.N.iso(CUT+'T15:10:00+08:00')
            else:assert p.run_prepared(root/'prefix-physical-source',90,end=CUT)
        assert observable(p)==original_state,'physical truncated native prefix mismatch'
        restarted=N.CoupledRunner(shared,receipts,**kwargs);restarted.source_freeze=dict(freeze)
        with IO.atomic_runner_outputs(restarted,L,root/'restart',canonicalize=J.W.canon):
            last=restarted.restore(checkpoint)
            assert observable(restarted)==original_state,'native all-state restart mismatch'
        negative={}
        bad=N.DecoupledRunner(shared,receipts,**kwargs);bad.source_freeze=dict(freeze)
        try:
            with IO.atomic_runner_outputs(bad,L,root/'wrong-policy',canonicalize=J.W.canon):bad.restore(checkpoint)
        except (AssertionError,ValueError) as e:negative['wrong_policy']=str(e)
        assert 'wrong_policy' in negative
        bad2=N.CoupledRunner(shared,receipts,**kwargs);bad2.source_freeze=dict(freeze)
        bad2.route=types.MethodType(N.decoupled_route,bad2)
        try:
            with IO.atomic_runner_outputs(bad2,L,root/'wrong-route',canonicalize=J.W.canon):bad2.restore(checkpoint)
        except (AssertionError,ValueError) as e:negative['wrong_bound_route']=str(e)
        assert 'wrong_bound_route' in negative
        assert N.source_freeze()=={k:v for k,v in freeze.items() if k in N.source_freeze()}
        result=dict(passed=True,label='ORIGINAL-POLICY identity check; NOT a new-strategy financial result',
                    window=[J.START,CUT],original_saved_events_exact=checks,counts=counts,
                    physical_prefix_all_native_state_exact=True,both_sides_persisted=True,
                    restart_all_native_state_exact=True,last_event=str(last),negative_guards=negative,
                    fixed_snapshot_stocks=1709,industries=90,input_identity=identity,
                    seconds=dict(load=loaded-t,original_short_prefix_or_restore=first-loaded,total=time.monotonic()-t),
                    original_short_prefix_resumed_without_replay=resumed_existing,
                    decoupled_historical_events=0,full_financial_paths=0,source_freeze=freeze)
        IO.write_json(O/'IDENTITY_GATE.json',result)
        print('IDENTITY_PASS',counts,round(time.monotonic()-t,3),flush=True)
    except BaseException as e:
        IO.write_json(root/'failure/ERROR.json',dict(action='native readiness input/construct/short identity',error_type=type(e).__name__,reason=str(e)))
        raise

if __name__=='__main__':main()
