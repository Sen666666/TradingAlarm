"""Static parameterization and existing controls only; no signal imports."""
from pathlib import Path
import ast,hashlib,json
import numpy as np,pandas as pd

R=Path(__file__).resolve().parents[2];E=R.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
FIELDS=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']
def main():
    wrapper=R/'run_two_dates.py';source=wrapper.read_text();tree=ast.parse(source)
    worker=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='worker');text=ast.get_source_segment(source,worker)
    assert 'm.DAY=day'in text and'm.HERE=Path(out)'in text and'm.block_worker(stage,block_id,symbols)'in text
    olddriver=E/'full_local_signal_20240924_v1/signals/run_signals.py';assert sha(olddriver)==read(olddriver.parent/'FREEZE.json')['driver_sha256']
    target=E/'no_future_cap_selection_v1/target_signal_completion';tf=read(target/'FREEZE.json')
    for p,h in tf['original_algorithm_code_sha256'].items():assert sha(p)==h
    old=pd.read_parquet(target/'TARGET42.parquet').set_index(['sid','day'])
    base=(E/'full_local_signal_20240924_v1/assemble_candidates.py').read_text();reports=[]
    for day,filename in [('2022-01-24','2022_01_24'),('2026-01-15','2026_01_15')]:
        out=R/day/'independent_review';out.mkdir(parents=True,exist_ok=True)
        assembly=R/day/'assemble_candidates.py';normalized=assembly.read_text().replace('ENTRY=HERE.parents[1]','ENTRY=HERE.parent').replace("DAY='"+day+"'","DAY='2024-09-24'").replace(filename,'2024_09_24')
        assert normalized==base
        sf=R/day/'signals/FREEZE.json';available=sf.exists();controls=[]
        if available:
            f=read(sf)
            assert f['day']==day and f['date_wrapper_sha256']==sha(wrapper)and f['immutable_worker_driver_sha256']==sha(olddriver)
            assert f['source_sha256']==tf['source_sha256']and f['original_algorithm_code_sha256']==tf['original_algorithm_code_sha256']
            previous=old.reset_index();reuse=previous[previous.day.eq(day)&previous.status.eq('EXACT_TARGET_STOCK_SIGNAL')]
            assert set(reuse.sid)==set(f['reused_ids'])and len(reuse)==(4 if day=='2022-01-24'else 6)
            assert sha(R/day/'signals/REUSED_TARGETS.jsonl')==f['reused_jsonl_sha256']
            for p in(R/day/'signals/controls').glob('*.jsonl'):
                for line in p.open():
                    row=json.loads(line);prior=old.loc[(row['sid'],day)]
                    for c in FIELDS:
                        a,b=row[c],prior[c]
                        if pd.isna(a)or pd.isna(b):assert pd.isna(a)and pd.isna(b)
                        elif isinstance(a,(int,float))and not isinstance(a,bool):assert np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64),(row['sid'],c)
                        else:assert a==b,(row['sid'],c)
                    assert row['prefix_end_day']==day and row['full_S0_eligibility_q']is None;controls.append(row['sid'])
        result={'status':'PASS_BOUNDED_PARAMETERIZED_DRIVER_AND_ASSEMBLY_STATIC_REVIEW','day':day,'signal_run_freeze_available':available,'saved_target_control_rows_checked':controls,'formal_input':'Unmodified original block_worker receives only day/output-directory parameter changes; physical dataset filter symbolset AND trade_date<=DAY. No924 __main__ invoked.','assembly_normalized_to_924_identical':True,'all11_original_source_hashes_exact':True,'source_cap_or_roster_model_input':False,'full_output_audit':'PENDING_FINAL_SAVED_RESULTS','price_path_group_audit':'PENDING_SAVED_PRIOR_AND_PATHS','unknown_PVR_requirements':['Freeze every knownTrue i_buy before labels, retaining unknownPVR.','Rank/decile/top/rest use only knownPVR and Nrankable; explicit PVR_UNKNOWN bucket.','ALL=rankable+unknown; global complete-tail labels include original full signal cohort.','Empty group/zero positive mass gives NA, topk=min(k,Nrankable).'],'prior924_prefix_test_sha256':sha(E/'full_local_signal_20240924_v1/independent_review/PREFIX_CAUSALITY_AUDIT.json'),'prior924_prefix_test_rerun':False,'new_independent_models':0,'new_accounts':0,'remaining_static_blocks':[],'source_sha256':{str(p.resolve()):sha(p)for p in[wrapper,olddriver,assembly,R/'FREEZE.json',R/day/'FREEZE.json',target/'FREEZE.json',Path(__file__)]},'limits':['Static source and available target controls, not full new-date output or PIT/legal/strategy certification.','If runtime freeze unavailable, per-run identity remains pending sequential date start.']}
        if available:result['source_sha256'][str(sf)]=sha(sf)
        p=out/'STATIC_SOURCE_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');reports.append({'day':day,'sha256':sha(p),'runtime_freeze':available,'controls':controls})
    print(json.dumps(reports,ensure_ascii=False))
if __name__=='__main__':main()
