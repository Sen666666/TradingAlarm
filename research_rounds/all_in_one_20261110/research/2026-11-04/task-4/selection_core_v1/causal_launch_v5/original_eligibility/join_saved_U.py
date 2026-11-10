"""Join already-saved U masks to already-extracted original facts. No source feature calculation."""
from pathlib import Path
import hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent
maskpath=O.parent/'burst_raw/U_T_MASK_ALL_FIXED_DATES.parquet'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=pd.read_parquet(maskpath);assert not m.duplicated(['date','sid']).any()
s=pd.read_parquet(O/'STATIC_MEMBERS_ORIGINAL_STOCK_FACTS.parquet')
a=pd.read_parquet(O/'ORIGINAL_STOCK_FACTS_SECTOR_AGGREGATES.parquet')
f=s.merge(m[['date','sid','sector_id_static','qualified_U_t']],on=['date','sid','sector_id_static'],how='left',validate='many_to_one')
assert len(f)==len(s)and f.qualified_U_t.notna().all()
measures=['e0_ready','e0_target','i_target','i_buy_exact_field','i_buy_original_daily_event','g_ready','g_fresh_up','g_acute_down']
for i,r in a.iterrows():
 g=f.loc[f.case_id.eq(r.case_id)&f.date.eq(r.date)&f.qualified_U_t.eq(True)]
 assert len(g)==r.U_N_from_saved_industry_aggregate,(r.case_id,r.date,len(g),r.U_N_from_saved_industry_aggregate)
 a.at[i,'U_inside_original_E0_I_counts_status']='KNOWN_FROM_SAME_PASS_SAVED_U_MASK'
 a.at[i,'U_facts_exact_date_N']=int(g.exact_date.sum());a.at[i,'U_facts_asof_known_N']=int(g.source_date.notna().sum())
 a.at[i,'U_facts_asof_source_date_counts']=json.dumps(g.source_date.fillna('NO_PRIOR').value_counts().to_dict(),sort_keys=True)
 for q in measures:
  vals={'known_N':int(g[q].notna().sum()),'true_N':int(g[q].eq(True).sum()),'false_N':int(g[q].eq(False).sum()),'unknown_N':int(g[q].isna().sum())}
  assert vals['known_N']+vals['unknown_N']==len(g)and vals['true_N']+vals['false_N']==vals['known_N']
  for suffix,v in vals.items():a.at[i,'U_'+q+'_'+suffix]=v
for name,frame in [('STATIC_MEMBERS_ORIGINAL_STOCK_FACTS_WITH_SAVED_U',f),('ORIGINAL_STOCK_FACTS_SECTOR_AGGREGATES',a),('ANCHOR_ORIGINAL_STOCK_AGGREGATES',a.loc[a.relative_session.eq(0)])]:
 frame.to_parquet(O/(name+'.parquet'),index=False);frame.to_csv(O/(name+'.csv'),index=False)
summary=json.loads((O/'SUMMARY.json').read_text());summary['U_inside_qualification_counts']='KNOWN_FROM_SAME_PASS_SAVED_U_MASK';summary['U_join_rows']=len(f);summary['U_all_168_sector_counts_exact']=True;save('SUMMARY.json',summary)
sources=json.loads((O/'SOURCE_SHA256.json').read_text());sources[str(maskpath.resolve())]=sha(maskpath);sources[str(Path(__file__).resolve())]=sha(__file__);save('SOURCE_SHA256.json',sources)
save('SAVED_U_JOIN_VERIFICATION.json',{'all_168_sector_counts_exact':True,'mask_rows':len(m),'mask_unique_dates':m.date.nunique(),'static_fact_rows':len(f),'unmatched_stock_masks':int(f.qualified_U_t.isna().sum()),'new_U_computation':False,'new_source_stock_reads':0,'new_models':0,'new_accounts':0,'input_mask_path':str(maskpath.resolve()),'input_mask_sha256':sha(maskpath)})
print(a.loc[a.relative_session.eq(0),['case_id','date','whole_static_sector_N','U_N_from_saved_industry_aggregate','U_e0_target_true_N','U_i_target_true_N','U_i_buy_exact_field_true_N','U_i_target_unknown_N']].to_string(index=False))
