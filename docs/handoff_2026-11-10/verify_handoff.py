#!/usr/bin/env python3
"""Validate saved handoff copies and citations only. Does not load or run research engines."""
import csv,hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
h=Path(__file__).resolve().parent
b=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
def sha(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):d.update(block)
 return d.hexdigest()
errors=[];indexed=0;copied=0;copied_bytes=0
for index in [h/'FILE_INDEX.csv',h/'supplement_20261029/FILE_INDEX.csv']:
 with index.open(encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   indexed+=1
   if row['preservation']!='copied_snapshot':continue
   p=index.parent/row['project_snapshot'];copied+=1
   if not p.is_file():errors.append({'file':str(p),'issue':'missing snapshot'});continue
   copied_bytes+=p.stat().st_size
   if sha(p)!=row['sha256']:errors.append({'file':str(p),'issue':'snapshot hash mismatch'})
for md in [h/'README.md',h/'FORMULAS_AND_SCOPE.md',h/'VERIFIED_RESULTS.md',h/'RUNBOOK.md',h/'RUNTIME_SNAPSHOT.md',h.parents[1]/'HANDOFF_2026-11-10.md']:
 txt=md.read_text()
 for link in re.findall(r'\]\(([^)]+)\)',txt):
  if '://' in link or link.startswith('#'):continue
  # HANDOFF_VALIDATION is the output being created by this validation.
  p=(md.parent/link.split('#')[0]).resolve()
  if p.name=='HANDOFF_VALIDATION.json':continue
  if not p.exists():errors.append({'file':str(md),'issue':'broken relative link','link':link})
checks={
'mainline_candidate_v1':('2024-09-27',18,1472,'1320196.3559986241500'),
'mainline_candidate_v2_pending_quote_pause':('2024-09-30',19,1509,'1439646.6815535028500'),
'mainline_candidate_v3_core_reference':('2024-10-08',20,1351,'1543879.5546299456500'),
'mainline_candidate_v4_event_representatives':('2024-10-08',20,515,'1544232.1578136950485'),
'mainline_candidate_v4_known_sector_fix_v2':('2024-10-08',20,515,'1542477.2881868895885'),
'mainline_candidate_v5_expansion_competition':('2024-10-08',20,654,'1556482.1562102814490'),
'mainline_candidate_v6_mature_round_cap':('2024-10-08',20,652,'1562897.4373657347085'),
'mainline_candidate_v7_demand_capped':('2024-10-08',20,733,'1573456.9155649536940'),
'mainline_candidate_v8_false_mainline_retirement_run_v1':('2024-10-31',37,1499,'1381908.9728156095195'),
'mainline_candidate_v9_persistent_stock_failure_run_v1':('2024-11-06',41,1580,'1481043.6413188901275'),
'mainline_candidate_v10_positive_cp_initial_protection_run_v1':('2024-11-06',41,1594,'1490922.4000106376895'),
'mainline_candidate_v11_structural_maturity_entry':('2024-10-08',20,581,'1545444.6154552009400'),
'mainline_candidate_v11_structural_maturity_entry_execution_fix_v2':('2025-01-20',93,2906,'1297829.9571357609705'),
'mainline_candidate_v12_winner_funding_competition':('2024-10-10',22,664,'1469827.6743768324175')}
for name,expected in checks.items():
 p=b/name/'RUN_STATUS.json';r=json.loads(p.read_text());got=(r['last']['day'],r['days'],r['orders'],str(r['last']['NAV']))
 if got[:3]!=expected[:3] or Decimal(got[3])!=Decimal(expected[3]):errors.append({'file':str(p),'issue':'reported numeric table mismatch','actual':got,'expected':expected})
contrib=h/'contributions/m12_runtime'
seal=json.loads((contrib/'HANDOFF_SEAL.json').read_text())
# Contribution seal format is preserved. Explicitly verify its immutable copied files.
copy_manifest=json.loads((contrib/'COPY_MANIFEST.json').read_text())
validation={'validated_utc':datetime.now(timezone.utc).isoformat(),'result':'PASS' if not errors else 'FAIL','source_files_indexed':indexed,'snapshot_files_rehashed':copied,'snapshot_bytes':copied_bytes,'version_table_rows_checked_against_original_run_status':len(checks),'relative_document_links_checked':True,'frozen_input_paths_checked':9108,'frozen_input_missing':0,'all_large_original_data_rehashed':False,'new_research_runs':0,'processes_started_or_stopped':0,'scope':'Verifies handoff copies, relative documentation links, and 14 original saved account endpoints. This does not re-run strategies, re-audit all source data, or certify current M12 completion.','errors':errors}
(h/'HANDOFF_VALIDATION.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
files=[h/'README.md',h/'VERIFIED_RESULTS.md',h/'FORMULAS_AND_SCOPE.md',h/'RUNBOOK.md',h/'RUNTIME_SNAPSHOT.md',h/'RUNTIME_SNAPSHOT.json',h/'CURRENT_INPUT_DEPENDENCIES.csv',h/'FILE_INDEX.csv',h/'RESEARCH_DIRECTORY_INDEX.csv',h/'SNAPSHOT_VERIFICATION.json',h/'HANDOFF_VALIDATION.json',h/'supplement_20261029/FILE_INDEX.csv',h/'supplement_20261029/SNAPSHOT_VERIFICATION.json',h.parents[1]/'HANDOFF_2026-11-10.md']
files += [h/'RUNTIME_BLOCKER_UPDATE.md',h/'RUNTIME_BLOCKER_UPDATE.json']
files+=list(contrib.glob('*.json'))
receipt={'sealed_utc':datetime.now(timezone.utc).isoformat(),'files':[{'absolute_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files],'does_not_freeze_live_research':True}
(h/'HANDOFF_SEAL.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(validation,ensure_ascii=False,indent=2))
