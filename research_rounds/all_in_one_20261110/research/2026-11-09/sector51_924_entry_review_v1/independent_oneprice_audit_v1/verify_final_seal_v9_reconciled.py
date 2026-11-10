from pathlib import Path
from collections import Counter
import json,hashlib
A=Path(__file__).resolve().parent;R=A.parent/'oneprice_execution_stress_v1';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();errors=[];checks=Counter();sources={};scenarios={}
def ck(label,a,b,ctx=None):
 checks[label]+=1
 if a!=b:errors.append(dict(check=label,context=ctx,actual=str(a),expected=str(b)))
for folder in sorted(R.glob('facts_v[0-9]*'))+sorted(R.glob('gateoff_validation_facts_v[0-9]*')):
 f=read(folder/'FREEZE.json')
 for p,h in f['source_hashes'].items():
  if p in sources:ck('cross_version_same_path_hash',sources[p],h,p)
  sources[p]=h
 for p,h in f['scenario_hashes'].items():
  if p in scenarios:ck('cross_version_scenario_same_path_hash',scenarios[p],h,p)
  scenarios[p]=h
for p,h in sources.items():ck('all_union_frozen_source_hashes',sha(p),h,p)
for p,h in scenarios.items():ck('all_union_frozen_scenario_hashes',sha(p),h,p)
author=read(R/'FINAL_BOUNDED_RESEARCH_SEAL.json');ck('author_total_frozen_file_count',len(set(sources)|set(scenarios)),author['frozen_source_files_verified'])
for p,h in author['source_evidence'].items():ck('author_evidence_hash',sha(p),h,p)
ck('author_final_readout_hash',sha(R/'FINAL_RESEARCH_READOUT_ZH.md'),author['final_readout_sha256'])
qa=read(A/'INDEPENDENT_SYNTHETIC.json');ck('independent_47_case_engine_unchanged',sha(R/'stress_engine.py'),qa['engine_sha256']);ck('independent_47_case_fixture_unchanged',sha(A/'independent_synthetic.py'),qa['source_sha256']);ck('independent_synthetic_previous_result',qa['status'],'PASS')
report=dict(status='PASS' if not errors else 'FAIL',checks=dict(checks),check_count=sum(checks.values()),errors=errors,distinct_frozen_source_files=len(sources),distinct_frozen_scenario_files=len(scenarios),distinct_all_frozen_files=len(set(sources)|set(scenarios)),count_definition_correction='The author field frozen_source_files_verified counts the union of data-source and scenario-source hashes. Initial independent check incorrectly compared its 8685 total against 8681 data-only files. All individual hashes passed in that first report. Correct union is 8681 data/source files plus 4 scenario files = 8685. Original initial-check output retained.',prior_independent_synthetic_cases=qa['cases'],prior_synthetic_result_reused_because_exact_engine_and_fixture_hashes_match=True,no_strategy_or_synthetic_rerun=True)
p=A/'facts_v9/FINAL_SEAL_VERIFICATION_RECONCILED.json';assert not p.exists();p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
