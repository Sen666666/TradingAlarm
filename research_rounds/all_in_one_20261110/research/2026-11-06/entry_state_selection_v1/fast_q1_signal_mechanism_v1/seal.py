from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
src={};verified=0
for name in ['SOURCE_HASHES.json','ANCHOR_SOURCE_HASHES.json','sector_attempt_source_hashes.json']:
 m=json.loads((O/name).read_text())
 for p,h in m.items():
  assert sha(p)==h,(name,p,'source drift')
  if p in src:assert src[p]==h,(p,'inconsistent source hashes')
  src[p]=h;verified+=1
(O/'FINAL_SOURCE_HASHES.json').write_text(json.dumps(src,ensure_ascii=False,indent=2))
status={'status':'DIAGNOSIS_COMPLETE_NO_NEW_ECONOMIC_RUN','initial_target_34_35_not_met_or_claimed':True,'failure_only_rule':'DEFINED_BUT_SCOPE_INSUFFICIENT_FOR_ECONOMIC_ADVANCEMENT','higher_birth_anchor_hard_gate':'STOPPED_AFTER_CAUSAL_STARTUP_PREFLIGHT','source_paths':len(src),'source_hash_references_verified':verified,'independent_audits':['5031 permits / 5002 conditional fills / 559 execution UNKNOWN / 54 financial unknown closed preserved','Q1 1832 usable and 176 initial winners independently reconstructed','38 stocks 190 causal physical prefix checks','90 sector full-warm original trace and Stage exactly reproduced; independent 21780 sector day / 5031 permit / 654 startup state checks','35 stock cross-root floor causal prefixes and 7 startup direct native fact verification','PIT source-publication time, static universe and actual orderability NOT verified'],'economic_runs':0,'not_account':True,'NET80_scenario':True}
(O/'COMPLETION.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
files={str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='FINAL_OUTPUT_HASHES.json'}
(O/'FINAL_OUTPUT_HASHES.json').write_text(json.dumps(files,ensure_ascii=False,indent=2))
for rel,h in files.items():assert sha(O/rel)==h
print(json.dumps(dict(status= status,output_files=len(files),output_manifest_sha256=sha(O/'FINAL_OUTPUT_HASHES.json')),ensure_ascii=False,indent=2))
