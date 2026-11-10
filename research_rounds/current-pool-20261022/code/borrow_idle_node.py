"""Temporarily stop only this task's queue parent; let its active child finish.
Run one bounded diagnostic after the node is idle, and always resume the parent.
No shared collector code, frozen plan, or completed market evidence is modified.
"""
from pathlib import Path
import json,os,signal,subprocess,sys,time
from datetime import datetime
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parents[1]
PID=26889
O=R/'diagnostics/crossnode-control-01';O.mkdir(exist_ok=False)
log=[]
def stamp(stage,**kw):
    log.append(dict(stage=stage,at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),**kw))
    (O/'receipt.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(log[-1],ensure_ascii=False),flush=True)
def processes():
    text=subprocess.check_output(['ps','-axo','pid=,ppid=,stat=,command='],text=True)
    return [line.strip().split(None,3) for line in text.splitlines() if len(line.strip().split(None,3))==4]
rows=processes();parent=next(x for x in rows if int(x[0])==PID)
if 'history_queue.py' not in parent[3] or '--output research_rounds/current-pool-20261022/downloads/a-tail-queue-01' not in parent[3]:
    raise SystemExit('Queue process identity no longer matches; no signal sent')
stamp('validated_own_queue',pid=PID)
paused=False
try:
    os.kill(PID,signal.SIGSTOP);paused=True;stamp('parent_stopped_child_allowed_to_finish')
    deadline=time.monotonic()+180
    while True:
        active=[x for x in processes() if int(x[1])==PID and not x[2].startswith('Z')]
        if not active:break
        if time.monotonic()>deadline:raise RuntimeError('Child did not finish within bounded wait; diagnostic skipped')
        time.sleep(2)
    stamp('node_idle')
    py='/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python'
    cmd=[py,str(R/'code/history_batch.py'),'--plan',str(R/'plans/crossnode-sector-fx-01.json'),'--output',str(R/'diagnostics/crossnode-sector-fx-01')]
    with (O/'diagnostic.stdout.log').open('x') as out,(O/'diagnostic.stderr.log').open('x') as err:
        p=subprocess.run(cmd,stdout=out,stderr=err,timeout=600,check=False)
    stamp('diagnostic_exited',returncode=p.returncode)
finally:
    if paused:
        os.kill(PID,signal.SIGCONT);stamp('parent_resumed')
