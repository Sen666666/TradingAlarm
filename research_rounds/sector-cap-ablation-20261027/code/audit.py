from study import *
import gzip
from decimal import Decimal as D

def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]

FIELDS=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']

def run_audit(version,stage):
 root=O/version;A.CORE=PRIOR/'input';A.PREP=Path(read(PRIOR/'input.json')['snapshot']['path']);A.HERE=root
 if version.endswith('_NC'):
  src=inspect.getsource(A.old.audit_account);needle="(1 if aid.startswith('S1') else 3)";assert src.count(needle)==1;src=src.replace(needle,"(1 if aid.startswith('S1') else 6)");scope=dict(A.old.__dict__);exec(src,scope);A.old.audit_account=scope['audit_account']
 if stage=='control':
  src=inspect.getsource(A.main).replace("HERE/('technical/short-v2' if stage=='short' else 'accounts-v2')","HERE/'technical/control'").replace("HERE/('technical/short-analysis' if stage=='short' else 'analysis')","HERE/'technical/control-analysis'");scope=dict(A.__dict__);exec(src,scope);fn=scope['main']
 else:fn=A.main
 fn('short' if stage=='short' else 'full')

def admission():
 assert read(O/'synthetic.json')['passed'];receipts=[]
 for v in ['RS','PVR','RS_NC','PVR_NC']:
  a=read(O/v/'technical/short-analysis/accounting.json');assert a['passed'];receipts.append(a)
 for v in ['RS','PVR']:
  ref={(r['account'],r['at']):r for r in rows(PRIOR/v/'accounts-v2/daily.jsonl.gz')}
  for r in rows(O/v/'technical/short-v2/daily.jsonl.gz'):
   for k in FIELDS:assert r[k]==ref[r['account'],r['at']][k],(v,r['at'],k)
  for sc in ['base','cost2','delay1']:
   aid='I__S0_'+sc;assert read(O/v/'technical/short-v2'/f'{aid}.json')['fills']==[r for r in read(PRIOR/v/'accounts-v2'/f'{aid}.json')['fills'] if r['at'][:10]<='2024-06-28']
 save(O/'admission.json',{'passed':True,'short_paths':12,'original_controls':6,'audits':receipts})

if __name__=='__main__':admission() if sys.argv[1]=='admission' else run_audit(sys.argv[1],sys.argv[2])
