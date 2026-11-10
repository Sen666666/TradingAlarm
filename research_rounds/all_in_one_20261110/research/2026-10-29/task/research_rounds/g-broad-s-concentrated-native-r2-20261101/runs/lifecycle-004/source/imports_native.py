"""Read-only bindings to audited native ledger and immutable market kernel."""
from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'case-stage-ledger-20261031/v3'))
import joint_v3 as J
C=J.C;LR=J.LR;D=J.D;Z=D(0)
T=J.W.load('capital_v2_original_native_fixtures',J.W.RR/'rs-h1-execution-20261025/code/test_sector_account.py')
F1_PATH=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/v2-frozen/signal_core.py')
F1=J.W.load('capital_v2_frozen_F1',F1_PATH)
IO=J.W.load('capital_v2_shared_output_io',W/'_shared/research_output_io.py')
CONTRACT_ROOT=W/'capital-capability-design-only-20261101'
BASE=CONTRACT_ROOT/'G_BROAD_S_CONCENTRATED_CONTRACT_PROPOSAL.txt'
V2=CONTRACT_ROOT/'G_BROAD_S_CONCENTRATED_CONTRACT_V2.txt'
MANIFEST=CONTRACT_ROOT/'G_BROAD_S_CONCENTRATED_CONTRACT_V2_MANIFEST.json'
COMPOSITE='a26b1959379ed6c7e8d82e35f9d3fca9dd050caa5e824850a0d75543005bcc50'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def contract_guard():
 m=json.loads(MANIFEST.read_text());assert m['composite_contract_sha256']==COMPOSITE
 assert sha(BASE)==m['base_sha256'] and sha(V2)==m['amendment_sha256']
 assert sha(F1_PATH)=='962275bd41b5c7bbc062a1191780a6b6a9c616f8d3097ea669b602eabbc9ac59'
 return m
contract_guard()
RULES_PATH=J.W.RR/'pvr-act-comparison-20261027/execution-rules-v2.json'
RULES=json.loads(RULES_PATH.read_text())
def dated(rows,day):
 xs=[r for r in rows if r['from']<=day and (r.get('to') is None or day<r['to'])]
 if len(xs)!=1:raise ValueError('dated rule unavailable')
 return xs[0]
def quantity(at,star=True):
 return T.QuantityRule(**dated(RULES['quantity_versions']['688001.SH' if star else '600000.SH'],at.date().isoformat())['rule'])
def fees(at,star=True):
 s=dated(RULES['fee_versions']['SSE_STAR' if star else 'SSE_MAIN'],at.date().isoformat())['schedule']
 return T.FeeSchedule(s['schedule_id'],tuple(T.FeeComponent(**x) for x in s['components']))
