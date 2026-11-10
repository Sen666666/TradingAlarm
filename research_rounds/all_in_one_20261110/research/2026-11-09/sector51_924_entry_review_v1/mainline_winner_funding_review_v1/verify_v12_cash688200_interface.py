"""Independent v2 interface recheck, synthetic only; never Data() or historical launcher."""
from pathlib import Path
import os,sys,json,subprocess,hashlib,importlib.util,random
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
O=Path(__file__).resolve().parent
P=ROOT/'mainline_candidate_v12_winner_funding_cash_688200_v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest_path=P/'SOURCE_HASHES.json'
manifest_sha=sha(manifest_path)
manifest=json.loads(manifest_path.read_text())
def verify():
    assert sha(manifest_path)==manifest_sha,'SOURCE_MANIFEST_CHANGED_DURING_REVIEW'
    for p,h in manifest['files'].items():assert sha(p)==h,('SOURCE_DRIFT',p)
verify()
before={n:sha(P/n) for n in ['engine.py','stream_output.py','checkpoint.py','prefix_check.py','run_approved_once.py','synthetic_tests.py','checkpoint_tests.py','bridge_branch_tests.py','runner_tests.py','CONTRACT.md','ADMISSION_LOCK.json','PREFIX_REFERENCE.json']}
results={}
for stem,script in [('SYNTHETIC','synthetic_tests.py'),('CHECKPOINT','checkpoint_tests.py'),('BRIDGE_BRANCH','bridge_branch_tests.py'),('RUNNER','runner_tests.py')]:
    target=O/('V12_CASH688200_INDEPENDENT_'+stem+'_QA.json')
    env=dict(os.environ,QA_RESULT_PATH=str(target))
    r=subprocess.run([sys.executable,'-B',str(P/script)],cwd=ROOT,env=env,text=True,capture_output=True)
    if r.returncode:
        raise AssertionError(('INDEPENDENT_SUITE_FAILED',script,r.returncode,r.stdout[-3000:],r.stderr[-3000:]))
    q=json.loads(target.read_text());assert q['result']=='PASS' and not q['history_run'] and not q['real_Data_constructed']
    results[stem]=dict(assertions=q['assertions'],path=str(target),sha256=sha(target))
    print(stem+' '+str(q['assertions'])+' PASS',flush=True)
spec=importlib.util.spec_from_file_location('independent_final_cash688200',P/'engine.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
static=m.self_check();assert static['result']=='PASS'
rng=random.Random(688200)
scalar=[None,True,False,0,-3,1.25,-0.0,'汉字\n\t"',m.D('.2300'),m.frozen.np.bool_(False),m.frozen.np.int64(9),m.frozen.np.float32(2.5),m.pd.Timestamp('2024-10-11'),float('nan'),float('inf')]
def value(depth=0):
    if depth>4 or rng.random()<.5:return rng.choice(scalar)
    kind=rng.randrange(4)
    if kind==0:return [value(depth+1) for _ in range(rng.randrange(7))]
    if kind==1:return tuple(value(depth+1) for _ in range(rng.randrange(7)))
    if kind==2:return {k:value(depth+1) for k in rng.sample(['x','汉字',1,'1',None,True,3.5],rng.randrange(8))}
    return set(rng.sample([1,2,'x','汉字',(1,2),m.D('.2300')],rng.randrange(7)))
for i in range(250):
    v=value()
    assert ''.join(m.stream.json_chunks(v))==json.dumps(m.frozen.clean(v),ensure_ascii=False,indent=2,default=str),('ENCODING',i)
verify()
assert before=={n:sha(P/n) for n in before},'CODE_CHANGED_DURING_REVIEW'
result=dict(result='PASS_V12_CASH688200_CONTINUATION_INTERFACE',source_manifest_sha256=manifest_sha,
    checked_files=before,source_files_verified=len(manifest['files']),source_unchanged_after_review=True,
    suites=results,native_synthetic_assertions=sum(r['assertions'] for r in results.values()),
    independent_random_encoding_cases=250,independent_random_seed=688200,static=static,
    history_run=False,real_Data_constructed=False,remaining_blockers=[],
    scope=['Exact 688200 event only; inherited original economic methods unchanged.',
        'Full original export equivalence including branch gzip decompression; no fields dropped.',
        'Old CLOSE-factor book to admitted OPEN bridge preserves live factor, old ticket, zero entitlements.',
        'Same-manifest joint-state checkpoint preserves aliases; no cross-source migration or automatic history permission.',
        'One-shot runner must receive parent approval with exact interface review/source/QA hashes before run.',
        'Actual 22-day prefix remains to be proved by approved runner: 25 daily families, whole branch contents, final state; only specified 10/10 zero-snapshot diagnostic digests may differ.'],
    not_certified=['Historical 93-day outcome','actual 22-day replay prefix','real full-Data/runtime storage scale','full PIT or production tradability'])
target=O/'V12_CASH688200_INTERFACE_QA.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['result','source_manifest_sha256','source_files_verified','native_synthetic_assertions','independent_random_encoding_cases','remaining_blockers']},ensure_ascii=False))
