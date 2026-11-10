"""Traceable unchanged-original no_budget replay. No shared economic runner."""
from pathlib import Path
import sys, json, time, traceback, contextlib
from datetime import datetime, timezone
import bridge

def utc(): return datetime.now(timezone.utc).isoformat()
def write_new(path, value):
    with Path(path).open('x') as f:
        json.dump(value,f,indent=2,ensure_ascii=False,default=str);f.write('\n')
class Tee:
    def __init__(self,*streams):self.streams=streams
    def write(self,text):
        for stream in self.streams:stream.write(text);stream.flush()
        return len(text)
    def flush(self):
        for stream in self.streams:stream.flush()
def check_runner_seal():
    seal=json.loads((bridge.HERE/'EXECUTION_SEAL.json').read_text())
    for name,digest in seal['sha256'].items():
        assert bridge.sha(bridge.HERE/name)==digest,('execution drift',name)
    return seal
def json_normal(value):
    return json.loads(json.dumps(value,default=str))
def main():
    if len(sys.argv)!=2 or sys.argv[1] not in bridge.ENGINES:
        raise SystemExit('Usage: run_sealed.py 2022|2024_924')
    window=sys.argv[1];seal=check_runner_seal();bridge.verified_manifest()
    destination=bridge.HERE/('sealed_full_'+window);destination.mkdir(exist_ok=False)
    started=utc();clock=time.monotonic()
    write_new(destination/'STARTED.json',{'state':'STARTED','at':started,'window':window,'stage':'ORIGINAL_NO_BUDGET_FULL',
        'execution_seal_sha256':bridge.sha(bridge.HERE/'EXECUTION_SEAL.json'),'execution_sha256':seal['sha256'],
        'source_manifest_sha256':bridge.sha(bridge.HERE/'SOURCE_MANIFEST.json'),'shared_account':False,'new_strategy':False})
    with (destination/'RUN_LOG.txt').open('x') as log:
        with contextlib.redirect_stdout(Tee(sys.stdout,log)),contextlib.redirect_stderr(Tee(sys.stderr,log)):
            try:
                module=bridge.load_original(window);print('LOADED',window,round(time.monotonic()-clock,3),flush=True)
                bridge.replay_no_budget(module)
                checks=bridge.compare_original(module)
                directory,baseline=bridge.ENGINES[window]
                json_checks={}
                for name,actual in [('BRIDGES',module.bridges),('CLAIMS',list(module.claims.values()))]:
                    expected=json.loads((bridge.EVENT_ROOT/directory/baseline/(name+'.json')).read_text())
                    expected=[r for r in expected if r['arm']=='A_UNION_B']
                    assert json_normal(actual)==expected,(name,'exact normalized original JSON mismatch')
                    json_checks[name]={'rows':len(actual),'exact_normalized_match':True}
                qa=module.ledger_qa()
                hashes=bridge.export_new(module,destination/'outputs',checks)
                write_new(destination/'LEDGER_QA.json',qa)
                check_runner_seal();bridge.verified_manifest()
                result={'status':'PASS_ORIGINAL_NO_BUDGET_FULL','window':window,'started':started,'finished':utc(),
                    'seconds':time.monotonic()-clock,'eight_table_checks':checks,'additional_json_checks':json_checks,
                    'original_ledger_qa_rows':len(qa),'output_sha256':hashes,'shared_account':False,'new_strategy':False,
                    'coverage':'full latest original A_UNION_B window consumer and original NET80 equity wrapper',
                    'not_claimed':['shared-account integration','new returns','2026-equivalent equity replay','actual historical exchange tradability','PIT']}
                write_new(destination/'RESULT.json',result)
                print(json.dumps(result,default=str),flush=True)
            except BaseException as exc:
                traceback.print_exc()
                write_new(destination/'RESULT.json',{'status':'FAILED_ORIGINAL_NO_BUDGET_FULL','window':window,'started':started,
                    'finished':utc(),'seconds':time.monotonic()-clock,'error_type':type(exc).__name__,'error':str(exc),
                    'shared_account':False,'outputs_may_be_partial':True})
                raise
if __name__=='__main__': main()
