from pathlib import Path
import hashlib, json
from datetime import datetime, timezone
D=Path(__file__).resolve().parent

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

def dump(name, obj):
    (D/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

sources={}
for f in ['BASELINE_SOURCE_HASHES.json','FEATURE_SOURCE_HASHES.json']:
    for p,h in json.loads((D/f).read_text()).items():
        assert p not in sources or sources[p]==h, ('inconsistent source hash',p)
        sources[p]=h
for p,h in json.loads((D/'LABEL_CONNECTION_QA.json').read_text())['source_sha256'].items():
    assert p not in sources or sources[p]==h, ('inconsistent source hash',p)
    sources[p]=h
errors=[p for p,h in sources.items() if not Path(p).is_file() or sha(p)!=h]
assert not errors, errors
worker=json.loads((D/'FIXED_COHORT_OUTPUT_HASHES.json').read_text())
errors=[p for p,h in worker.items() if not (D/p).is_file() or sha(D/p)!=h]
assert not errors, errors
assert not list(D.rglob('__pycache__'))
dump('FINAL_SOURCE_HASHES.json',dict(sorted(sources.items())))
dump('COMPLETION.json',{
    'status':'FIXED_COHORT_DIAGNOSTIC_COMPLETE_NOT_PROMOTED',
    'sealed_at_utc':datetime.now(timezone.utc).isoformat(),
    'baseline_permits':{'2022':2732,'2024_autumn':1354},
    'baseline_usable_closed_initial':{'2022':2616,'2024_autumn':1312},
    'baseline_initial_wins':{'2022':834,'2024_autumn':530},
    'execution_unknown':{'2022':103,'2024_autumn':27},
    'closed_financial_unknown':{'2022':11,'2024_autumn':8},
    'nofill':{'2022':2,'2024_autumn':7},
    'fixed_cases':25,'existing_labels_connected':19,'input_only_without_labels':6,
    'fixed_case_industries':12,'original_stock_signals':389,'member_rows':1198,
    'small_formula_diagnostics':1,'parameter_searches':0,'new_economic_runs':0,
    'synthetic_checks_passed':21,
    'source_hashes_verified':len(sources),
    'worker_output_hashes_verified':len(worker),
    'independent_audit':'Corrected calculation, identity, existing labels and uncertainty accounting passed. No efficacy or causality certification.',
    'engineering_correction':'Before label connection, case context M3 was corrected from an erroneous PVR3 cache to canonical M3. Formula and fixed cases unchanged; superseded files retained.',
    'limitations':['Historical cases already seen, not blind or out of sample','Static pool and industry mapping are NON-PIT','Finite corporate-action coverage and NET80 assumptions differ by window','Conditional fills and core decomposition are not real account trading','Coverage bounds are not statistical confidence intervals','Native E0 anchor is not a verified joint innovation event','No score consumer or 34/35 percent target attainment demonstrated']
})
outputs={str(p.relative_to(D)):sha(p) for p in sorted(D.rglob('*')) if p.is_file() and p.name!='FINAL_OUTPUT_HASHES.json'}
dump('FINAL_OUTPUT_HASHES.json', outputs)
assert all(sha(D/p)==h for p,h in outputs.items())
print(json.dumps({'sources':len(sources),'outputs':len(outputs),'source_mismatches':0,'output_mismatches':0,'final_output_manifest_sha256':sha(D/'FINAL_OUTPUT_HASHES.json')},indent=2))
