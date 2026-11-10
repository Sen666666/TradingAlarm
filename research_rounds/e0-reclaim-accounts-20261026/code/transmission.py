from pathlib import Path
import gzip,json
from collections import Counter
P=Path(__file__).resolve().parents[1]
def load(v,file):
 with gzip.open(P/v/'accounts-v2'/file,'rt') as f:return {(r['account'],r['at']):r for r in map(json.loads,f)}
a=load('ON','decisions.jsonl.gz');b=load('OFF','decisions.jsonl.gz');diff=[]
for k,x in a.items():
 y=b[k]
 assert x['accepted']==y['accepted'];assert x['exits']==y['exits']
 if x!=y:diff.append(dict(account=k[0],at=k[1],on_only=sorted(set(x['eligible'])-set(y['eligible'])),off_only=sorted(set(y['eligible'])-set(x['eligible'])),on_accepted=x['accepted'],off_accepted=y['accepted'],on_selected=x['selected'],off_selected=y['selected'],on_occupancy=x['occupancy'],off_occupancy=y['occupancy']))
(P/'decision-differences.json').write_text(json.dumps(diff,indent=2,ensure_ascii=False)+'\n');receipts=[]
da=load('ON','daily.jsonl.gz');db=load('OFF','daily.jsonl.gz');assert da==db
for aid in sorted({k[0] for k in a}):
 x=json.loads((P/'ON/accounts-v2'/f'{aid}.json').read_text());y=json.loads((P/'OFF/accounts-v2'/f'{aid}.json').read_text());assert x['fills']==y['fills'];assert x['audit_log']==y['audit_log'];q=[r for r in diff if r['account']==aid]
 receipts.append(dict(account=aid,different_decision_days=len(q),on_only_candidate_days=sum(len(r['on_only']) for r in q),off_only_candidate_days=sum(len(r['off_only']) for r in q),post_decision_occupancy=dict(Counter(len(r['on_occupancy']) for r in q)),fills=len(x['fills']),fills_audit_and_daily_identical=True))
(P/'transmission-verified.json').write_text(json.dumps(dict(passed=True,receipts=receipts),indent=2)+'\n');print('All paired fills, audit logs and entire daily records identical; eligibility differs.')
