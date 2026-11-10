from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
from ce_adapter import CELookup
from account_rank import rank_stock_slots
O=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
loader=CELookup();day='2022-03-03'
frame=pd.DataFrame([dict(sid=s,rank=float(r),was_empty=e,has_mobile_intent=m,has_core_intent=c,PVR_score=p,PVR_ready=ready,priority_rank=float(r+100),budget=12345.,cap=200,untouched='original') for s,r,e,m,c,p,ready in [('600056.SH',10,True,True,False,88.,True),('601607.SH',20,True,True,True,80.,True),('001232.SZ',40,True,True,False,79.,True),('600606.SH',70,True,True,False,np.nan,True),('300182.SZ',90,False,True,False,78.,True),('600299.SH',99,True,True,False,54.,True)]])
snapshot=frame.copy(deep=True);got,a=rank_stock_slots(frame,day,loader)
assert got.sid.tolist()==['600299.SH','601607.SH','001232.SZ','600606.SH','300182.SZ','600056.SH'];assert got.ce_stock_rank.tolist()==[10,20,40,70,90,99]
pd.testing.assert_frame_equal(frame,snapshot,check_exact=True)
for col in frame.columns:pd.testing.assert_series_equal(got.set_index('sid')[col].sort_index() if col!='sid' else got.sid.sort_values().reset_index(drop=True),frame.set_index('sid')[col].sort_index() if col!='sid' else frame.sid.sort_values().reset_index(drop=True),check_exact=True)
zero=frame.copy();zero['has_core_intent']=True;z,za=rank_stock_slots(zero,day,loader);assert z.ce_stock_rank.eq(z['rank']).all() and za['movable_stock_groups']==0
single=zero.copy();single.loc[single.sid=='600056.SH','has_core_intent']=False;s,sa=rank_stock_slots(single,day,loader);assert s.ce_stock_rank.eq(s['rank']).all() and sa['movable_stock_groups']==1
empty=frame.iloc[:0];e,ea=rank_stock_slots(empty,day,loader);assert len(e)==0 and ea['stock_groups']==0
notready=frame.copy();notready.loc[notready.sid=='600299.SH','PVR_ready']=False;n,na=rank_stock_slots(notready,day,loader);assert n.ce_stock_rank.eq(n['rank']).all()
# Tie path can be checked using a tiny read-only test source, no native indicator recomputation.
class Ties:
 def query(self,sid,day):return dict(CE=1.23456789012341 if sid=='600056.SH' else 1.23456789012349,CE_known=True,reason='synthetic_round12_tie',formation_n=1,variance_budget=.01)
