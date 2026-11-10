"""No ACT recalculation. Verify saved raw/CSV domains, source AST and roster metadata."""
from pathlib import Path
import ast,copy,hashlib,json
import numpy as np,pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');C=O.parent/'ar6_native_feasibility/VOLUME_FULL_FEATURES_V1_CODE';P=O.parent/'ar6_native_feasibility/VOLUME_ACT_SHARED_GATE_V1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def norm_index(x):x=x.copy(deep=False);x.index=x.index.as_unit('ns');return x
def exact(a,b):pd.testing.assert_frame_equal(norm_index(a),norm_index(b),check_exact=True,check_dtype=False,check_freq=False,check_names=False)
f=load(C/'ACT_PRE_RUN_FREEZE.json');inp=load(f['input_manifest']);fail=load(P/'TRUE_PARITY_FAILURE.json');status=load(P/'STATUS.json')
for p,h in f['source_sha256'].items():assert sha(p)==h
for key in ['metadata','original_stock_order_manifest','source_prepared_manifest']:
 p=inp[key+'_path']if key=='metadata'else inp[key];assert sha(p)==inp[key+'_sha256']
ids=load(inp['original_stock_order_manifest'])['stocks'];assert ids==[r['sid']for r in inp['stock_order']]and len(ids)==1709
pm=load(inp['source_prepared_manifest']);recs={r['series_id']:r for r in pm['series']};base=Path(inp['source_prepared_manifest']).parent
for r in inp['stock_order']:
 old=recs[r['sid']]['files']['signal'];assert Path(r['signal_path']).resolve()==(base/old['path']).resolve()and r['signal_sha256']==old['sha256']
# Frozen source/roster preserve original grouping and iteration order, never worker completionorder.
coverage=load(P/'INPUT_COVERAGE.json');assert [r['sid']for r in coverage]==ids;absent=[r['sid']for r in coverage if r['status']=='NA_NO_OBSERVATION_THROUGH_CUTOFF'];assert absent==inp['empty_ids_expected']and len(absent)==22
roster=load(P/'ROSTER_ORDER.json');meta=load(inp['metadata_path']);expected=[dict(symbol=r['sid'],sector_id=meta[r['sid']]['sector_id'])for r in coverage if r['status']=='OBSERVED'];assert roster==expected and len(roster)==1687
old=Path(f['reference_recovery_csv']);new=P/'REAL_COLD.csv';assert old.read_bytes()==new.read_bytes()
raw=norm_index(pd.read_parquet(P/'REAL_COLD.parquet'));default=norm_index(pd.read_csv(old,index_col=0,parse_dates=True));new_default=norm_index(pd.read_csv(new,index_col=0,parse_dates=True));rt=norm_index(pd.read_csv(old,index_col=0,parse_dates=True,float_precision='round_trip'))
exact(raw,rt);exact(default,new_default)
diffs={}
for k in raw:
 a=raw[k];b=default[k];mask=~(a.eq(b)|(a.isna()&b.isna()))
 if mask.any():diffs[k]=dict(count=int(mask.sum()),max_abs=float((a-b).abs().max()))
assert diffs=={k:{z:v for z,v in x.items()if z!='first'}for k,x in fail['differences'].items()}
for k in ['fast_on','breakout']:pd.testing.assert_series_equal(raw[k],default[k],check_exact=True,check_names=False,check_freq=False)
assert not fail['round_trip_parse_differences']and fail['recomputed_csv_bytes_equal_reference']and fail['neutral_not_run'];assert not status['neutral_computed']and status['full_workers_started']==0
assert not (P/'NEUTRAL_FEATURES.parquet').exists()and not (P/'MULTIPLIER_MASK_AUDIT.json').exists()
# Verify the exact intended one-expression AST replacement; do not execute it.
tree=ast.parse(Path(f['compute_recovery_source']).read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='compute_recovery');orig=ast.dump(node,include_attributes=False);neutral=copy.deepcopy(node);count=0
for n in ast.walk(neutral):
 if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='u':
  assert ast.dump(n.value)==ast.dump(ast.parse('r*np.minimum(1,np.sqrt(q))',mode='eval').body);n.value=ast.parse('r.where(np.minimum(1,np.sqrt(q)).notna())',mode='eval').body;count+=1
assert count==1;bind=load(P/'AST_BINDING.json');assert hashlib.sha256(orig.encode()).hexdigest()==bind['original_function_AST_sha256'];assert hashlib.sha256(ast.dump(ast.fix_missing_locations(neutral),include_attributes=False).encode()).hexdigest()==bind['neutral_function_AST_sha256']
x=dict(status='PASS_REAL_ACT_SERIALIZED_PIPELINE_CONTROL_ONLY_NEUTRAL_MASK_GATE_PENDING',source_SHA_checks=len(f['source_sha256']),input_manifest_all1709_paths_order_hashes_match_original=True,roster=dict(all=1709,observed=1687,NA=22),comparable_saved_rows=len(raw),
 exact_proofs=['Cold REAL_COLD.csv bytes exactly equal original recovery.csv.', 'Cold raw parquet values exactly equal original CSV round_trip parse.', 'Default parser(originalCSV) exactly equals default parser(coldCSV), the originalruntime serialization+reader pipeline.', 'All fast_on/breakout flags equal across raw/defaultfloat domains.'],
 preserved_original_strict_failure=dict(default_parse_vs_raw_differences=diffs,seconds=status['seconds'],no_tolerance=True,original_failure_not_relabelled_as_strictfloatpass=True),
 source_review={'ACT':'Original AST exact and onlyknown multiplier->1 AST delta; sameprice/source/fullwarm/64/5/8/.6/prior63MAX. Unknown multiplier remains unknown by r.where(oldmultiplier.notna()).', 'inputs':'Only local source signals read, originalamount/volume files never modified. Full fixedrosterorder matches original; neither worker order nor emptyfilling changes M.', 'worker':'Frozen pureassemble only after future fullgrant; no Account/Runner constructors or financialimports; empty22 returns explicitNA before initialize/assemble.', 'controller':'Only act-gate reachable, no1799pool scheduler; fullbatch not ready or authorized.'},
 remains_unverified=['Neutral ACT output and full per-stock multiplierknownmask audit did not execute because first strictfloat gate stopped.', 'Full1799workers/controller/sourcegrant binding and longbatch not executed/authorized; future model/SCORES manifests must be bound.', 'No ACT20 accountDD/flat feedback, neutral_ACT_on, financial stage or economic result.'],
 current_disposition='ROOT_LATEST_STOP: no further1799/controller development, no ACTneutral continuation/v2, no newmodel or account. Serializedpipeline identity is a readonly realcontrol result only, not an automatic continuation grant. Mainloss/winner economiccoverage remains unknown.',
 reviewer_model_or_account_runs=0,inputs={str(p):sha(p)for p in [C/'ACT_PRE_RUN_FREEZE.json',C/'ACT_INPUT_MANIFEST.json',C/'shared_act.py',C/'feature_worker.py',C/'controller.py',P/'REAL_COLD.parquet',P/'REAL_COLD.csv',old,P/'TRUE_PARITY_FAILURE.json',P/'STATUS.json',P/'AST_BINDING.json',Path(__file__)]})
(O/'VOLUME_ACT_SERIALIZED_CONTROL_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],rows=len(raw),diffs=diffs,roster=x['roster'])))
