"""Join only the frozen 25 cases to their explicitly assigned existing label source."""
from pathlib import Path
import hashlib,json,datetime
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;R=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal=json.loads((O/'FEATURE_SEAL.json').read_text())
for n,h in seal['sha256'].items():assert sha(O/n)==h,(n,'feature changed after seal')
f=pd.read_csv(O/'FIXED_CASE_FEATURES_PRELABEL.csv')
sourcefiles={
 'AB_2022':R/'m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv',
 'AB_2024':R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv',
 'FAST_2022':R/'fast_entry_equity_2022_v1/report/INITIAL_AND_FULL_ROUNDS.csv'}
src={r:pd.read_csv(p) for r,p in sourcefiles.items()}
joined=[];rawlabels=[];checks=[]
for c in f.to_dict('records'):
 role=c['role'];d=dict(c)
 if role.startswith('INPUT_ONLY'):
  d['label_connection']='INPUT_ONLY_NO_ECONOMIC_LABEL';d['economic_role']='INPUT_ONLY';d['execution_inference']='NONE'
 else:
  g=src[role];arm='AB_FAST_SMALL' if role=='FAST_2022' else 'A_UNION_B'
  matches=g[g.arm.eq(arm)&g.sid.eq(c['sid'])&g.signal_day.eq(c['day'])]
  assert len(matches)==1,(c['case_id'],len(matches))
  lab=matches.iloc[0];assert lab.sector==c['sector']
  np.testing.assert_allclose(lab.PVR_score,c['PVR_original_cached_score'],rtol=0,atol=1e-10,equal_nan=True)
  d.update({'label_'+k:v for k,v in lab.items()});d['label_connection']='EXACT_EXISTING_IDENTITY';d['economic_role']='FAST_INITIAL_AND_FULL' if role=='FAST_2022' else 'AB_CORE_AND_FULL'
  d['label_source_file']=str(sourcefiles[role]);d['label_source_sha256']=sha(sourcefiles[role]);d['execution_inference']='EXISTING_CONDITIONAL_PROXY_ONLY'
  rawlabels.append(dict(case_id=c['case_id'],assigned_role=role,source_file=str(sourcefiles[role]),**lab.to_dict()))
  checks.append(dict(case_id=c['case_id'],sid=c['sid'],day=c['day'],arm=arm,round_id=lab.round_id,event_id=lab.event_id,one_exact_match=True,sector_exact=True,PVR_exact_1e_10=True))
 joined.append(d)
out=pd.DataFrame(joined);out.to_csv(O/'FIXED_CASE_FEATURES_WITH_EXISTING_LABELS.csv',index=False)
pd.DataFrame(rawlabels).to_csv(O/'EXACT_EXISTING_LABEL_ROWS.csv',index=False)
qa={'connected_after_feature_seal':True,'feature_seal_sha256':sha(O/'FEATURE_SEAL.json'),'joined_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':{str(p):sha(p) for p in sourcefiles.values()},'fixed_cases':25,'AB_2022':9,'AB_2024':7,'FAST_2022':3,'input_only':6,'checks':checks,'no_economic_paths_recomputed':True,'not_blind_or_OOS':True,'no_roles_or_denominators_combined':True,'NET80_boundary':'Use original financial/initial/full coverage status separately; absence of complete historical corporate-action evidence is not proof of no action. Execution tradability remains UNKNOWN.'}
(O/'LABEL_CONNECTION_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
cols=['case_id','role','sid','day','sector_E0_age','LOO_R_known','LOO_R_lower','LOO_R_upper','LOO_R_equal_known','LOO_R_u_known','target_positive_cohort','target_h','label_core_return','label_initial_return','label_net_return_on_buy_cash','label_financial_coverage_status','label_initial_coverage_status']
print(out[[k for k in cols if k in out]].to_string(index=False))
