"""Descriptive rank overlap in the already-frozen Sstar peer sets, no new rule."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent
src=P/'ALL5127_STATIC_DIAGNOSTIC_WITH_REASONS.parquet'
d=pd.read_parquet(src);d=d[d.Sstar_rankable].copy();assert len(d)==1269
def corr(a,b,rank=False):
 a=pd.Series(a,dtype=float);b=pd.Series(b,dtype=float)
 if len(a)<3:return None,'N_LT3'
 if a.nunique()<2 or b.nunique()<2:return None,'CONSTANT_RANK'
 if rank:a=a.rank(method='average');b=b.rank(method='average')
 z=float(np.corrcoef(a.to_numpy(),b.to_numpy())[0,1]);return min(1.,max(-1.,z)),'DEFINED_DESCRIPTIVE_ONLY'
rows=[]
for (date,sector),g in d.groupby(['date','sector_id_static']):
 n=len(g);assert g.percentile_N.eq(n).all()
 rho,status=corr(g.p_PVR,g.p_RS_stock20,True)
 rows.append({'date':date,'sector_id_static':sector,'industry_static':g.industry_static.iloc[0],
  'N_frozen_same_peer_set':n,'PVR_rank_unique':g.p_PVR.nunique(),'RS20_rank_unique':g.p_RS_stock20.nunique(),
  'spearman_pPVR_pRS20':rho,'status':status,
  'scope':'same_U_t__original_Q_signal_legal__all_four_Sstar_inputs_known__unique_sid',
  'formal_historical_membership_PIT_verified':False})
r=pd.DataFrame(rows);r.to_csv(O/'BY_DATE_INDUSTRY_SPEARMAN.csv',index=False);r.to_parquet(O/'BY_DATE_INDUSTRY_SPEARMAN.parquet',index=False)
pooled=[]
for date,g in d.groupby('date'):
 sub=r[r.date==date];p,ps=corr(g.p_PVR,g.p_RS_stock20,False);s,ss=corr(g.p_PVR,g.p_RS_stock20,True)
 valid_sectors=set(sub.loc[sub.status.eq('DEFINED_DESCRIPTIVE_ONLY'),'sector_id_static']);z=g[g.sector_id_static.isin(valid_sectors)]
 pv,pvs=corr(z.p_PVR,z.p_RS_stock20,False)
 pooled.append({'date':date,'N_all_frozen_scoreable_stocks':len(g),'industry_groups':len(sub),'groups_defined_Nge3_nonconstant':len(valid_sectors),
  'groups_N_lt3':int(sub.status.eq('N_LT3').sum()),'groups_constant_rank_Nge3':int(sub.status.eq('CONSTANT_RANK').sum()),
  'pooled_Pearson_of_within_industry_midpercentiles':p,'pooled_Pearson_status':ps,
  'pooled_Spearman_of_within_industry_midpercentiles':s,'pooled_Spearman_status':ss,
  'N_stocks_in_defined_industry_groups':len(z),'pooled_midpercentile_Pearson_only_defined_groups':pv,'pooled_defined_groups_status':pvs,
  'weighting':'one stockdate one row; industry sizes differ; this is not mean industry rho or independent sample inference',
  'note':'Pooled Spearman reranks all within-industry percentile values together; pooled Pearson directly correlates those normalized within-industry ranks.'})
q=pd.DataFrame(pooled);q.to_csv(O/'DAILY_POOLED_WITHIN_PERCENTILES.csv',index=False)
summary={'source_rows':len(d),'date_industry_groups':len(r),'defined_group_correlations':int(r.spearman_pPVR_pRS20.notna().sum()),
 'unknown_N_lt3':int(r.status.eq('N_LT3').sum()),'unknown_constant_rank_Nge3':int(r.status.eq('CONSTANT_RANK').sum()),
 'all_source_peer_sets_unchanged':True,'new_selection_thresholds_or_weights_or_accounts_or_returns':0}
(O/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(O/'SOURCE_SHA256.json').write_text(json.dumps({str(src.resolve()):hashlib.sha256(src.read_bytes()).hexdigest(),str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
print(q.drop(columns=['weighting','note']).to_string(index=False));print(json.dumps(summary,ensure_ascii=False));print(r[r.sector_id_static.eq('URFI881121')].to_string(index=False))
