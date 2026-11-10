from driver import *
from collections import defaultdict
import gzip

def rows(path):
 out=defaultdict(list)
 with gzip.open(path,'rt') as f:
  for line in f:
   r=json.loads(line);out[r['account']].append(r)
 return out
if __name__=='__main__':
 receipts=[];fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
 control=rows(O/'ON/accounts-v2/daily.jsonl.gz');old=rows(BASE/'accounts-v2/daily.jsonl.gz')
 for aid,rs in control.items():
  assert len(rs)==len(old[aid])
  for a,b in zip(rs,old[aid]):
   assert a['at']==b['at']
   for k in fields:assert a[k]==b[k],(aid,a['at'],k)
  x=json.loads((O/'ON/accounts-v2'/f'{aid}.json').read_text());y=json.loads((BASE/'accounts-v2'/f'{aid}.json').read_text());assert x['fills']==y['fills'];receipts.append(dict(kind='old_control',account=aid,rows=len(rs),fills=len(x['fills'])))
 for v in ['ON','OFF']:
  full=rows(O/v/'accounts-v2/daily.jsonl.gz');pre=rows(O/v/'technical/prefix/daily.jsonl.gz')
  for aid,rs in pre.items():
   xs=[x for x in full[aid] if x['at'][:10]<='2024-12-31'];assert len(rs)==len(xs)
   for a,b in zip(rs,xs):
    assert a['at']==b['at']
    for k in fields:assert a[k]==b[k],(v,aid,a['at'],k)
   x=json.loads((O/v/'technical/prefix'/f'{aid}.json').read_text());y=json.loads((O/v/'accounts-v2'/f'{aid}.json').read_text());ys=[f for f in y['fills'] if f['at'][:10]<='2024-12-31'];assert x['fills']==ys;receipts.append(dict(kind=v+'_account_prefix',account=aid,rows=len(rs),fills=len(ys)))
 (O/'verification.json').write_text(json.dumps(dict(passed=True,receipts=receipts),indent=2)+'\n');print('passed',len(receipts))
