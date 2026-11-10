"""Read-only two-policy own-state2024 horizon/entry evidence audit."""
from pathlib import Path
from decimal import Decimal as D
import gzip,hashlib,json
R=Path(__file__).resolve().parents[1]/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def same(p,q):
    with gzip.open(p,'rb')as a,gzip.open(q,'rb')as b:
        while True:
            x=a.read(1048576);y=b.read(1048576);assert x==y
            if not x:return
out={}
for policy,parentNAV in [('original','662557.9101669831085'),('no60','745426.9583780900535')]:
    root=R/'cycle2024'/policy;v=read(root/'VERIFIED_HORIZON_IMPORT.json')
    i=read(root/'IMPORT_GATE.json');t=read(root/'TECHNICAL_GATE.json');c=read(root/'CROSS_PROCESS_GATE.json')
    assert i['passed']and t['passed']and c['passed']and c['separate_process']
    assert all(v['all_account_fields_equal'].values())and all(v['all_strategy_fields_equal'].values())and all(v['bookchecks'].values())
    assert v['parent_NAV']==parentNAV and i['account_events']==0 and len(i['negative_guards'])==5
    assert v['parent_lookup_reconstructed_from_immutable_state']and v['parent_lookup_not_serialized']
    assert all(sha(p)==h for p,h in t['source_freeze'].items())
    assert c['restored_parent_checkpoint_sha256']==sha(root/'imported-Dec29/checkpoint.pkl')
    assert c['reference_Jan2_checkpoint_sha256']==sha(root/'first-session/full-input/checkpoint.pkl')
    for branch in ['first-session/physical-input','cross-process/Jan2']:
        for n in ['daily','funding','opportunities','industry','balances','rank-policy']:
            same(root/branch/'pair'/(n+'.jsonl.gz'),root/'first-session/full-input/pair'/(n+'.jsonl.gz'))
        assert json.loads(gzip.decompress((root/branch/'pair/B.json.gz').read_bytes()))==json.loads(gzip.decompress((root/'first-session/full-input/pair/B.json.gz').read_bytes()))
    with gzip.open(root/'first-session/full-input/pair/daily.jsonl.gz','rt')as f:ds=[json.loads(s)for s in f]
    d=ds[-1];assert len(ds)==485 and d['at']=='2024-01-02 15:10:00+08:00'
    assert d['positions']=={}and D(d['inventory'])==0
    assert sum(D(d[k])for k in ['available','order_reserved','sale_receivable','dividend_receivable'])==D(d['nav'])==D(parentNAV)
    assert t['full_accounting']['new_fills']==c['accounting']['new_fills']==0
    proposal=read(root/'PROPOSED_FULL_EXECUTION_FREEZE.json')
    assert proposal['checkpoint_source_freeze']==t['source_freeze']
    assert proposal['resume_after']==d['at']and proposal['end']=='2024-12-31'
    assert all(sha(p)==h for p,h in proposal['entry_sources'].items())
    out[policy]=dict(status='PASS_WITH_SCOPE',parent_NAV=parentNAV,account_fields=len(v['all_account_fields_equal']),strategy_fields=len(v['all_strategy_fields_equal']),
        source_SHA_checks=len(t['source_freeze']),parent_lookup_entries=v['parent_lookup_entries'],future_lookup_entries=v['future_lookup_entries'],
        import_receipt_SHA256=sha(root/'IMPORT_GATE.json'),technical_receipt_SHA256=sha(root/'TECHNICAL_GATE.json'),cross_receipt_SHA256=sha(root/'CROSS_PROCESS_GATE.json'),
        execution_proposal_SHA256=sha(root/'PROPOSED_FULL_EXECUTION_FREEZE.json'),
        six_exports_and_fullbook_full_physical_cross_exact=True,independent_Jan2_no_stock_cash_divAR_NAV_bridge=True,
        technical_market_events=dict(full_OPEN=1,full_CLOSE=1,physical_OPEN=1,physical_CLOSE=1,cross_OPEN=1,cross_CLOSE=1,new_fills_per_branch=0))
out['reviewer_account_events']=0
out['scope']='Source+output+binding review, no independent engine import/restore. Serialized2023 parents intentionally omit pure episode lookup; original state-based setdefault algorithm reconstructs it from frozen industry inputs, old transition count and every past value preserved. This is not an account reset. Initial missing-lookup/class-field bugs corrected before frozen technical execution; old parent CPs unchanged. Both parents flat/pending0, hence first-day covers no active-order fills; original positive-fill normal/D1 gates and full input causality reused.'
out['entry_recommendation']='Support only two separately root-granted2024 continuations from their own committedJan2full checkpoints, no Jan2 replay/fresh1m/407substitution. Full2022-2024 cumulative wealth/DD plus each own2024 segment required. run_cycle2024.py reviewed: preservedCP.sourcefreeze, external entry/card/auth freeze, strict scope/policy/cursor/hash/complete/failure/own-resume guards. No economic outcome inferred.'
out['reviewer_source_SHA256']=sha(__file__)
(Path(__file__).parent/'PVR_2024_HORIZON_TECHNICAL_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
