"""JOINT/R/P minus BASE grouping of already measured actual wealth changes."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import csv,hashlib,json
getcontext().prec=65
HERE=Path(__file__).resolve().parent;P=HERE/'results_v1';SRC={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def save(n,x):
 with (P/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
matrix=read(P/'FIXED_PERIOD_PERFORMANCE.json');lookup={(x['arm'],x['period']):x for x in matrix};rows=[]
for period in [x['period'] for x in matrix if x['arm']=='BASELINE']:
 base=read(P/f'BASELINE_{period}_DETAIL.json')
 for arm in ['R_ONLY','P_ONLY','JOINT']:
  cand=read(P/f'{arm}_{period}_DETAIL.json');details={};summaries={};target=D(lookup[arm,period]['net_wealth_change'])-D(lookup['BASELINE',period]['net_wealth_change'])
  for dimension in ['stock','sector','day','week','month']:
   b={x['group']:x for x in base['group_rows'][dimension]};a={x['group']:x for x in cand['group_rows'][dimension]};rr=[]
   for key in sorted(b.keys()|a.keys()):
    bb=b.get(key,{});aa=a.get(key,{});r=dict(group=key,baseline_wealth=D(bb.get('wealth','0')),candidate_wealth=D(aa.get('wealth','0')))
    for k in ['name','industry','sector']:
     if k in aa or k in bb:r[k]=aa.get(k,bb.get(k))
    r['difference']=r['candidate_wealth']-r['baseline_wealth'];rr.append(r)
   rr.sort(key=lambda x:x['difference'],reverse=True);pos=[x for x in rr if x['difference']>0];negative=sum((min(Z,x['difference']) for x in rr),Z);positive=sum((x['difference'] for x in pos),Z);net=positive+negative
   assert abs(net-target)<D('0.000001'),(arm,period,dimension,str(net),str(target))
   s=dict(arm=arm,period=period,grouping=dimension,groups=len(rr),positive_groups=len(pos),positive_difference=positive,negative_difference=negative,net_difference=net,
    top={str(n):dict(groups=[x['group'] for x in pos[:n]],positive_difference=sum((x['difference'] for x in pos[:n]),Z),share_of_all_positive_differences=None if not positive else sum((x['difference'] for x in pos[:n]),Z)/positive,
      descriptive_net_after_subtracting_these_positive_differences=net-sum((x['difference'] for x in pos[:n]),Z)) for n in [1,5,10]},
    positive_share_HHI=None if not positive else sum(((x['difference']/positive)**2 for x in pos),Z),
    caveat='Difference of two full actual account paths; period starting NAV/inventory, sizes, selection, realized cash reuse and ACT can differ. Neither a same-hold causal effect nor investable stock/month exclusion.')
   summaries[dimension]=s;details[dimension]=rr;rows.append(s)
  save(f'{arm}_{period}_INCREMENTAL_GROUPS.json',dict(summary=summaries,groups=details))
save('INCREMENTAL_CONCENTRATION_SUMMARY.json',rows)
with (P/'INCREMENTAL_CONCENTRATION_SUMMARY.csv').open('x',newline='') as f:
 fields=['arm','period','grouping','positive_difference','negative_difference','net_difference']+[f'top{n}_{z}' for n in [1,5,10] for z in ['share_of_positive_difference','descriptive_remaining_net']]
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in rows:
  v={k:r[k] for k in fields if k in r}
  for n in [1,5,10]:v[f'top{n}_share_of_positive_difference']=r['top'][str(n)]['share_of_all_positive_differences'];v[f'top{n}_descriptive_remaining_net']=r['top'][str(n)]['descriptive_net_after_subtracting_these_positive_differences']
  w.writerow(v)
SRC[str(Path(__file__).resolve())]=sha(__file__);save('INCREMENTAL_SOURCE_SHA256.json',SRC)
save('INCREMENTAL_VALIDATION.json',dict(status='PASS_270_DIMENSION_BRIDGES',existing_paths_only=True,new_accounts=0,fixed_periods=18,candidate_arms=3,dimensions=5,all_group_differences_equal_actual_period_account_difference=True))
print('INCREMENTAL_COMPLETE',len(rows),'dimension bridges')
