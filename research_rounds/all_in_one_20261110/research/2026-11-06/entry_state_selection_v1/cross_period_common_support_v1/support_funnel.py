"""Support accounting at the original frozen constraints; no new matching or outcomes."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal=json.loads((O/'FEATURE_MATCH_SEAL.json').read_text())
for p,h in seal.items():assert sha(O/p)==h
p=json.loads((O/'PROTOCOL_V1.json').read_text())
a=pd.read_csv(O/'FEATURES_SCALED_PRELABEL.csv');g=a[a.feature_known].copy()
keys=p['exact_match'];zs=[c+'_z' for c in p['features']]
records=[];viol=[];edge_counts={};common_members=set()
for key,z in g.groupby(keys,dropna=False,sort=True):
 period_members={per:z[z.period.eq(per)] for per in ['Q1','Q3','AUTUMN']}
 if all(len(v)>0 for v in period_members.values()):common_members.update(z.round_id)
 aa=period_members['Q1']
 for ix,row in aa.iterrows():
  rec={'round_id':row.round_id,'exact_Q3':len(period_members['Q3']),'exact_AUTUMN':len(period_members['AUTUMN'])}
  for per in ['Q3','AUTUMN']:
   b=period_members[per];dx=np.abs(b[zs].to_numpy(float)-row[zs].to_numpy(float))
   if len(b):
    mx=dx.max(axis=1);rms=np.sqrt(np.mean(dx*dx,axis=1))
    rec[per+'_within_caliper']=int((mx<=1).sum());rec[per+'_nearest_Linf']=float(mx.min());rec[per+'_nearest_RMS']=float(rms.min())
    for j,f in enumerate(p['features']):viol.append(dict(comparison=per+'-Q1',feature=f,pairs=len(b),fails=int((dx[:,j]>1).sum())))
   else:rec[per+'_within_caliper']=0;rec[per+'_nearest_Linf']=None;rec[per+'_nearest_RMS']=None
  records.append(rec)
f=pd.DataFrame(records);f['exact_counterparts_both']=f.exact_Q3.gt(0)&f.exact_AUTUMN.gt(0);f['within_caliper_both']=f.Q3_within_caliper.gt(0)&f.AUTUMN_within_caliper.gt(0)
f.to_csv(O/'ANCHOR_SUPPORT_FUNNEL.csv',index=False)
v=pd.DataFrame(viol).groupby(['comparison','feature'])[['pairs','fails']].sum().reset_index();v['fail_fraction']=v.fails/v.pairs
v.to_csv(O/'FIXED_CALIPER_VIOLATIONS.csv',index=False)
summary={'Q1_complete':len(f),'Q1_exact_Q3_counterpart':int(f.exact_Q3.gt(0).sum()),'Q1_exact_autumn_counterpart':int(f.exact_AUTUMN.gt(0).sum()),'Q1_exact_both':int(f.exact_counterparts_both.sum()),'Q1_within_Q3_caliper':int(f.Q3_within_caliper.gt(0).sum()),'Q1_within_autumn_caliper':int(f.AUTUMN_within_caliper.gt(0).sum()),'Q1_within_both_anchor_calipers':int(f.within_caliper_both.sum()),'exact_three_period_stratum_members':g[g.round_id.isin(common_members)].groupby('period').size().to_dict(),'new_thresholds':0,'new_matches':0,'outcomes_read':False,'warning':'Violations overlap and are diagnostics only, not feature-deletion ablations or recommendations to relax calipers.'}
(O/'SUPPORT_FUNNEL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
for p,h in seal.items():assert sha(O/p)==h
print(json.dumps(summary,ensure_ascii=False))
