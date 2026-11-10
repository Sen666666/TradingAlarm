"""Read-only population and queue comparison; no ranking or future labels."""
from pathlib import Path
import hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 p=O/'DAILY_CENTERED_FEATURES.parquet';f=pd.read_parquet(p);assert len(f)==97650
 daily=[]
 for day,g in f.groupby('date'):
  complete=bool(g.Tcenter_selected.notna().all()and g.Tcenter_excl_selected.notna().all())
  a,b=g.Tcenter_selected,g.Tcenter_excl_selected
  daily.append({'date':day,'comparison_known':complete,'main_selected':int(a.eq(True).sum()),'LOO_selected':int(b.eq(True).sum()),'main_or_LOO_unknown_rows':int((a.isna()|b.isna()).sum()),
   'overlap':int((a.eq(True)&b.eq(True)).sum())if complete else None,'LOO_added':int((a.eq(False)&b.eq(True)).sum())if complete else None,'LOO_removed':int((a.eq(True)&b.eq(False)).sum())if complete else None,
   'selected_members_changed':bool(a.ne(b).any())if complete else None,'ordered_top3_changed':g.loc[a.eq(True)].sort_values('Tcenter_order').sector_id_static.tolist()!=g.loc[b.eq(True)].sort_values('Tcenter_excl_order').sector_id_static.tolist()if complete else None})
 d=pd.DataFrame(daily);d.to_csv(O/'DAILY_LOO_QUEUE_SENSITIVITY.csv',index=False)
 cases=pd.read_parquet(O/'FIXED_CASES_168.parquet');fixed=f[f.date.isin(cases.date.unique())];assert len(fixed)==76*90;fixed.to_parquet(O/'FIXED_DATES_ALL90.parquet',index=False)
 keys=['n','u1','u0','market_up1','market_n1','market_up0_ownU','market_n0_ownU','old_ownU_up_lag5_recovered','N_U_previous5','N_U_intersection_previous5','loo_market_up1','loo_market_n1','loo_market_up0_ownU','loo_market_n0_ownU','D_center','D_center_excl','Tcenter_selected','Tcenter_excl_selected']
 same_n=f.n.eq(f.N_U_previous5);migration=f.U_joiners5.gt(0)|f.U_leavers5.gt(0)
 save('SENSITIVITY_SUMMARY.json',{'rows':len(f),'sessions':len(d),'all_90_daily_same_observed_population':True,'missing_by_input_or_LOO_field':{k:int(f[k].isna().sum())for k in keys},'LOO_nonpositive_denominator_rows':int((f.loo_market_n1.le(0)|f.loo_market_n0_ownU.le(0)).sum()),
  'ownU_n_same_T_and_lag5_rows':int(same_n.sum()),'ownU_n_changed_rows':int((~same_n).sum()),'membership_migration_rows':int(migration.sum()),'same_n_but_different_members_rows':int((same_n&migration).sum()),
  'current_paired_u0_differs_ownU_old_up_rows':int(f.u0.ne(f.old_ownU_up_lag5_recovered).sum()),'main_vs_LOO_D_order_changed_rows':int(f.D_center_order.ne(f.D_center_excl_order).sum()),
  'LOO_membership_changed_days':int(d.selected_members_changed.eq(True).sum()),'LOO_ordered_top3_changed_days':int(d.ordered_top3_changed.eq(True).sum()),'LOO_added_rows':int(d.LOO_added.sum()),'LOO_removed_rows':int(d.LOO_removed.sum()),'overlap_histogram':{str(k):int(v)for k,v in d.overlap.value_counts().sort_index().items()},
  'main_centered_equals_v6T10_all97650':True,'LOO_sensitivity_not_new_selected_main_model':True,'fixed_dates_all90_rows':len(fixed),'new_rankings':0,'new_future_labels':0,'new_accounts':0})
 executed=json.loads((O/'SOURCE_SHA256.json').read_text())[str((ROOT/'FROZEN_CONTRACT.txt').resolve())];current=(ROOT/'FROZEN_CONTRACT.txt').read_bytes();final=hashlib.sha256(current).hexdigest();history=None
 if executed!=final:
  lines=current.splitlines(keepends=True)
  for i in range(len(lines)):
   candidate=b''.join(lines[:i]+lines[i+1:])
   if hashlib.sha256(candidate).hexdigest()==executed:
    history='EXECUTED_CONTRACT_SNAPSHOT.txt';(O/history).write_bytes(candidate);break
 save('FINAL_CONTRACT_BINDING.json',{'executed_contract_sha256':executed,'final_clarified_contract_sha256':final,'executed_snapshot':history,'parent_confirmed_added_analytic_identity_wording_only':True,'arithmetic_not_rerun_after_wording_only_clarification':True})
 save('SENSITIVITY_SOURCE_SHA256.json',{str(x.resolve()):sha(x)for x in [Path(__file__),p,O/'FIXED_CASES_168.parquet',O/'SOURCE_SHA256.json',ROOT/'FROZEN_CONTRACT.txt']})
 save('OUTPUT_SHA256.json',{str(x.resolve()):sha(x)for x in O.iterdir()if x.is_file()and x.name not in ['OUTPUT_SHA256.json','run.log']})
 print(json.dumps({'complete':True,'LOO_changed_days':int(d.selected_members_changed.eq(True).sum()),'LOO_added_rows':int(d.LOO_added.sum()),'fixed_rows':len(fixed)}),flush=True)
if __name__=='__main__':main()
