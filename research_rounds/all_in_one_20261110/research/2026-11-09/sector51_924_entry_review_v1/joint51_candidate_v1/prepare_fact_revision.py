"""Prepare a new sibling research version; old code/results are immutable inputs."""
from pathlib import Path
import json,hashlib,shutil,sys
O=Path(__file__).resolve().parent;N=O.parent/'joint51_candidate_v2_facts'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert len(sys.argv)>1,'Pass reviewed event adapter JSON path(s).'
inputs=[Path(p).resolve() for p in sys.argv[1:]];extra=[]
for p in inputs:
 v=json.loads(p.read_text());assert isinstance(v,list);extra+=v
assert extra and len({(x['sid'],x['ex_date']) for x in extra})==len(extra)
N.mkdir(exist_ok=False)
for name in ['CLASSIFICATION_ALL1709.csv','EXCLUDED_UNCLASSIFIED.csv','MAPPING_SOURCE_HASHES.json','MAPPING_QA.json','synthetic_joint.py']:
 shutil.copyfile(O/name,N/name)
for x in extra:
 x['evidence_hashes']=dict(x.get('evidence_hashes',{}),**{str(p):sha(p) for p in inputs if any((r['sid'],r['ex_date'])==(x['sid'],x['ex_date']) for r in json.loads(p.read_text()))})
(N/'ADDITIONAL_REVIEWED_EVENTS.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2)+'\n')
s=(O/'engine.py').read_text()
s=s.replace("xp=P/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json';events+=read(hashed(xp))","xp=P/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json';events+=read(hashed(xp))\n  events+=read(hashed(O/'ADDITIONAL_REVIEWED_EVENTS.json'))")
needle="    if checkpoint and day(d)=='2024-09-23':"
replacement="""    if checkpoint and day(d)=='2024-09-13':
     self.pending=pending;self.export(O/'replay_20240913');checks={}
     prior=O.parent/'joint51_candidate_v1/full_20241031_once'
     for name in ['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END']:
      old=read(prior/(name+'.json'));new=read(O/'replay_20240913'/(name+'.json'));assert old==new,('PRIOR_PREFIX_MISMATCH',name);checks[name]=len(new)
     save(O/'PRIOR_PREFIX_REPLAY_QA.json',dict(result='PASS',certified_through='2024-09-13',economic_rule_changes=0,exact_records=checks));print('PRIOR_PREFIX_REPLAY_PASS '+json.dumps(checks),flush=True)
    if checkpoint and day(d)=='2024-09-23':"""
assert needle in s;s=s.replace(needle,replacement)
s=s.replace("O/'synthetic_joint.py']:hashed(p)","O/'synthetic_joint.py',O/'FACT_REVISION.json']:hashed(p)")
(N/'engine.py').write_text(s)
contract=(O/'FROZEN_CONTRACT.md').read_text()+'''\n## Fact-only revision v2\nThe original joint51_candidate_v1 engine, freeze and complete-through-2024-09-13 outputs remain unchanged. This revision adds separately reviewed company cash-event facts and evidence only. No signal, queue, capital, cost, CP, protection or exit rule changes are permitted. The prior ten trading days must replay exactly across orders, candidates, CP, daily cash/NAV, holdings, equity events, sector attribution, attempts and pending requests before any later day runs. New complete-through-2024-09-23 checkpoint and final certified prefix stay in this new sibling directory. d_cash, d_source and d_ref are distinct: ownership uses d_cash, frozen source-coordinate bridge uses d_source, and official reference-price fact d_ref is preserved without replacing the source factor.\n'''
(N/'FROZEN_CONTRACT.md').write_text(contract)
revision=dict(kind='FACT_EVIDENCE_ONLY',economic_rule_changes=0,original_directory=str(O),prior_freeze_sha256=sha(O/'FREEZE.json'),prior_engine_sha256=sha(O/'engine.py'),prior_run_output_hashes_sha256=sha(O/'full_20241031_once/OUTPUT_HASHES.json'),reviewed_adapter_inputs={str(p):sha(p) for p in inputs},new_event_keys=[x['sid']+'|'+x['ex_date'] for x in extra],technical_changes=['Append separately reviewed cash-event evidence input','Require exact old ten-day prefix replay before continuing','Write new outputs only in sibling version directory'])
(N/'FACT_REVISION.json').write_text(json.dumps(revision,ensure_ascii=False,indent=2)+'\n');print(N,'events',len(extra))
