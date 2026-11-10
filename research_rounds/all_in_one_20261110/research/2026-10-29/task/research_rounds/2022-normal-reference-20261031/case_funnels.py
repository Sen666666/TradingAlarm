"""Read only existing three fixed sector opportunity/funding logs."""
from pathlib import Path
import json,gzip,collections
O=Path(__file__).resolve().parent
META=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text())
TARGET={'URFI881160','URFI881158','URFI881105'}
def stream(p):
 with gzip.open(p,'rt') as f:
  for row in f:yield json.loads(row)
for ref in ['B3','B_diag']:
 p=O/'runs'/ref;dest=O/'analysis'/ref/'CASE_FUNNELS.json'
 if not (p/'DONE.json').exists() or dest.exists():continue
 opp=collections.defaultdict(list);fund=collections.defaultdict(list)
 for r in stream(p/'pair/opportunities.jsonl.gz'):
  if r['sector'] in TARGET:opp[r['sector']].append(r)
 for r in stream(p/'pair/funding.jsonl.gz'):
  g=META[r['sid']]['sector_id']
  if g in TARGET:fund[g].append(r)
 with gzip.open(p/'pair/B.json.gz','rt') as f:a=json.load(f)
 result=[]
 for g in sorted(TARGET):
  o=opp[g];u=fund[g];fresh={r['CP1_id'] for r in o if r['CP1_id'] and r['mobile_Q'] is True};reserved={r['CP1_id'] for r in u if r['role']=='mobile' and r['result']=='reserved' and r.get('CP1_id')};filled={r['CP1_id'] for r in a['journal'] if r['kind']=='real_buy_fill' and r.get('CP1_id') in fresh}
  result.append(dict(sector=g,snapshot_members=[s for s,v in META.items() if v['sector_id']==g],original_core_Q_true_stockdays=sum(r['core_Q'] is True for r in o),fresh_CP1_Q_true_receipts=len(fresh),fresh_CP1_reserved=len(reserved&fresh),fresh_CP1_with_fill=len(filled),fresh_CP1_Q_unknown=sum(bool(r['CP1_id']) and r['mobile_Q'] is None for r in o),first_core_Q_true=min((r['day'] for r in o if r['core_Q'] is True),default=None),first_mobile_Q_true=min((r['day'] for r in o if r['CP1_id'] and r['mobile_Q'] is True),default=None),opportunity_barriers=dict(collections.Counter(v for r in o for v in r['barriers'])),role_funding_counts={str(k):v for k,v in collections.Counter((r['role'],r['result']) for r in u).items()},counts_not_independent_opportunities=True,joint_resource_reasons_not_exclusive=True))
 dest.parent.mkdir(exist_ok=True,parents=True);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(ref,[(r['sector'],len(r['snapshot_members']),r['fresh_CP1_Q_true_receipts'],r['fresh_CP1_with_fill']) for r in result])
