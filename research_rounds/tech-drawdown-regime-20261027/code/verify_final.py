from pathlib import Path
from collections import defaultdict
import gzip,json,hashlib
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
def load(p):
 d=defaultdict(list)
 with gzip.open(p,'rt') as f:
  for r in map(json.loads,f):d[r['account']].append(r)
 return d
if __name__=='__main__':
 receipts=[];fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells'];old=load(ROOT/'research_rounds/e0-reclaim-accounts-20261026/OFF/accounts-v2/daily.jsonl.gz');control=load(O/'CONTROL/accounts-v2/daily.jsonl.gz')
 for aid,rs in control.items():
  assert rs==old[aid];f=json.loads((O/'CONTROL/accounts-v2'/f'{aid}.json').read_text())['fills'];r=json.loads((ROOT/'research_rounds/e0-reclaim-accounts-20261026/OFF/accounts-v2'/f'{aid}.json').read_text())['fills'];assert f==r;receipts.append(dict(kind='old_control',account=aid,days=len(rs),fills=len(f)))
 for root in sorted(O.iterdir()):
  if not (root/'accounts-v2').exists():continue
  a=load(root/'accounts-v2/daily.jsonl.gz');b=load(root/'technical/prefix/daily.jsonl.gz');assert json.loads((root/'analysis/accounting.json').read_text())['passed']
  for aid,rs in b.items():
   target=[r for r in a[aid] if r['at'][:10]<='2025-12-31'];assert len(rs)==len(target)
   for x,y in zip(rs,target):
    assert x['at']==y['at']
    for k in fields:assert x[k]==y[k],(root.name,aid,x['at'],k)
   full=json.loads((root/'accounts-v2'/f'{aid}.json').read_text());pre=json.loads((root/'technical/prefix'/f'{aid}.json').read_text());assert pre['fills']==[r for r in full['fills'] if r['at'][:10]<='2025-12-31'];receipts.append(dict(kind='prefix',version=root.name,account=aid,days=len(rs),fills=len(pre['fills'])))
 for fn in ['economic-freeze.json','round2-freeze.json','shadow-freeze.json','shock-freeze.json']:
  for path,h in json.loads((O/fn).read_text()).items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
 (O/'account-validation-final.json').write_text(json.dumps({'passed':True,'receipts':receipts,'frozen_unchanged':True},indent=2));print('account and freeze checks',len(receipts))
