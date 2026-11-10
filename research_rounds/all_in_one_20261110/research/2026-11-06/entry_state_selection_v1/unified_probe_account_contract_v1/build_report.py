from pathlib import Path
import json,gzip,hashlib
from collections import Counter
from decimal import Decimal as D
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):(HERE/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str))
failed=read(HERE/'first_day_check/FAILURE.json')
freeze=read(HERE/'first_day_check/PREDECLARED.json')['source_freeze']
original={p:h for p,h in freeze.items() if not p.startswith(str(HERE)+'/')}
changes={p:dict(before=h,now=sha(Path(p))) for p,h in original.items() if sha(Path(p))!=h}
write('ORIGINAL_SOURCE_INTEGRITY.json',dict(passed=not changes,checked=len(original),source_hashes=original,changes=changes))
checks={n:read(HERE/n) for n in ['SYNTHETIC_RESULTS.json','EDGE_CASE_RESULTS.json','REPAIR_RESULTS.json']}
assert all(x['passed'] for x in checks.values())
code=sha(HERE/'unified_probe.py');assert all(x['implementation_sha256']==code for x in checks.values())
summary_path=HERE/'first_day_check_v2/SUMMARY.json'
summary=read(summary_path) if summary_path.exists() else None
baseline=read(HERE.parent/'first_day_52_history_audit_v1/FIRST_DAY_COMPARISON.json')['arms'][1]
comparison=dict(baseline=baseline,new=summary,comparison_scope='first-day engineering, not strategy performance')
if summary:
 out=summary_path.parent;p=read(out/'PREDECLARED.json');log=json.load(gzip.open(out/'pair/PVR.json.gz','rt'))
 journal=log['journal'];reserve=[x for x in journal if x['kind']=='real_reserve'];fills=[x for x in journal if x['kind']=='real_buy_fill'];admissions=read(out/'ADMISSION_EVENTS.json')
 comparison['new_details']=dict(first_reserve_role_pools=dict(Counter((x['role']+'|'+x['pool']) for x in reserve)),first_fill_role_pools=dict(Counter((x['role']+'|'+x['pool']) for x in fills)),all_mobile_reserve_CP_consumed=all(x['receipt'] in log['budget']['consumed'] for x in reserve if x['role']=='mobile'),unique_mobile_CP=len({x['receipt'] for x in reserve if x['role']=='mobile'}),ending_real_buy_orders=len(log['orders']),ending_real_exit_orders=len(log['exits']),open_budget_orders=sum(x['qty']>0 and x['status'] in ('open','cancel_pending') for x in log['budget']['orders'].values()),max_first_gross_fraction=max(D(x['gross'])/D(x['decision_nav']) for x in admissions),max_first_fee_inclusive_risk_fraction=max(D(x['fee_inclusive_risk'])/D(x['decision_nav']) for x in admissions),close_probe_fraction=D(str(summary['close_probe'][0]))/D(summary['close_nav']))
write('FIRST_DAY_COMPARISON.json',comparison)
status=dict(state='FIRST_DAY_ENGINEERING_PASSED_AWAITING_FINAL_REVIEW' if summary else 'AWAITING_RESTORE_REVIEW_NO_ACTIVE_RUN',implementation_sha256=code,synthetic_test_count=sum(x['count'] for x in checks.values()),original_sources_unchanged=not changes,first_attempt='FAILED_RESTORE_REPLAY_PRESERVED',first_attempt_last_complete_event=failed['last_complete_event'],first_day_completed=bool(summary),full_window_run=False,full_window_paused_for_sector_breadth_contract=True)
write('STATUS.json',status)
report=f'''# Unified first-probe contract: engineering report

Implementation SHA256: {code}

## Scope and result

{status['synthetic_test_count']} synthetic checks passed on this exact implementation. Original source files checked: {len(original)}; changes: {len(changes)}. Only isolated research files are written. No full-window economic run, no trading orders.

Two-day first-entry check: {'PASS, see FIRST_DAY_COMPARISON.json and first_day_check_v2/SUMMARY.json.' if summary else 'Not passed yet. The first attempt failed during restored replay; review is pending before a separate new-directory run.'}

## Retained failed attempt

The normal Jan 5 OPEN call completed, then restored/poisoned replay failed an inventory invariant. Its normal-event count was not separately saved, so this report does not attribute a count or success to it. first_day_check/FAILURE.json and checkpoint remain unchanged. Source diagnosis: native restore updates dictionaries but does not delete four lazy attributes created after a zero-inventory checkpoint. The isolated wrapper now permits cleanup only of `_ix`, `_ixn`, `_buy_filling`, `_deferred_buy_cancels` when absent from the checkpoint. Any unrecognized extra state fails; source/policy/provenance checks remain. The empty-checkpoint versus baseline-ending-checkpoint field difference independently equals those four keys. No native ledger method was replaced.

## Contract changes

All real Q=0 entries, including original MOBILE, use probe and frozen 2% decision-NAV gross plus 0.25% modeled fee-inclusive protection loss. Original roles, CP consumption, CORE epoch lock, original I versus CP protection, fees, dated units, T+1, corporate-action callbacks and PVR ranking stay.

Shared probe10% capital/0.5% nominal protection risk applies to lots plus unfilled/cancel-pending reservations. There is no fixed stock-count cap. Held additions require positive fee-inclusive remaining-holding liquidation profit and valid fresh original CP. Per-layer 0.25% is only the first-probe constraint; it is not quietly imposed on all later MOBILE adds.

Promotion happens in a separate snapshot phase after original OPEN sells/settlement and before unchanged PVR buy allocation. Every eligible stock is evaluated against one shared state before commits. Only matching profitable stock/current-attempt probe layers migrate, with pool/jmeta equality. Profit is not credited as spendable cash. A new stock CP must confirm after actual probe fill, and OP must remain above its CP/I line. Independent promotion does not demand an affordable new buy. Native CP buy consumption remains separate. Canonical evidence, missing OPEN, invalid factor, no position and pending-order reasons are auditable.

## Conflicts and limits not hidden

The inherited industry probe capital gate counts ALL same-industry holdings, including confirmed. Existing 10% confirmed exposure can therefore prevent another stock's new probe under the 2% gate. A distinct formula-only comparison arm is documented; the main route is not relaxed. Industry-upgrade cancellation of old outstanding probe orders remains native and does not release reserve until ACK or migrate another stock.

The user's new requirement that a sector contain many right-side stocks is a separate unresolved admission specification. Existing sector E0/CP is not claimed to satisfy it. No arbitrary breadth threshold was added, and full-window economic launch remains paused.

Fixed future 1709 pool is NonPIT; historical tradability is UNKNOWN. Daily OPEN-known/same-price execution is a research proxy, not a live executable claim. First-day mechanics and synthetic tests cannot establish profitability, drawdown, 35% win rate, or robust right-side identification.

## Artifacts

- CONTRACT.md: formulas, state machine, ordering, inherited conflicts.
- unified_probe.py: isolated adapter and exact minimal native opening/request derivations.
- SYNTHETIC_RESULTS.json, EDGE_CASE_RESULTS.json, REPAIR_RESULTS.json: test scopes and exact hashes.
- FIRST_DAY_COMPARISON.json: baseline versus new first-entry details when available.
- ORIGINAL_SOURCE_INTEGRITY.json: protected original file hashes.
- STATUS.json: current verification stage; no economic completion claim.
'''
(HERE/'REPORT.md').write_text(report)
print(json.dumps(status,indent=2))
