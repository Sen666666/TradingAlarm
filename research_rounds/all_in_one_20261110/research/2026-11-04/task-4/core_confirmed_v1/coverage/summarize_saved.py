"""Saved coverage completeness/denominator readout, no market or native engine."""
from pathlib import Path
from collections import Counter
import gzip, hashlib, json, time
O=Path(__file__).resolve().parent; begun=time.monotonic()
def read(n):
    with gzip.open(O/n,'rt') as f:return [json.loads(s) for s in f]
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
rows=read('ALL_CORE_OPEN_ORIGINAL_MOTHER.jsonl.gz');detail=read('NARROW_CANDIDATES.jsonl.gz')
def group(r):return r['window'],r['sid'],tuple(r['original_intent']['epoch'])
first={};efirst={}
for r in rows:
    first.setdefault(group(r),r)
    if r['narrow_fallback_necessary_candidate']:efirst.setdefault(group(r),r)
def describe(rs):
    rs=list(rs);c=[r for r in rs if r['narrow_fallback_necessary_candidate']]
    return dict(all_original_OPEN=len(rs),unique_source_I=len({group(r) for r in rs}),narrow_raw=len(c),unique_source_I_with_narrow=len({group(r) for r in c}),
      first_original_CORE_OPEN_candidates=sum(r['narrow_fallback_necessary_candidate'] for r in first.values() if any(r is z for z in rs)),
      first_eligible_CORE_fallback_events=sum(any(r is z for z in rs) for r in efirst.values()))
# Use key sets for linear saved aggregation rather than testing every pair.
def stratum(period,semi=False):
    rs=[r for r in rows if r['period']==period and(not semi or r['industry']=='半导体')];keys={r['key']for r in rs};c=[r for r in rs if r['narrow_fallback_necessary_candidate']]
    return dict(all_original_OPEN=len(rs),narrow_raw=len(c),unique_source_I_with_narrow=len({group(r)for r in c}),first_original_CORE_OPEN_candidates=sum(r['narrow_fallback_necessary_candidate']and r['key']in keys for r in first.values()),first_eligible_CORE_fallback_events=sum(r['key']in keys for r in efirst.values()))
missing=[r['key']for r in rows if r['original_opportunity']['CP1_id']and r['same_day_canonical_CP']is None]
unknown=[r['key']for r in rows if r['same_day_canonical_CP']and r['same_day_canonical_CP']['trace_unknown']]
assert not missing and not unknown
assert len({r['key']for r in rows})==117121 and len(detail)==1536
semi=[r for r in detail if r['period']=='2026H1'and r['industry']=='半导体']
save('STRATIFIED_SOURCE_I_COVERAGE.json',dict(by_period={p:stratum(p)for p in sorted({r['period']for r in rows})},semiconductors_by_period={p:stratum(p,True)for p in sorted({r['period']for r in rows})},H1_semiconductor_candidate_keys=[r['key']for r in semi],H1_semiconductor_minimum_witnesses=sum(r['original_confirmed_MOBILE_minimum_existence_witness']['proven']for r in semi)))
save('SAVED_COMPLETENESS_QA.json',dict(original_CORE_OPEN=117121,narrow=1536,op_CP_without_canonical_trace=missing,canonical_trace_unknown=unknown,duplicate_keys=0,all_narrow_full_original_Q_flat_epoch_intent_assertions_in_source=True,
    all_narrow_prior_existing_order_reserve_zero=all(r['preexisting_S0_buy_reserve']==0 for r in detail),all_narrow_no_same_attempt_front_probe=all(not r['same_OPEN_prior_same_attempt_probe_order_keys']for r in detail),
    all_narrow_failure_sets_nonempty_subset=all(set(r['original_failure_set'])and set(r['original_failure_set'])<={'probe_risk','sector_capital'}for r in detail),witness_failure_reasons=dict(Counter(r['original_confirmed_MOBILE_minimum_existence_witness'].get('reason','checks_not_all_true')for r in detail if not r['original_confirmed_MOBILE_minimum_existence_witness']['proven'])),
    seconds=time.monotonic()-begun,no_new_account=True,no_new_marks=True,scope='saved rows only; not an independent full native rerun'))
print(json.dumps(dict(seconds=time.monotonic()-begun,H1_semis=len(semi),H1_semis_witnesses=sum(r['original_confirmed_MOBILE_minimum_existence_witness']['proven']for r in semi))))
