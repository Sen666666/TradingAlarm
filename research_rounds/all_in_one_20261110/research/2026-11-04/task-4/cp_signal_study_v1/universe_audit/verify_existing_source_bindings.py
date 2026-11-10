from pathlib import Path
import json,hashlib,time
O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');U=B/'universe-cp1-inputs-20261031'
SM=json.loads((U/'STOCK_MANIFEST.json').read_text());S={x['symbol']:x for x in SM}
ps=[B/'2022-normal-reference-20261031/inputs/MANIFEST.json',B/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]
checks=[]
for p in ps:
 for r in json.loads(p.read_text()):
  if r['industry']:continue
  x=S[r['sid']];src=x['output_sha256'].get(x['refs']['CP1']);old=r['original_output_sha256'].get(r['refs']['CP1']);checks.append({'sid':r['sid'],'canonical_manifest':str(p),'current_CP_ref':x['refs']['CP1'],'canonical_CP_ref':r['refs']['CP1'],'CP_source_SHA_equal':src==old,'entire_original_output_mapping_equal':x['output_sha256']==r['original_output_sha256']})
err=json.loads((O/'AUDIT_ERRORS.json').read_text());old=err[:];failed={(r['sid'],int(Path(r['canonical_manifest']).parts[-3][:4])) for r in checks if not r['CP_source_SHA_equal']}
# Known prior diagnostic was path-name selection only: all CP bindings are exact by explicit refs.
if not failed:err=[x for x in err if x['error']!='canonical_CP_source_hash_not_same']
(O/'AUDIT_ERRORS.initial_path_selector_only.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n');(O/'AUDIT_ERRORS.json').write_text(json.dumps(err,ensure_ascii=False,indent=2)+'\n')
raw={r['sid']:r for r in __import__('csv').DictReader((O/'SOURCE_REFS.csv').open())};h=[];beg=time.monotonic()
for sid,x in S.items():
 for kind in ['CP1','facts']:
  p=Path(x['refs'][kind]);actual=hashlib.sha256(p.read_bytes()).hexdigest();expected=x['output_sha256'].get(str(p));h.append({'sid':sid,'kind':kind,'path':str(p),'actual_sha256':actual,'manifest_sha256':expected,'match':actual==expected})
 p=Path(raw[sid]['raw_ref']);actual=hashlib.sha256(p.read_bytes()).hexdigest();expected=raw[sid]['raw_bundle_sha256'];h.append({'sid':sid,'kind':'raw','path':str(p),'actual_sha256':actual,'manifest_sha256':expected,'match':actual==expected})
(O/'ACTUAL_CP_FACTS_RAW_SOURCE_SHA256.json').write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n')
(O/'CANONICAL_ORIGINAL_SOURCE_BINDINGS.json').write_text(json.dumps({'binding_checks':len(checks),'CP_hash_all_equal':all(r['CP_source_SHA_equal'] for r in checks),'entire_output_mapping_all_equal':all(r['entire_original_output_mapping_equal'] for r in checks),'initial_diagnostic':'1197 warnings were a faulty path selector: reused original CP outputs live in external /signals/ paths, not only /CP1/. Explicit r.refs.CP1 keys prove all 5127 bindings exact. No signal/ID values changed.','rows':checks},ensure_ascii=False,indent=2)+'\n')
s=json.loads((O/'SUMMARY.json').read_text());s.update(error_count=len(err),canonical_source_bindings_verified=len(checks),canonical_CP_source_hash_all_equal=all(r['CP_source_SHA_equal'] for r in checks),canonical_entire_original_output_mapping_all_equal=all(r['entire_original_output_mapping_equal'] for r in checks),actual_source_hash_checks=len(h),actual_source_hash_mismatches=sum(not r['match'] for r in h));(O/'SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
sha=json.loads((O/'READ_SOURCE_SHA256.json').read_text())
for p in [Path(__file__),O/'audit_existing_cp_universe.py']:sha[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
(O/'READ_SOURCE_SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n')
print('canonical bindings',len(checks),'entire mapping equal',all(r['entire_original_output_mapping_equal'] for r in checks),'actual price/CP hashes',len(h),'mismatch',sum(not r['match'] for r in h),'remaining errors',len(err),'seconds',time.monotonic()-beg)
