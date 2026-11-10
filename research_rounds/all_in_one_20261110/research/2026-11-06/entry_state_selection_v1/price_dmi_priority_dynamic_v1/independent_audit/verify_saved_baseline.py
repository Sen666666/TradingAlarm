"""Independent saved baseline audit. No consumer or historical replay."""
from pathlib import Path
import ast,hashlib,json,os,sys
O=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(A))
from finalize_audit import sha,read,compare_csv,compare_json,save_exclusive_atomic,SOURCE
w=sys.argv[1];assert w in ['2022','2024']
dest=O/('baseline_exact_'+w);ref=SOURCE/('economic_'+w)
before={str(p):sha(p) for p in dest.rglob('*') if p.is_file()}
assert read(dest/'ECONOMIC_LOOP_COMPLETE.json')['loop_complete']
failure=read(dest/'FAILED_NO_RETRY.json');assert failure['loop_saved'] and failure['no_retry']
assert failure['error'].startswith('KeyError(')
driver=O/'recover_baseline_qa.py'
assert sha(driver)=='04bcee626a8bd860b2f6cd401d0362b0c50c788aa5639b48388aeb869ded2ed3'
for n in ast.walk(ast.parse(driver.read_text())):
 if isinstance(n,ast.Call):
  name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
  assert name not in {'load_engine','run_window','run_isolated','process_day','reset','finalize','dump','make_consumer'}
tables=['ROUNDS','ACTIONS','DECISIONS','RANKING_AUDIT','END_STATES','REGISTRATIONS','CLAIM_LEDGER','PROFIT_GATES']
checks={n:compare_csv(dest/'joint'/(n+'.csv'),ref/'joint'/(n+'.csv')) for n in tables}
for n in ['CLAIMS','BRIDGES','LEDGER_QA','SOURCE_HASHES']:checks[n]=compare_json(dest/'joint'/(n+'.json'),ref/'joint'/(n+'.json'))
for n in ['PRICE_AUDIT','OFFER_AUDIT','AB_DECISION_AUDIT','FROZEN_RESPONSIBILITIES','EXECUTION_BOOKS']:checks[n]=compare_json(dest/(n+'.json'),ref/(n+'.json'))
approved=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')['input_sha256']
plan={str(Path(p).resolve()):h for p,h in approved.items()}
assert all(plan[str(Path(p).resolve())]==h for p,h in approved.items())
sources=read(dest/'joint/SOURCE_HASHES.json');aliases=[]
assert len({str(Path(p).resolve()) for p in sources})==len(sources),'NORMALIZATION_MERGED_KEYS'
for p,h in sources.items():
 q=Path(p).resolve();assert plan.get(str(q))==h and sha(p)==sha(q)==h
 if p!=str(q):
  a,b=Path(p).stat(),q.stat()
  assert os.path.samefile(p,q) and (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)
  aliases.append(dict(logical=p,resolved=str(q),same_file=True,device=a.st_dev,inode=a.st_ino,sha256=h))
for p,h in read(dest/'MARKET_SOURCES.json').items():assert plan.get(str(Path(p).resolve()))==h and sha(p)==h
for n,h in read(dest/'joint/OUTPUT_HASHES.json').items():assert sha(dest/'joint'/n)==h
for p,h in before.items():assert sha(p)==h
qa=read(dest/'EXACT_QA.json')
assert qa['result']=='PASS_ORIGINAL_JOINT_EXACT' and qa['postprocess_only'] is True and qa['recovery_consumer_calls']==0 and qa['old_failure_preserved']
for n,h in read(O/'REVIEW_CODE_SHA256_v3.json').items():assert sha(O/n)==h
out=dict(status='PASS_INDEPENDENT_SAVED_ORIGINAL_JOINT_EXACT',window=w,checks=checks,aliases=aliases,source_count=len(sources),all_source_bytes_and_authorized_resolved_identity_exact=True,source_normalization_merges_no_keys=True,recovery_driver_sha256=sha(driver),recovered_qa_sha256=sha(dest/'EXACT_QA.json'),failure_sha256=sha(dest/'FAILED_NO_RETRY.json'),all_preexisting_saved_files_unchanged=before,frozen_v3_code_unchanged=True,economic_runs=0,new_dmi_runs=0)
save_exclusive_atomic(A/('SAVED_BASELINE_'+w+'.json'),out)
print(json.dumps(dict(status=out['status'],window=w,rows={n:x['rows'] for n,x in checks.items()},aliases=aliases,recovered_qa_sha256=out['recovered_qa_sha256']),indent=2),flush=True)
