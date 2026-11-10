"""Reuse sealed, already-verified June22 runtime for bounded fixed-state tests."""
from pathlib import Path
import pickle,copy,json,sys,time,resource,traceback
import compound_bridge_v1 as E
import additional_adapter_tests_v1 as T
P=Path(__file__).resolve().parent;B=P.parent
def save(out,name,x):
    with (out/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def main():
    name=sys.argv[1];assert name.startswith('qa_additional_') and name[14:].isdigit()
    out=P/name;out.mkdir(exist_ok=False);start=time.monotonic();checks=[]
    def passed(name,detail=None):
        checks.append(dict(name=name,status='PASS',detail=detail));print('PASS',name,flush=True)
    try:
        ref=P/'qa_attempt_02';seal=json.loads((ref/'OUTPUT_SEAL.json').read_text())
        for fn,h in seal.items():assert E.sha(ref/fn)==h,fn
        result=json.loads((ref/'RESULT.json').read_text());assert result['prefix_phases']==221 and result['prefix_actions']==253
        protected=json.loads((B/'annual_2022_marked_nav_v1/PROTECTED_OLD_INPUTS.json').read_text())
        originals={str(p):E.sha(p) for p in (B/'annual_2022_marked_nav_v1/economic_run_2022_annual_once').iterdir() if p.is_file()}
        code_start={str(p):E.sha(p) for p in P.glob('*.py')}
        s=E.bridge.load_original('2022');b=E.ExecutionBridge(s,halt_evidence=E.AnnualHalts())
        with (ref/'PREFIX_CHECKPOINT.pkl').open('rb') as f:saved=pickle.load(f)
        for sid in saved['union']['loaded_sids']:s.load(sid)
        b.restore_runtime(saved)
        assert E.structural_digest(b.capture_runtime())==E.structural_digest(saved)
        passed('sealed_qa02_prefix_checkpoint_fresh_source_reload_and_restore')
        T.run(b,saved,out,passed)
        for p,h in code_start.items():assert E.sha(p)==h,('QA code drift',p)
        for p,h in protected.items():assert E.sha(p)==h,p
        for p,h in originals.items():assert E.sha(p)==h,p
        save(out,'SOURCE_HASHES.json',E.merge_hashes(s.hashes,b.source_hashes,code_start))
        save(out,'CHECKS.json',checks)
        save(out,'RESULT.json',dict(status='AUTHOR_ADDITIONAL_QA_PASS_PENDING_INDEPENDENT_REVIEW',
          checks=len(checks),prefix_reference=str(ref),prefix_phases=221,prefix_actions=253,
          whole_prefix_reexecuted=False,fixed_state_fixtures_only=True,new_annual_runs=0,
          fresh_binding_test_market_cache='Second fixture adapter shares verified immutable market reads to avoid duplicate multi-GiB cache; original source function and state bindings are reconstructed.',
          protected_old_files=len(protected),old_output_files=len(originals),unchanged=True,
          seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        print('ADDITIONAL_QA_DONE',flush=True)
    except BaseException:
        save(out,'FAILURE.json',dict(traceback=traceback.format_exc(),seconds=time.monotonic()-start));raise
    finally:save(out,'OUTPUT_SEAL.json',{p.name:E.sha(p) for p in out.iterdir() if p.is_file()})
if __name__=='__main__':main()
