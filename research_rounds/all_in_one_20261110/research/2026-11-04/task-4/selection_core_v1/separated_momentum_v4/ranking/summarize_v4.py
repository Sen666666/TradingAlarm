"""Read-only state-table summaries; no prices, ranks, accounts or forward labels."""
from pathlib import Path
import hashlib,json
import pandas as pd

O=Path(__file__).resolve().parent
SNAP=['2022-01-24','2024-09-24','2026-01-15']
WINDOWS=[('2024_924','2024-09-24','2024-12-31'),('2026H1','2026-01-01','2026-06-30')]
def clean(v):
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,dict):return {k:clean(x)for k,x in v.items()}
 if isinstance(v,list):return [clean(x)for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float)and pd.isna(v):return None
 return v
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def first(g,flag):
 a=g.loc[g[flag].eq(True),'date'];return None if a.empty else a.iloc[0]
def main():
 p=O/'STATES_ALL_2021_2026.parquet';f=pd.read_parquet(p).sort_values(['sector_id_static','date']);assert len(f)==119520
 previous=f.groupby('sector_id_static').possible_states_after.shift()
 valid=previous.notna();assert f.loc[valid,'possible_states_before'].eq(previous[valid]).all()
 conv=[];windows=[];boundary=[]
 for sec,g in f.groupby('sector_id_static',sort=True):
  g=g.sort_values('date').copy();g['prev_T']=g.T_selected.shift();g['prev_union']=g.UNION_selected.shift()
  single=g.possible_states_after.map(lambda s:len(json.loads(s))==1)
  resolved=g.P_mature.notna();warm=g[g.warmup]
  conv.append({'sector_id_static':sec,'industry_static':g.industry_static.iloc[0],
   'first_singleton_after_date':None if not single.any()else g.loc[single,'date'].iloc[0],
   'first_public_phase_known_date':None if not resolved.any()else g.loc[resolved,'date'].iloc[0],
   'warm_final_states':warm.iloc[-1].possible_states_after,'warm_final_public_mature':warm.iloc[-1].P_mature,
   'first2022_before_states':g.loc[g.date.ge('2022-01-01')].iloc[0].possible_states_before})
  for year in ['2022','2023','2024','2025','2026']:
   x=g[g.date.str.startswith(year)].iloc[0];before=g[g.date.lt(x.date)].iloc[-1]
   boundary.append({'year':year,'sector_id_static':sec,'last_date':before.date,'first_date':x.date,
    'prior_after':before.possible_states_after,'next_before':x.possible_states_before,
    'state_exact_carry':before.possible_states_after==x.possible_states_before})
  for name,start,end in WINDOWS:
   h=g[g.date.between(start,end)].copy();assert len(h)
   x=h.iloc[0];r={'window':name,'sector_id_static':sec,'industry_static':x.industry_static,
    'first_session':x.date,'last_session':h.date.iloc[-1],'sessions':len(h),
    'P_carryin':x.P_prevpublic,'T_carryin':x.prev_T,'union_carryin':x.prev_union,
    'P_states_before_window':x.possible_states_before,
    'P_first_observed_mature':first(h,'P_mature'),'P_first_true_new_maturity':first(h,'P_known_new_maturity'),
    'P_true_new_maturities':int(h.P_known_new_maturity.sum()),'P_true_removals':int(h.P_known_exit.sum()),
    'P_resolved_active':int(h.P_state_event.eq('RESOLVED_ACTIVE').sum()),'P_data_resume_active':int(h.P_state_event.eq('DATA_RESUME_ACTIVE').sum())}
   for prefix,col,prev in [('P','P_mature','P_prevpublic'),('T','T_selected','prev_T'),('union','UNION_selected','prev_union')]:
    r[prefix+'_selected_days']=int(h[col].eq(True).sum());r[prefix+'_unknown_days']=int(h[col].isna().sum())
    r[prefix+'_first_observed_selected']=first(h,col)
    r[prefix+'_certain_false_to_true_count']=int((h[col].eq(True)&h[prev].eq(False)).sum())
    r[prefix+'_unknown_to_true_count']=int((h[col].eq(True)&h[prev].isna()).sum())
   windows.append(r)
 pd.DataFrame(conv).to_csv(O/'WARM_CONVERGENCE_ALL90.csv',index=False)
 pd.DataFrame(boundary).to_csv(O/'YEAR_BOUNDARY_CARRY_ALL90.csv',index=False)
 pd.DataFrame(windows).to_csv(O/'FIXED_WINDOWS_ALL90.csv',index=False)
 snapshots=[];lists={}
 for day in SNAP:
  g=f[f.date.eq(day)].copy();g.to_csv(O/('SNAPSHOT_ALL90_'+day+'.csv'),index=False)
  lists[day]={name:g.loc[g[flag].eq(True)].sort_values(order).industry_static.tolist()
   for name,flag,order in [('P_mature','P_mature','P_order'),('T3','T_selected','T_order'),('union','UNION_selected','P_order'),('H1sameN','main_H1_selected','v3_native_H1_order'),('DsameN','main_D_selected','v3_native_D_order')]}
  snapshots.extend(g[g.industry_static.isin(['房地产','软件服务','软件开发','通信设备','半导体','电子化学品'])].to_dict('records'))
 save('SNAPSHOT_SELECTION_LISTS.json',lists);pd.DataFrame(snapshots).to_csv(O/'FOCAL_RANKS_AND_STATES_3D.csv',index=False)
 save('SUMMARY_SUPPLEMENT.json',{'state_adjacency_checks':int(valid.sum()),'all_state_carry_exact':True,
  'warm90_singleton_by_end':sum(len(json.loads(x['warm_final_states']))==1 for x in conv),
  'warm90_public_known_by_end':sum(not pd.isna(x['warm_final_public_mature'])for x in conv),
  'source_table_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  'windows_rows':len(windows),'new_price_reads':0,'new_rankings':0,'new_forward_labels':0,'new_accounts':0})
 save('OUTPUT_SHA256.json',{str(x.resolve()):hashlib.sha256(x.read_bytes()).hexdigest()for x in O.iterdir()if x.is_file()and x.name not in ['OUTPUT_SHA256.json','run_v4.log']})
 print(json.dumps({'complete':True,'warm_converged':sum(len(json.loads(x['warm_final_states']))==1 for x in conv),'windows_rows':len(windows)}),flush=True)
if __name__=='__main__':main()
