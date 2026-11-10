"""Append only exact cached observation age, then descriptive continuous summaries."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,csv
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};clocks={};summaries={};checks=0
def dist(values):
 v=[float(x) for x in values if x is not None]
 return dict(n=len(v),min=min(v) if v else None,p10=float(np.quantile(v,.1)) if v else None,median=float(np.median(v)) if v else None,p90=float(np.quantile(v,.9)) if v else None,max=max(v) if v else None,meaning='descriptive continuous distribution only; no cutoffs or selected gate')
for ref in ['2022_2024','strong']:
 p=O/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.json');z=read(p)
 for x in z:
  sid=x['sid'];freeze=x['CP1_scale_frozen_at'];x['CP1_freeze_age_clock']='original CP1 valid observation index, excludes freeze observation and includes decision; never calendar days'
  if freeze is None:x['CP1_freeze_to_decision_original_valid_observations']=None;continue
  if sid not in clocks:
   fp=Path(sm[sid]['refs']['CP1']);assert sha(fp)==sm[sid]['output_sha256'][str(fp)];clocks[sid]=pd.read_parquet(fp,columns=[]).index
  ix=clocks[sid];start=pd.Timestamp(freeze);end=pd.Timestamp(x['decision_at'][:10]);age=int(ix.get_loc(end)-ix.get_loc(start));assert age>=1
  x['CP1_freeze_to_decision_original_valid_observations']=age;assert x['CP1_current_z']>0 and x['CP1_used_scale_over_current_z']==x['CP1_used_scale']/x['CP1_current_z'];checks+=1
 p.write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 columns=['window','layer','sid','name','decision_at','actual_fill_at','budget_order','role','action','receipt','original_cost','original_net','original_order_floor_causal','original_I_floor_causal','initial_order_floor_binding','order_floor_unique_semantic_origin_day','I_floor_current_numeric_run_first_visible_day','CP1_used_scale','CP1_current_z','CP1_next_scale','CP1_used_scale_over_current_z','CP1_scale_frozen_at','CP1_freeze_to_decision_original_valid_observations','CP1_formation_start_exclusive','initial_log_distance_close_to_order_floor','initial_width_over_used_scale','initial_width_over_current_z','later_ratchet_origin']
 with (O/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.csv')).open('w') as f:w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows([{k:x.get(k) for k in columns} for x in z])
 groups=defaultdict(list)
 for x in z:groups[(x['role'],x['action'],x['initial_order_floor_binding'])].append(x)
 summaries[ref]=dict(all_mobile_ratio=dist([x['CP1_used_scale_over_current_z'] for x in z if x['role']=='mobile']),all_mobile_freeze_age=dist([x['CP1_freeze_to_decision_original_valid_observations'] for x in z if x['role']=='mobile']),by_original_role_action_binding=[dict(role=k[0],action=k[1],binding=k[2],ratio_used_over_current_z=dist([x['CP1_used_scale_over_current_z'] for x in xs]),freeze_age_original_valid_observations=dist([x['CP1_freeze_to_decision_original_valid_observations'] for x in xs])) for k,xs in sorted(groups.items())])
(O/'CONTINUOUS_SCALE_DISTRIBUTIONS.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2)+'\n');v=read(O/'THIN_JOIN_VALIDATION.json');v['canonical_scale_freeze_age_exact_original_observation_rows']=checks;v['ratio_only_positive_current_z']=True;(O/'THIN_JOIN_VALIDATION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');s=read(O/'THIN_JOIN_SOURCES.json');s['script_sha256']=sha(O/'extract_entry_scales.py');s['observation_age_append_script_sha256']=sha(__file__);s['continuous_distributions_not_threshold_search']=True;(O/'THIN_JOIN_SOURCES.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');print('APPENDED canonical freeze observations',checks)
for ref,s in summaries.items():print(ref,'ratio',s['all_mobile_ratio'],'age',s['all_mobile_freeze_age'])
