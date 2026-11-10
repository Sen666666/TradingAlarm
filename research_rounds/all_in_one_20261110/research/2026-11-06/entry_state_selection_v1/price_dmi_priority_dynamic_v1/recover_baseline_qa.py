"""Saved original-joint replay QA recovery. No engine, lifecycle or dump calls.
Only resolve file aliases before looking up the original approved source map,
matching the frozen run_economic.verify_inputs behavior. Preserve all failures.
"""
import argparse,time
from pathlib import Path
from collections import Counter
from runtime import O,SOURCE,sha,read,verify_original
from baseline_regression import TABLES,compare_csv,csv_rows
from run_economic import save

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True)
    w=p.parse_args().window;dest=O/('baseline_exact_'+w);ref=SOURCE/('economic_'+w)
    assert (dest/'ECONOMIC_LOOP_COMPLETE.json').exists() and (dest/'joint/OUTPUT_HASHES.json').exists()
    assert not (dest/'EXACT_QA.json').exists(),'NO_OVERWRITE_QA'
    failure=read(dest/'FAILED_NO_RETRY.json')
    assert failure['loop_saved'] is True and failure['error'].startswith('KeyError('),'ONLY_KNOWN_POSTPROCESS_ALIAS_FAILURE'
    before={str(p):sha(p) for p in dest.rglob('*') if p.is_file()}
    for folder in [dest/'joint',ref/'joint']:
        for name,h in read(folder/'OUTPUT_HASHES.json').items():assert sha(folder/name)==h
    a=verify_original()
    checks={n:compare_csv(dest/'joint'/(n+'.csv'),ref/'joint'/(n+'.csv'),selected=False) for n in TABLES}
    for name in ['CLAIMS','BRIDGES','LEDGER_QA']:
        av=read(dest/'joint'/(name+'.json'));bv=read(ref/'joint'/(name+'.json'))
        assert av==bv,('EXACT_JSON_MISMATCH',name);checks[name]=dict(exact=True,rows=len(av))
    for name in ['PRICE_AUDIT','OFFER_AUDIT','AB_DECISION_AUDIT','FROZEN_RESPONSIBILITIES','EXECUTION_BOOKS']:
        av=read(dest/(name+'.json'));bv=read(ref/(name+'.json'))
        assert av==bv,('EXACT_AUDIT_MISMATCH',name);checks[name]=dict(exact=True,rows=len(av))
    av=read(dest/'joint/SOURCE_HASHES.json');bv=read(ref/'joint/SOURCE_HASHES.json')
    assert av==bv,'SOURCE_READ_SET_MISMATCH'
    plan={str(Path(p).resolve()):h for p,h in a['input_sha256'].items()}
    aliases=[]
    for p,h in av.items():
        resolved=str(Path(p).resolve())
        assert plan.get(resolved)==h and sha(p)==h,('SOURCE_MAPPING_OR_BYTES_DRIFT',p)
        if p!=resolved:aliases.append(dict(original=p,resolved=resolved,sha256=h))
    for p,h in read(dest/'MARKET_SOURCES.json').items():assert plan.get(str(Path(p).resolve()))==h and sha(p)==h
    for p,h in before.items():assert sha(p)==h,('SAVED_REPLAY_CHANGED',p)
    statuses=Counter(r['status'] for r in csv_rows(dest/'joint/ROUNDS.csv')[1])
    save(dest/'EXACT_QA.json',dict(result='PASS_ORIGINAL_JOINT_EXACT',window=w,checks=checks,source_set_exact=True,source_entries=len(av),aliases=aliases,original_code_inputs_outputs_unchanged=True,status_counts=dict(statuses),all_csv_columns_order_nan_numeric_exact=True,equity_scope='Original claims, bridges, registrations, claim ledger, profitability gates, round cash/receivables exact',dmi_runs=0,recovery_consumer_calls=0,postprocess_only=True,old_failure_preserved=True,recovery_driver_sha256=sha(__file__),failed_replay_driver_sha256=read(dest/'STARTED.json')['code']['run_baseline.py'],frozen_artifacts_unchanged=before))
    print('BASELINE_SAVED_EXACT_PASS',w,dict(statuses),'aliases',len(aliases),flush=True)
if __name__=='__main__':main()
