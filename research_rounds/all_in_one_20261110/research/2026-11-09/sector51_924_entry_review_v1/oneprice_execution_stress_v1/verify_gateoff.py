from pathlib import Path
import json,hashlib,sys
R=Path(sys.argv[1]);rd=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();B=Path(rd(R/'FREEZE.json')['source_facts'])/'full_20241031_once';S=R/'full_20241031_once';result={}
for n in ['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END']:
 a=rd(S/(n+'.json'));b=rd(B/(n+'.json'))
 if n=='CANDIDATES':a=[{k:v for k,v in x.items() if k not in ['original_intended_q','reserved_q','fill_status']} for x in a]
 assert a==b,('GATEOFF_BASELINE_MISMATCH',n);result[n]=len(a)
assert rd(S/'NO_FILLS.json')==[]
out=dict(result='PASS',all_nine_baseline_families_exact=True,scope='Gate disabled wrapper validation, not an alternative strategy or parameter trial.',candidate_annotation_fields_removed=['original_intended_q','reserved_q','fill_status'],through=rd(S/'DAY_LEDGER.json')[-1]['day'],exact_rows=result,source_hashes={str(p):sha(p) for p in [Path(__file__),R/'FREEZE.json',S/'OUTPUT_HASHES.json',B/'OUTPUT_HASHES.json']})
(R/'BASELINE_EXACT_VALIDATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
