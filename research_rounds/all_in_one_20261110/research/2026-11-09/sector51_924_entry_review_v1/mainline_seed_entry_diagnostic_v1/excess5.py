from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,csv
O=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1/mainline_seed_entry_diagnostic_v1')
r=json.loads((O/'FILLED_SEED_CLASSIFICATION.json').read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def tag(x):
 e=x.get('stock_excess5')
 return 'UNKNOWN' if e is None else 'POSITIVE' if D(e)>0 else 'NEGATIVE' if D(e)<0 else 'ZERO'
for x in r:x['excess5_sign']=tag(x)
out=[]
for name,rs in [('ALL_MATURE',[x for x in r if x['phase']=='MATURE']),('NEW_MATURE_AFTER_1106',[x for x in r if x['phase']=='MATURE' and x['seed_day']>'2024-11-06']),('ACTUAL_0924_MATURE',[x for x in r if x['phase']=='MATURE' and x['seed_day']=='2024-09-24'])]:
 for sign in ['POSITIVE','ZERO','NEGATIVE','UNKNOWN']:
  aa=[x for x in rs if tag(x)==sign]
  for state in ['ALL','CLOSED','OPEN']:
   a=[x for x in aa if state=='ALL' or (not x['final_qty'])==(state=='CLOSED')]
   out.append(dict(cohort=name,sign=sign,state=state,n=len(a),net=sum((D(x['net']) for x in a),D(0)),gross_losses=-sum((min(D(0),D(x['net'])) for x in a),D(0)),gross_gains=sum((max(D(0),D(x['net'])) for x in a),D(0)),losing=sum(D(x['net'])<0 for x in a),positive=sum(D(x['net'])>0 for x in a),seed_cost=sum((D(x['seed_cost']) for x in a),D(0)),top_winners=[{k:x[k] for k in ['round_id','name','sector51','plan_day','seed_day','stock_excess5','net','add_count']} for x in sorted(a,key=lambda x:D(x['net']),reverse=True)[:5]]))
save('EXCESS5_SIGN_SUMMARY',out);save('EXCESS5_FILLED_CLASSIFICATION',r)
print(json.dumps([x for x in out if x['state']=='ALL'],ensure_ascii=False,default=str))
