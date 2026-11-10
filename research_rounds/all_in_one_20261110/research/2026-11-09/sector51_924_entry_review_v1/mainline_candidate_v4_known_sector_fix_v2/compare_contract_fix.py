from pathlib import Path
import json,collections
from decimal import Decimal as D
import pandas as pd
O=Path(__file__).resolve().parent;old=O.parent/'mainline_candidate_v4_event_representatives/once_20241008';new=O/'once_20241008';read=lambda p:json.loads(p.read_text());results={}
for p in old.glob('*.json'):
 n=new/p.name
 if not n.exists() or p.name=='OUTPUT_HASHES.json':continue
 a=read(p);b=read(n);equal=a==b;details=[]
 if not equal and isinstance(a,list) and isinstance(b,list):
  for i,(x,y) in enumerate(zip(a,b)):
   if x!=y:
    if len(details)<5:details.append({'index':i,'old':x,'fixed':y})
  count=sum(x!=y for x,y in zip(a,b))+abs(len(a)-len(b))
 else:count=0 if equal else 1
 results[p.name]={'equal_exact_ordered':equal,'old_count':len(a) if hasattr(a,'__len__') else None,'fixed_count':len(b) if hasattr(b,'__len__') else None,'different_positions':count,'first_differences':details}
(O/'FIX_ALL_FAMILY_COMPARISON.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));rows=[];b={(r['day'],r['sector51']):r for r in read(old/'REFERENCE_DAILY.json')}
for r in read(new/'REFERENCE_DAILY.json'):
 a=b[(r['day'],r['sector51'])];ks=['fixed','T','buy_envelope','budget_before_event','event_reserve_total','budget','stress','outside_fixed'];delta={k:str(D(r[k])-D(a[k])) for k in ks}
 if any(D(v)!=0 for v in delta.values()):rows.append({'day':r['day'],'sector51':r['sector51'],**delta})
(O/'FIX_REFERENCE_DIFFERENCES.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));pd.DataFrame(rows).to_csv(O/'FIX_REFERENCE_DIFFERENCES.csv',index=False)
print(json.dumps({'all_family_results':{n:{k:v for k,v in r.items() if k!='first_differences'} for n,r in results.items()},'reference_different_rows':len(rows)},ensure_ascii=False))
