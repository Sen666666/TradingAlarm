from pathlib import Path
import lifecycle as l
s=l.s;pd=l.pd;O=Path(__file__).resolve().parent
assert not (O/'FREEZE.json').exists() and not (O/'RUN_ONCE.json').exists()
sources={}
for file in ['INPUT_SOURCE_HASHES.json','INPUT_PREFIX_SOURCE_HASHES.json']:
 sources.update(s.read(O/file))
sources.update(s.hashes)
for p in [l.BASE/'dynamic/ACTIONS.csv',l.BASE/'dynamic/DECISIONS.csv',l.BASE/'dynamic/ROUNDS.csv',l.BASE/'dynamic/CLAIMS.json',l.BASE/'report/CORE_AND_FULL_ROUNDS.csv',l.BASE/'report/FINANCIAL_COVERAGE.csv',l.R/'dynamic_entry_formation_mechanism_v1/POSTHOC_TIMING_CASES.csv',l.R/'dynamic_entry_formation_mechanism_v1/FIXED_CLOCK_BOUNDARY_CASES.csv']:
 sources[str(p)]=s.sha(p)
for path,h in sources.items():assert s.sha(path)==h,(path,'source mismatch')
art=s.read(O/'INPUT_OUTPUT_HASHES.json')
for p in ['PROTOCOL_DRAFT.md','lifecycle.py','run.py','report.py','test_synthetic.py','baseline_regression.py','SYNTHETIC_QA.json','BASELINE_OFF_PREFIX_QA.json','CONSUMER_INPUT_QA.json','NATIVE_CONTRACT_NOTES.md']:
 art[p]=s.sha(O/p)
for name,h in art.items():assert s.sha(O/name)==h
audit=dict(passed=True,scope='Independent pre-run input, protocol and implementation audit; one AB_FAST_SMALL 2022 lifecycle only. Not economic validation.',issues_fixed=['OTHER_UNKNOWN_OR_LEFT not AB','CP initial risk uses its actual live CP floor','Unknown floor cannot silently downgrade or bypass'],input_rows=413578,candidates=52453,AB_exact=12917,canonical_CP=99031,canonical_2022=16932,synthetic_pass=True,baseline_regression='January 2022 only',physical_input_prefix_cases=10,economic_runs_before_freeze=0,files={n:art[n] for n in ['PROTOCOL_DRAFT.md','lifecycle.py','run.py','report.py','SYNTHETIC_QA.json']})
s.save(O/'PRE_ECONOMIC_AUDIT.json',audit);art['PRE_ECONOMIC_AUDIT.json']=s.sha(O/'PRE_ECONOMIC_AUDIT.json')
s.save(O/'FREEZE.json',dict(created=pd.Timestamp.now(tz='UTC').isoformat(),independent_audit_passed=True,new_arm='AB_FAST_SMALL',new_runs=1,baseline_cached=True,source_hashes=sources,artifact_hashes=art,no_new_outcomes_computed=True))
print('FROZEN',len(sources),len(art),s.sha(O/'FREEZE.json'),flush=True)
