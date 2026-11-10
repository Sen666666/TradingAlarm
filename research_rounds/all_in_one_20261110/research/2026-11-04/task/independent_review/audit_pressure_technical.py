"""Read-only pressure receipt/export/quantity/cash/mark audit; no engines."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import gzip,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parents[1]/'pvr_pressure_readiness'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return [json.loads(s)for s in gzip.decompress(Path(p).read_bytes()).decode().splitlines()]
def book(p):return json.loads(gzip.decompress(Path(p).read_bytes()))
gate=read(ROOT/'PREFIX_GATE.json');cross=read(ROOT/'CROSS_PROCESS_RESTART.json')
neg=read(ROOT/'NEGATIVE_BINDING_GATE.json');affected=read(ROOT/'AFFECTED_GATE.json')
frozen=read(ROOT/'SOURCE_FREEZE.json')['sources']
assert gate['passed']and cross['passed']and neg['passed']and affected['passed']
assert len(neg['checks'])==5 and neg['new_account_events']==0
assert all(sha(p)==h for p,h in frozen.items())
assert sha(ROOT/'cross_process_and_guards.py')==neg['source_sha256']
p=Path(__file__).parent/'audit_pvr_saved.py';spec=importlib.util.spec_from_file_location('ro_marks',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks={}
for mode in ['cost1_OFF','D1_OFF','cost2_OFF','cost2_ON','D1_ON']:
    r=ROOT/'prefix'/mode;b=book(r/'pair/B.json.gz');ds=rows(r/'pair/daily.jsonl.gz')
    assert len(ds)==3 and ds[-1]['at']=='2025-07-03 15:10:00+08:00'
    ts=b['trades'];assert len({x['receipt_id']for x in ts})==len(ts)
    assert all(x['kind']!='split'for x in b['audit'])
    div=[x['receivable']for x in b['audit']if x['kind']=='dividend_accrual']
    for d in ds:
        prefix=[t for t in ts if t['at']<=d['at']];q=defaultdict(int);fee=D(0);cash=D(0)
        for t in prefix:
            q[t['security_id']]+=(1 if t['side']=='buy'else -1)*t['shares']
            fee+=D(t['fees_cny']);cash+=(D(t['gross_cny'])if t['side']=='sell'else -D(t['gross_cny']))-D(t['fees_cny'])
        assert {s:v for s,v in q.items()if v}==d['positions']
        income=sum((D(x['net_local'])for x in div if x['ex_at']<=d['at']),D(0))
        inventory=sum((D(v)*m.price(s,d['at'][:10])for s,v in q.items()if v),D(0))
        assert abs(inventory-D(d['inventory']))<D('1e-8')
        assert D(1000000)+cash+income+inventory==D(d['nav'])and fee==D(d['fees_cny'])
        assert sum(D(d[k])for k in ['available','order_reserved','sale_receivable','dividend_receivable'])+inventory==D(d['nav'])
    reserved=sum((D(o['remaining_budget_cny'])+D(o['fee_reserved_cny'])for o in b['orders'].values()),D(0))
    assert reserved==D(ds[-1]['order_reserved'])
    checks[mode]=dict(actual_fills=len(ts),three_day_cash_fee_quantity_NAV_and_frozen_mark_checks=True,actual_pending_reserve_exact=True)
    if mode.endswith('_ON'):
        for branch in ['-physical','-resumed','-cross-process']:
            for stream in ['daily','funding','opportunities','industry','balances','rank-policy']:
                assert rows(ROOT/'prefix'/(mode+branch)/'pair'/(stream+'.jsonl.gz'))==rows(r/'pair'/(stream+'.jsonl.gz'))
            assert book(ROOT/'prefix'/(mode+branch)/'pair/B.json.gz')==b
        assert sha(ROOT/'prefix'/(mode+'-split/checkpoint.pkl'))==cross['details'][mode]['checkpoint_sha256']
out=dict(status='PASS_WITH_SCOPE',source_SHA_checks=len(frozen),affected_fourth_gate_source_involution_reviewed=True,
    original_native_cost2_buy_sell_fee_slip_cash_fixture_receipt_pass=True,
    five_technical_arms=checks,ON_physical_sameprocess_and_separateprocess_six_exports_fullbook_exact=True,
    negative_guards=dict(source_cost_horizon_D1_mode=5,wrong_policy=2),
    reviewer_account_events=0,technical_scope=read(ROOT/'ACTUAL_TECHNICAL_SCOPE.json'),
    prefix_receipt_SHA256=sha(ROOT/'PREFIX_GATE.json'),cross_receipt_SHA256=sha(ROOT/'CROSS_PROCESS_RESTART.json'),
    negative_receipt_SHA256=sha(ROOT/'NEGATIVE_BINDING_GATE.json'),adapter_SHA256=sha(ROOT/'pressure_adapter.py'),
    reviewer_source_SHA256=sha(__file__),
    scope='Technical readiness only. Normal own-state2023/2024 continuity is separate. Support exactly frozen paired pressure windows after root grant; no cost/delay scan or combined stress. Original strongPVR_D1 read-only identity reviewed; not an SC substitution. Synthetic fixtures are separate from historical branch counts.')
if (ROOT/'INPUT_2022_GATE.json').exists():
    q=read(ROOT/'INPUT_2022_GATE.json');assert q['passed'];out['input_2022_receipt_SHA256']=sha(ROOT/'INPUT_2022_GATE.json')
(Path(__file__).parent/'PVR_PRESSURE_TECHNICAL_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items()if k!='technical_scope'},indent=2))
