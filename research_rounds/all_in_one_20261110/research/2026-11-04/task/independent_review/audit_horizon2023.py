"""Read-only horizon evidence review; execute with existing pyarrow venv."""
from pathlib import Path
import gzip,hashlib,importlib.util,json
from decimal import Decimal as D
R=Path(__file__).resolve().parents[1]/'pvr_pool_feasibility/continuation2023'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
i=read(R/'IMPORT_GATE.json');t=read(R/'TECHNICAL_GATE.json');c=read(R/'CROSS_PROCESS_GATE.json');v=read(R/'VERIFIED_HORIZON_IMPORT.json')
assert i['passed']and t['passed']and c['passed']and c['separate_process']
assert i['actual_new_account_events']==0 and i['own_parent_NAV']=='704487.8470098769005'
assert all(v['all_account_fields_equal'].values())and all(v['all_strategy_fields_equal'].values())and all(v['final_book_fields_equal'].values())
assert len(i['negative_guards'])==8 and all(sha(p)==h for p,h in t['sources'].items())
assert len(v['all_account_fields_equal'])==63 and len(v['all_strategy_fields_equal'])==28
assert sha(R/'imported-Dec30/checkpoint.pkl')==c['zero_event_imported_checkpoint_sha256']
assert sha(R/'first-session/full-input/checkpoint.pkl')==c['reference_Jan3_checkpoint_sha256']==t['prefix_checkpoint_sha256']
assert all(sha(p)==h for p,h in c['scripts_sha256'].items())
def same_gzip(p,q):
    with gzip.open(p,'rb')as a,gzip.open(q,'rb')as b:
        while True:
            x=a.read(1048576);y=b.read(1048576);assert x==y,(p,q)
            if not x:return
for branch in ['first-session/physical-input','cross-process/Jan3']:
    for f in ['daily','funding','opportunities','industry','balances','rank-policy']:
        same_gzip(R/branch/'pair'/(f+'.jsonl.gz'),R/'first-session/full-input/pair'/(f+'.jsonl.gz'))
    assert json.loads(gzip.decompress((R/branch/'pair/B.json.gz').read_bytes()))==json.loads(gzip.decompress((R/'first-session/full-input/pair/B.json.gz').read_bytes()))
b=json.loads(gzip.decompress((R/'first-session/full-input/pair/B.json.gz').read_bytes()))
parent=json.loads(gzip.decompress((R.parent/'runs/2022/pair/B.json.gz').read_bytes()))
assert b['trades']==parent['trades']and b['journal']==parent['journal']
ds=[json.loads(s)for s in gzip.decompress((R/'first-session/full-input/pair/daily.jsonl.gz').read_bytes()).decode().splitlines()]
d=ds[-1];assert len(ds)==243 and d['at']=='2023-01-03 15:10:00+08:00'
p=Path(__file__).parent/'audit_pvr_saved.py';spec=importlib.util.spec_from_file_location('ro_math',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
inventory=sum((D(q)*m.price(s,'2023-01-03')for s,q in d['positions'].items()),D(0))
assert abs(inventory-D(d['inventory']))<D('1e-8')
assert inventory+sum(D(d[k])for k in ['available','order_reserved','sale_receivable','dividend_receivable'])==D(d['nav'])
assert b['ending_cash']==parent['ending_cash']and D(b['ending_NAV'])==D('708850.7670098769005')
manifest=read(R/'PROPOSED_FULL_EXECUTION_FREEZE.json')
assert manifest['resume_checkpoint_sha256']==sha(R/'first-session/full-input/checkpoint.pkl')
assert manifest['resume_after']==d['at']and manifest['end']=='2023-12-29'
assert manifest['checkpoint_source_freeze_preserved']==t['sources']
assert manifest['launcher_sha256']==sha(R/'run_full.py')and manifest['card_sha256']==sha(R/'FULL_2023_CARD.txt')
out=dict(status='PASS_WITH_SCOPE',source_SHA_checks=len(t['sources']),all63_account_and28_strategy_fields_exact_import=True,
    own_parent_NAV=i['own_parent_NAV'],score_prefix_cells=i['prefix_score_cells'],eight_negative_guards=True,
    full_physical_and_genuine_cross_process_six_exports_and_fullbook_exact=True,
    reviewer_independent_Jan3_rawclose_inventory_and_cash_NAV_bridge=True,
    technical_native_events=dict(full_OPEN=1,full_CLOSE=1,physical_OPEN=1,physical_CLOSE=1,cross_OPEN=1,cross_CLOSE=1,fills_per_branch=0),
    horizon_source_SHA256=sha(R/'horizon_adapter.py'),technical_receipt_SHA256=sha(R/'TECHNICAL_GATE.json'),
    cross_receipt_SHA256=sha(R/'CROSS_PROCESS_GATE.json'),proposed_execution_manifest_SHA256=sha(R/'PROPOSED_FULL_EXECUTION_FREEZE.json'),
    full_launcher_source_reviewed=True,reviewer_account_events=0,reviewer_source_SHA256=sha(__file__),
    recommendation='Support unique root-granted remaining2023 from savedJan3full CP; no Jan3 replay or oldPVR injection. Report own-year and cumulative paths. No economic promotion inferred.',
    analysis_attempt_note='First inline reviewer mark check used system Python without pyarrow and failed read-only; rerun this same arithmetic using existing project venv. No account events or installations.')
(Path(__file__).parent/'PVR_2023_HORIZON_TECHNICAL_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
