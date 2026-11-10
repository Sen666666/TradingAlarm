from pathlib import Path
import json,gzip
from collections import defaultdict
O=Path(__file__).resolve().parents[1];R=O.parents[1]
def load(p):
 d=defaultdict(list)
 with gzip.open(p,'rt') as f:
  for r in map(json.loads,f):d[r['account']].append(r)
 return d
if __name__=='__main__':
 receipts=[];fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
 control=load(O/'CONTROL/accounts-v2/daily.jsonl.gz');refroot=R/'research_rounds/e0-reclaim-accounts-20261026/OFF/accounts-v2';ref=load(refroot/'daily.jsonl.gz')
 for aid,rs in control.items():
  assert rs==ref[aid];a=json.loads((O/'CONTROL/accounts-v2'/f'{aid}.json').read_text());b=json.loads((refroot/f'{aid}.json').read_text());assert a['fills']==b['fills'];receipts.append(dict(kind='old_control',account=aid,rows=len(rs),fills=len(a['fills'])))
 for v in ['R1','R2','R3','P1']:
  for pol in ['H','C']:
   root=O/v/pol;a=load(root/'accounts-v2/daily.jsonl.gz');b=load(root/'technical/prefix/daily.jsonl.gz')
   for aid,rs in b.items():
    target=[r for r in a[aid] if r['at'][:10]<='2024-12-31'];assert len(rs)==len(target)
    for x,y in zip(rs,target):
     assert x['at']==y['at']
     for k in fields:assert x[k]==y[k],(v,pol,aid,x['at'],k)
    full=json.loads((root/'accounts-v2'/f'{aid}.json').read_text());pre=json.loads((root/'technical/prefix'/f'{aid}.json').read_text());fills=[r for r in full['fills'] if r['at'][:10]<='2024-12-31'];assert pre['fills']==fills;receipts.append(dict(kind=v+'-'+pol,account=aid,rows=len(rs),fills=len(fills)))
 # R3 only changes cooling policy; H participation must equal R2.
 a=load(O/'R2/H/accounts-v2/daily.jsonl.gz');b=load(O/'R3/H/accounts-v2/daily.jsonl.gz');assert a==b
 (O/'account-verification.json').write_text(json.dumps(dict(passed=True,receipts=receipts,r2_r3_h_exact=True),indent=2)+'\n');print('verified controls and prefixes',len(receipts))
