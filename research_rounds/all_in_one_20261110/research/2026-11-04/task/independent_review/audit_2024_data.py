"""Read-only output/data-interface audit; no model/strategy/account imports."""
from pathlib import Path
import hashlib,json
import pandas as pd

TASK=Path(__file__).resolve().parents[1]
ROOT=TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full'
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/continuation-2023-readiness')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(ROOT/'DATA_GATE.json');assert g['passed']and g['account_events']==0
f=read(ROOT/'SOURCE_FREEZE.json');assert all(sha(p)==h for p,h in f['sources'].items())
assert sha(ROOT/'SOURCE_FREEZE.json')==g['source_freeze_sha256']
assert sha(ROOT/'SCORES_MANIFEST.json')==g['score_manifest_sha256']
assert sha(ROOT/'inputs/MANIFEST.json')==g['canonical_manifest_sha256']
sm=read(ROOT/'SCORES_MANIFEST.json');old=read(OLD/'SCORES_MANIFEST.json')
assert sm['fixed_stock_ids']==old['fixed_stock_ids']and len(sm['entries'])==1709
assert sm['formula_sha256']==old['formula_sha256']
assert sm['old_score_manifest_sha256']==sha(OLD/'SCORES_MANIFEST.json')
dates=sm['decision_calendars'];assert all(len(x)==242 for x in dates.values())
assert len(set(sum(dates.values(),[])))==726
prefix=dates['2022']+dates['2023'];ready=0;NA=0;cells=0
for s in sm['entries']:
    sid=s['symbol'];p=ROOT/'scores'/(sid+'.parquet');a=pd.read_parquet(p)
    assert sha(p)==s['output_sha256'];assert a.index.strftime('%Y-%m-%d').tolist()==sum(dates.values(),[])
    previous=OLD/'scores'/(sid+'.parquet');assert sha(previous)==s['old_score_file_sha256']
    pd.testing.assert_frame_equal(a.loc[prefix],pd.read_parquet(previous),check_exact=True,check_freq=False)
    r=int(a.loc[dates['2024']].score.notna().sum());na=int(a.loc[dates['2024']].score.isna().sum())
    assert r==s['ready_2024']and na==s['NA_2024']and r+na==242
    ready+=r;NA+=na;cells+=len(prefix)
canonical=read(ROOT/'inputs/MANIFEST.json');assert len(canonical)==1799
assert {r['sid']for r in canonical if not r['industry']}==set(sm['fixed_stock_ids'])
counts={False:0,True:0};allids=[]
for r in canonical:
    assert sha(r['output_path'])==r['output_sha256'];rr=read(r['output_path'])
    assert len(rr)==r['receipt_count'];counts[r['industry']]+=len(rr)
    assert all(x['canonical_series']==r['sid']and not x['trace_unknown']and '2024-01-01'<=x['confirmed_day']<='2024-12-31'for x in rr)
    assert all(x['formation_start_exclusive']<=x['scale_frozen_at']<=x['confirmed_day']and x['formation_end_inclusive']==x['confirmed_day']for x in rr)
    assert len({x['receipt_id']for x in rr})==len(rr);allids.extend(x['receipt_id']for x in rr)
    z=pd.read_parquet(r['refs']['CP1']).loc['2024-01-01':'2024-12-31']
    assert [x['confirmed_day']for x in rr]==z.index[z.receipt.eq(True)].strftime('%Y-%m-%d').tolist()
    if r['industry']:
        st=pd.read_parquet(r['refs']['state']).set_index('day')
        assert all(st.loc[x['confirmed_day'],'receipt_id']==x['receipt_id']for x in rr)
assert len(allids)==len(set(allids))
assert counts[False]==25251 and counts[True]==1762 and ready==390394 and NA==23184 and cells==827156
loader=read(ROOT/'LOADER_GATE.json');assert loader['passed']and loader['account_construction']==loader['account_events']==0
tf=read(ROOT/'TECHNICAL_SOURCE_FREEZE.json');assert all(sha(p)==h for p,h in tf['sources'].items())
assert all(sha(p)==h for p,h in tf['unchanged_native_sources'].items())
out=dict(status='PASS_WITH_SCOPE',account_events=0,stocks=1709,industries=90,
    independently_verified_old_score_cells=cells,independently_verified_2024_score_cells=ready+NA,
    ready=ready,NA=NA,canonical_stock_receipts=counts[False],canonical_industry_receipts=counts[True],
    all_output_SHA_exact=True,all_numeric_receipt_dates_exact=True,all_industry_state_receipt_IDs_exact=True,
    globally_unique_receipt_IDs=True,original_full_warm_formula_source_reviewed=True,
    physical_causal_scope='Reviewed producer all1799 canonical and1709 score physical-prefix code/receipts; independently did not rerun original trace/PVR formula or full physical loader.',
    score_manifest_SHA256=sha(ROOT/'SCORES_MANIFEST.json'),canonical_manifest_SHA256=sha(ROOT/'inputs/MANIFEST.json'),
    loader_receipt_SHA256=sha(ROOT/'LOADER_GATE.json'),reviewer_source_SHA256=sha(__file__),
    remaining_scope='Inputs only; no2024 account horizon/import/financial readiness implied.1709current/development universe is not407/PIT/OOS. NA is retained, not an executable-stock claim.')
(Path(__file__).parent/'PVR_2024_INPUT_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
