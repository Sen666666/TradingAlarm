"""One isolated original A+B/PRICE exact replay per window; no DMI import."""
import argparse, json, os, time
from collections import Counter
from runtime import O,SOURCE,sha,read,verify_original,make_consumer,run_isolated,dump_consumer

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True)
    w=p.parse_args().window
    from run_economic import save,clean
    dest=O/('baseline_exact_'+w)
    assert not dest.exists(),'NO_OVERWRITE_OR_UNREVIEWED_RETRY'
    dest.mkdir()
    save(dest/'STARTED.json',dict(window=w,role='ORIGINAL_JOINT_EXACT_REPLAY',dmi_enabled=False,code={n:sha(O/n) for n in ['runtime.py','run_baseline.py']},started=time.time()))
    start=time.monotonic()
    try:
        a=verify_original()
        print('BASELINE_START',w,flush=True)
        c=run_isolated(make_consumer(w,'baseline'))
        dump_consumer(c,dest)
        print('BASELINE_LOOP_SAVED',w,len(c.s.rounds),len(c.s.actions),flush=True)
        from baseline_regression import TABLES,compare_csv
        ref=SOURCE/('economic_'+w)
        checks={name:compare_csv(dest/'joint'/(name+'.csv'),ref/'joint'/(name+'.csv'),selected=False) for name in TABLES}
        for name in ['CLAIMS','BRIDGES','LEDGER_QA']:
            av=read(dest/'joint'/(name+'.json'));bv=read(ref/'joint'/(name+'.json'))
            assert av==bv,('EXACT_JSON_MISMATCH',name)
            checks[name]=dict(exact=True,rows=len(av))
        for name in ['PRICE_AUDIT','OFFER_AUDIT','AB_DECISION_AUDIT','FROZEN_RESPONSIBILITIES','EXECUTION_BOOKS']:
            av=read(dest/(name+'.json'));bv=read(ref/(name+'.json'))
            assert av==bv,('EXACT_AUDIT_MISMATCH',name)
            checks[name]=dict(exact=True,rows=len(av))
        av=read(dest/'joint/SOURCE_HASHES.json');bv=read(ref/'joint/SOURCE_HASHES.json')
        assert av==bv,'SOURCE_READ_SET_MISMATCH'
        for source,h in av.items():assert a['input_sha256'][source]==h
        verify_original()
        save(dest/'EXACT_QA.json',dict(result='PASS_ORIGINAL_JOINT_EXACT',window=w,checks=checks,source_set_exact=True,original_code_inputs_outputs_unchanged=True,status_counts=dict(Counter(r['status'] for r in c.s.rounds)),dmi_runs=0,elapsed_seconds=time.monotonic()-start,all_csv_columns_order_nan_numeric_exact=True,equity_scope='Original claims, bridges, registrations, claim ledger, profitability gates, round cash/receivables exact'))
        print('BASELINE_EXACT_PASS',w,'seconds',time.monotonic()-start,flush=True)
    except BaseException as exc:
        save(dest/'FAILED_NO_RETRY.json',dict(error=repr(exc),loop_saved=(dest/'ECONOMIC_LOOP_COMPLETE.json').exists(),no_retry=True,elapsed_seconds=time.monotonic()-start))
        raise
if __name__=='__main__':main()
