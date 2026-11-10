"""Finish already-authorized A snapshot/head work after its node lock is free.

Never resumes a failed queue or starts an alternative source automatically.
All requests go through the frozen collectors and existing bounded plans.
"""
from pathlib import Path
import json, subprocess, time
from datetime import datetime
from zoneinfo import ZoneInfo

R=Path(__file__).resolve().parents[1]
PY='/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python'
OUT=R/'diagnostics/a-followon-control-01'; OUT.mkdir(exist_ok=False)
log=[]
def stamp(stage, **kwargs):
    log.append(dict(stage=stage, at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), **kwargs))
    (OUT/'receipt.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(log[-1],ensure_ascii=False),flush=True)
def run(name, script, args, timeout):
    stamp('starting', job=name)
    with (OUT/(name+'.stdout.log')).open('x') as out, (OUT/(name+'.stderr.log')).open('x') as err:
        proc=subprocess.run([PY,str(R/'code'/script)]+[str(x) for x in args],stdout=out,stderr=err,timeout=timeout,check=False)
    stamp('finished',job=name,returncode=proc.returncode)
    if proc.returncode: raise RuntimeError(name+' failed; remaining work not launched')

stamp('waiting_for_original_tail_queue')
deadline=time.monotonic()+5400
while True:
    state=json.loads((R/'downloads/a-tail-queue-01/queue-state.json').read_text())
    if state['status']=='finished': break
    if state['status']=='halted': raise RuntimeError('Tail queue halted; no automatic retry')
    if time.monotonic()>deadline: raise RuntimeError('Bounded queue wait elapsed')
    time.sleep(5)
# State is persisted just before queue shutdown; respect the collector's lock.
time.sleep(5)
stamp('tail_queue_finished',batches=len(state['batches']))
run('snapshot-pilot','snapshot_batch.py',['--plan',R/'plans/a-snapshot-pilot-02.json','--output',R/'downloads/a-snapshot-pilot-03'],180)
pilot=json.loads((R/'downloads/a-snapshot-pilot-03/snapshot.json').read_text())['rows']
assert len(pilot)==8 and all(float(x['raw_fields'].get('3541450') or 0)>0 for x in pilot)
stamp('pilot_cap_and_identity_passed',securities=8)
run('snapshot-all','snapshot_batch.py',['--plan',R/'plans/a-snapshot-all-01.json','--output',R/'downloads/a-snapshot-all-01'],600)
run('head-boundaries','history_queue.py',['--plan-index',R/'audit-a/batch-plans-v2/index.json','--group','02-start-boundary','--output',R/'downloads/a-head-queue-01'],3600)
run('fx-first-request','history_batch.py',['--plan',R/'plans/fx-history-9602-01.json','--output',R/'downloads/fx-history-9602-01'],180)
fx=json.loads((R/'downloads/fx-history-9602-01/run-summary.json').read_text())
stamp('sequence_closed',fx_summary=fx,account_runs=0)
