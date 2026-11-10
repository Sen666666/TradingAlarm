"""Independent saved-baseline revalidation only. No historical consumer calls."""
from pathlib import Path
import sys,ast,json,hashlib,time,datetime
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=Path(__file__).resolve().parent;D=R/'price_dmi_priority_dynamic_v1';J=R/'independent_channel_joint_economic_v1'
sys.dont_write_bytecode=True;sys.path.insert(0,str(D/'independent_audit'))
from finalize_audit import compare_csv,compare_json,read,sha
start=time.monotonic();checks={};saved={}
for w in ['2022','2024']:
 dest=D/('baseline_exact_'+w);ref=J/('economic_'+w)
 c={n:compare_csv(dest/'joint'/(n+'.csv'),ref/'joint'/(n+'.csv')) for n in ['ROUNDS','ACTIONS','DECISIONS','RANKING_AUDIT','END_STATES','REGISTRATIONS','CLAIM_LEDGER','PROFIT_GATES']}
 for n in ['CLAIMS','BRIDGES','LEDGER_QA','SOURCE_HASHES']:c[n]=compare_json(dest/'joint'/(n+'.json'),ref/'joint'/(n+'.json'))
 for n in ['PRICE_AUDIT','OFFER_AUDIT','AB_DECISION_AUDIT','FROZEN_RESPONSIBILITIES','EXECUTION_BOOKS']:c[n]=compare_json(dest/(n+'.json'),ref/(n+'.json'))
 audit=read(D/'independent_audit'/('SAVED_BASELINE_'+w+'.json'))
 for p,h in audit['all_preexisting_saved_files_unchanged'].items():assert sha(p)==h,('BASELINE_SAVED_FILE_CHANGED',p)
 for n,v in c.items():
  old=audit['checks'][n]
  assert old['actual_sha256']==v['actual_sha256'] and old['reference_sha256']==v['reference_sha256']
 checks[w]=c;saved[w]=dict(independent_previous_audit_sha256=sha(D/'independent_audit'/('SAVED_BASELINE_'+w+'.json')),baseline_exact_qa_sha256=sha(dest/'EXACT_QA.json'),preserved_failure_sha256=sha(dest/'FAILED_NO_RETRY.json'))
a=read(J/'ROOT_ECONOMIC_AUTHORIZATION.json');seal=read(J/'FINAL_RUN_SEAL.json')
assert a['code_sha256']==seal['code_sha256']
for n,h in a['code_sha256'].items():assert sha(J/n)==h,('ORIGINAL_CODE_DRIFT',n)
for p,h in a['input_sha256'].items():assert sha(p)==h,('ORIGINAL_INPUT_DRIFT',p)
for p,h in seal['files'].items():assert sha(Path(p) if Path(p).is_absolute() else J/p)==h,('ORIGINAL_OUTPUT_DRIFT',p)
for w in ['2022','2024']:
 folder=J/('economic_'+w)/'joint'
 for n,h in read(folder/'OUTPUT_HASHES.json').items():assert sha(folder/n)==h
plan={str(Path(p).resolve()):h for p,h in a['input_sha256'].items()};sources={}
for w in ['2022','2024']:
 sources[w]={}
 for f in ['joint/SOURCE_HASHES.json','MARKET_SOURCES.json']:
  x=read(D/('baseline_exact_'+w)/f)
  assert len({str(Path(p).resolve()) for p in x})==len(x)
  for p,h in x.items():assert plan.get(str(Path(p).resolve()))==h and sha(p)==h
  sources[w][f]=dict(count=len(x),all_authorized_resolved_bytes_exact=True,sha256=sha(D/('baseline_exact_'+w)/f))
for n,h in read(D/'REVIEW_CODE_SHA256_v3.json').items():assert sha(D/n)==h
# Verify no economic run was called from this script and preserve the old lock evidence.
for n in ast.walk(ast.parse(Path(__file__).read_text())):
 if isinstance(n,ast.Call):
  name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
  assert name not in {'load_engine','run_isolated','make_consumer','run_authorized','process_day','dump','reset','finalize'}
locks={}
for w in ['2022','2024']:
 p=J/('ECONOMIC_RUN_ONCE_'+w+'.json');st=p.stat()
 locks[w]=dict(sha256=sha(p),created_utc=datetime.datetime.fromtimestamp(st.st_birthtime,datetime.timezone.utc).isoformat(),mtime_utc=datetime.datetime.fromtimestamp(st.st_mtime,datetime.timezone.utc).isoformat(),old_seal_sha256=seal['files'][p.name])
 assert locks[w]['sha256']==locks[w]['old_seal_sha256']
out=dict(status='PASS_INDEPENDENT_ORIGINAL_JOINT_SAVED_BASELINE_REUSE',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,saved_evidence=saved,source_bindings=sources,original_code_count=len(a['code_sha256']),original_input_count=len(a['input_sha256']),original_sealed_output_count=len(seal['files']),all_original_inputs_codes_outputs_unchanged=True,old_locks=locks,original_authorization_sha256=sha(J/'ROOT_ECONOMIC_AUTHORIZATION.json'),original_final_seal_sha256=sha(J/'FINAL_RUN_SEAL.json'),old_dmi_review_code_manifest_sha256=sha(D/'REVIEW_CODE_SHA256_v3.json'),script_sha256=sha(__file__),economic_calls=0,elapsed_seconds=time.monotonic()-start)
p=O/'BASELINE_REUSE_AUDIT.json'
with p.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
print(out['status'],sha(p),out['elapsed_seconds'],flush=True)
