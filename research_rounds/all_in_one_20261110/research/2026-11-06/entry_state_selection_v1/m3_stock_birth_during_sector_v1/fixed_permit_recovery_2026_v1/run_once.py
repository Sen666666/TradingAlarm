"""The sole recovery run. Requires explicit independent reviewer approval of frozen code."""
import engine as s
from engine import pd
O=s.O
review=s.read(O/'PRE_ECONOMIC_AUDIT.json')
assert review['approved'] is True and review['scope']=='FIXED20_NET80_SOURCE16'
for name,h in review['code_sha256'].items():assert s.sha(O/name)==h,(name,'unreviewed code')
s.verify_frozen_inputs(review['input_sha256'])
fp=s.E/'cash_facts_2026_v1/EVENT_ADAPTER_CANDIDATES.json'
assert review['cash_adapter_sha256']==s.sha(fp)
assert review['fact_evidence_independently_approved'] is True
assert not (O/'ECONOMIC_RUN_ONCE.json').exists() and not (O/'economic').exists()
s.verify_cash_fact_review();s.prepare_sources();events=s.load_cash_candidates();s.verify_frozen_inputs();s.install_events(events)
s.save(O/'ECONOMIC_RUN_ONCE.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),scope='FIXED20_NET80_SOURCE16',permits=20,original_denominator=46,review_sha256=s.sha(O/'PRE_ECONOMIC_AUDIT.json'),code_sha256=review['code_sha256'],cash_adapter_sha256=s.sha(fp)))
s.reset(True,True)
for r in s.original[s.original.status.str.contains('UNKNOWN')].itertuples():s.run_fixed(r.round_id)
assert len(s.rounds)==20 and len({r['round_id'] for r in s.rounds})==20
s.dump(O/'economic')
# Retain the other26 original outcomes and ledgers exactly, without execution or reselection.
retained=s.original[~s.original.status.str.contains('UNKNOWN')].copy();retained['recovery_origin']='ORIGINAL_UNCHANGED'
recovered=pd.DataFrame(s.rounds);recovered['recovery_origin']='ORIGINAL_UNKNOWN_FIXED_PERMIT_RECOVERY'
full=pd.concat([retained,recovered],ignore_index=True);assert len(full)==46 and full.round_id.is_unique
full.to_csv(O/'ALL_FIXED46_ROUNDS.csv',index=False)
a=pd.read_csv(s.E/'lifecycle_v1/ACTIONS.csv',float_precision='round_trip');a=a[a.round_id.isin(retained.round_id)]
pd.concat([a,pd.DataFrame(s.actions)],ignore_index=True).to_csv(O/'ALL_FIXED46_ACTIONS.csv',index=False)
s.save(O/'ECONOMIC_EVENTS.json',events)
print('RECOVERY_FINISHED',len(s.rounds))
