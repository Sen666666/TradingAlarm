"""Read-only edge plan/receipt and one saved physical prefix; zero model imports."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
f=read(R/'FREEZE.json');plan=read(R/'EDGE_PLAN.json');receipt=read(R/'EDGE_RECEIPT.json');main=read(O/'SAVED_OUTPUT_AUDIT.json')
frames={sid:pd.read_parquet(R/'full'/sid/'BASELINE_FULL_HISTORY.parquet')for sid in f['stocks']}
allrows=[]
for sid,z in frames.items():
 x=z.loc[z.index>=pd.Timestamp('2022-01-01')].copy();x['sid']=sid;x['day']=x.index
 x['cold_to_warm']=x.native__g_grade.ge(2)&x.native__g_grade.shift().lt(2);allrows.append(x)
a=pd.concat(allrows).sort_values(['day','sid'])
# Main independent source audit established all20 positive finite volume/amount.
assert main['all20_source_volume_positive_finite']and all(x['first_bad_CP']is None for x in main['per_stock'])
conditions={
 'E0_exit_and_positive_event_same_close':a.native__e0_exited.eq(1)&a.native__numeric_event.eq(1),
 'I_restore_without_new_E0_entry':a.native__i_entered.eq(1)&~a.native__e0_entered.eq(1),
 'I_exit':a.native__i_exited.eq(1),
 'CP_receipt':a.cp__receipt.eq(True),
 'E0_down_with_I_still_active':a.native__numeric_event.eq(-1)&a.native__i_target.eq(1),
 'G1_cold_to_warm':a.cold_to_warm,
 'Eligible_price_bad_volume':pd.Series(False,index=a.index),
 'Eligible_CP_input_bad_amount':pd.Series(False,index=a.index)}
expected=[];missing=[];used=set()
for name,mask in conditions.items():
 g=a.loc[mask.fillna(False)]
 if g.empty:missing.append({'branch':name,'status':'NOT_EXERCISED_NO_REAL_PILOT_FIXTURE'});continue
 g=g.loc[[(r.sid,str(r.day.date()))not in used for r in g.itertuples()]]
 if g.empty:missing.append({'branch':name,'status':'ONLY_ALREADY_SELECTED_CUTS'});continue
 row=g.iloc[0];key=(row.sid,str(row.day.date()));used.add(key);expected.append({'branch':name,'sid':key[0],'day':key[1]})
assert expected==plan['plan']and missing==plan['not_exercised']==receipt['not_exercised']
assert receipt['additional_kernel_calls']==len(receipt['results'])==len(expected)==5
actual={(r['branch'],r['sid'],r['day']):r for r in receipt['results']};checks=[]
for item in expected:
 r=actual[(item['branch'],item['sid'],item['day'])];z=frames[item['sid']].loc[:item['day']]
 assert r['status']=='PASS_ALL_COMMON_PREFIX_FIELDS' and r['rows']==len(z)and r['columns']==len(z.columns)and r['exact_cells']==z.size and r['physical_input_max']==item['day']
 assert r['profile']['input_rows']==len(z) and r['profile']['cp_first_bad_date'] is None
 checks.append({**item,'rows':len(z),'columns':len(z.columns),'cells':z.size,'independent_value_recomparison':'NOT_AVAILABLE_PREFIX_FRAME_NOT_SAVED'})
wp=read(R/'PVR_WARM_BOUNDARY_PLAN.json');wr=read(R/'PVR_WARM_BOUNDARY_RECEIPT.json')
first=[]
for sid,z in frames.items():
 k=z.pvr__score.first_valid_index()
 if k is not None and k>=pd.Timestamp('2022-01-01'):first.append((k,sid))
first.sort();assert (str(first[0][0].date()),first[0][1])==(wp['cut'],wp['sid'])==('2022-12-09','301308.SZ')
p=R/'prefix/PVR_FIRST_KNOWN_PREFIX.parquet';assert sha(p)==wr['output_sha256']
prefix=pd.read_parquet(p);base=frames[wp['sid']].loc[:wp['cut']]
assert prefix.index.equals(base.index)and prefix.columns.equals(base.columns)
for c in prefix:
 u,v=prefix[c],base[c];assert u.isna().equals(v.isna())
 good=u.notna()
 if pd.api.types.is_numeric_dtype(u)and not pd.api.types.is_bool_dtype(u):assert np.array_equal(u[good].to_numpy(float).view(np.uint64),v[good].to_numpy(float).view(np.uint64)),c
 else:assert u[good].astype(str).equals(v[good].astype(str)),c
assert prefix.size==wr['exact_cells']==6715 and prefix.shape==(85,79)and prefix.pvr__score.iloc[:-1].isna().all()and np.isfinite(prefix.pvr__score.iloc[-1])
assert prefix.pvr__valid_observation.all()and prefix.pvr__clock_block.nunique()==1
cold=next(z for z in expected if z['branch']=='G1_cold_to_warm');cf=frames[cold['sid']];j=cf.index.get_loc(pd.Timestamp(cold['day']));previous=float(cf.native__g_grade.iloc[j-1]);current=float(cf.native__g_grade.iloc[j]);assert previous<2<=current
out={'status':'PASS_BOUNDED_REAL_EDGE_RECEIPTS_AND_SAVED_PVR85_PREFIX_VALUES','remaining_blocks':[],'mechanical_real_branch_plan_exact':True,'producer_additional_edge_calls':5,'edge_receipt_checks':checks,'not_exercised':missing,'G1_branch_label_semantics':{'code_criterion':'previous grade<2 and current>=2 means below-warm to warm, not always nativecold','actual_previous_grade':previous,'actual_current_grade':current,'actual_sid':cold['sid'],'actual_day':cold['day']},'additional_PVR85_producer_calls':1,'saved_PVR_prefix_independent_all_value_cells':6715,'saved_PVR_prefix_rows':85,'saved_PVR_prefix_columns':79,'producer_total_original_stock_signal_calls':66,'reviewer_model_calls':0,'reviewer_numeric_calls':0,'reviewer_accounts':0,'limits':['Forty regular and five edge prefixes exist as executed bound-code assertion receipts, not saved frames; no independent value recompare claimed for those45.','The sixth extra prefix frame is saved and all6715cells were independently compared to the complete baseline prefix.','No real pilot fixture for exit+up/badvolume/badamount; invalidprice/multisource branches also not certified.','CP first-invalid permanent BLOCKED behavior is static-only here because all20 selected source inputs satisfy CP amount/close validation.','Edge script current bytes bound in this review; its receipt has no separately recorded pre-run script SHA. No code change evidence observed, but do not label it pre-run cryptographic binding.'],'source_sha256':{str(p.resolve()):sha(p)for p in [R/'edge_controls.py',R/'EDGE_PLAN.json',R/'EDGE_RECEIPT.json',R/'PVR_WARM_BOUNDARY_PLAN.json',R/'PVR_WARM_BOUNDARY_RECEIPT.json',R/'prefix/PVR_FIRST_KNOWN_PREFIX.parquet',O/'SAVED_OUTPUT_AUDIT.json',Path(__file__)]}}
p=O/'EDGE_AND_SAVED_PREFIX_AUDIT.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':out['status'],'sha256':sha(p),'producer_calls':66,'independent_saved_prefix_cells':6715,'G1':out['G1_branch_label_semantics']},ensure_ascii=False))
