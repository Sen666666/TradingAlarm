"""Audit frozen score arithmetic and compare old orders in same Sstar numeric set."""
from pathlib import Path
from fractions import Fraction
import hashlib,json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
d=pd.read_parquet(O/'ALL5127_STATIC_DIAGNOSTIC_WITH_REASONS.parquet')
r=d[d.Sstar_rankable].copy();audit=[]
for (day,sector),g in r.groupby(['date','sector_id_static']):
 n=len(g);assert g.percentile_N.eq(n).all()
 num=np.zeros(n,dtype=np.int64)
 for x,tag,w in [('PVR_cache_score','PVR',4),('RS_stock20','RS_stock20',3),('drawdown20_prior_high','drawdown20',2),('amount_change','amount_change',1)]:
  raw=g[x].to_numpy();mid=[]
  for v in raw:mid.append(2*int((raw<v).sum())+int((raw==v).sum()))
  mid=np.array(mid,dtype=np.int64)
  assert np.array_equal(mid,g['midrank_numerator_'+tag].to_numpy())
  assert int(mid.sum())==n*n
  assert np.array_equal(mid/(2*n),g['p_'+tag].to_numpy())
  num+=w*mid
 assert np.array_equal(num,g.Sstar_numerator.to_numpy())
 assert g.Sstar_denominator.eq(20*n).all()
 assert int(num.sum())==10*n*n  # Every within-industry group has exact mean S=.5.
 audit.append({'date':day,'sector_id_static':sector,'N':n,'score_numerator_sum':int(num.sum()),'exact_group_mean_score':'1/2','all_four_midpercentiles_exact':True})
r['same_Sstar_pool_original_H1_order1']=np.nan;r['same_Sstar_pool_true_PVR_numeric_order1']=np.nan
for date,g in r.groupby('date'):
 h=g.sort_values(['original_H1_rank0','sid']);r.loc[h.index,'same_Sstar_pool_original_H1_order1']=np.arange(1,len(g)+1)
 p=g.sort_values(['PVR_cache_score','original_H1_rank0','sid'],ascending=[False,True,True]);r.loc[p.index,'same_Sstar_pool_true_PVR_numeric_order1']=np.arange(1,len(g)+1)
r['comparison_scope']='Same_U_source_Q_four-known_numeric_set; PVR_numeric_order_is_not_original_native_pending_priority'
r.to_parquet(O/'SAME_SSTAR_POOL_OLD_H1_PVR_COMPARISON.parquet',index=False);r.to_csv(O/'SAME_SSTAR_POOL_OLD_H1_PVR_COMPARISON.csv',index=False)
f=pd.read_parquet(O/'FOCAL_ORIGINAL_AND_SSTAR.parquet');f=f.merge(r[['sid','date','same_Sstar_pool_original_H1_order1','same_Sstar_pool_true_PVR_numeric_order1']],on=['sid','date'],how='left',validate='one_to_one')
f.to_csv(O/'FOCAL_SAME_POOL_OLD_COMPARISON.csv',index=False)
summary={'scoreable_rows':len(r),'industry_date_groups':len(audit),'all_exact_component_midrank_and_integer_score':True,'formal_PIT_Sstar_all_unknown':bool(d.Sstar_formal_PIT.isna().all()),
 'first_single_candidate_score_check':bool(r.loc[r.percentile_N.eq(1),'Sstar_static'].eq(.5).all()),
 'old_H1_PVR_comparison_uses_same_rankable_set':True,'no_new_score_variants_or_accounts_or_returns':True,'group_checks':audit}
(O/'INTEGER_SCORE_AND_SAME_POOL_AUDIT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(f[f.date=='2026-01-15'][['sid','name_static','Sstar_static','same_Sstar_pool_original_H1_order1','same_Sstar_pool_true_PVR_numeric_order1','Sstar_global_numeric_inventory_order1']].to_string(index=False))
print(json.dumps({k:v for k,v in summary.items() if k!='group_checks'},indent=2))
