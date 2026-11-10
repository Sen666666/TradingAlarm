from pathlib import Path
import json,hashlib,shutil,sys
P=Path(__file__).resolve().parent.parent;old=P/sys.argv[1];N=P/sys.argv[2];inputs=[Path(p).resolve() for p in sys.argv[3:]]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
assert inputs and not N.exists();assert all(sha(p)==h for p,h in read(old/'FREEZE.json')['hashes'].items());assert all(sha(old/'full_20241031_once'/p)==h for p,h in read(old/'full_20241031_once/OUTPUT_HASHES.json').items())
base=read(old/'ADDITIONAL_REVIEWED_EVENTS.json');extra=[]
for p in inputs:
 for x in read(p):
  x['evidence_hashes']={**x.get('evidence_hashes',{}),str(p):sha(p)};extra.append(x)
all_events=base+extra;assert len({(x['sid'],x['ex_date']) for x in all_events})==len(all_events)
last=read(old/'full_20241031_once/DAY_LEDGER.json')[-1]['day'];stamp=last.replace('-','');N.mkdir()
for name in ['CLASSIFICATION_ALL1709.csv','EXCLUDED_UNCLASSIFIED.csv','MAPPING_SOURCE_HASHES.json','MAPPING_QA.json','synthetic_joint.py']:shutil.copyfile(old/name,N/name)
(N/'ADDITIONAL_REVIEWED_EVENTS.json').write_text(json.dumps(all_events,ensure_ascii=False,indent=2)+'\n')
s=(old/'engine.py').read_text();a=s.index("    if checkpoint and day(d)=='",s.index('def run(self,checkpoint=False)'));b=s.index("    if checkpoint and day(d)=='2024-09-23':",a)
block=f'''    if checkpoint and day(d)=='{last}':
     self.pending=pending;self.export(O/'replay_{stamp}');checks={{}}
     prior=O.parent/'{old.name}/full_20241031_once'
     for name in ['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END']:
      prior_rows=read(prior/(name+'.json'));new_rows=read(O/'replay_{stamp}'/(name+'.json'));assert prior_rows==new_rows,('PRIOR_PREFIX_MISMATCH',name);checks[name]=len(new_rows)
     save(O/'PRIOR_PREFIX_REPLAY_QA.json',dict(result='PASS',certified_through='{last}',economic_rule_changes=0,exact_records=checks));print('PRIOR_PREFIX_REPLAY_PASS '+json.dumps(checks),flush=True)
'''
s=s[:a]+block+s[b:];(N/'engine.py').write_text(s)
contract=(P/'joint51_candidate_v1/FROZEN_CONTRACT.md').read_text()+f'''\n## Fact-only revision lineage\nOriginal v1 and all prior versions remain immutable. This version extends {old.name} by reviewed corporate cash-event facts only; no economic rule changes. All nine account output families through {last} must replay exactly before later days run. The original 2024-09-23 checkpoint remains independently available; this version also exports it using the same algorithm. d_cash owns cash entitlement, d_source translates frozen source coordinates, d_ref preserves official reference-price facts and does not replace either.\n''';(N/'FROZEN_CONTRACT.md').write_text(contract)
revision=dict(kind='FACT_EVIDENCE_ONLY',economic_rule_changes=0,previous_directory=str(old),previous_certified_through=last,previous_freeze_sha256=sha(old/'FREEZE.json'),previous_engine_sha256=sha(old/'engine.py'),previous_output_hashes_sha256=sha(old/'full_20241031_once/OUTPUT_HASHES.json'),new_adapter_inputs={str(p):sha(p) for p in inputs},new_event_keys=[x['sid']+'|'+x['ex_date'] for x in extra],carried_event_keys=[x['sid']+'|'+x['ex_date'] for x in base],technical_changes=['Add reviewed factual event evidence','Advance exact prior-prefix replay gate','Preserve previous outputs and all economic rules'])
(N/'FACT_REVISION.json').write_text(json.dumps(revision,ensure_ascii=False,indent=2)+'\n');print(N,'extra',len(extra),'replay through',last)