t=frame[frame.sid.isin(['600056.SH','600299.SH'])].copy();t.loc[t.sid=='600299.SH','PVR_score']=99.;tt,ta=rank_stock_slots(t,day,Ties());assert tt.sid.tolist()==['600299.SH','600056.SH']
t.PVR_score=88.;tt,ta=rank_stock_slots(t,day,Ties());assert tt.sid.tolist()==['600056.SH','600299.SH']
checks=dict(status='PASS',checks=['actual CORE+MOBILE whole stock fixed','held MOBILE fixed','unknown CE source fixed','unknown PVR numeric fixed','PVR not-ready fixed','nonconsecutive original rank keys retained','zero movable groups unchanged','single movable group unchanged','empty typed queue supported','round12 CE ties use original PVR then original native rank/sid','all original fields unchanged including rank/priority_rank/budget/cap','input dataframe not mutated','no top-K; all groups returned'])
(O/'BOUNDARY_TESTS.json').write_text(json.dumps(checks,indent=2))
# Reconfirm all originally frozen analysis files and both native account inputs remained unchanged.
for p,h in json.loads((O/'ORIGINAL_TEST_FILES_BEFORE.json').read_text()).items():assert sha(p)==h
for p,h in json.loads((O/'ACCOUNT_SCOPE_INPUT_SHA256.json').read_text()).items():assert sha(p)==h
manifest=json.loads((O/'ADAPTER_MANIFEST.json').read_text());manifest['account_interface']='account_rank.rank_stock_slots(frame, signal_day, lookup) -> (ranked_frame, audit_dict)';manifest['diagnostic_interface_not_for_account']='ce_adapter.CELookup.rank_frame';manifest['artifact_sha256']['account_rank.py']=sha(O/'account_rank.py');manifest['account_scope_audit_sha256']=sha(O/'ACCOUNT_SCOPE_AUDIT.json');manifest['boundary_tests_sha256']=sha(O/'BOUNDARY_TESTS.json');manifest['status']='READY_FULL_POOL_CE_INPUT_AND_CORE_FIXED_ACCOUNT_RANKING';(O/'ADAPTER_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
readme='''# Frozen CE account handoff

READY: full original fixed-pool input and CORE-fixed stock-slot ranking. No account run has been performed here.

## Runtime interfaces

Directory: this account_adapter folder. Load it on sys.path, import CELookup from ce_adapter and rank_stock_slots from account_rank. Instantiate lookup = CELookup(directory=adapter_directory, verify_hashes=True) once.

- lookup.query(sid, signal_day) -> dictionary with CE, CE_known, reason, formation_n, variance_budget, source D/K/r/m and related diagnostics for original fresh CP only.
- lookup.score_candidates(frame) -> all input rows plus CE/status fields; only sid/day determine score. Original account/held fields do not influence CE. Never inner join and never drop a missing lookup.
- rank_stock_slots(frame, signal_day, lookup) -> (ranked_frame, audit_dict). Required columns: sid, rank, was_empty, has_mobile_intent, has_core_intent, PVR_score, PVR_ready. One row per stock from ACTUAL current counterfactual pending AFTER unchanged native planning. Original rank must be unique finite native stock values; gaps are allowed. Boolean fields must be explicit. Empty typed queue is supported.

Output adds ce_stock_rank and CE audit columns. Original rank and priority_rank fields, if present, remain unchanged, as do all original fields. The caller applies only ce_stock_rank to pending execution rank for that stock, retaining original priority_rank for comparison. It must keep original CORE-before-MOBILE ordering within stock and original done-per-stock handling. Do not change order sizing, budget, cash, exposure, admission, protection, exit or account state logic.

## Account scope and tie contract

Only current empty + actual pending MOBILE + NO actual pending CORE + PVR_ready/finite + CE known whole-stock slots can exchange. CORE+MOBILE groups are entirely fixed. All held groups, non-MOBILE groups, unknown CE, unknown/not-ready PVR stay in their original stock rank slot. Use actual pending role, NOT core_Q qualification. A CORE rejected by original planning/size checks and absent from pending is not an actual pending CORE.

All native stock rank keys are preserved without compressing to 1..N. Finite movable rows sort by CE rounded12 desc, original PVR rounded12 desc, original native stock rank then sid. Assign to the original movable rank keys. No K=20 and no truncation: every original stock group returns. The original account alone determines how many orders its actual cash/position/lot-size rules can accept.

`CELookup.rank_frame` is ONLY the old signal-diagnostic reproduction interface. It can reproduce all old 103766 candidate scores and 1568 queues, but it does not freeze CORE groups. Do NOT use rank_frame directly for the account intervention.

Fixed CORE ordering cannot guarantee identical CORE fills or cash: different preceding MOBILE purchases can change available cash indirectly. That is an account path consequence, not a direct CORE sorting change. Audit and report it.

## Formula and state/restart

The formula is exactly the frozen prepare_ce.py implementation whose hash is in ADAPTER_MANIFEST. r/m/D/K are original native cache values. v_j^2=max(mean(last 21 finite same-source r strictly BEFORE j squared), log(1.001)^2). V sums v_j^2 from the observation AFTER the true native anchor through current receipt. CE=min(original D,original K)/sqrt(V). No score threshold, n cap, receipt revival or delay.

Original start/E0_down_reset/lower_anchor establish an anchor with V=n=0; E0_invalid/unprepared/source change reset. Ordinary pullbacks accumulate. Current receipt is scored before consumption, then resets. Source change also resets r history; ordinary CP/E0 reset does not. The whole CP lineage is independent of account holdings.

The runtime lookup has no mutable incremental/account state. Restart requires only loading the exact same immutable files and querying the same original signal date. There is no warm-up state to serialize or recover in the account engine. All score preparation used source-only full-prefix histories and passed physical truncated-input checks. Scores must never be recomputed from account entry dates or truncated at the account start.

The serialized table covers every original cached fresh CP for all complete-source fixed-pool stocks, including dates not in the original candidate domain. It does not load original account history at runtime. Historical account files are read only by the separate scope audit, not by ce_adapter/account_rank.

## Coverage and explicit fallback

1709 fixed-pool names: 1687 complete native sources; 22 original manifest entries explicitly have no local observation by the original endpoint. All 232520 cached native receipts have finite CE. 177668 receipt keys are outside the previous 54852 candidate-stock-day domain. This avoids silently restricting a counterfactual account to original held/empty history.

query outside the fixed pool, on one of the 22 unavailable stocks, outside native source dates, or on a day without original cached fresh CP returns UNKNOWN with reason. Insufficient formation-variance/warm history would also be UNKNOWN. On any UNKNOWN the exact original slot stays unchanged; no interpolation, old receipt carry, score filling, inner join deletion, or replacement by a guessed CE. A future dataset extension requires a newly authorized adapter version; this adapter does not silently fetch/recompute data.

## Proven checks and scope difference

- 4081068 original source observations; native credit/D/anchor/frozen-scale lineage audit.
- 5061 whole-prefix checks over 1687 stocks × 2022-03-31/2024-09-24/2026-01-15.
- All original 103766 candidate rows / 54852 stock-days exactly identical in all saved CE state columns.
- All 1568 old complete diagnostic queues and 91 PVR-unknown exact slots reproduced.
- All 1579 original actual pending stock queues tested under CORE-fixed account scope; original fields and CORE rank slots preserved.
- Original legal MOBILE candidates include 83165 actual CORE+MOBILE groups (80.15%). Only 20601 are MOBILE-only, 20591 finite-score movable. These counts come from actual decisions/intents, never core_Q.
- Unknown CE/PVR, PVR not-ready, CORE overlap, held MOBILE, zero/one movable group, nonconsecutive rank values, exact tie ordering, typed empty queue, restart and input immutability tests pass.

Thus the account intervention is deliberately narrower than the original same-K20 diagnostic. Its original path win-rate/coverage changes do not establish an equivalent account improvement. No complete 0→0 round win-rate improvement, 30% target attainment, or account return has been shown by this adapter.

## Inputs, hashes, audit files

ADAPTER_MANIFEST.json includes runtime source/data hashes and audit identities. ALL_NATIVE_CP_RECEIPT_CE.parquet is the immutable score table. STOCK_COVERAGE.csv retains every fixed-pool name; EXPLICIT_UNAVAILABLE_STOCKS.csv lists the 22. CACHE_SOURCE_HASHES.csv records each native CP/facts hash and original manifest match. ADAPTER_AUDIT.json is full-input verification. ACCOUNT_SCOPE_AUDIT.json / ACTUAL_CORE_INTERSECTION_BY_YEAR.csv / ORIGINAL_CANDIDATE_ACTUAL_ROLE_SCOPE.parquet record actual CORE overlap. BOUNDARY_TESTS.json covers final runtime edge cases. FINAL_HANDOFF_HASHES.json covers all final files. Original candidate_test sealed artifacts remain byte-identical.
'''
(O/'README.md').write_text(readme)
(O/'FINAL_HANDOFF_HASHES.json').write_text(json.dumps({p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='FINAL_HANDOFF_HASHES.json'},indent=2))
print('READY',json.dumps(manifest,ensure_ascii=False));print(json.dumps(checks,ensure_ascii=False))
