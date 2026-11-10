from pathlib import Path
import sys,json,traceback,hashlib,time,contextlib,resource
HERE=Path(__file__).resolve().parent
def dump(p,x):
    with p.open('x') as f:json.dump(x,f,indent=2,default=str);f.write('\n')
def main():
    run=HERE/sys.argv[1];run.mkdir(exist_ok=False)
    paths=[HERE/x for x in ['engine_indexed_v1.py','source_split_v2.py','test_execution_indexed.py','run_synthetic_indexed.py','API_AND_TEST_PLAN.md','EXECUTION_BOUNDARIES_V2.md']]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dump(run/'STARTED.json',dict(stage='SYNTHETIC_SOURCE_DEFINITION_ONLY',code_hashes=hashes,started_utc=time.time(),real_economics=False))
    begin=time.monotonic()
    try:
        with (run/'execution.log').open('x') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):
            import engine_indexed_v1 as E,test_execution_indexed
            source=E.bridge.load_original('2022')
            results=test_execution_indexed.test_suite(source)
            dump(run/'TEST_RESULTS.json',results)
        dump(run/'RESULT.json',dict(status='PASS_SYNTHETIC_ONLY',tests=len(results),elapsed=time.monotonic()-begin,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,code_hashes=hashes))
        print('PASS',run,len(results))
    except BaseException as e:
        dump(run/'RESULT.json',dict(status='FAILED',error=repr(e),traceback=traceback.format_exc(),elapsed=time.monotonic()-begin,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,code_hashes=hashes));print(traceback.format_exc());raise
if __name__=='__main__':main()
